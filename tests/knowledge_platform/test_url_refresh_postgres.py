"""Fresh retained observations through the actual worker; HTTP is deterministic."""
import asyncio
from dataclasses import replace

import pytest

from campus247.application.knowledge.document_identity import UrlIntakeInput, RefreshUrlInput
from campus247.application.knowledge.platform_models import PlatformError
from .test_draft_postgres import setup, pytestmark
from .test_document_fetch import fake_pool


def test_refresh_304_new_bytes_and_fetch_failure_preserve_original_history(monkeypatch, retained_directory):
    async def run():
        pool, repo, platform, actor, intake, worker = await setup(retained_directory)
        try:
            fake_pool(monkeypatch, [(200, {"content-type": "text/plain", "etag": '"v1"'}, b"First synthetic public URL document, without institutional facts.")])
            first = await intake.accept_url(actor, UrlIntakeInput(url="https://huce.edu.vn/synthetic-refresh.txt"), "first")
            assert await worker.run_once(target_job_id=first["job_id"]) == "PROCESSED"
            row = next(row for row in (await intake.list(actor))["items"] if row["id"] == first["intake_id"])
            assert row["can_refresh_url"]
            request = RefreshUrlInput(expected_original_sha256=row["original_sha256"])
            with pytest.raises(PlatformError, match="KNOWLEDGE_FORBIDDEN"):
                await intake.refresh_url(replace(actor, tenant_id="other"), first["intake_id"], request, "other")
            with pytest.raises(PlatformError, match="SOURCE_FETCH_BINDING"):
                await intake.refresh_url(actor, first["intake_id"], request.model_copy(update={"expected_original_sha256":"f"*64}), "wrong")
            unchanged = await intake.refresh_url(actor, first["intake_id"], request, "refresh")
            assert (await intake.refresh_url(actor, first["intake_id"], request, "refresh"))["is_replay"]
            calls = fake_pool(monkeypatch, [(304, {}, b"")])
            assert await worker.run_once(target_job_id=unchanged["job_id"]) == "PROCESSED"
            assert calls[0][2]["If-None-Match"] == '"v1"'
            async with pool.acquire() as conn:
                observations = await conn.fetch("SELECT * FROM knowledge_intake_fetch WHERE tenant_id=$1 ORDER BY recorded_at", repo.tenant)
                assert len(observations) == 2 and observations[0]["original_id"] == observations[1]["original_id"]
                first_observation = dict(observations[0])
            changed = await intake.refresh_url(actor, first["intake_id"], request, "changed")
            fake_pool(monkeypatch, [(200, {"content-type":"text/plain", "etag":'"v2"'}, b"Second synthetic URL document; new bytes must not overwrite prior content.")])
            await worker.run_once(target_job_id=changed["job_id"])
            failed = await intake.refresh_url(actor, first["intake_id"], request, "failed")
            fake_pool(monkeypatch, [(503, {}, b"")])
            await worker.run_once(target_job_id=failed["job_id"])
            async with pool.acquire() as conn:
                assert dict(await conn.fetchrow("SELECT * FROM knowledge_intake_fetch WHERE intake_id=$1 AND tenant_id=$2", first["intake_id"], repo.tenant)) == first_observation
                changed_original = await conn.fetchval("SELECT original_id FROM knowledge_intake_fetch WHERE intake_id=$1", changed["intake_id"])
                assert changed_original != first_observation["original_id"]
                failed_job = await conn.fetchrow("SELECT state,error_code,attempts FROM knowledge_ingestion_job WHERE id=$1", failed["job_id"])
                assert failed_job["state"] == "RETRY_WAIT" and failed_job["error_code"] == "SOURCE_FETCH_UNAVAILABLE" and failed_job["attempts"] == 1
                assert await conn.fetchval("SELECT count(*) FROM knowledge_ingest_version WHERE tenant_id=$1", repo.tenant) == 0
                assert await conn.fetchval("SELECT count(*) FROM knowledge_release WHERE tenant_id=$1", repo.tenant) == 0
        finally:
            await pool.close()
    asyncio.run(run())
