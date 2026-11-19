"""Retained synthetic vectors test cache mechanics, never semantic quality."""
import asyncio
import io
import json
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from starlette.datastructures import Headers, UploadFile

from campus247.application.knowledge.platform import KnowledgePlatform
from campus247.application.knowledge.platform_models import EMBED_MODEL, EMBED_REVISION, IntakeMetadata, PlatformError
from campus247.domain.action.confirmation import ConfirmationTokenService
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.knowledge.repository import KnowledgeRepository
from campus247.infrastructure.knowledge.storage import FileKnowledgeStorage
from campus247.ports.embedding import EmbeddingBatch, EmbeddingProfile, validate_embedding_vector
from campus247.ports.identity import IdentityContext, IdentityRole
from campus247_worker.knowledge import KnowledgeIngestionWorker
from .conftest import ROOT

pytestmark = pytest.mark.skipif(not os.environ.get("KNOWLEDGE_AUTOMATION_CORRECTIONS"), reason="Explicit isolated 0022 rehearsal required")


class SyntheticVectors:
    profile = EmbeddingProfile(EMBED_MODEL, EMBED_REVISION, 1024, batch_limit=1, timeout_ms=30000)

    def __init__(self):
        self.inputs = []

    async def _embed(self, texts):
        self.inputs.extend(texts)
        vector = validate_embedding_vector((1.0,)+(0.0,)*1023, self.profile)
        return EmbeddingBatch((vector,), EMBED_MODEL, EMBED_REVISION, 1024, "l2")


async def setup(path):
    from knowledge_platform import components
    pool, _, _, _ = await components(rehearsal=ROOT / os.environ["KNOWLEDGE_AUTOMATION_CORRECTIONS"])
    repo = KnowledgeRepository(pool, "incremental-synthetic-"+uuid4().hex)
    platform = KnowledgePlatform(repo, FileKnowledgeStorage(ROOT, path / "artifacts"), ConfirmationTokenService("incremental-test-key"))
    at = datetime.now(UTC)
    actor = IdentityContext(generate_uuid7(), "synthetic", "test", (IdentityRole.KNOWLEDGE_ADMIN,), "Synthetic vector test", at,
        at+timedelta(hours=1), tenant_id=repo.tenant, session_id="synthetic-incremental")
    model = SyntheticVectors()
    worker = KnowledgeIngestionWorker(repo, platform.storage, model, owner="incremental-synthetic", low_watermark=0,
        parser_python=ROOT / ".venv/Scripts/python.exe")
    metadata = IntakeMetadata(title="Synthetic incremental index — no semantic acceptance", owner_unit="Synthetic publisher",
        canonical_uri="urn:incremental:"+uuid4().hex, programs=["PUBLIC"], audiences=["STUDENT"])
    return pool, platform, actor, worker, model, metadata


async def add(platform, actor, worker, metadata, pages, key):
    # Feed a complete source-bound extraction checkpoint, not a fake BGE service.
    # Form-feed makes inserted pages visible in the immutable original too.
    content = "\f".join(pages).encode()
    upload = UploadFile(io.BytesIO(content), filename="synthetic-pages.txt", headers=Headers({"content-type": "text/plain"}))
    result = await platform.upload(actor, metadata, upload, key)
    job = await platform.repo.claim(worker.owner, target_job_id=result["job_id"])
    assert job
    extracted = {"pages": [{"page": index, "text": text} for index, text in enumerate(pages, 1)], "page_count": len(pages), "issues": []}
    artifact = platform.storage.write_json(json.dumps(extracted, ensure_ascii=False, sort_keys=True).encode(), "synthetic-extraction")
    async with platform.repo.fenced(job) as conn:
        await platform.repo.save_step(conn, job, "EXTRACT", result["original_sha256"], worker.parse_config_hash,
            artifact.sha256, artifact, {"synthetic_fixture": True})
        await conn.execute("UPDATE knowledge_ingest_version SET rendition_id=$2,rendition_sha256=$3 WHERE version_id=$1", result["version_id"], artifact.id, artifact.sha256)
    try:
        await worker._process(job)
    except Exception:
        await platform.repo.finish(job, "FAILED", "RETAINED_SYNTHETIC_PROBE_FAILURE")
        raise
    else:
        await platform.repo.finish(job, "SUCCEEDED")
    async with platform.repo.pool.acquire() as conn:
        receipt = json.loads(await conn.fetchval("SELECT result FROM knowledge_job_step WHERE job_id=$1 AND stage='INDEX'", job["id"]))
        chunks = await conn.fetch("SELECT c.id,c.page_start,c.content_text,ci.provenance FROM knowledge_chunk c JOIN knowledge_chunk_input ci ON ci.chunk_id=c.id WHERE c.document_version_id=$1 ORDER BY c.ordinal", result["version_id"])
    return result, receipt["incremental"], chunks


def test_changed_and_inserted_pages_reuse_vectors_but_keep_new_locators(retained_directory):
    async def run():
        pool, platform, actor, worker, model, metadata = await setup(retained_directory)
        try:
            first, before, old = await add(platform, actor, worker, metadata, ["Synthetic first page with repeated code 001234.", "Synthetic second page with condition only when approved."], "first")
            assert before["recomputed"] == 2 and len(model.inputs) == 2
            metadata = metadata.model_copy(update={"source_id": str(first["source_id"])})
            second, after, new = await add(platform, actor, worker, metadata, ["Synthetic inserted opening page with different content.", "Synthetic first page with repeated code 001234.", "Synthetic changed final page retains its condition."], "second")
            assert after["reused"] == 1 and after["recomputed"] == 2 and len(model.inputs) == 4
            assert old[0]["id"] != new[1]["id"] and old[0]["page_start"] == 1 and new[1]["page_start"] == 2
            assert old[0]["content_text"] == new[1]["content_text"]
            assert json.loads(old[0]["provenance"])["original_sha256"] != json.loads(new[1]["provenance"])["original_sha256"]
            async with pool.acquire() as conn:
                assert await conn.fetchval("SELECT count(*) FROM knowledge_review WHERE version_id=ANY($1::uuid[])", [first["version_id"], second["version_id"]]) == 0
                assert await conn.fetchval("SELECT count(*) FROM knowledge_release WHERE tenant_id=$1", platform.repo.tenant) == 0
                assert await conn.fetchval("SELECT sum((result->>'new_model_calls')::int) FROM knowledge_job_step WHERE job_id=$1 AND stage LIKE 'EMBED:%'", second["job_id"]) == 2
                assert await conn.fetchval("SELECT sum(COALESCE((result->>'new_model_calls')::int,0)) FROM knowledge_job_step WHERE job_id=$1", second["job_id"]) == 2
            third, repeated, _ = await add(platform, actor, worker, metadata, [row["content_text"] for row in new], "third")
            assert repeated["reused"] == 3 and repeated["recomputed"] == 0 and len(model.inputs) == 4
        finally:
            await pool.close()
    asyncio.run(run())


def test_corrupt_receipt_fails_closed_without_model_or_overwrite(retained_directory):
    async def run():
        pool, platform, actor, worker, model, metadata = await setup(retained_directory)
        try:
            first, _, _ = await add(platform, actor, worker, metadata, ["Synthetic cache corruption probe with explicit source."], "first")
            # Simulate storage corruption through the read boundary, preserving
            # the real artifact and every original byte on disk.
            read = platform.storage.read
            def corrupted(row):
                if row["kind"] == "embedding-input-vector":
                    return b"corruption injected at test boundary"
                return read(row)
            platform.storage.read = corrupted
            with pytest.raises(PlatformError, match="EMBEDDING_CACHE_INTEGRITY"):
                await add(platform, actor, worker, metadata.model_copy(update={"source_id": str(first["source_id"])}),
                    ["Synthetic cache corruption probe with explicit source."], "corrupt")
            assert len(model.inputs) == 1
        finally:
            await pool.close()
    asyncio.run(run())
