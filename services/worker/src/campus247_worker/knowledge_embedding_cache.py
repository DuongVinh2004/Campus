"""Exact-input vector reuse; source occurrences and admission stay independent.

Only newly recorded immutable vector receipts are eligible. Legacy vectors are
never trusted by model name alone. A cache hit creates a new chunk/locator for
the target version and cannot inherit a review, publication, or effective date.
"""
import json
from dataclasses import asdict
from pathlib import Path

from campus247.application.knowledge.platform_models import EMBED_ARTIFACT, PROCESSOR, PlatformError, digest, metadata_binding
from campus247.ports.embedding import validate_embedding_vector

SCHEMA = "scoped-embedding-input-v1"


class EmbeddingInputCache:
    def __init__(self, repo, storage, profile, config_sha256, parser_sha256):
        self.repo, self.storage, self.profile = repo, storage, profile
        from campus247.infrastructure.retrieval import tei
        self.config = digest({"schema": SCHEMA, "embedding": asdict(profile),
            "artifact": EMBED_ARTIFACT, "pipeline": config_sha256, "parser": parser_sha256,
            "cache_code": digest(Path(__file__).read_bytes()), "adapter_code": digest(Path(tei.__file__).read_bytes())})

    def binding(self, version, text):
        if metadata_binding(version) != version["metadata_sha256"]:
            raise PlatformError(409, "EMBEDDING_SCOPE_CHANGED", "Metadata đã đổi; cần xử lý lại đúng phạm vi.")
        return {"schema": SCHEMA, "tenant_id": self.repo.tenant,
            "source_id": str(version["source_id"]), "metadata_sha256": version["metadata_sha256"],
            "config_sha256": self.config, "input_sha256": digest(text.encode()), "input_text": text}

    async def current(self, conn, version):
        current = await self.repo.version(conn, version["version_id"], lock=True)
        if (current["revoked_at"] or current["review_state"] == "REJECTED"
            or current["processor_profile"] != PROCESSOR
            or any(current[field] != version[field] for field in
                ("source_id", "metadata_sha256", "original_id", "rendition_id", "rendition_sha256"))
            or metadata_binding(current) != current["metadata_sha256"]):
            raise PlatformError(409, "EMBEDDING_SCOPE_CHANGED", "Nguồn hoặc phạm vi đã đổi trong khi tạo chỉ mục.")
        return current

    async def lookup(self, conn, binding):
        row = await conn.fetchrow("""SELECT step.*,job.version_id FROM knowledge_job_step step
            JOIN knowledge_ingestion_job job ON job.id=step.job_id AND job.tenant_id=$1
            JOIN knowledge_ingest_version x ON x.version_id=job.version_id AND x.tenant_id=job.tenant_id
            JOIN document_version v ON v.id=x.version_id
            JOIN knowledge_source_scope scope ON scope.source_id=v.knowledge_source_id AND scope.tenant_id=x.tenant_id
            WHERE step.stage='EMBED_VECTOR' AND step.input_sha256=$2 AND step.config_sha256=$3
            AND v.knowledge_source_id=$4 AND x.metadata_sha256=$5 AND x.revoked_at IS NULL
            AND x.review_state<>'REJECTED' AND step.artifact_id IS NOT NULL
            ORDER BY step.completed_at,step.job_id LIMIT 1""", self.repo.tenant, digest(binding), self.config,
            binding["source_id"], binding["metadata_sha256"])
        if not row:
            return None
        await self.revalidate(conn, row, binding)
        artifact = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", row["artifact_id"], self.repo.tenant)
        raw = self.storage.read(artifact)
        if digest(raw) != row["output_sha256"]:
            raise PlatformError(409, "EMBEDDING_CACHE_INTEGRITY", "Vector receipt không khớp checkpoint.")
        payload = json.loads(raw)
        if payload.get("binding") != binding or payload.get("profile") != asdict(self.profile):
            raise PlatformError(409, "EMBEDDING_CACHE_MISMATCH", "Vector receipt không khớp toàn bộ input/profile.")
        values = validate_embedding_vector(payload["values"], self.profile).values
        return {**dict(row), "values": values}

    async def revalidate(self, conn, donor, binding):
        version = await self.repo.version(conn, donor["version_id"], lock=True)
        await self.current(conn, version)
        if self.binding(version, binding["input_text"]) != binding:
            raise PlatformError(409, "EMBEDDING_CACHE_MISMATCH", "Nguồn vector không còn cùng binding.")
        for field in ("original_id", "rendition_id"):
            artifact = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", version[field], self.repo.tenant)
            raw = self.storage.read(artifact)
            if field == "rendition_id" and digest(raw) != version["rendition_sha256"]:
                raise PlatformError(409, "EMBEDDING_CACHE_INTEGRITY", "Bản trích xuất của vector đã đổi.")

    def prepare(self, binding, values):
        values = validate_embedding_vector(values, self.profile).values
        return self.storage.write_json(json.dumps({"binding": binding, "profile": asdict(self.profile),
            "values": values}, ensure_ascii=False, sort_keys=True).encode(), "embedding-input-vector")

    async def save(self, conn, job, binding, values, *, accounted_stage, donor=None, artifact=None):
        if donor:
            await self.revalidate(conn, donor, binding)
        await self.repo.save_step(conn, job, "EMBED_VECTOR", digest(binding), self.config,
            donor["output_sha256"] if donor else artifact.sha256, artifact,
            {"input_sha256": binding["input_sha256"], "vector_sha256": digest(values),
             # The chunk's EMBED stage owns inference accounting. Recording
             # its reusable vector artifact must not count that call again.
             "new_model_calls": 0, "inference_accounted_at": accounted_stage, "admission_granted": False,
             "reused_from_job_id": str(donor["job_id"]) if donor else None},
            artifact_ref=donor["artifact_id"] if donor else None)
