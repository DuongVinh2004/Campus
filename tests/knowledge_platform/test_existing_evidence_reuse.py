"""Use a restored copy's real retained bindings; no new reviews or publication."""
import asyncio
import io
import json
import os
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from starlette.datastructures import UploadFile, Headers

from campus247.application.knowledge.document_identity import DraftIntakeInput, LinkExistingInput, SeparateIntakeInput
from campus247.application.knowledge.intake import KnowledgeIntake
from campus247.application.knowledge.platform_models import PlatformError
from campus247.domain.shared.values import generate_uuid7
from campus247.ports.identity import IdentityContext, IdentityRole
from campus247_worker.knowledge import KnowledgeIngestionWorker
from .test_draft_postgres import NoModel

pytestmark = pytest.mark.skipif(not os.environ.get("KNOWLEDGE_AUTOMATION_RESTORED"), reason="Exact retained restored-copy manifest required")


def test_duplicate_uses_existing_review_bindings_without_reparse_or_embedding():
    async def run():
        from knowledge_platform import components, TENANT
        pool, _, platform, _ = await components(rehearsal=os.environ["KNOWLEDGE_AUTOMATION_RESTORED"])
        intake = KnowledgeIntake(platform)
        now = datetime.now(UTC)
        actor = IdentityContext(generate_uuid7(), "synthetic-intake-test", "test", (IdentityRole.KNOWLEDGE_ADMIN,),
            "Synthetic intake test", now, now+timedelta(hours=1), tenant_id=TENANT, session_id="synthetic-test")
        worker = KnowledgeIngestionWorker(platform.repo, platform.storage, NoModel(), owner="inheritance-test", low_watermark=0, platform=platform)
        async def prohibited(*args): raise AssertionError("Existing valid evidence must not be processed again")
        worker._parse = prohibited
        worker.renderer.render = prohibited
        try:
            async with pool.acquire() as conn:
                pointer_before = await platform.repo.pointer(conn)
                reviews = await conn.fetchval("SELECT count(*) FROM knowledge_review")
                version_count = await conn.fetchval("SELECT count(*) FROM knowledge_ingest_version")
                original = await conn.fetchrow("""SELECT a.* FROM knowledge_release_member m
                    JOIN knowledge_ingest_version x ON x.version_id=m.version_id
                    JOIN knowledge_artifact a ON a.id=x.original_id AND a.tenant_id=x.tenant_id
                    WHERE m.release_id=$1 AND x.tenant_id=$2 AND a.media_type='application/pdf'
                    ORDER BY a.byte_size,m.version_id LIMIT 1""", pointer_before["release_id"], TENANT)
            raw = platform.storage.read(original)
            def file(): return UploadFile(io.BytesIO(raw), filename="duplicate-public-source.pdf", headers=Headers({"content-type":"application/pdf"}))
            from uuid import uuid4
            accepted = await intake.accept(actor, file(), DraftIntakeInput(), "inheritance-"+uuid4().hex)
            job = await platform.repo.claim(worker.owner, target_job_id=accepted["job_id"])
            assert job is not None
            # Selecting an exact queued job must not bypass the shared heavy-job
            # lease, even for a different owner or the same currently held job.
            waiting = await intake.accept(actor, file(), DraftIntakeInput(), "lease-wait-"+uuid4().hex)
            assert await platform.repo.claim("other-owner", target_job_id=waiting["job_id"]) is None
            assert await platform.repo.claim("other-owner", target_job_id=job["id"]) is None
            async with pool.acquire() as conn:
                waiting_row = await conn.fetchrow("SELECT state,attempts,fencing_token FROM knowledge_ingestion_job WHERE id=$1", waiting["job_id"])
                assert waiting_row["state"] == "QUEUED" and waiting_row["attempts"] == 0 and waiting_row["fencing_token"] == 0
            await platform.repo.finish(job, await worker._process(job))
            item = next(i for i in (await intake.list(actor))["items"] if i["id"] == accepted["intake_id"])
            assert item["state"] == "NEEDS_INFORMATION" and item["stage"] == "DUPLICATE_REVIEW"
            evidence = item["issues"][-1]["evidence"]
            candidate = evidence["duplicate_candidates"][0]
            body = LinkExistingInput(expected_revision=1, expected_generation=evidence["generation"],
                expected_policy_generation=evidence["policy_generation"], version_id=candidate["version_id"],
                source_uri=candidate["canonical_uri"], basis="Synthetic integration assertion of the retained acquisition binding; no new approval.", confirmed_same_source=True)
            with pytest.raises(ValidationError):
                LinkExistingInput(**(body.model_dump() | {"confirmed_same_source": False}))
            with pytest.raises(PlatformError, match="ACTIVE_GENERATION_CHANGED"):
                await intake.link_existing(actor, item["id"], body.model_copy(update={"expected_generation":0}), "stale")
            with pytest.raises(PlatformError, match="SOURCE_ORIGIN_CONFLICT"):
                await intake.link_existing(actor, item["id"], body.model_copy(update={"source_uri":"https://other.huce.edu.vn/different"}), "wrong-origin")
            result = await intake.link_existing(actor, item["id"], body, "link")
            assert result["reused_existing_evidence"] and result["new_model_calls"] == 0 and not result["release_changed"]
            assert (await intake.link_existing(actor, item["id"], body, "link"))["is_replay"]
            async with pool.acquire() as conn:
                assert await platform.repo.pointer(conn) == pointer_before
                assert await conn.fetchval("SELECT count(*) FROM knowledge_review") == reviews
                assert await conn.fetchval("SELECT count(*) FROM knowledge_ingest_version") == version_count
                steps = await conn.fetch("SELECT stage FROM knowledge_job_step WHERE job_id=$1", accepted["job_id"])
                assert {r["stage"] for r in steps} == {"DUPLICATE_CANDIDATES","LINK_EXISTING"}
                new_original = await conn.fetchval("SELECT original_id FROM knowledge_intake WHERE id=$1", accepted["intake_id"])
                assert new_original != original["id"]
            # Same bytes at a different claimed publisher remain a separate observation.
            separate = await intake.accept(actor, file(), DraftIntakeInput(source_uri="https://other.huce.edu.vn/different"), "separate-"+uuid4().hex)
            job = await platform.repo.claim(worker.owner, target_job_id=separate["job_id"])
            assert job is not None
            await platform.repo.finish(job, await worker._process(job))
            item = next(i for i in (await intake.list(actor))["items"] if i["id"] == separate["intake_id"])
            with pytest.raises(PlatformError, match="SOURCE_ORIGIN_CONFLICT"):
                await intake.link_existing(actor, item["id"], body, "conflicting-publisher")
            decision = SeparateIntakeInput(expected_revision=1, reason="Explicit different publisher scope; keep separate provenance.")
            await intake.separate(actor, item["id"], decision, "separate")
            assert (await intake.separate(actor, item["id"], decision, "separate"))["is_replay"]
            async with pool.acquire() as conn:
                assert not await conn.fetchval("SELECT EXISTS(SELECT 1 FROM knowledge_intake_resolution WHERE intake_id=$1)", item["id"])
                assert await conn.fetchval("SELECT state FROM knowledge_ingestion_job WHERE id=$1", item["job_id"]) == "QUEUED"
        finally:
            await pool.close()
    asyncio.run(run())
