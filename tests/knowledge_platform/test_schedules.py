"""Deterministic scheduler authorization/dispatch tests, no model or DB claims."""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from campus247.application.knowledge.platform import KnowledgePlatform
from campus247.application.knowledge.platform_models import PlatformError
from campus247.application.knowledge.schedules import KnowledgeSchedules, ScheduleInput, due_slot
from campus247.domain.shared.values import generate_uuid7
from campus247.ports.identity import IdentityContext, IdentityRole


def setup():
    now = datetime.now(UTC)
    actor = IdentityContext(generate_uuid7(), "synthetic-scheduler", "test", (IdentityRole.KNOWLEDGE_ADMIN,),
        "Synthetic test", now-timedelta(minutes=1), now+timedelta(hours=1), tenant_id="synthetic-only", session_id="session")
    conn = SimpleNamespace(execute=AsyncMock(), fetchval=AsyncMock(return_value=None), fetchrow=AsyncMock())
    @asynccontextmanager
    async def transaction(*args):
        yield conn
    conn.transaction = transaction
    repo = SimpleNamespace(tenant=actor.tenant_id, transaction=transaction, replay=AsyncMock(return_value=None),
        remember=AsyncMock(), audit=AsyncMock())
    platform = KnowledgePlatform(repo, SimpleNamespace(), None)
    service = KnowledgeSchedules(platform)
    service._definitions = AsyncMock(return_value=[])
    service.intake.refresh_url = AsyncMock(return_value={"job_id": generate_uuid7(), "intake_id": generate_uuid7()})
    return service, actor, conn


def body(actor, kind="URL_REFRESH", **updates):
    now = datetime.now(UTC)
    return ScheduleInput.model_validate({"kind": kind, "target_id": generate_uuid7(),
        "not_before": now-timedelta(seconds=1), "expires_at": actor.expires_at,
        "interval_seconds": 900, "confirmed": True,
        **({"expected_original_sha256": "a"*64} if kind == "URL_REFRESH" else {"expected_generation": 0}), **updates})


def definition(actor, kind="URL_REFRESH", **updates):
    value = body(actor, kind).model_dump(mode="json", exclude={"confirmed"})
    return {**value, "id": generate_uuid7(), "session_id": actor.session_id, "issuer": actor.issuer,
        "binding": {}, "publication_authority": False, **updates}


@pytest.mark.parametrize("offset,slot", [(-1, None), (0, 0), (899, 0), (900, 1), (3599, 3), (3600, None)])
def test_slots_coalesce_missed_intervals_and_use_half_open_expiry(offset, slot):
    start = datetime(2026, 10, 27, tzinfo=UTC)
    data = {"kind": "URL_REFRESH", "not_before": start.isoformat(),
        "expires_at": (start+timedelta(hours=1)).isoformat(), "interval_seconds": 900}
    assert due_slot(data, start+timedelta(seconds=offset)) == slot
    data["kind"] = "RELEASE_DUE"
    assert due_slot(data, start+timedelta(seconds=offset)) == (0 if slot is not None else None)


@pytest.mark.parametrize("updates", [
    {"confirmed": False}, {"interval_seconds": 0}, {"interval_seconds": 899},
    {"expected_original_sha256": None}, {"expected_generation": 1},
    {"not_before": "2026-10-27T00:00:00"}, {"expires_at": "2020-01-01T00:00:00Z"},
    {"service_actor": "invented"},
])
def test_invalid_or_unconfirmed_scope_rejected(updates):
    service, actor, _ = setup()
    with pytest.raises(ValidationError):
        body(actor, **updates)
    service.intake.refresh_url.assert_not_called()


def test_resume_never_mints_identity_and_rechecks_current_session():
    service, actor, _ = setup()
    assert service.resume(actor, lambda: actor)["publication_authority"] is False
    for current in (replace(actor, session_id="different"), replace(actor, tenant_id="other"),
            replace(actor, roles=(IdentityRole.SUPPORT_OFFICER,)),
            replace(actor, expires_at=datetime.now(UTC)-timedelta(seconds=1))):
        with pytest.raises(PlatformError):
            service.resume(actor, lambda: current)
    def revoked():
        raise ValueError("revoked")
    with pytest.raises(ValueError):
        asyncio.run(service.tick(actor, revoked))
    service.repo.remember.assert_not_called()
    service.intake.refresh_url.assert_not_called()


def test_creation_bound_to_session_lifetime_and_latest_source_binding():
    async def run():
        service, actor, _ = setup()
        service._binding = AsyncMock(return_value={"original_sha256": "a"*64})
        with pytest.raises(PlatformError, match="SCHEDULE_SESSION_LIMIT"):
            await service.create(actor, body(actor, expires_at=actor.expires_at+timedelta(seconds=1)), "too-long", lambda: actor)
        service._binding.assert_not_called()
        created = await service.create(actor, body(actor), "first", lambda: actor)
        assert created["session_id"] == actor.session_id and not created["publication_authority"]
        assert created["binding"] == {"original_sha256": "a"*64}
        service.repo.replay.return_value = created
        replay = await service.create(actor, body(actor), "first", lambda: actor)
        assert replay["is_replay"] and replay["id"] == created["id"]
        assert service.repo.remember.await_count == 1
    asyncio.run(run())


def test_url_dispatch_composes_existing_guarded_refresh_in_same_transaction():
    async def run():
        service, actor, conn = setup()
        data = definition(actor)
        outcome = await service._run(conn, actor, data, "slot", lambda: actor)
        assert outcome["state"] == "QUEUED"
        args, kwargs = service.intake.refresh_url.call_args
        assert args[0] is actor and args[1] == data["target_id"]
        assert args[2].expected_original_sha256 == "a"*64 and kwargs["_connection"] is conn
        service.repo.remember.assert_not_called()
    asyncio.run(run())


@pytest.mark.parametrize("state", ["QUEUED", "RUNNING", "RETRY_WAIT"])
def test_pending_job_backpressure_does_not_stack_or_reset_attempts(state):
    async def run():
        service, actor, conn = setup()
        conn.fetchval.return_value = {"job_id": "previous-job", "intake_id": "previous-intake"}
        conn.fetchrow.return_value = {"state": state}
        result = await service._run(conn, actor, definition(actor), "next-slot", lambda: actor)
        assert result == {"state": "WAITING_FOR_JOB", "job_id": "previous-job", "intake_id": "previous-intake"}
        service.intake.refresh_url.assert_not_called()
    asyncio.run(run())


def test_successful_fetch_becomes_next_validator_binding_without_changing_old_observation():
    async def run():
        service, actor, conn = setup()
        conn.fetchval.side_effect = [{"job_id": "old-job", "intake_id": "new-observation"}, "b"*64]
        conn.fetchrow.return_value = {"state": "NEEDS_INFORMATION"}
        await service._run(conn, actor, definition(actor), "slot", lambda: actor)
        args = service.intake.refresh_url.call_args.args
        assert args[1] == "new-observation" and args[2].expected_original_sha256 == "b"*64
        conn.execute.assert_not_called()
    asyncio.run(run())


def test_release_due_requires_confirmation_and_does_not_call_preview_or_confirm():
    async def run():
        service, actor, conn = setup()
        service._binding = AsyncMock(return_value={})
        service.platform._release = AsyncMock(return_value=({"_edition_state": (None, (), ())}, []))
        service.platform.preview, service.platform.confirm = AsyncMock(), AsyncMock()
        data = definition(actor, "RELEASE_DUE")
        result = await service._run(conn, actor, data, "slot", lambda: actor)
        assert result["state"] == "AWAITING_CONFIRMATION" and result["release_id"] == data["target_id"]
        service.platform.preview.assert_not_called()
        service.platform.confirm.assert_not_called()
        conn.execute.assert_not_called()
        service._binding.return_value = {"changed": True}
        with pytest.raises(PlatformError, match="SCHEDULE_BINDING_CHANGED"):
            await service._run(conn, actor, data, "slot", lambda: actor)
    asyncio.run(run())


def test_cancel_and_duplicate_slots_never_dispatch_and_blocked_outcome_is_retained():
    async def run():
        service, actor, conn = setup()
        data = definition(actor)
        service._definitions.return_value = [data]
        service._run = AsyncMock(side_effect=PlatformError(409, "SOURCE_CHANGED", "test"))
        conn.fetchval.return_value = True
        assert not (await service.tick(actor, lambda: actor))["outcomes"]
        service._run.assert_not_called()
        conn.fetchval.return_value = False
        service.repo.replay.return_value = {"state": "QUEUED"}
        assert not (await service.tick(actor, lambda: actor))["outcomes"]
        service._run.assert_not_called()
        service.repo.replay.return_value = None
        result = (await service.tick(actor, lambda: actor))["outcomes"][0]
        assert result["state"] == "BLOCKED" and result["code"] == "SOURCE_CHANGED"
        assert result["publication_authority"] is False
        service.repo.remember.assert_awaited_once()
    asyncio.run(run())


def test_list_and_cancel_preserve_definition_and_require_own_actor_scope():
    async def run():
        service, actor, conn = setup()
        data = definition(actor)
        service._definitions.return_value = [data]
        items = (await service.list(actor))["items"]
        assert items[0]["state"] == "SESSION_REQUIRED"
        service.resume(actor, lambda: actor)
        assert (await service.list(actor))["items"][0]["state"] == "ACTIVE"
        with pytest.raises(PlatformError, match="SCHEDULE_NOT_FOUND"):
            await service.cancel(actor, generate_uuid7())
        result = await service.cancel(actor, data["id"])
        assert result["state"] == "CANCELLED"
        assert service._definitions.return_value == [data]
        assert conn.execute.call_args.args[1] == actor.tenant_id+":schedule:"+data["id"]
    asyncio.run(run())


def test_background_auth_failure_discards_only_in_memory_authority():
    async def run():
        service, actor, _ = setup()
        service.resume(actor, lambda: actor)
        service.tick = AsyncMock(side_effect=ValueError("revoked"))
        task = asyncio.create_task(service.serve())
        await asyncio.sleep(0)
        assert service._sessions == {}
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        service.repo.remember.assert_not_called()
    asyncio.run(run())
