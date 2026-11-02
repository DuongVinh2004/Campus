"""Metadata-free intake in the existing PostgreSQL queue, never automatic approval."""
from __future__ import annotations

import json
from pathlib import PurePath
from types import SimpleNamespace

from campus247.application.knowledge.document_identity import (
    ApplicabilityScope, DraftIntakeInput, EditionIdentity, RenditionIdentity, ScopeAxis,
)
from campus247.application.knowledge.platform_models import IntakeMetadata, PlatformError, digest
from campus247.application.knowledge.release_members import member_reads
from campus247.domain.shared.values import generate_uuid7
from campus247.application.knowledge.platform_models import json_value
from campus247.application.knowledge.values import StoredArtifact, public_row

SEPARATE_ROUTE_CONFIG = digest({"intake_route": "explicit-separate-observation-v1"})


async def reusable_candidates(platform, conn, artifact):
    """Offer existing evidence only after its admission bindings revalidate.

    This never chooses a family/issuer or grants the new observation authority.
    """
    pointer = await platform.repo.pointer(conn)
    if not pointer["release_id"]:
        return [], pointer
    versions = await conn.fetch(member_reads("""SELECT x.version_id FROM knowledge_release_member member
        JOIN knowledge_ingest_version x ON x.version_id=member.version_id AND x.tenant_id=$2
        JOIN knowledge_artifact a ON a.id=x.original_id AND a.tenant_id=x.tenant_id
        JOIN document_version v ON v.id=x.version_id
        JOIN knowledge_source s ON s.id=v.knowledge_source_id AND s.id=member.source_id
        WHERE member.release_id=$1 AND a.sha256=$3 AND a.byte_size=$4
        AND x.revoked_at IS NULL AND v.status='PUBLISHED' AND s.approval_status='APPROVED' AND NOT s.is_synthetic
        AND v.effective_from<=clock_timestamp() AND (v.effective_until IS NULL OR v.effective_until>clock_timestamp())"""),
        pointer["release_id"], platform.repo.tenant, artifact["sha256"], artifact["byte_size"])
    candidates = []
    for item in versions:
        version = await platform._eligible(conn, item["version_id"])
        original = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", version["original_id"], platform.repo.tenant)
        platform.storage.read(original)
        candidates.append({"version_id": str(version["version_id"]), "source_id": str(version["source_id"]),
            "title": version["title"], "canonical_uri": version["canonical_uri"], "original_sha256": version["original_sha256"],
            "rendition_sha256": version["rendition_sha256"], "metadata_sha256": version["metadata_sha256"],
            "index_version": version["index_version"], "family_assignment_confirmed": False})
    return candidates, pointer


class KnowledgeIntake:
    def __init__(self, platform):
        self.platform, self.repo, self.storage = platform, platform.repo, platform.storage

    async def ready(self, _connection=None):
        if _connection is not None:
            if not await _connection.fetchval("SELECT to_regclass('knowledge_intake_fetch') IS NOT NULL"):
                raise PlatformError(503, "INTAKE_SCHEMA_NOT_READY", "Luồng tiếp nhận nền cần schema và phiên ứng dụng mới; kho đang phục vụ được giữ nguyên.")
            return
        async with self.repo.pool.acquire() as conn:
            if not await conn.fetchval("SELECT to_regclass('knowledge_intake_fetch') IS NOT NULL"):
                raise PlatformError(503, "INTAKE_SCHEMA_NOT_READY", "Luồng tiếp nhận nền cần schema và phiên ứng dụng mới; kho đang phục vụ được giữ nguyên.")

    async def accept_url(self, actor, body, key):
        self.platform.admin(actor)
        await self.ready()
        from campus247.application.knowledge.values import public_document_url
        url = public_document_url(body.url)
        hints = DraftIntakeInput(source_uri=url, title_hint=body.title_hint)
        fingerprint = digest({"kind": "URL", "hints": hints.model_dump(mode="json")})
        async with self.repo.transaction() as conn:
            replay = await self.repo.replay(conn, actor.subject_id, "url-intake:"+key, fingerprint)
            if replay:
                return {**replay, "is_replay": True}
            identifier, job_id = generate_uuid7(), generate_uuid7()
            await conn.execute("""INSERT INTO knowledge_intake(id,tenant_id,filename,hints,created_by)
                VALUES($1,$2,'source-from-url',$3::jsonb,$4)""", identifier, self.repo.tenant, hints.model_dump_json(), actor.subject_id)
            await conn.execute("""INSERT INTO knowledge_ingestion_job(id,tenant_id,intake_id,stage)
                VALUES($1,$2,$3,'FETCH')""", job_id, self.repo.tenant, identifier)
            result = {"intake_id": identifier, "job_id": job_id, "state": "QUEUED", "revision": 1, "is_replay": False}
            await self.repo.audit(conn, actor.subject_id, "knowledge.url-intake.accepted", identifier, {"url_sha256": digest(url.encode()), "job_id": job_id})
            await self.repo.outbox(conn, "knowledge.intake.accepted", identifier, result)
            await self.repo.remember(conn, actor.subject_id, "url-intake:"+key, fingerprint, result)
            return result

    async def refresh_url(self, actor, intake_id, body, key, *, _connection=None):
        """Queue a new observation; never rewrite a prior source or its dates."""
        self.platform.admin(actor)
        if _connection is not None:
            await self.ready(_connection)
        else:
            await self.ready()
        fingerprint = digest({"previous_intake_id": str(intake_id), **body.model_dump(mode="json")})
        async with self.repo.transaction(_connection) as conn:
            replay = await self.repo.replay(conn, actor.subject_id, "url-refresh:"+key, fingerprint)
            if replay:
                return {**replay, "is_replay": True}
            previous = await conn.fetchrow("""SELECT i.hints,f.original_id,f.acquisition,a.sha256
                FROM knowledge_intake i JOIN knowledge_intake_fetch f ON f.intake_id=i.id AND f.tenant_id=i.tenant_id
                JOIN knowledge_artifact a ON a.id=f.original_id AND a.tenant_id=f.tenant_id
                WHERE i.id=$1 AND i.tenant_id=$2""", intake_id, self.repo.tenant)
            if not previous or previous["sha256"] != body.expected_original_sha256:
                raise PlatformError(409, "SOURCE_FETCH_BINDING", "Cần hồ sơ URL đã tải và đúng hash nguồn trước khi kiểm tra lại.")
            acquisition = json_value(previous["acquisition"])
            hints = DraftIntakeInput.model_validate(json_value(previous["hints"]))
            from campus247.application.knowledge.values import public_document_url
            if hints.source_uri != acquisition.get("requested_url"):
                raise PlatformError(409, "SOURCE_FETCH_BINDING", "URL không khớp acquisition đã giữ.")
            public_document_url(hints.source_uri)
            original = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", previous["original_id"], self.repo.tenant)
            self.storage.read(original)
            identifier, job_id = generate_uuid7(), generate_uuid7()
            await conn.execute("""INSERT INTO knowledge_intake(id,tenant_id,filename,hints,created_by)
                VALUES($1,$2,'source-url-recheck',$3::jsonb,$4)""", identifier, self.repo.tenant, hints.model_dump_json(), actor.subject_id)
            await conn.execute("INSERT INTO knowledge_ingestion_job(id,tenant_id,intake_id,stage) VALUES($1,$2,$3,'FETCH')", job_id, self.repo.tenant, identifier)
            binding = {"previous_intake_id": str(intake_id), "original_id": str(original["id"]), "original_sha256": original["sha256"],
                "acquisition_sha256": digest(acquisition), "requested_url": hints.source_uri}
            await self.repo.save_step(conn, {"id": job_id}, "FETCH_CONDITION", original["sha256"],
                digest({"policy": "same-url-conditional-observation-v1"}), digest(binding), None, binding)
            result = {"intake_id": identifier, "job_id": job_id, "state": "QUEUED", "revision": 1,
                "previous_intake_id": str(intake_id), "is_replay": False, "release_changed": False}
            await self.repo.audit(conn, actor.subject_id, "knowledge.url.refresh.requested", identifier, binding)
            await self.repo.outbox(conn, "knowledge.intake.accepted", identifier, result)
            await self.repo.remember(conn, actor.subject_id, "url-refresh:"+key, fingerprint, result)
            return result

    async def accept(self, actor, upload, hints: DraftIntakeInput, key, *, artifact=None):
        self.platform.admin(actor)
        await self.ready()
        if not key or not key.strip() or len(key) > 128:
            raise PlatformError(422, "IDEMPOTENCY_REQUIRED", "Cần mã yêu cầu tiếp nhận.")
        filename = upload.filename or ""
        if not filename or filename != PurePath(filename).name or len(filename) > 200 or any(c in filename for c in "\\/\r\n\x00"):
            raise PlatformError(422, "INVALID_FILENAME", "Tên tệp không hợp lệ.")
        media = {".pdf": "application/pdf", ".txt": "text/plain"}.get(PurePath(filename.lower()).suffix)
        if not media or upload.content_type not in {media, "application/octet-stream"}:
            raise PlatformError(415, "UNSUPPORTED_MEDIA", "Hỗ trợ PDF/TXT với MIME phù hợp.")
        artifact = artifact or await self.storage.receive(upload, media)
        fingerprint = digest({"hints": hints.model_dump(mode="json"), "filename": filename,
                              "sha256": artifact.sha256, "size": artifact.byte_size, "media": media})
        async with self.repo.transaction() as conn:
            replay = await self.repo.replay(conn, actor.subject_id, "intake:" + key, fingerprint)
            if replay:
                return {**replay, "is_replay": True}
            intake_id, job_id = generate_uuid7(), generate_uuid7()
            await self.repo.artifact(conn, artifact)
            await conn.execute("""INSERT INTO knowledge_intake(id,tenant_id,original_id,filename,hints,created_by)
                VALUES($1,$2,$3,$4,$5::jsonb,$6)""", intake_id, self.repo.tenant, artifact.id,
                filename, json.dumps(hints.model_dump(mode="json")), actor.subject_id)
            await conn.execute("""INSERT INTO knowledge_ingestion_job(id,tenant_id,intake_id)
                VALUES($1,$2,$3)""", job_id, self.repo.tenant, intake_id)
            result = {"intake_id": intake_id, "job_id": job_id, "state": "QUEUED",
                      "original_sha256": artifact.sha256, "revision": 1, "is_replay": False}
            await self.repo.audit(conn, actor.subject_id, "knowledge.intake.accepted", intake_id,
                                  {"job_id": job_id, "sha256": artifact.sha256})
            await self.repo.outbox(conn, "knowledge.intake.accepted", intake_id, result)
            await self.repo.remember(conn, actor.subject_id, "intake:" + key, fingerprint, result)
            return result

    async def list(self, actor):
        self.platform.admin(actor)
        await self.ready()
        async with self.repo.transaction() as conn:
            rows = await conn.fetch("""SELECT i.id,i.filename,i.hints,i.observed_at,i.created_by,
                f.original_id IS NOT NULL AS can_refresh_url,
                a.sha256 AS original_sha256,j.id AS job_id,j.state,j.stage,j.progress,j.error_code,
                r.version_id,CASE WHEN r.intake_id IS NULL THEN 1 ELSE 2 END AS revision
                FROM knowledge_intake i LEFT JOIN knowledge_intake_fetch f ON f.intake_id=i.id AND f.tenant_id=i.tenant_id
                LEFT JOIN knowledge_artifact a ON a.id=COALESCE(i.original_id,f.original_id) AND a.tenant_id=i.tenant_id
                JOIN knowledge_ingestion_job j ON j.intake_id=i.id AND j.tenant_id=i.tenant_id
                LEFT JOIN knowledge_intake_resolution r ON r.intake_id=i.id AND r.tenant_id=i.tenant_id
                WHERE i.tenant_id=$1 ORDER BY i.observed_at DESC,i.id DESC LIMIT 200""", self.repo.tenant)
            result = []
            for row in rows:
                item = public_row(row)
                item["hints"] = json_value(row["hints"])
                issues = await conn.fetch("SELECT id,code,fields,evidence FROM knowledge_intake_issue WHERE intake_id=$1 AND tenant_id=$2 ORDER BY recorded_at,id", row["id"], self.repo.tenant)
                item["issues"] = [{**public_row(issue), "fields": json_value(issue["fields"]), "evidence": json_value(issue["evidence"])} for issue in issues]
                result.append(item)
            return {"items": result}

    async def original(self, actor, intake_id):
        self.platform.admin(actor)
        await self.ready()
        async with self.repo.transaction() as conn:
            row = await conn.fetchrow("""SELECT a.*,i.filename FROM knowledge_intake i
                LEFT JOIN knowledge_intake_fetch f ON f.intake_id=i.id AND f.tenant_id=i.tenant_id
                JOIN knowledge_artifact a ON a.id=COALESCE(i.original_id,f.original_id) AND a.tenant_id=i.tenant_id
                WHERE i.id=$1 AND i.tenant_id=$2""", intake_id, self.repo.tenant)
            if not row:
                raise PlatformError(404, "INTAKE_NOT_FOUND", "Không tìm thấy hồ sơ tiếp nhận.")
            return self.storage.read(row), row["media_type"], row["filename"]

    async def recheck(self,actor,intake_id,body,key):
        self.platform.admin(actor)
        await self.ready()
        fingerprint=digest({"intake_id":intake_id,**body.model_dump(mode="json")})
        async with self.repo.transaction() as conn:
            replay=await self.repo.replay(conn,actor.subject_id,"intake-recheck:"+key,fingerprint)
            if replay: return {**replay,"is_replay":True}
            row=await conn.fetchrow("""SELECT j.id AS job_id,j.state,j.attempts,a.* FROM knowledge_intake i
                JOIN knowledge_ingestion_job j ON j.intake_id=i.id AND j.tenant_id=i.tenant_id
                LEFT JOIN knowledge_intake_fetch f ON f.intake_id=i.id AND f.tenant_id=i.tenant_id
                JOIN knowledge_artifact a ON a.id=COALESCE(i.original_id,f.original_id) AND a.tenant_id=i.tenant_id
                WHERE i.id=$1 AND i.tenant_id=$2 FOR UPDATE OF i,j""",intake_id,self.repo.tenant)
            if not row: raise PlatformError(404,"INTAKE_NOT_FOUND","Không tìm thấy hồ sơ tiếp nhận.")
            if body.expected_revision!=1 or await conn.fetchval("SELECT EXISTS(SELECT 1 FROM knowledge_intake_resolution WHERE intake_id=$1 AND tenant_id=$2)",intake_id,self.repo.tenant):
                raise PlatformError(409,"INTAKE_REVISION_CHANGED","Hồ sơ đã chuyển sang phiên bản khác; tải lại để tiếp tục.")
            if row["state"]!="NEEDS_INFORMATION" or row["sha256"]!=body.expected_original_sha256:
                raise PlatformError(409,"INTAKE_NOT_READY","Hồ sơ hoặc nguồn đã đổi; chờ xử lý hoặc tải lại.")
            if row["attempts"]>=3:
                raise PlatformError(409,"RECHECK_ATTEMPTS_EXHAUSTED","Hồ sơ đã dùng hết giới hạn lần xử lý; cần đối chiếu nguyên nhân và tạo rendition/run mới phù hợp.")
            self.storage.read(row)
            await conn.execute("""UPDATE knowledge_ingestion_job SET state='QUEUED',next_attempt_at=clock_timestamp(),
                fencing_token=fencing_token+1,updated_at=clock_timestamp() WHERE id=$1 AND tenant_id=$2""",row["job_id"],self.repo.tenant)
            result={"intake_id":str(intake_id),"job_id":str(row["job_id"]),"state":"QUEUED","attempts_preserved":row["attempts"],"is_replay":False}
            await self.repo.audit(conn,actor.subject_id,"knowledge.intake.recheck",intake_id,{"job_id":str(row["job_id"]),"attempts_preserved":row["attempts"]})
            await self.repo.outbox(conn,"knowledge.intake.recheck",intake_id,result)
            await self.repo.remember(conn,actor.subject_id,"intake-recheck:"+key,fingerprint,result)
            return result

    async def evidence(self, actor, intake_id, offset=0, limit=20):
        self.platform.admin(actor)
        await self.ready()
        if type(offset) is not int or type(limit) is not int or offset < 0 or not 1 <= limit <= 100:
            raise PlatformError(422, "EVIDENCE_PAGE_INVALID", "Chọn phạm vi bằng chứng hợp lệ.")
        from campus247.application.knowledge.evidence_units import EvidenceManifest, configuration_hash, verify_manifest
        async with self.repo.transaction() as conn:
            row = await conn.fetchrow("""SELECT j.id AS job_id,a.* FROM knowledge_intake i
                JOIN knowledge_ingestion_job j ON j.intake_id=i.id AND j.tenant_id=i.tenant_id
                LEFT JOIN knowledge_intake_fetch f ON f.intake_id=i.id AND f.tenant_id=i.tenant_id
                JOIN knowledge_artifact a ON a.id=COALESCE(i.original_id,f.original_id) AND a.tenant_id=i.tenant_id
                WHERE i.id=$1 AND i.tenant_id=$2""", intake_id, self.repo.tenant)
            if not row:
                raise PlatformError(404, "INTAKE_NOT_FOUND", "Không tìm thấy hồ sơ tiếp nhận.")
            self.storage.read(row)
            extraction = await conn.fetchrow("""SELECT s.* FROM knowledge_job_step s WHERE s.job_id=$1 AND s.stage='EXTRACT'
                AND s.input_sha256=$2 ORDER BY s.completed_at DESC LIMIT 1""", row["job_id"], row["sha256"])
            if not extraction:
                raise PlatformError(404, "EVIDENCE_NOT_READY", "Chưa có bằng chứng trích xuất của hồ sơ này.")
            binding = {"tenant_id": self.repo.tenant, "original_sha256": row["sha256"],
                "extraction_sha256": extraction["output_sha256"], "parser_config_sha256": extraction["config_sha256"]}
            step = await self.repo.checkpoint({"id": row["job_id"]}, "EVIDENCE", digest(binding), configuration_hash())
            if not step:
                raise PlatformError(404, "EVIDENCE_NOT_READY", "Cần checkpoint bằng chứng theo validator hiện tại.")
            source = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", extraction["artifact_id"], self.repo.tenant)
            evidence = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", step["artifact_id"], self.repo.tenant)
            source_bytes, evidence_bytes = self.storage.read(source), self.storage.read(evidence)
            if digest(source_bytes) != extraction["output_sha256"] or digest(evidence_bytes) != step["output_sha256"]:
                raise PlatformError(409, "EVIDENCE_INTEGRITY", "Bằng chứng không khớp checkpoint.")
            try:
                manifest = verify_manifest(EvidenceManifest.model_validate_json(evidence_bytes), json.loads(source_bytes), **binding)
            except ValueError:
                raise PlatformError(409, "EVIDENCE_INTEGRITY", "Bằng chứng không khớp nguồn hoặc phạm vi.") from None
            payload = manifest.model_dump(mode="json")
            payload["units"] = payload["units"][offset:offset+limit]
            shown = {unit["id"] for unit in payload["units"]}
            payload["dependencies"] = [edge for edge in payload["dependencies"] if edge["unit_id"] in shown]
            payload["issues"] = [issue for issue in payload["issues"] if not issue.get("unit_ids") or shown.intersection(issue["unit_ids"])][:100]
            return {"manifest_sha256": step["output_sha256"], **payload, "offset": offset,
                "unit_count": len(manifest.units), "dependency_count": len(manifest.dependencies), "issue_count": len(manifest.issues),
                "next_offset": offset+limit if offset+limit < len(manifest.units) else None}

    async def ocr(self, actor, intake_id, page, offset=0, limit=20):
        self.platform.admin(actor)
        await self.ready()
        if type(page) is not int or page<1:
            raise PlatformError(422,"OCR_PAGE_INVALID","Cần trang OCR hợp lệ.")
        if type(offset) is not int or type(limit) is not int or offset < 0 or not 1 <= limit <= 100:
            raise PlatformError(422,"EVIDENCE_PAGE_INVALID","Chọn phạm vi bằng chứng hợp lệ.")
        async with self.repo.transaction() as conn:
            original = await conn.fetchrow("""SELECT a.*,job.id AS job_id FROM knowledge_intake i
                JOIN knowledge_ingestion_job job ON job.intake_id=i.id AND job.tenant_id=i.tenant_id
                LEFT JOIN knowledge_intake_fetch f ON f.intake_id=i.id AND f.tenant_id=i.tenant_id
                JOIN knowledge_artifact a ON a.id=COALESCE(i.original_id,f.original_id) AND a.tenant_id=i.tenant_id
                WHERE i.id=$1 AND i.tenant_id=$2""",intake_id,self.repo.tenant)
            if not original: raise PlatformError(404,"INTAKE_NOT_FOUND","Không tìm thấy hồ sơ tiếp nhận.")
            self.storage.read(original)
            step = await conn.fetchrow("SELECT * FROM knowledge_job_step WHERE job_id=$1 AND stage=$2 ORDER BY completed_at DESC LIMIT 1",original["job_id"],"OCR:"+str(page))
            if not step: raise PlatformError(404,"OCR_NOT_READY","Chưa có OCR của trang này; ảnh gốc vẫn được giữ.")
            saved = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2",step["artifact_id"],self.repo.tenant)
            raw = self.storage.read(saved)
            payload = json.loads(raw)
            rendered = await conn.fetchrow("SELECT * FROM knowledge_job_step WHERE job_id=$1 AND stage=$2 AND input_sha256=$3 ORDER BY completed_at DESC LIMIT 1",original["job_id"],"RENDER:"+str(page),original["sha256"])
            if not rendered: raise PlatformError(409,"OCR_CACHE_BINDING","Thiếu ảnh gắn với kết quả OCR.")
            image = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2",rendered["artifact_id"],self.repo.tenant)
            image_bytes = self.storage.read(image)
            expected = digest({"tenant_id":self.repo.tenant,"source_sha256":original["sha256"],"image_sha256":image["sha256"],"page":page})
            if (digest(raw)!=step["output_sha256"] or step["input_sha256"]!=expected or payload.get("source_sha256")!=original["sha256"]
                or payload.get("image_sha256")!=image["sha256"] or payload.get("page")!=page
                or digest(payload.get("automation_profile"))!=step["config_sha256"] or payload.get("index_status")!="not_admitted"):
                raise PlatformError(409,"OCR_CACHE_BINDING","OCR không khớp nguồn, ảnh hoặc profile.")
            from campus247.application.knowledge import ocr_evidence
            binding = {"tenant_id": self.repo.tenant, "original_sha256": original["sha256"],
                "image_sha256": image["sha256"], "ocr_sha256": step["output_sha256"],
                "ocr_config_sha256": step["config_sha256"], "page": page}
            evidence_step = await self.repo.checkpoint({"id": original["job_id"]}, "OCR_EVIDENCE:"+str(page),
                digest(binding), ocr_evidence.configuration_hash())
            evidence_view = None
            if evidence_step:
                evidence = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", evidence_step["artifact_id"], self.repo.tenant)
                evidence_bytes = self.storage.read(evidence)
                if digest(evidence_bytes) != evidence_step["output_sha256"]:
                    raise PlatformError(409,"OCR_EVIDENCE_INTEGRITY","Bằng chứng OCR không khớp checkpoint.")
                try:
                    manifest = ocr_evidence.verify_manifest(ocr_evidence.OcrEvidenceManifest.model_validate_json(evidence_bytes), raw, image_bytes, **binding)
                except ValueError:
                    raise PlatformError(409,"OCR_EVIDENCE_INTEGRITY","Bằng chứng OCR không khớp nguồn hoặc phạm vi.") from None
                shown = manifest.units[offset:offset+limit]
                ids = {unit.id for unit in shown}
                evidence_view = {"manifest_sha256": evidence_step["output_sha256"], "unit_count": len(manifest.units),
                    "dependency_count": len(manifest.dependencies), "coordinate_space": manifest.coordinate_space,
                    "units": [unit.model_dump(mode="json") for unit in shown],
                    "dependencies": [edge.model_dump(mode="json") for edge in manifest.dependencies if edge.unit_id in ids],
                    "offset": offset, "next_offset": offset+limit if offset+limit < len(manifest.units) else None,
                    "semantics_verified": False, "dependency_graph_verified": False, "admission_granted": False}
            return {"page":page,"text":payload["text"],"confidence":payload["confidence"],"image_width":payload["image_width"],"image_height":payload["image_height"],
                "source_sha256":original["sha256"],"image_sha256":image["sha256"],"ocr_sha256":step["output_sha256"],
                "profile":payload["automation_profile"],"semantics_verified":False,"admission_granted":False,"evidence":evidence_view}

    async def resolve(self, actor, intake_id, expected_revision, metadata: IntakeMetadata, key):
        self.platform.admin(actor)
        await self.ready()
        fingerprint = digest({"intake_id": intake_id, "revision": expected_revision, "metadata": metadata.model_dump(mode="json")})
        async with self.repo.transaction() as conn:
            replay = await self.repo.replay(conn, actor.subject_id, "intake-resolve:" + key, fingerprint)
            if replay:
                return {**replay, "is_replay": True}
            row = await conn.fetchrow("SELECT * FROM knowledge_intake WHERE id=$1 AND tenant_id=$2 FOR UPDATE", intake_id, self.repo.tenant)
            if not row:
                raise PlatformError(404, "INTAKE_NOT_FOUND", "Không tìm thấy hồ sơ tiếp nhận.")
            if expected_revision != 1 or await conn.fetchval("SELECT EXISTS(SELECT 1 FROM knowledge_intake_resolution WHERE intake_id=$1 AND tenant_id=$2)", intake_id, self.repo.tenant):
                raise PlatformError(409, "INTAKE_REVISION_CHANGED", "Hồ sơ đã được bổ sung; tải lại trước khi xử lý.")
            job = await conn.fetchrow("SELECT * FROM knowledge_ingestion_job WHERE intake_id=$1 AND tenant_id=$2 FOR UPDATE", intake_id, self.repo.tenant)
            if job["state"] != "NEEDS_INFORMATION" or job["stage"] == "DUPLICATE_REVIEW":
                raise PlatformError(409, "INTAKE_NOT_READY", "Chờ worker hoàn tất trích xuất trước khi bổ sung metadata.")
            original_id = row["original_id"] or await conn.fetchval("SELECT original_id FROM knowledge_intake_fetch WHERE intake_id=$1 AND tenant_id=$2", intake_id, self.repo.tenant)
            artifact = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", original_id, self.repo.tenant)
            if not artifact or artifact["media_type"] not in {"application/pdf", "text/plain"}:
                raise PlatformError(422, "LINKED_ORIGINAL_REQUIRED", "Cần tệp PDF/TXT gốc; trang HTML hoặc tệp đính kèm chưa được xác minh.")
            saved = StoredArtifact(**{k: str(artifact[k]) if k == "id" else artifact[k] for k in StoredArtifact.__dataclass_fields__})
            filename = row["filename"] if row["original_id"] else row["filename"] + (".pdf" if artifact["media_type"] == "application/pdf" else ".txt")
            result = await self.platform.upload(actor, metadata, SimpleNamespace(filename=filename, content_type=artifact["media_type"]),
                "intake-" + str(intake_id), artifact=saved, _connection=conn)
            # A candidate edition has its own ID; received time is never an issuance/effect date.
            # Same bytes/title do not merge this observation with another issuer or business edition.
            edition_id = generate_uuid7()
            identity = EditionIdentity(tenant_id=self.repo.tenant, family_id=result["source_id"], issuer=metadata.owner_unit,
                scope=ApplicabilityScope(programmes=ScopeAxis(kind="VALUES", values=tuple(metadata.programs))))
            await conn.execute("""INSERT INTO knowledge_document_edition(id,tenant_id,source_id,identity,identity_sha256,created_by)
                VALUES($1,$2,$3,$4::jsonb,$5,$6)""", edition_id, self.repo.tenant, result["source_id"],
                identity.model_dump_json(), digest(identity.model_dump(mode="json")), actor.subject_id)
            step = await conn.fetchrow("SELECT * FROM knowledge_job_step WHERE job_id=$1 AND stage='EXTRACT' ORDER BY completed_at DESC LIMIT 1", job["id"])
            if not step or not step["artifact_id"] or step["input_sha256"] != artifact["sha256"]:
                raise PlatformError(409, "CHECKPOINT_INTEGRITY", "Chưa có checkpoint trích xuất đúng nguồn.")
            extracted_artifact = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", step["artifact_id"], self.repo.tenant)
            extracted_bytes = self.storage.read(extracted_artifact)
            if digest(extracted_bytes) != step["output_sha256"]:
                raise PlatformError(409, "CHECKPOINT_INTEGRITY", "Checkpoint trích xuất không khớp.")
            parser_identity = json.loads(extracted_bytes).get("parser_identity", {})
            rendition = RenditionIdentity(edition_id=edition_id, source_sha256=artifact["sha256"], artifact_id=step["artifact_id"],
                processor_revision="text-pdf-pages-v1", config_sha256=step["config_sha256"], schema_revision=parser_identity.get("schema", "pages-issues-v1"))
            await conn.execute("""INSERT INTO knowledge_intake_resolution
                (intake_id,tenant_id,version_id,expected_revision,metadata_sha256,resolved_by)
                VALUES($1,$2,$3,1,$4,$5)""", intake_id, self.repo.tenant, result["version_id"], digest(metadata.model_dump(mode="json")), actor.subject_id)
            await conn.execute("""INSERT INTO knowledge_version_lineage(version_id,tenant_id,edition_id,observation_id,rendition_identity)
                VALUES($1,$2,$3,$4,$5::jsonb)""", result["version_id"], self.repo.tenant, edition_id, intake_id, rendition.model_dump_json())
            await conn.execute("UPDATE knowledge_ingestion_job SET state='SUCCEEDED',stage='METADATA_RESOLVED',progress=100,updated_at=clock_timestamp() WHERE id=$1", job["id"])
            result = {**result, "intake_id": intake_id, "revision": 2}
            await self.repo.audit(conn, actor.subject_id, "knowledge.intake.resolved", intake_id, {"version_id": result["version_id"]})
            await self.repo.outbox(conn, "knowledge.intake.resolved", intake_id, result)
            await self.repo.remember(conn, actor.subject_id, "intake-resolve:" + key, fingerprint, result)
            return result

    async def preview(self, actor, intake_id, page_number):
        self.platform.admin(actor)
        await self.ready()
        async with self.repo.transaction() as conn:
            row = await conn.fetchrow("""SELECT s.* FROM knowledge_intake i
                JOIN knowledge_ingestion_job j ON j.intake_id=i.id AND j.tenant_id=i.tenant_id
                JOIN knowledge_job_step s ON s.job_id=j.id AND s.stage='EXTRACT'
                WHERE i.id=$1 AND i.tenant_id=$2 ORDER BY s.completed_at DESC LIMIT 1""", intake_id, self.repo.tenant)
            if not row:
                raise PlatformError(404, "PREVIEW_NOT_FOUND", "Chưa có ảnh đối chiếu trang này.")
            extracted = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", row["artifact_id"], self.repo.tenant)
            raw = self.storage.read(extracted)
            if digest(raw) != row["output_sha256"]:
                raise PlatformError(409, "CHECKPOINT_INTEGRITY", "Checkpoint không khớp.")
            page = next((p for p in json.loads(raw)["pages"] if p["page"] == page_number), None)
            if not page:
                raise PlatformError(404, "PREVIEW_NOT_FOUND", "Chưa có ảnh đối chiếu trang này.")
            render = await conn.fetchrow("""SELECT * FROM knowledge_job_step WHERE job_id=$1 AND stage=$2
                AND input_sha256=$3 ORDER BY completed_at DESC LIMIT 1""", row["job_id"], "RENDER:"+str(page_number), row["input_sha256"])
            if not render:
                raise PlatformError(404, "PREVIEW_NOT_FOUND", "Ảnh trang này còn chờ xử lý.")
            receipt = json_value(render["result"])
            image = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2 AND kind='review-preview'",
                render["artifact_id"], self.repo.tenant)
            if (not image or image["sha256"] != render["output_sha256"] or receipt["source_sha256"] != row["input_sha256"]
                    or receipt["page"] != page_number):
                raise PlatformError(409, "PREVIEW_INTEGRITY", "Ảnh không khớp đúng original/trang/receipt.")
            return self.storage.read(image)

    async def link_existing(self, actor, intake_id, body, key):
        self.platform.admin(actor)
        await self.ready()
        fingerprint = digest({"intake_id": intake_id, "decision": body.model_dump(mode="json")})
        async with self.repo.transaction() as conn:
            replay = await self.repo.replay(conn, actor.subject_id, "intake-link:"+key, fingerprint)
            if replay: return {**replay, "is_replay": True}
            row = await conn.fetchrow("""SELECT i.*,COALESCE(i.original_id,f.original_id) AS acquired_original_id
                FROM knowledge_intake i LEFT JOIN knowledge_intake_fetch f ON f.intake_id=i.id AND f.tenant_id=i.tenant_id
                WHERE i.id=$1 AND i.tenant_id=$2 FOR UPDATE OF i""", intake_id, self.repo.tenant)
            if not row: raise PlatformError(404, "INTAKE_NOT_FOUND", "Không tìm thấy hồ sơ tiếp nhận.")
            if body.expected_revision != 1 or await conn.fetchval("SELECT EXISTS(SELECT 1 FROM knowledge_intake_resolution WHERE intake_id=$1)", intake_id):
                raise PlatformError(409, "INTAKE_REVISION_CHANGED", "Hồ sơ đã thay đổi.")
            job = await conn.fetchrow("SELECT * FROM knowledge_ingestion_job WHERE intake_id=$1 AND tenant_id=$2 FOR UPDATE", intake_id, self.repo.tenant)
            if job["state"] != "NEEDS_INFORMATION" or job["stage"] != "DUPLICATE_REVIEW":
                raise PlatformError(409, "INTAKE_NOT_READY", "Hồ sơ chưa ở bước đối chiếu tệp trùng.")
            pointer = await self.repo.pointer(conn, lock=True)
            if pointer["generation"] != body.expected_generation or pointer["policy_generation"] != body.expected_policy_generation:
                raise PlatformError(409, "ACTIVE_GENERATION_CHANGED", "Kho hoặc chính sách đã đổi; đối chiếu lại.")
            artifact = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", row["acquired_original_id"], self.repo.tenant)
            if not artifact: raise PlatformError(409, "ARTIFACT_INTEGRITY", "Chưa có original đã kiểm hash.")
            self.storage.read(artifact)
            candidates, _ = await reusable_candidates(self.platform, conn, artifact)
            candidate = next((c for c in candidates if c["version_id"] == str(body.version_id)), None)
            origin = json_value(row["hints"]).get("source_uri")
            if not candidate or body.source_uri != candidate["canonical_uri"] or origin and origin != body.source_uri:
                raise PlatformError(409, "SOURCE_ORIGIN_CONFLICT", "Trùng bytes chưa đủ xác lập cùng nhà xuất bản/phạm vi; giữ hồ sơ riêng để đối chiếu.")
            decision = {"kind": "EXPLICIT_OBSERVATION_LINK", "intake_id": intake_id,
                "original_sha256": artifact["sha256"], "selected": candidate, "basis": body.basis,
                "actor_id": actor.subject_id, "authority_granted": False, "release_changed": False}
            saved = self.storage.write_json(json.dumps(decision, ensure_ascii=False, sort_keys=True).encode(), "intake-association")
            await self.repo.save_step(conn, job, "LINK_EXISTING", artifact["sha256"], SEPARATE_ROUTE_CONFIG,
                saved.sha256, saved, {"version_id": str(body.version_id), "new_model_calls": 0, "release_changed": False})
            await conn.execute("""INSERT INTO knowledge_intake_resolution
                (intake_id,tenant_id,version_id,expected_revision,metadata_sha256,resolved_by)
                VALUES($1,$2,$3,1,$4,$5)""", intake_id, self.repo.tenant, body.version_id, candidate["metadata_sha256"], actor.subject_id)
            await conn.execute("UPDATE knowledge_ingestion_job SET state='SUCCEEDED',stage='LINKED_EXISTING',progress=100,updated_at=clock_timestamp() WHERE id=$1", job["id"])
            result = {"intake_id": intake_id, "version_id": str(body.version_id), "revision": 2, "is_replay": False,
                "reused_existing_evidence": True, "new_model_calls": 0, "release_changed": False}
            await self.repo.audit(conn, actor.subject_id, "knowledge.intake.linked-existing", intake_id, {"decision_sha256": saved.sha256, "version_id": str(body.version_id)})
            await self.repo.outbox(conn, "knowledge.intake.linked-existing", intake_id, result)
            await self.repo.remember(conn, actor.subject_id, "intake-link:"+key, fingerprint, result)
            return result

    async def separate(self, actor, intake_id, body, key):
        self.platform.admin(actor)
        await self.ready()
        fingerprint = digest({"intake_id": intake_id, "decision": body.model_dump(mode="json")})
        async with self.repo.transaction() as conn:
            replay = await self.repo.replay(conn, actor.subject_id, "intake-separate:"+key, fingerprint)
            if replay: return {**replay, "is_replay": True}
            job = await conn.fetchrow("""SELECT j.*,COALESCE(i.original_id,f.original_id) AS original_id
                FROM knowledge_ingestion_job j JOIN knowledge_intake i ON i.id=j.intake_id AND i.tenant_id=j.tenant_id
                LEFT JOIN knowledge_intake_fetch f ON f.intake_id=i.id AND f.tenant_id=i.tenant_id
                WHERE i.id=$1 AND i.tenant_id=$2 FOR UPDATE OF j""", intake_id, self.repo.tenant)
            if not job: raise PlatformError(404, "INTAKE_NOT_FOUND", "Không tìm thấy hồ sơ.")
            if body.expected_revision != 1 or job["state"] != "NEEDS_INFORMATION" or job["stage"] != "DUPLICATE_REVIEW":
                raise PlatformError(409, "INTAKE_REVISION_CHANGED", "Tải lại hồ sơ để đối chiếu.")
            artifact = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", job["original_id"], self.repo.tenant)
            decision = {"mode": "SEPARATE_OBSERVATION", "reason": body.reason, "actor_id": actor.subject_id}
            await self.repo.save_step(conn, job, "ROUTE_DECISION", artifact["sha256"], SEPARATE_ROUTE_CONFIG,
                digest(decision), None, decision)
            await conn.execute("UPDATE knowledge_ingestion_job SET state='QUEUED',stage='EXTRACT',next_attempt_at=clock_timestamp(),updated_at=clock_timestamp() WHERE id=$1", job["id"])
            result = {"intake_id": intake_id, "state": "QUEUED", "is_replay": False}
            await self.repo.audit(conn, actor.subject_id, "knowledge.intake.kept-separate", intake_id, {"decision_sha256": digest(decision)})
            await self.repo.outbox(conn, "knowledge.intake.kept-separate", intake_id, result)
            await self.repo.remember(conn, actor.subject_id, "intake-separate:"+key, fingerprint, result)
            return result
