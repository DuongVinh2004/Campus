"""Actual durable schedule/slot transactions, opt in to a retained rehearsal DB."""
import asyncio
from datetime import UTC, datetime, timedelta

from campus247.application.knowledge.document_identity import UrlIntakeInput
from campus247.application.knowledge.schedules import KnowledgeSchedules, ScheduleInput
from .test_draft_postgres import setup, pytestmark
from .test_document_fetch import fake_pool


def test_recent_history_cannot_starve_a_due_schedule_before_the_scan_limit(monkeypatch, retained_directory):
    async def run():
        from uuid import uuid4
        from campus247.application.knowledge.platform_models import digest
        pool, repo, platform, actor, intake, worker = await setup(retained_directory)
        try:
            fake_pool(monkeypatch, [(200, {"content-type":"text/plain"}, b"Synthetic scheduler fairness fixture; no publication or institutional facts.")])
            first = await intake.accept_url(actor, UrlIntakeInput(url="https://huce.edu.vn/synthetic-fairness.txt"), "initial")
            await worker.run_once(target_job_id=first["job_id"])
            observed = next(row for row in (await intake.list(actor))["items"] if row["id"] == first["intake_id"])
            now = datetime.now(UTC)
            schedules = KnowledgeSchedules(platform)
            original = await schedules.create(actor, ScheduleInput(kind="URL_REFRESH", target_id=first["intake_id"],
                not_before=now-timedelta(seconds=1),expires_at=now+timedelta(minutes=20),interval_seconds=900,
                expected_original_sha256=observed["original_sha256"],confirmed=True), "oldest-due", lambda: actor)
            # Retained history fixtures exercise the real SQL filter, not fetch,
            # authority or source semantics. Every row remains in its test tenant.
            async with repo.transaction() as conn:
                for index in range(205):
                    entry = {**original, "id":str(uuid4())}
                    kind = index % 4
                    if kind == 0:
                        entry["not_before"] = (now+timedelta(minutes=5)).isoformat()
                    elif kind == 1:
                        entry["expires_at"] = (now-timedelta(milliseconds=1)).isoformat()
                    await repo.remember(conn,actor.subject_id,"schedule:create:history-"+str(index),digest(entry),entry)
                    if kind in {2,3}:
                        key = "schedule:cancel:"+entry["id"] if kind == 2 else "schedule:run:"+entry["id"]+":0"
                        outcome = {"state":"CANCELLED" if kind == 2 else "BLOCKED", "synthetic_history":True}
                        await repo.remember(conn,actor.subject_id,key,digest(outcome),outcome)
            outcomes = (await schedules.tick(actor, lambda:actor))["outcomes"]
            assert len(outcomes) == 1 and outcomes[0]["schedule_id"] == original["id"] and outcomes[0]["state"] == "QUEUED"
            assert not (await schedules.tick(actor,lambda:actor))["outcomes"]
            # Finish exactly the synthetic refresh job so no live test lease remains.
            fake_pool(monkeypatch, [(304, {}, b"")])
            await worker.run_once(target_job_id=outcomes[0]["job_id"])
            async with pool.acquire() as conn:
                assert await conn.fetchval("SELECT count(*) FROM knowledge_platform_request WHERE tenant_id=$1 AND request_key LIKE 'schedule:create:%'",repo.tenant) == 206
        finally:
            await pool.close()
    asyncio.run(run())


def test_schedule_survives_service_recreation_and_same_slot_is_not_queued_twice(monkeypatch, retained_directory):
    async def run():
        pool, repo, platform, actor, intake, worker = await setup(retained_directory)
        try:
            fake_pool(monkeypatch, [(200, {"content-type": "text/plain", "etag": '"schedule-1"'},
                b"Synthetic scheduled URL fixture; no institutional facts or publication.")])
            first = await intake.accept_url(actor, UrlIntakeInput(url="https://huce.edu.vn/synthetic-schedule.txt"), "initial")
            await worker.run_once(target_job_id=first["job_id"])
            item = next(row for row in (await intake.list(actor))["items"] if row["id"] == first["intake_id"])
            now = datetime.now(UTC)
            body = ScheduleInput(kind="URL_REFRESH", target_id=first["intake_id"], not_before=now-timedelta(seconds=1),
                expires_at=now+timedelta(minutes=20), interval_seconds=900,
                expected_original_sha256=item["original_sha256"], confirmed=True)
            schedules = KnowledgeSchedules(platform)
            created = await schedules.create(actor, body, "new-schedule", lambda: actor)
            assert (await schedules.create(actor, body, "new-schedule", lambda: actor))["is_replay"]
            # A recreated service reads the durable definition but has no authority until resumed.
            restored = KnowledgeSchedules(platform)
            assert (await restored.list(actor))["items"][0]["state"] == "SESSION_REQUIRED"
            restored.resume(actor, lambda: actor)
            first_tick, second_tick = await asyncio.gather(restored.tick(actor, lambda: actor), restored.tick(actor, lambda: actor))
            results = first_tick["outcomes"]+second_tick["outcomes"]
            assert len(results) == 1 and results[0]["state"] == "QUEUED"
            fake_pool(monkeypatch, [(304, {}, b"")])
            await worker.run_once(target_job_id=results[0]["job_id"])
            async with pool.acquire() as conn:
                assert await conn.fetchval("SELECT count(*) FROM knowledge_intake WHERE tenant_id=$1", repo.tenant) == 2
                assert await conn.fetchval("SELECT count(*) FROM knowledge_release WHERE tenant_id=$1", repo.tenant) == 0
                assert await conn.fetchval("SELECT count(*) FROM knowledge_intake_fetch WHERE tenant_id=$1", repo.tenant) == 2
            await restored.cancel(actor, created["id"])
            assert (await restored.list(actor))["items"][0]["state"] == "CANCELLED"
            assert not (await restored.tick(actor, lambda: actor))["outcomes"]
        finally:
            await pool.close()
    asyncio.run(run())
