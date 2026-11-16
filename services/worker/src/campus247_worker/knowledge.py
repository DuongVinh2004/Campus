"""Durable single-heavy-job ingestion; model calls use the shared real BGE service."""
from __future__ import annotations

import asyncio
import ctypes
import json
import os
import sys
import time
import subprocess
from pathlib import Path
from contextlib import suppress
from dataclasses import asdict

from campus247.application.knowledge.platform_models import (
    EMBED_ARTIFACT, EMBED_MODEL, EMBED_REVISION, PROCESSOR, PlatformError, digest,
)
from campus247.application.retrieval.profile import load_retrieval_profile
from campus247.infrastructure.knowledge.repository import LeaseLost, json_value
from campus247.infrastructure.retrieval.public_knowledge import normalized, stable_id
from campus247_worker.ingestion.chunk import SemanticChunker
from campus247_worker.ingestion.parse import DocumentParser


def available_memory() -> int | None:
    if sys.platform != "win32":
        return None
    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in ("total", "available", "page_total", "page_available",
                                                  "virtual_total", "virtual_available", "extended")]
    state = MemoryStatus()
    state.length = ctypes.sizeof(state)
    return state.available if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)) else None


def chunks_for_pages(pages, version_id, title):
    """Reuse the existing structure-aware chunker while preserving exact page offsets."""
    rows = []
    for page_ordinal, page in enumerate(pages, 1):
        document = DocumentParser().parse(page["text"], {"title": title})
        for chunk in SemanticChunker(max_chars=1800, overlap_chars=180).chunk(document, version_id):
            ordinal = len(rows)
            content = chunk.content
            rows.append({"id": stable_id(f"{version_id}:{PROCESSOR}:{page_ordinal}:{ordinal}:{digest(content.encode())}"),
                "ordinal": ordinal, "text": content, "sha256": digest(content.encode()),
                "section": f"{chunk.section_path} · block {ordinal + 1} · chars {chunk.char_start}:{chunk.char_end}",
                "page": page["page"], "char_start": chunk.char_start, "char_end": chunk.char_end,
                "index_text": normalized(content)})
    if not rows or len(rows) > 30_000:
        raise ValueError("CHUNK_LIMIT")
    return rows


class KnowledgeIngestionWorker:
    def __init__(self, repository, storage, embedding, *, owner, low_watermark=2 * 1024**3, parser_python=None, platform=None, ocr_adapter=None):
        if (embedding.profile.model_id, embedding.profile.model_revision, embedding.profile.dimension,
            embedding.profile.normalization) != (EMBED_MODEL, EMBED_REVISION, 1024, "l2"):
            raise ValueError("Exact BGE-M3 profile required")
        self.repo, self.storage, self.embedding = repository, storage, embedding
        self.owner, self.low_watermark = owner, low_watermark
        if platform is not None and (platform.repo is not repository or platform.storage is not storage):
            raise ValueError("Intake inheritance must use the same PostgreSQL/storage composition")
        self.platform = platform
        if ocr_adapter is not None and ocr_adapter.storage is not storage:
            raise ValueError("OCR must use the same scoped immutable artifact store")
        self.ocr = ocr_adapter
        self.config_hash = digest({"processor": PROCESSOR, "embedding": asdict(embedding.profile), "artifact": EMBED_ARTIFACT})
        self.parser_python = str(parser_python or sys.executable)
        probe = subprocess.run([self.parser_python, "-B", "-m", "campus247_worker.knowledge_parse", "--identity"],
            capture_output=True, timeout=10, cwd=self.storage.workspace, env=self._parser_environment(),
            creationflags=0x08000000 if sys.platform == "win32" else 0, check=False)
        if probe.returncode or len(probe.stdout) > 20000:
            raise ValueError("Parser dependency identity unavailable")
        self.parser_identity = json.loads(probe.stdout)
        if self.parser_identity["parser_code_sha256"] != digest(Path(__file__).with_name("knowledge_parse.py").read_bytes()):
            raise ValueError("Parser runtime code identity mismatch")
        self.parse_config_hash = digest(self.parser_identity)
        from campus247.application.knowledge import evidence_units
        self.evidence_config_hash = evidence_units.configuration_hash()
        from campus247_worker.knowledge_render import PreviewRenderer
        self.renderer = PreviewRenderer(storage)

    def _parser_environment(self):
        environment = {k: v for k, v in os.environ.items() if k.upper() in
            {"PATH", "SYSTEMROOT", "WINDIR", "PYTHONIOENCODING", "PYTHONDONTWRITEBYTECODE"}}
        environment["PYTHONPATH"] = os.pathsep.join(str(self.storage.workspace / p) for p in (
            "services/api/src", "services/worker/src", ".tooling/knowledge-platform-20261023/site-packages"))
        return environment

    async def _heartbeat(self, job):
        while True:
            await asyncio.sleep(10)
            try:
                if not await self.repo.heartbeat(job):
                    return False
            except Exception:
                return False  # Ownership cannot be proved; stop this owned parser/batch.

    async def _parse(self, artifact, media_type):
        path = self.storage.path(artifact["object_key"])
        self.storage.read(artifact)  # Hash check immediately before the read-only child.
        parser_environment = self._parser_environment()
        child = await asyncio.create_subprocess_exec(self.parser_python, "-B", "-m", "campus247_worker.knowledge_parse",
            str(path), media_type, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            env=parser_environment, cwd=self.storage.workspace,
            creationflags=0x08000000 if sys.platform == "win32" else 0)
        try:
            output, _ = await asyncio.wait_for(child.communicate(), timeout=120)
            if child.returncode or len(output) > 100 * 1024**2:
                raise PlatformError(422, "DOCUMENT_EXTRACTION_FAILED", "Tệp cần kiểm tra định dạng hoặc OCR.")
            result = json.loads(output)
            if "error_code" in result:
                raise PlatformError(422, "DOCUMENT_EXTRACTION_FAILED", "Không thể trích xuất đầy đủ tài liệu.")
            if result.get("parser_identity") != self.parser_identity:
                raise PlatformError(409, "PARSER_IDENTITY_CHANGED", "Parser/dependency đổi giữa các bước; cần pipeline revision mới.")
            return result
        finally:
            if child.returncode is None:
                # Only the parser process created above belongs to this job.
                child.kill()
                await child.wait()

    async def _evidence(self, job, artifact, extracted, extraction_sha256, parser_config_hash=None):
        from campus247.application.knowledge.evidence_units import EvidenceManifest, build_manifest, verify_manifest
        binding = {"tenant_id": self.repo.tenant, "original_sha256": artifact["sha256"],
            "extraction_sha256": extraction_sha256, "parser_config_sha256": parser_config_hash or self.parse_config_hash}
        input_hash = digest(binding)
        step = await self.repo.checkpoint(job, "EVIDENCE", input_hash, self.evidence_config_hash)
        if step:
            async with self.repo.pool.acquire() as conn:
                saved = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", step["artifact_id"], self.repo.tenant)
            raw = self.storage.read(saved)
            if digest(raw) != step["output_sha256"]:
                raise PlatformError(409, "EVIDENCE_INTEGRITY", "Bằng chứng không khớp checkpoint.")
            manifest = verify_manifest(EvidenceManifest.model_validate_json(raw), extracted, **binding)
            return saved["id"], manifest
        manifest = build_manifest(extracted, **binding)
        saved = self.storage.write_json(manifest.model_dump_json().encode(), "evidence-units")
        async with self.repo.fenced(job) as conn:
            await self.repo.save_step(conn, job, "EVIDENCE", input_hash, self.evidence_config_hash,
                saved.sha256, saved, {"unit_count": len(manifest.units), "dependency_count": len(manifest.dependencies),
                    "issue_count": len(manifest.issues), "admission_granted": False, "new_model_calls": 0})
        return saved.id, manifest

    async def _ocr_evidence(self, job, original, image, raw_ocr):
        from campus247.application.knowledge import ocr_evidence
        binding = {"tenant_id": self.repo.tenant, "original_sha256": original["sha256"],
            "image_sha256": image["sha256"], "ocr_sha256": digest(raw_ocr),
            "ocr_config_sha256": self.ocr.config_hash, "page": json.loads(raw_ocr)["page"]}
        input_hash, config = digest(binding), ocr_evidence.configuration_hash()
        stage = "OCR_EVIDENCE:"+str(binding["page"])
        image_bytes = self.storage.read(image)
        step = await self.repo.checkpoint(job, stage, input_hash, config)
        if step:
            async with self.repo.pool.acquire() as conn:
                saved = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", step["artifact_id"], self.repo.tenant)
            raw = self.storage.read(saved)
            if digest(raw) != step["output_sha256"]:
                raise PlatformError(409, "OCR_EVIDENCE_INTEGRITY", "Bằng chứng OCR không khớp checkpoint.")
            manifest = ocr_evidence.verify_manifest(ocr_evidence.OcrEvidenceManifest.model_validate_json(raw), raw_ocr, image_bytes, **binding)
            return {"artifact_id": str(saved["id"]), "sha256": step["output_sha256"], "unit_count": len(manifest.units)}
        manifest = ocr_evidence.build_manifest(raw_ocr, image_bytes, **binding)
        saved = self.storage.write_json(manifest.model_dump_json().encode(), "ocr-evidence-units")
        async with self.repo.fenced(job) as conn:
            await self.repo.save_step(conn, job, stage, input_hash, config, saved.sha256, saved,
                {"unit_count": len(manifest.units), "dependency_count": len(manifest.dependencies),
                    "semantics_verified": False, "admission_granted": False, "new_model_calls": 0})
        return {"artifact_id": str(saved.id), "sha256": saved.sha256, "unit_count": len(manifest.units)}

    async def _process_intake(self, job):
        async with self.repo.pool.acquire() as conn:
            artifact = await conn.fetchrow("""SELECT a.* FROM knowledge_intake i
                LEFT JOIN knowledge_intake_fetch f ON f.intake_id=i.id AND f.tenant_id=i.tenant_id
                JOIN knowledge_artifact a ON a.id=COALESCE(i.original_id,f.original_id) AND a.tenant_id=i.tenant_id
                WHERE i.id=$1 AND i.tenant_id=$2""", job["intake_id"], self.repo.tenant)
            intake = await conn.fetchrow("SELECT * FROM knowledge_intake WHERE id=$1 AND tenant_id=$2", job["intake_id"], self.repo.tenant)
        if not artifact and intake and not intake["original_id"]:
            from campus247.infrastructure.knowledge.fetch import PublicDocumentFetcher
            previous_artifact, previous_acquisition = None, None
            async with self.repo.fenced(job) as conn:
                condition = await conn.fetchrow("SELECT * FROM knowledge_job_step WHERE job_id=$1 AND stage='FETCH_CONDITION'", job["id"])
                if condition:
                    binding = json_value(condition["result"])
                    previous = await conn.fetchrow("""SELECT a.*,f.acquisition FROM knowledge_intake_fetch f
                        JOIN knowledge_artifact a ON a.id=f.original_id AND a.tenant_id=f.tenant_id
                        WHERE f.intake_id=$1 AND f.tenant_id=$2 AND a.id=$3 AND a.sha256=$4""",
                        binding["previous_intake_id"], self.repo.tenant, binding["original_id"], binding["original_sha256"])
                    if (digest(binding) != condition["output_sha256"] or not previous
                        or digest(json_value(previous["acquisition"])) != binding["acquisition_sha256"]
                        or json_value(intake["hints"])["source_uri"] != binding["requested_url"]):
                        raise PlatformError(409, "SOURCE_FETCH_BINDING", "Checkpoint tải có điều kiện không khớp nguồn.")
                    previous_artifact, previous_acquisition = dict(previous), json_value(previous["acquisition"])
            conditional = {"previous_artifact": previous_artifact, "previous_acquisition": previous_acquisition} if previous_artifact is not None else {}
            fetched, acquisition = await PublicDocumentFetcher().fetch(json_value(intake["hints"])["source_uri"], self.storage, **conditional)
            async with self.repo.fenced(job) as conn:
                registered = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", fetched.id, self.repo.tenant)
                if registered:
                    if any(str(registered[field]) != str(getattr(fetched, field)) for field in fetched.__dataclass_fields__):
                        raise PlatformError(409, "SOURCE_FETCH_BINDING", "Artifact không khớp nguồn tải có điều kiện.")
                    self.storage.read(registered)
                else:
                    await self.repo.artifact(conn, fetched)
                await conn.execute("""INSERT INTO knowledge_intake_fetch(intake_id,tenant_id,original_id,acquisition)
                    VALUES($1,$2,$3,$4::jsonb)""", job["intake_id"], self.repo.tenant, fetched.id, json.dumps(acquisition))
                await self.repo.save_step(conn, job, "FETCH", digest(json_value(intake["hints"])["source_uri"].encode()),
                    digest({"policy": acquisition["fetch_policy"]}), fetched.sha256, None,
                    {"http_calls": len(acquisition["hops"]), "bytes": fetched.byte_size, "new_model_calls": 0}, artifact_ref=fetched.id)
                artifact = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", fetched.id, self.repo.tenant)
        if not artifact:
            raise PlatformError(404, "INTAKE_NOT_FOUND", "Không tìm thấy nguồn tiếp nhận.")
        if self.platform is not None:
            from campus247.application.knowledge.intake import reusable_candidates, SEPARATE_ROUTE_CONFIG
            separate = await self.repo.checkpoint(job, "ROUTE_DECISION", artifact["sha256"], SEPARATE_ROUTE_CONFIG)
            if not separate:
                async with self.repo.fenced(job) as conn:
                    candidates, pointer = await reusable_candidates(self.platform, conn, artifact)
                    if candidates:
                        payload = {"original_sha256": artifact["sha256"], "duplicate_candidates": candidates,
                            "generation": pointer["generation"], "policy_generation": pointer["policy_generation"],
                            "automatic_family_merge": False, "authority_granted": False, "new_model_calls": 0}
                        manifest_hash = digest(payload)
                        await self.repo.save_step(conn, job, "DUPLICATE_CANDIDATES", artifact["sha256"],
                            digest({"inheritance": "current-eligible-bindings-v1", "pointer": pointer}), manifest_hash, None, payload)
                        if not await conn.fetchval("""SELECT EXISTS(SELECT 1 FROM knowledge_intake_issue
                            WHERE intake_id=$1 AND tenant_id=$2 AND evidence->>'candidate_manifest_sha256'=$3)""", job["intake_id"], self.repo.tenant, manifest_hash):
                            from campus247.domain.shared.values import generate_uuid7
                            await conn.execute("""INSERT INTO knowledge_intake_issue(id,tenant_id,intake_id,code,fields,evidence)
                                VALUES($1,$2,$3,'DUPLICATE_BYTES_CANDIDATE',$4::jsonb,$5::jsonb)""", generate_uuid7(), self.repo.tenant,
                                job["intake_id"], json.dumps(["source_identity", "publisher_basis", "scope"]),
                                json.dumps({**payload, "candidate_manifest_sha256": manifest_hash}))
                        await conn.execute("UPDATE knowledge_ingestion_job SET stage='DUPLICATE_REVIEW',progress=20 WHERE id=$1", job["id"])
                        return "NEEDS_INFORMATION"
        step = await self.repo.checkpoint(job, "EXTRACT", artifact["sha256"], self.parse_config_hash)
        if step:
            async with self.repo.pool.acquire() as conn:
                output = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", step["artifact_id"], self.repo.tenant)
            raw = self.storage.read(output)
            if digest(raw) != step["output_sha256"]:
                raise PlatformError(409, "CHECKPOINT_INTEGRITY", "Checkpoint không khớp artifact.")
            extracted = json.loads(raw)
            saved = None
        else:
            if artifact["media_type"] in {"application/pdf", "text/plain"}:
                extracted = await self._parse(artifact, artifact["media_type"])
            else:
                extracted = {"pages": [], "page_count": 0, "processor": "unsupported-media-preserved",
                    "issues": [{"page": None, "code": "LINKED_ORIGINAL_REQUIRED"}]}
            raw = json.dumps(extracted, ensure_ascii=False, sort_keys=True).encode()
            saved = self.storage.write_json(raw, "extraction")
        async with self.repo.fenced(job) as conn:
            if saved:
                await self.repo.save_step(conn, job, "EXTRACT", artifact["sha256"], self.parse_config_hash,
                    saved.sha256, saved, {"pages": extracted["page_count"], "issues": extracted["issues"]})
        evidence_id, evidence_manifest = await self._evidence(job, artifact, extracted, digest(raw))
        preview_pages = []
        if artifact["media_type"] == "application/pdf":
            wanted = sorted({issue["page"] for issue in extracted["issues"] if issue.get("page")})
            for page in wanted[:12]:
                stage = "RENDER:"+str(page)
                rendered = await self.repo.checkpoint(job, stage, artifact["sha256"], self.renderer.config_hash)
                if rendered:
                    async with self.repo.pool.acquire() as conn:
                        image = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", rendered["artifact_id"], self.repo.tenant)
                    if not image or digest(self.storage.read(image)) != rendered["output_sha256"]:
                        raise PlatformError(409, "PREVIEW_INTEGRITY", "Ảnh đối chiếu không khớp checkpoint.")
                else:
                    image, receipt = await self.renderer.render(artifact, page)
                    async with self.repo.fenced(job) as conn:
                        await self.repo.save_step(conn, job, stage, artifact["sha256"], self.renderer.config_hash,
                            image.sha256, image, receipt)
                preview_pages.append(page)
        ocr_pages, ocr_pending, ocr_evidence_pages = [], [], {}
        for page in preview_pages:
            native = next(p for p in extracted["pages"] if p["page"] == page)
            route = (native.get("layout") or {}).get("route")
            if route not in {"RASTER_OR_MIXED", "UNCLASSIFIED_GRAPHICS"} and len(native["text"].strip())>=20:
                continue
            if self.ocr is None:
                ocr_pending.append(page)
                continue
            rendered = await self.repo.checkpoint(job, "RENDER:"+str(page), artifact["sha256"], self.renderer.config_hash)
            async with self.repo.pool.acquire() as conn:
                image = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2",rendered["artifact_id"],self.repo.tenant)
            input_hash = digest({"tenant_id":self.repo.tenant,"source_sha256":artifact["sha256"],"image_sha256":image["sha256"],"page":page})
            ocr = await self.repo.checkpoint(job,"OCR:"+str(page),input_hash,self.ocr.config_hash)
            if ocr:
                async with self.repo.pool.acquire() as conn:
                    output = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2",ocr["artifact_id"],self.repo.tenant)
                raw_ocr = self.storage.read(output)
                self.storage.read(image)
                payload = json.loads(raw_ocr)
                if (digest(raw_ocr)!=ocr["output_sha256"] or payload.get("automation_profile")!=self.ocr.profile
                    or payload.get("source_sha256")!=artifact["sha256"] or payload.get("image_sha256")!=image["sha256"] or payload.get("page")!=page):
                    raise PlatformError(409,"OCR_CACHE_BINDING","OCR cache không khớp nguồn, ảnh hoặc profile.")
            else:
                memory = available_memory()
                if memory is not None and memory<self.low_watermark:
                    raise PlatformError(503,"RESOURCE_WAIT","Chờ RAM khả dụng cho OCR cục bộ; giữ checkpoint trước đó.")
                output,receipt = await self.ocr.recognize(artifact,image,page)
                async with self.repo.fenced(job) as conn:
                    await self.repo.save_step(conn,job,"OCR:"+str(page),input_hash,self.ocr.config_hash,output.sha256,output,receipt)
                raw_ocr = self.storage.read(asdict(output))
            ocr_evidence_pages[str(page)] = await self._ocr_evidence(job, artifact, image, raw_ocr)
            ocr_pages.append(page)
        async with self.repo.fenced(job) as conn:
            # One root issue retains extraction problems and missing fields. Hints never become authority.
            if not await conn.fetchval("""SELECT EXISTS(SELECT 1 FROM knowledge_intake_issue WHERE intake_id=$1 AND tenant_id=$2
                AND code='SOURCE_METADATA_REQUIRED' AND evidence->>'evidence_artifact_id'=$3 AND evidence->'ocr_pages'=$4::jsonb
                AND evidence->'ocr_evidence_pages'=$5::jsonb)""",
                job["intake_id"],self.repo.tenant,str(evidence_id),json.dumps(ocr_pages),json.dumps(ocr_evidence_pages)):
                text = next((p["text"] for p in extracted["pages"] if p["text"].strip()), "")
                proposal = next((line.strip() for line in text.splitlines() if len(line.strip()) >= 3), "")[:300]
                evidence = {"original_sha256": artifact["sha256"], "extraction_artifact_id": str(saved.id if saved else step["artifact_id"]),
                    "extraction_sha256": digest(raw), "title_candidate": proposal,
                    "evidence_artifact_id": str(evidence_id), "evidence_unit_count": len(evidence_manifest.units),
                    "evidence_issue_count": len(evidence_manifest.issues), "evidence_is_verified": False,
                    "locator": {"page": extracted["pages"][0]["page"] if extracted["pages"] else None},
                    "extraction_issues": extracted["issues"], "issued_at": None, "valid_from": None,
                    "preview_pages": preview_pages,
                    "ocr_pages":ocr_pages,"ocr_pending_pages":ocr_pending,"ocr_is_verified":False,
                    "ocr_evidence_pages":ocr_evidence_pages,
                    "preview_pending_pages": [p["page"] for p in extracted["pages"] if p.get("preview_status") and p["page"] not in preview_pages],
                    "candidate_is_verified": False}
                from campus247.domain.shared.values import generate_uuid7
                await conn.execute("""INSERT INTO knowledge_intake_issue(id,tenant_id,intake_id,code,fields,evidence)
                    VALUES($1,$2,$3,'SOURCE_METADATA_REQUIRED',$4::jsonb,$5::jsonb)""", generate_uuid7(), self.repo.tenant,
                    job["intake_id"], json.dumps(["title", "owner_unit", "canonical_uri", "programs", "audiences", "effective_from_basis"]), json.dumps(evidence))
            await conn.execute("UPDATE knowledge_ingestion_job SET stage='METADATA_REVIEW',progress=40 WHERE id=$1", job["id"])
        return "NEEDS_INFORMATION"

    async def _process(self, job):
        if job.get("intake_id") and not job["version_id"]:
            return await self._process_intake(job)
        async with self.repo.pool.acquire() as conn:
            version = await self.repo.version(conn, job["version_id"])
            artifact = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", version["original_id"], self.repo.tenant)
        self.storage.read(artifact)
        if version["processor_profile"] != PROCESSOR:
            raise PlatformError(409, "PROCESSOR_MISMATCH", "Không thể tiếp tục job bằng processor khác.")
        from campus247.application.knowledge.rendition_corrections import verified_checkpoint
        manual_step, manual_config = await verified_checkpoint(self.repo,self.storage,job,self.parse_config_hash)
        step = manual_step or await self.repo.checkpoint(job, "EXTRACT", artifact["sha256"], self.parse_config_hash)
        if not step:
            # Only the exact resolved observation may reuse draft extraction. No hash-only authority merge.
            async with self.repo.pool.acquire() as conn:
                intake_schema = await conn.fetchval("SELECT to_regclass('knowledge_intake_fetch') IS NOT NULL")
                if intake_schema:
                    lineage = await conn.fetchval("SELECT rendition_identity FROM knowledge_version_lineage WHERE version_id=$1 AND tenant_id=$2", job["version_id"], self.repo.tenant)
                    if lineage and json_value(lineage)["config_sha256"] != self.parse_config_hash:
                        raise PlatformError(409, "PARSER_IDENTITY_CHANGED", "Rendition có binding parser khác; cần tạo phiên bản kỹ thuật mới.")
                previous = await conn.fetchrow("""SELECT s.* FROM knowledge_intake_resolution r
                    JOIN knowledge_intake i ON i.id=r.intake_id AND i.tenant_id=r.tenant_id
                    JOIN knowledge_ingestion_job j ON j.intake_id=i.id AND j.tenant_id=i.tenant_id
                    LEFT JOIN knowledge_intake_fetch f ON f.intake_id=i.id AND f.tenant_id=i.tenant_id
                    JOIN knowledge_job_step s ON s.job_id=j.id
                    WHERE r.version_id=$1 AND r.tenant_id=$2 AND COALESCE(i.original_id,f.original_id)=$3
                    AND s.stage='EXTRACT' AND s.input_sha256=$4 AND s.config_sha256=$5""",
                    job["version_id"], self.repo.tenant, version["original_id"], artifact["sha256"], self.parse_config_hash) if intake_schema else None
            if previous:
                async with self.repo.fenced(job) as conn:
                    await self.repo.save_step(conn, job, "EXTRACT", artifact["sha256"], self.parse_config_hash,
                        previous["output_sha256"], None, {"reused_from_job_id": str(previous["job_id"])}, artifact_ref=previous["artifact_id"])
                    await conn.execute("""UPDATE knowledge_ingest_version SET rendition_id=$2,rendition_sha256=$3,
                        review_state='NEEDS_REVIEW' WHERE version_id=$1""", job["version_id"], previous["artifact_id"], previous["output_sha256"])
                step = dict(previous)
        if step:
            async with self.repo.pool.acquire() as conn:
                extracted_artifact = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", step["artifact_id"], self.repo.tenant)
            extracted = json.loads(self.storage.read(extracted_artifact))
            if digest(json.dumps(extracted, ensure_ascii=False, sort_keys=True).encode()) != step["output_sha256"]:
                raise PlatformError(409, "CHECKPOINT_INTEGRITY", "Checkpoint không khớp artifact.")
        else:
            extracted = await self._parse(artifact, version["media_type"])
            raw = json.dumps(extracted, ensure_ascii=False, sort_keys=True).encode()
            saved = self.storage.write_json(raw, "extraction")
            async with self.repo.fenced(job) as conn:
                await self.repo.save_step(conn, job, "EXTRACT", artifact["sha256"], self.parse_config_hash,
                    saved.sha256, saved, {"pages": extracted["page_count"], "issues": extracted["issues"]})
                await conn.execute("""UPDATE knowledge_ingest_version SET rendition_id=$2,rendition_sha256=$3,
                    review_state='NEEDS_REVIEW' WHERE version_id=$1""", job["version_id"], saved.id, saved.sha256)
                await conn.execute("UPDATE knowledge_ingestion_job SET stage='CHUNK_EMBED',progress=25 WHERE id=$1", job["id"])
        extraction_hash = digest(json.dumps(extracted, ensure_ascii=False, sort_keys=True).encode())
        await self._evidence(job, artifact, extracted, extraction_hash, manual_config)
        if extracted["issues"]:
            raise PlatformError(422, "EXTRACTION_NEEDS_REVIEW", "Trang thiếu chữ hoặc lỗi ký tự cần OCR/đối chiếu; chưa tạo chỉ mục.")
        chunks = chunks_for_pages(extracted["pages"], str(job["version_id"]), version["title"])
        # Refresh after EXTRACT has bound the rendition. Every target keeps its
        # own chunk ID, page and offsets even when its exact vector input repeats.
        from campus247_worker.knowledge_embedding_cache import EmbeddingInputCache
        cache = EmbeddingInputCache(self.repo, self.storage, self.embedding.profile, self.config_hash,
            manual_config or self.parse_config_hash)
        async with self.repo.pool.acquire() as conn:
            version = await self.repo.version(conn, job["version_id"])
        incremental = {"schema": "incremental-chunks-v1", "resumed": 0, "reused": 0, "recomputed": 0, "chunks": []}
        for position, chunk in enumerate(chunks):
            memory = available_memory()
            if memory is not None and memory < self.low_watermark:
                raise PlatformError(503, "RESOURCE_WAIT", "Chờ RAM khả dụng cho batch BGE tiếp theo.")
            async with self.repo.fenced(job) as conn:
                await cache.current(conn, version)
                present = await conn.fetchrow("""SELECT c.content_checksum,c.embedding_model_version,c.embedding_dimension,
                    c.embedding_rag_v1 IS NOT NULL AS embedded,ci.index_text,ci.input_sha256,ci.processor_profile,ci.provenance
                    FROM knowledge_chunk c LEFT JOIN knowledge_chunk_input ci ON ci.chunk_id=c.id
                    WHERE c.id=$1 AND c.document_version_id=$2""", chunk["id"], job["version_id"])
                if present and (present["content_checksum"] != chunk["sha256"] or present["embedding_model_version"] != EMBED_MODEL + "@" + EMBED_REVISION
                                or present["embedding_dimension"] != 1024 or not present["embedded"]
                                or present["index_text"] != chunk["index_text"]
                                or present["input_sha256"] != digest(chunk["index_text"].encode())
                                or present["processor_profile"] != PROCESSOR
                                or json_value(present["provenance"] or {}).get("config_sha256") != self.config_hash):
                    raise PlatformError(409, "EMBEDDING_CACHE_MISMATCH", "Vector cache không khớp input/profile.")
            if not present:
                binding = cache.binding(version, chunk["index_text"])
                async with self.repo.fenced(job) as conn:
                    await cache.current(conn, version)
                    donor = await cache.lookup(conn, binding)
                vector_artifact = None
                model_elapsed = 0
                if donor:
                    values = donor["values"]
                else:
                    model_started = time.perf_counter()
                    batch = await self.embedding._embed((chunk["index_text"],))
                    model_elapsed = time.perf_counter() - model_started
                    values = batch.vectors[0].values
                    vector_artifact = cache.prepare(binding, values)
                literal = "[" + ",".join(str(v) for v in values) + "]"
                async with self.repo.fenced(job) as conn:
                    await cache.current(conn, version)
                    await cache.save(conn, job, binding, values, accounted_stage="EMBED:"+str(chunk["id"]), donor=donor, artifact=vector_artifact)
                    await conn.execute("""INSERT INTO knowledge_chunk
                        (id,document_version_id,ordinal,section_path,page_start,page_end,content_text,content_checksum,
                         content_tsv,embedding_rag_v1,embedding_model_version,embedding_dimension,embedded_at)
                        VALUES ($1,$2,$3,$4,$5,$5,$6,$7,to_tsvector('simple',$8),$9::vector(1024),$10,1024,clock_timestamp())
                        ON CONFLICT(id) DO NOTHING""", chunk["id"], job["version_id"], chunk["ordinal"], chunk["section"],
                        chunk["page"], chunk["text"], chunk["sha256"], chunk["index_text"], literal, EMBED_MODEL + "@" + EMBED_REVISION)
                    await conn.execute("""INSERT INTO knowledge_chunk_input
                        (chunk_id,index_text,input_sha256,processor_profile,provenance) VALUES ($1,$2,$3,$4,$5::jsonb)
                        ON CONFLICT DO NOTHING""", chunk["id"], chunk["index_text"], digest(chunk["index_text"].encode()), PROCESSOR,
                        json.dumps({"page":chunk["page"],"char_start":chunk["char_start"],"char_end":chunk["char_end"],
                                    "original_sha256":artifact["sha256"],"config_sha256":self.config_hash}))
                    await conn.execute("UPDATE knowledge_ingestion_job SET progress=$2 WHERE id=$1", job["id"], 25 + int(65*(position+1)/len(chunks)))
                    await self.repo.save_step(conn, job, "EMBED:" + str(chunk["id"]), digest(chunk["index_text"].encode()),
                        self.config_hash, digest(values), None, {"model_id": EMBED_MODEL, "model_revision": EMBED_REVISION,
                        "dimension": 1024, "new_model_calls": 0 if donor else 1, "model_elapsed_seconds": model_elapsed,
                        "reuse_reason": "EXACT_SCOPED_INPUT" if donor else "NO_MATCHING_SCOPED_RECEIPT",
                        "reused_from_version_id": str(donor["version_id"]) if donor else None,
                        "input_bytes": len(chunk["index_text"].encode()), "tokens": None,
                        "token_accounting": "provider ledger; not estimated from bytes"})
                disposition = "reused" if donor else "recomputed"
            else:
                disposition = "resumed"
            incremental[disposition] += 1
            incremental["chunks"].append({"chunk_id": str(chunk["id"]), "page": chunk["page"],
                "input_sha256": digest(chunk["index_text"].encode()), "disposition": disposition})
            # Yield between batch=1 calls so interactive queries can use the model service.
            await asyncio.sleep(0.05)
        async with self.repo.fenced(job) as conn:
            await cache.current(conn, version)
            profile = asdict(load_retrieval_profile())
            # Only trusted dataclass identifiers form this SQL; all values remain bound.
            fields = list(profile)
            await conn.execute("INSERT INTO retrieval_profile(" + ",".join(fields) +
                ",created_at,approved_at,approval_reference) VALUES (" +
                ",".join("$" + str(i+1) for i in range(len(fields))) +
                ",clock_timestamp(),clock_timestamp(),'KNOWLEDGE_PLATFORM_LOCAL_20261023') ON CONFLICT DO NOTHING", *profile.values())
            index_id = "knowledge-" + str(job["version_id"])
            checksum = digest([{k: c[k] for k in ("id", "sha256", "index_text", "page", "section")} for c in chunks])
            count = await conn.fetchval("SELECT count(*) FROM knowledge_chunk WHERE document_version_id=$1 AND embedding_rag_v1 IS NOT NULL", job["version_id"])
            if count != len(chunks):
                raise PlatformError(409, "INDEX_COUNT_MISMATCH", "Số chunk/vector không khớp extraction.")
            await conn.execute("""INSERT INTO embedding_index_manifest
                (index_version,profile_version,embedding_model_id,embedding_model_revision,artifact_sha256,dimension,
                 normalization,distance_metric,corpus_version,document_count,chunk_count,content_checksum,
                 build_status,built_at,validated_at) VALUES ($1,$2,$3,$4,$5,1024,'l2','cosine',$6,1,$7,$8,
                 'READY',clock_timestamp(),clock_timestamp()) ON CONFLICT DO NOTHING""", index_id,
                profile["profile_version"], EMBED_MODEL, EMBED_REVISION, EMBED_ARTIFACT,
                artifact["sha256"], len(chunks), checksum)
            await conn.execute("UPDATE document_version SET index_version=$2 WHERE id=$1", job["version_id"], index_id)
            await self.repo.save_step(conn, job, "INDEX", artifact["sha256"], self.config_hash, checksum, None,
                                      {"index_version": index_id, "chunk_count": count, "incremental": incremental})
            await conn.execute("UPDATE knowledge_ingestion_job SET stage='REVIEW',progress=100 WHERE id=$1", job["id"])

    async def run_once(self, *, target_job_id=None):
        memory = available_memory()
        if memory is not None and memory < self.low_watermark:
            return "RESOURCE_WAIT"
        job = await self.repo.claim(self.owner, target_job_id=target_job_id)
        if not job:
            return "IDLE"
        heartbeat = asyncio.create_task(self._heartbeat(job))
        processing = None
        try:
            if job["cancel_requested"]:
                await self.repo.finish(job, "CANCELLED")
            elif job["attempts"] > 3:
                await self.repo.finish(job, "FAILED", "ATTEMPTS_EXHAUSTED")
            else:
                processing = asyncio.create_task(self._process(job))
                done,_ = await asyncio.wait({processing,heartbeat},return_when=asyncio.FIRST_COMPLETED)
                if processing not in done:
                    processing.cancel()
                    await asyncio.gather(processing,return_exceptions=True)
                    raise LeaseLost("Job heartbeat no longer proves ownership")
                outcome = await processing
                await self.repo.finish(job, outcome or "SUCCEEDED")
        except LeaseLost:
            # The old process cannot commit after expiry/reclaim/cancellation.
            with suppress(LeaseLost):
                await self.repo.finish(job, "RETRY_WAIT" if job["attempts"]<3 else "FAILED", "LEASE_OR_CANCEL_CHANGED")
        except PlatformError as error:
            transient = error.status == 503 and job["attempts"] < 3
            with suppress(LeaseLost):
                await self.repo.finish(job, "RETRY_WAIT" if transient else "FAILED", error.code)
        except asyncio.CancelledError:
            # Retain lease/checkpoints for restart; do not mark success on shutdown.
            raise
        except Exception:
            with suppress(LeaseLost):
                await self.repo.finish(job, "RETRY_WAIT" if job["attempts"] < 3 else "FAILED", "PROCESSOR_DEPENDENCY_FAILURE")
        finally:
            if processing is not None and not processing.done():
                processing.cancel()
                await asyncio.gather(processing,return_exceptions=True)
            heartbeat.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat
        return "PROCESSED"
