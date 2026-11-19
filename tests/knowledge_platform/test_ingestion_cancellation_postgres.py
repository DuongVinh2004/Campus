"""Actual fenced worker orchestration with synthetic delayed model boundaries."""
import asyncio

import pytest

from campus247.infrastructure.knowledge.repository import LeaseLost
from campus247_worker import knowledge
from .test_incremental_index_postgres import setup, SyntheticVectors, pytestmark


async def queued(platform, actor, metadata, key):
    import io
    from starlette.datastructures import Headers, UploadFile
    return await platform.upload(actor, metadata, UploadFile(io.BytesIO(b"Synthetic cancellation and lease probe, without institutional facts."),
        filename="synthetic-cancel.txt", headers=Headers({"content-type": "text/plain"})), key)


def test_untargeted_claim_never_consumes_other_tenant_queue_even_with_expired_owner(retained_directory):
    async def run():
        from campus247.infrastructure.knowledge.repository import KnowledgeRepository
        pool, platform, actor, worker, _, metadata = await setup(retained_directory)
        other_repo = KnowledgeRepository(pool, platform.repo.tenant+"-other")
        try:
            result = await queued(platform, actor, metadata, "tenant-boundary")
            assert await other_repo.claim("wrong-tenant") is None
            assert await other_repo.claim("wrong-tenant", target_job_id=result["job_id"]) is None
            first = await platform.repo.claim(worker.owner)
            assert str(first["id"]) == result["job_id"]
            async with pool.acquire() as conn:
                await conn.execute("UPDATE knowledge_ingestion_job SET lease_until=clock_timestamp()-interval '1 second' WHERE id=$1", first["id"])
            assert await other_repo.claim("wrong-tenant") is None
            recovered = await platform.repo.claim("same-tenant-recovery")
            assert recovered["id"] == first["id"] and recovered["attempts"] == 2
            await platform.repo.finish(recovered, "FAILED", "RETAINED_TENANT_BOUNDARY_PROBE")
        finally:
            await pool.close()
    asyncio.run(run())


def test_cancel_while_model_is_pending_keeps_no_late_vector_and_preserves_attempts(retained_directory):
    async def run():
        pool, platform, actor, worker, model, metadata = await setup(retained_directory)
        entered, pending = asyncio.Event(), asyncio.Event()
        cancelled = []
        async def delayed(texts):
            entered.set()
            try:
                await pending.wait()
                return await SyntheticVectors._embed(model, texts)
            except asyncio.CancelledError:
                cancelled.append(True)
                raise
        worker.embedding._embed = delayed
        task = None
        try:
            result = await queued(platform, actor, metadata, "pending")
            task = asyncio.create_task(worker.run_once(target_job_id=result["job_id"]))
            await asyncio.wait_for(entered.wait(), 5)
            await platform.job_action(actor, result["job_id"], "cancel")
            # Keep the real ten-second heartbeat loop, not a patched fast path.
            assert await asyncio.wait_for(task, 13) == "PROCESSED"
            assert cancelled and not model.inputs
            async with pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM knowledge_ingestion_job WHERE id=$1", result["job_id"])
                assert row["state"] == "CANCELLED" and row["attempts"] == 1 and row["fencing_token"] == 1
                assert await conn.fetchval("SELECT count(*) FROM knowledge_chunk WHERE document_version_id=$1", result["version_id"]) == 0
                assert await conn.fetchval("SELECT count(*) FROM knowledge_job_step WHERE job_id=$1 AND stage='EXTRACT'", result["job_id"]) == 1
                assert await conn.fetchval("SELECT count(*) FROM knowledge_job_step WHERE job_id=$1 AND stage LIKE 'EMBED%'", result["job_id"]) == 0
        finally:
            if task and not task.done():
                task.cancel(); await asyncio.gather(task, return_exceptions=True)
            await pool.close()
    asyncio.run(run())


def test_lost_lease_rejects_model_completion_and_resource_wait_does_not_claim(monkeypatch, retained_directory):
    async def run():
        pool, platform, actor, worker, model, metadata = await setup(retained_directory)
        try:
            result = await queued(platform, actor, metadata, "fenced")
            worker.low_watermark = 2*1024**3
            monkeypatch.setattr(knowledge, "available_memory", lambda: worker.low_watermark-1)
            assert await worker.run_once(target_job_id=result["job_id"]) == "RESOURCE_WAIT"
            async with pool.acquire() as conn:
                assert await conn.fetchval("SELECT attempts FROM knowledge_ingestion_job WHERE id=$1", result["job_id"]) == 0
            monkeypatch.setattr(knowledge, "available_memory", lambda: worker.low_watermark+1)
            first = await platform.repo.claim(worker.owner, target_job_id=result["job_id"])
            assert first
            second = None
            async def expire_then_return(texts):
                nonlocal second
                async with pool.acquire() as conn:
                    await conn.execute("UPDATE knowledge_ingestion_job SET lease_until=clock_timestamp()-interval '1 second' WHERE id=$1", first["id"])
                second = await platform.repo.claim("synthetic-new-owner", target_job_id=first["id"])
                assert second and second["fencing_token"] == first["fencing_token"]+1
                return await SyntheticVectors._embed(model, texts)
            worker.embedding._embed = expire_then_return
            with pytest.raises(LeaseLost):
                await worker._process(first)
            async with pool.acquire() as conn:
                assert await conn.fetchval("SELECT count(*) FROM knowledge_chunk WHERE document_version_id=$1", result["version_id"]) == 0
                assert await conn.fetchval("SELECT count(*) FROM knowledge_job_step WHERE job_id=$1 AND stage LIKE 'EMBED%'", first["id"]) == 0
            await platform.repo.finish(second, "FAILED", "RETAINED_SYNTHETIC_FENCING_PROBE")
            async with pool.acquire() as conn:
                row = await conn.fetchrow("SELECT attempts,fencing_token FROM knowledge_ingestion_job WHERE id=$1", first["id"])
                assert row["attempts"] == 2 and row["fencing_token"] == 2
        finally:
            await pool.close()
    asyncio.run(run())


def test_manual_retry_and_expired_owner_cannot_reset_or_exceed_three_attempts(retained_directory):
    async def run():
        from campus247.application.knowledge.platform_models import PlatformError
        pool, platform, actor, worker, _, metadata = await setup(retained_directory)
        try:
            result = await queued(platform, actor, metadata, "three-attempt-cap")
            for number in range(1, 4):
                job = await platform.repo.claim(worker.owner, target_job_id=result["job_id"])
                assert job and job["attempts"] == number
                await platform.repo.finish(job, "FAILED", "SYNTHETIC_BOUNDARY_FAILURE")
                if number < 3:
                    await platform.job_action(actor, result["job_id"], "retry")
            with pytest.raises(PlatformError, match="ATTEMPTS_EXHAUSTED"):
                await platform.job_action(actor, result["job_id"], "retry")
            assert await platform.repo.claim(worker.owner, target_job_id=result["job_id"]) is None
            other = await queued(platform, actor, metadata.model_copy(update={"source_id": str(result["source_id"])}), "expired-third-owner")
            for number in range(1, 4):
                current = await platform.repo.claim(worker.owner, target_job_id=other["job_id"])
                assert current["attempts"] == number
                if number < 3:
                    await platform.repo.finish(current, "FAILED", "SYNTHETIC_BOUNDARY_FAILURE")
                    await platform.job_action(actor, other["job_id"], "retry")
            async with pool.acquire() as conn:
                await conn.execute("UPDATE knowledge_ingestion_job SET lease_until=clock_timestamp()-interval '1 second' WHERE id=$1", current["id"])
            assert await platform.repo.claim("late-successor", target_job_id=current["id"]) is None
            async with pool.acquire() as conn:
                final = await conn.fetchrow("SELECT state,error_code,attempts FROM knowledge_ingestion_job WHERE id=$1", current["id"])
                assert dict(final) == {"state": "FAILED", "error_code": "ATTEMPTS_EXHAUSTED", "attempts": 3}
            with pytest.raises(LeaseLost):
                await platform.repo.finish(current, "SUCCEEDED")
        finally:
            await pool.close()
    asyncio.run(run())
