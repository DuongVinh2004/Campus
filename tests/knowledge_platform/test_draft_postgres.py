"""Real PostgreSQL intake contracts in the fresh retained rehearsal database only."""
import asyncio
import io
import json
import os
import re
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from starlette.datastructures import Headers, UploadFile

from campus247.application.knowledge.document_identity import DraftIntakeInput, RecheckIntakeInput
from campus247.application.knowledge.intake import KnowledgeIntake
from campus247.application.knowledge.platform import KnowledgePlatform
from campus247.application.knowledge.platform_models import EMBED_MODEL, EMBED_REVISION, IntakeMetadata, PlatformError
from campus247.domain.action.confirmation import ConfirmationTokenService
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.knowledge.repository import KnowledgeRepository, LeaseLost
from campus247.infrastructure.knowledge.storage import FileKnowledgeStorage
from campus247.ports.embedding import EmbeddingProfile
from campus247.ports.identity import IdentityContext, IdentityRole
from campus247_worker.knowledge import KnowledgeIngestionWorker
from .conftest import ROOT

pytestmark = pytest.mark.skipif(not os.environ.get("KNOWLEDGE_AUTOMATION_REHEARSAL"), reason="Explicit fresh database rehearsal receipt required")


class NoModel:
    profile = EmbeddingProfile(EMBED_MODEL, EMBED_REVISION, 1024, batch_limit=1, timeout_ms=30000)

    async def _embed(self, *args):
        raise AssertionError("Draft intake must not use an embedding/model call")


def upload(content=b"Synthetic new document for durable draft intake. No institutional facts."):
    return UploadFile(io.BytesIO(content), filename="new-document.txt", headers=Headers({"content-type": "text/plain"}))


async def setup(path):
    import asyncpg
    from knowledge_platform import checked_path, connection
    file = checked_path(Path(os.environ["KNOWLEDGE_AUTOMATION_REHEARSAL"]), ROOT)
    receipt = json.loads(file.read_text(encoding="utf-8"))
    database = receipt["database"]
    assert file.parent == ROOT / "infra/local/knowledge-automation-20261026"
    assert receipt["status"] == "passed" and receipt["revision"] == "0020"
    assert re.fullmatch(r"campus247_automation_20261026_[0-9a-f]{12}", database)
    pool = await asyncpg.create_pool(**(connection() | {"database": database}), min_size=1, max_size=4)
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT current_database()") == database
        assert await conn.fetchval("SELECT version_num FROM alembic_version") == "0020"
    tenant = "automation-test-" + uuid4().hex
    repo = KnowledgeRepository(pool, tenant)
    platform = KnowledgePlatform(repo, FileKnowledgeStorage(ROOT, path / "artifacts"), ConfirmationTokenService("test-only-confirmation-key"))
    at = datetime.now(UTC)
    actor = IdentityContext(generate_uuid7(), "editor", "test", (IdentityRole.KNOWLEDGE_ADMIN,), "Editor", at, at+timedelta(hours=1), tenant_id=tenant, session_id="test-session")
    worker = KnowledgeIngestionWorker(repo, platform.storage, NoModel(), owner="draft-test-"+uuid4().hex, low_watermark=0)
    return pool, repo, platform, actor, KnowledgeIntake(platform), worker


def test_durable_draft_idempotency_and_metadata_resolution(retained_directory):
    async def run():
        pool, repo, platform, actor, intake, worker = await setup(retained_directory)
        try:
            first = await intake.accept(actor, upload(), DraftIntakeInput(), "new-draft")
            again = await intake.accept(actor, upload(), DraftIntakeInput(), "new-draft")
            assert again["is_replay"] and first["intake_id"] == again["intake_id"]
            with pytest.raises(PlatformError, match="IDEMPOTENCY_CONFLICT"):
                await intake.accept(actor, upload(b"Different bytes, same scoped idempotency key."), DraftIntakeInput(), "new-draft")
            async with pool.acquire() as conn:
                assert await conn.fetchval("SELECT count(*) FROM knowledge_source_scope WHERE tenant_id=$1", repo.tenant) == 0
                assert await conn.fetchval("SELECT count(*) FROM knowledge_ingestion_job WHERE tenant_id=$1", repo.tenant) == 1
            assert await worker.run_once() == "PROCESSED"
            # A new service instance can retrieve this job after the upload tab disappears.
            item = (await KnowledgeIntake(platform).list(actor))["items"][0]
            assert item["state"] == "NEEDS_INFORMATION" and item["revision"] == 1
            assert item["issues"][0]["evidence"]["valid_from"] is None
            assert (await intake.original(actor, first["intake_id"]))[0].startswith(b"Synthetic")
            metadata = IntakeMetadata(title="Explicit synthetic document", owner_unit="Test owner", canonical_uri="urn:new:"+uuid4().hex,
                programs=["PUBLIC"], audiences=["STUDENT"])
            result = await intake.resolve(actor, first["intake_id"], 1, metadata, "resolve")
            replay = await intake.resolve(actor, first["intake_id"], 1, metadata, "resolve")
            assert replay["is_replay"] and replay["version_id"] == result["version_id"]
            with pytest.raises(PlatformError, match="INTAKE_REVISION_CHANGED"):
                await intake.resolve(actor, first["intake_id"], 1, metadata, "different-resolution")
            async with pool.acquire() as conn:
                version = await repo.version(conn, result["version_id"])
                assert version["effective_from"] is None and version["review_state"] == "DRAFT"
                assert await conn.fetchval("SELECT count(*) FROM knowledge_artifact WHERE tenant_id=$1 AND kind='original'", repo.tenant) == 1
                assert not await conn.fetchval("SELECT EXISTS(SELECT 1 FROM knowledge_release_pointer WHERE tenant_id=$1 AND release_id IS NOT NULL)", repo.tenant)
            claimed = await repo.claim(worker.owner)
            async def must_reuse(*args):
                raise AssertionError("Resolved draft must reuse exact source/parser checkpoint")
            worker._parse = must_reuse
            # Reaches embedding (which is prohibited by NoModel), after proving extraction reuse.
            with pytest.raises(AssertionError, match="embedding/model"):
                await worker._process(claimed)
            step = await repo.checkpoint(claimed, "EXTRACT", first["original_sha256"], worker.parse_config_hash)
            assert step and step["artifact_id"]
            await repo.finish(claimed, "FAILED", "TEST_MODEL_NOT_CALLED")
        finally:
            await pool.close()
    asyncio.run(run())


def test_tenant_auth_and_foreign_key_boundaries(retained_directory):
    async def run():
        import asyncpg
        pool, repo, platform, actor, intake, worker = await setup(retained_directory)
        try:
            accepted = await intake.accept(actor, upload(), DraftIntakeInput(), "one")
            foreign = replace(actor, tenant_id="foreign")
            with pytest.raises(PlatformError, match="KNOWLEDGE_FORBIDDEN"):
                await intake.list(foreign)
            other = KnowledgeIntake(KnowledgePlatform(KnowledgeRepository(pool, "foreign"), platform.storage, platform.tokens))
            with pytest.raises(PlatformError, match="INTAKE_NOT_FOUND"):
                await other.original(foreign, accepted["intake_id"])
            async with pool.acquire() as conn:
                with pytest.raises(asyncpg.ForeignKeyViolationError):
                    async with conn.transaction():
                        original_id = await conn.fetchval("SELECT original_id FROM knowledge_intake WHERE id=$1", accepted["intake_id"])
                        await conn.execute("""INSERT INTO knowledge_intake(id,tenant_id,original_id,filename,hints,created_by)
                            VALUES($1,'foreign',$2,'cross-tenant.txt','{}',$3)""", generate_uuid7(), original_id, actor.subject_id)
                with pytest.raises(asyncpg.CheckViolationError):
                    async with conn.transaction():
                        await conn.execute("INSERT INTO knowledge_ingestion_job(id,tenant_id) VALUES($1,$2)", generate_uuid7(), repo.tenant)
                with pytest.raises(asyncpg.CheckViolationError):
                    async with conn.transaction():
                        await conn.execute("UPDATE knowledge_intake SET filename='changed.txt' WHERE id=$1", accepted["intake_id"])
            await worker.run_once()
        finally:
            await pool.close()
    asyncio.run(run())


def test_resume_uses_checkpoint_and_stale_owner_cannot_commit(retained_directory):
    async def run():
        pool, repo, platform, actor, intake, worker = await setup(retained_directory)
        try:
            accepted = await intake.accept(actor, upload(), DraftIntakeInput(), "resume")
            job = await repo.claim(worker.owner)
            assert await worker._process(job) == "NEEDS_INFORMATION"
            async with pool.acquire() as conn:
                checkpoint_before = await conn.fetch("SELECT stage,artifact_id,output_sha256,completed_at FROM knowledge_job_step WHERE job_id=$1 ORDER BY stage", job["id"])
                assert {step["stage"] for step in checkpoint_before} == {"EXTRACT", "EVIDENCE"}
                await conn.execute("UPDATE knowledge_ingestion_job SET lease_until=clock_timestamp()-interval '1 second' WHERE id=$1 AND tenant_id=$2", job["id"], repo.tenant)
            successor = await repo.claim("successor")
            assert successor["fencing_token"] > job["fencing_token"]
            with pytest.raises(LeaseLost):
                await repo.finish(job, "SUCCEEDED")
            async def no_parse(*args):
                raise AssertionError("Parser must not rerun after committed checkpoint")
            worker._parse = no_parse
            assert await worker._process(successor) == "NEEDS_INFORMATION"
            await repo.finish(successor, "NEEDS_INFORMATION")
            item = (await intake.list(actor))["items"][0]
            assert len(item["issues"]) == 1
            async with pool.acquire() as conn:
                assert await conn.fetch("SELECT stage,artifact_id,output_sha256,completed_at FROM knowledge_job_step WHERE job_id=$1 ORDER BY stage", job["id"]) == checkpoint_before
        finally:
            await pool.close()
    asyncio.run(run())


def test_explicit_recheck_reuses_checkpoints_preserves_attempt_limit_and_is_idempotent(retained_directory):
    async def run():
        pool,repo,_,actor,intake,worker=await setup(retained_directory)
        try:
            accepted=await intake.accept(actor,upload(),DraftIntakeInput(),"recheck-source")
            job=await repo.claim(worker.owner,target_job_id=accepted["job_id"])
            assert job is not None
            await repo.finish(job,await worker._process(job))
            body=RecheckIntakeInput(expected_revision=1,expected_original_sha256=accepted["original_sha256"])
            with pytest.raises(PlatformError,match="INTAKE_NOT_READY"):
                await intake.recheck(actor,accepted["intake_id"],body.model_copy(update={"expected_original_sha256":"f"*64}),"wrong-source")
            async with pool.acquire() as conn:
                before=await conn.fetch("SELECT stage,artifact_id,output_sha256,completed_at FROM knowledge_job_step WHERE job_id=$1 ORDER BY stage",job["id"])
            async def forbidden(*args): raise AssertionError("Recheck must use the exact valid extraction checkpoint")
            worker._parse=forbidden
            for attempt in (1,2):
                result=await intake.recheck(actor,accepted["intake_id"],body,"recheck-"+str(attempt))
                assert result["attempts_preserved"]==attempt
                assert (await intake.recheck(actor,accepted["intake_id"],body,"recheck-"+str(attempt)))["is_replay"]
                job=await repo.claim(worker.owner,target_job_id=accepted["job_id"])
                assert job is not None and job["attempts"]==attempt+1
                await repo.finish(job,await worker._process(job))
            with pytest.raises(PlatformError,match="RECHECK_ATTEMPTS_EXHAUSTED"):
                await intake.recheck(actor,accepted["intake_id"],body,"over-limit")
            async with pool.acquire() as conn:
                assert await conn.fetch("SELECT stage,artifact_id,output_sha256,completed_at FROM knowledge_job_step WHERE job_id=$1 ORDER BY stage",job["id"])==before
                assert await conn.fetchval("SELECT attempts FROM knowledge_ingestion_job WHERE id=$1",job["id"])==3
        finally: await pool.close()
    asyncio.run(run())


def test_url_is_queued_before_fetch_and_provenance_survives_resume(monkeypatch, retained_directory):
    async def run():
        from campus247.application.knowledge.document_identity import UrlIntakeInput
        from campus247.infrastructure.knowledge.fetch import PublicDocumentFetcher
        pool, repo, platform, actor, intake, worker = await setup(retained_directory)
        fetches = []
        job = None
        async def fetch(self, url, storage):
            fetches.append(url)
            artifact = await storage.receive(upload(), "text/plain")
            return artifact, {"requested_url": url, "final_url": url, "observed_at": datetime.now(UTC).isoformat(),
                "hops": [{"url": url, "http_status": 200}], "fetch_policy": "test-network-fixture",
                "issued_at": None, "valid_from": None, "source_verified": False}
        monkeypatch.setattr(PublicDocumentFetcher, "fetch", fetch)
        try:
            body = UrlIntakeInput(url="https://huce.edu.vn/new-test-document-"+uuid4().hex+".txt")
            accepted = await intake.accept_url(actor, body, "url-request")
            assert not fetches
            assert (await intake.accept_url(actor, body, "url-request"))["is_replay"]
            assert (await intake.list(actor))["items"][0]["state"] == "QUEUED"
            job = await repo.claim(worker.owner)
            assert await worker._process(job) == "NEEDS_INFORMATION"
            # A crash before final state commit retains acquisition/extraction.
            async def no_fetch(*args): raise AssertionError("Committed fetch must not rerun")
            monkeypatch.setattr(PublicDocumentFetcher, "fetch", no_fetch)
            assert await worker._process(job) == "NEEDS_INFORMATION"
            await repo.finish(job, "NEEDS_INFORMATION")
            assert len(fetches) == 1
            assert (await intake.original(actor, accepted["intake_id"]))[1] == "text/plain"
            metadata = IntakeMetadata(title="URL draft test", owner_unit="Synthetic publisher", canonical_uri=body.url,
                programs=["PUBLIC"], audiences=["STUDENT"])
            result = await intake.resolve(actor, accepted["intake_id"], 1, metadata, "metadata")
            async with pool.acquire() as conn:
                version = await repo.version(conn, result["version_id"])
                assert version["filename"].endswith(".txt") and version["effective_from"] is None
        finally:
            if job is not None:
                try:
                    await repo.finish(job, "FAILED", "RETAINED_TEST_FAILURE_IF_STILL_RUNNING")
                except LeaseLost:
                    pass
            await pool.close()
    asyncio.run(run())


@pytest.mark.skipif(os.environ.get("KNOWLEDGE_AUTOMATION_BGE_TESTS") != "1", reason="Explicit shared BGE smoke required")
def test_real_bge_index_resume_uses_full_input_binding(retained_directory):
    async def run():
        from knowledge_platform import models
        pool, repo, platform, actor, intake, worker = await setup(retained_directory)
        try:
            await intake.accept(actor, upload(), DraftIntakeInput(), "bge-draft")
            await worker.run_once()
            item = (await intake.list(actor))["items"][0]
            metadata = IntakeMetadata(title="New synthetic BGE document", owner_unit="Test publisher", canonical_uri="urn:bge:"+uuid4().hex,
                programs=["PUBLIC"], audiences=["STUDENT"])
            result = await intake.resolve(actor, item["id"], 1, metadata, "bge-resolution")
            embedding, _ = models()
            calls = []
            class CountReal:
                profile = embedding.profile
                async def _embed(self, texts):
                    calls.append(tuple(texts))
                    return await embedding._embed(texts)
            worker = KnowledgeIngestionWorker(repo, platform.storage, CountReal(), owner="real-bge-smoke", low_watermark=0)
            job = await repo.claim(worker.owner)
            save_step = repo.save_step
            async def crash_at_index(conn, current, stage, *args, **kwargs):
                if stage == "INDEX":
                    raise RuntimeError("TEST_CRASH_BEFORE_INDEX_COMMIT")
                return await save_step(conn, current, stage, *args, **kwargs)
            repo.save_step = crash_at_index
            with pytest.raises(RuntimeError, match="TEST_CRASH"):
                await worker._process(job)
            assert len(calls) == 1
            repo.save_step = save_step
            # A reconstructed worker resumes from committed extraction/vector receipts.
            resumed = KnowledgeIngestionWorker(repo, platform.storage, CountReal(), owner=worker.owner, low_watermark=0)
            async def never_parse(*args):
                raise AssertionError("Committed extraction must be reused")
            resumed._parse = never_parse
            await resumed._process(job)
            assert len(calls) == 1
            await repo.finish(job, "SUCCEEDED")
            async with pool.acquire() as conn:
                version = await repo.version(conn, result["version_id"])
                assert version["index_version"] and version["effective_from"] is None
                assert version["review_state"] == "NEEDS_REVIEW" and version["publication_state"] == "DRAFT"
                steps = await conn.fetch("SELECT * FROM knowledge_job_step WHERE job_id=$1 AND stage LIKE 'EMBED:%'", job["id"])
                assert len(steps) == 1 and json.loads(steps[0]["result"])["new_model_calls"] == 1
                assert await conn.fetchval("SELECT count(*) FROM knowledge_chunk WHERE document_version_id=$1", result["version_id"]) == 1
                lineage = await conn.fetchrow("""SELECT e.identity,l.rendition_identity FROM knowledge_version_lineage l
                    JOIN knowledge_document_edition e ON e.id=l.edition_id WHERE l.version_id=$1""", result["version_id"])
                assert json.loads(lineage["identity"])["issued_on"] is None
                assert json.loads(lineage["identity"])["effective"]["from_day"] is None
        finally:
            await pool.close()
    asyncio.run(run())
