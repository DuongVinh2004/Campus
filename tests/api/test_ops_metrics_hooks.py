"""The chat route, the rate limiter and the loop watchdog feed the operational metrics, and only with counts."""
from __future__ import annotations

import asyncio
import json
import time

import httpx
import pytest
from fastapi import FastAPI

from campus247.agent.state import AgentState, DraftResponse, Route, Terminal
from campus247.application.conversation.messages import ConversationMessageService
from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
from campus247.infrastructure.loop_watchdog import LoopWatchdog
from campus247.observability import ops_metrics
from campus247.observability.ops_metrics import OpsMetrics, route_group
from campus247.presentation import chat as chat_module
from campus247.presentation.admission import AdmissionGate
from campus247.presentation.chat import create_chat_router
from campus247.presentation.identity import IdentityMiddleware

STUDENT = "4b419a1b-6d41-7dfb-8943-2edd9f071385"
SECRET_QUESTION = "điểm của sinh viên 20215678 là bao nhiêu"


@pytest.fixture
def ops(monkeypatch):
    fresh = OpsMetrics()
    monkeypatch.setattr(chat_module, "OPS", fresh)
    monkeypatch.setattr("campus247.presentation.middleware.abuse_limits.OPS", fresh)
    monkeypatch.setattr("campus247.infrastructure.loop_watchdog.OPS", fresh)
    return fresh


def build(limit, wait_s, runner):
    app = FastAPI()
    adapter = SyntheticIdentityAdapter(secret_key="secret-test-key-247")
    app.add_middleware(IdentityMiddleware, adapter=adapter)
    service = ConversationMessageService()
    gate = AdmissionGate(limit, wait_s)
    app.include_router(create_chat_router(service, trusted_agent_runner=runner, admission=gate))
    return app, adapter, service, gate


def answer(text="Xin chào."):
    return AgentState(None, route=Route.PERSONAL_SCHEDULE, terminal=Terminal.ANSWERED, draft=DraftResponse(text))


async def post(client, adapter, conversation_id, content):
    token = adapter.mint_token(STUDENT)
    return await client.post(f"/v1/conversations/{conversation_id}/messages:stream",
                             headers={"Authorization": f"Bearer {token}"}, json={"content": content})


def only_minute(metrics):
    minutes = metrics.snapshot()["minutes"]
    assert len(minutes) == 1
    return minutes[0]


@pytest.mark.asyncio
async def test_a_completed_turn_is_counted_with_timings_and_no_text(ops):
    async def runner(turn, identity):
        return answer()

    app, adapter, service, gate = build(2, 0.2, runner)
    conversation = await service.create_conversation(owner_user_id=STUDENT)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        reply = await post(client, adapter, conversation.id, SECRET_QUESTION)
    assert reply.status_code == 200 and "message.completed" in reply.text
    minute = only_minute(ops)
    assert minute["turns"] == 1 and minute["ok"] + minute["abstained"] == 1 and not minute["errors"]
    assert sum(minute["total"]) == 1 and sum(minute["first_token"]) == 1
    assert "20215678" not in json.dumps(ops.snapshot())
    assert ops.gauges == {"in_flight": 0, "waiting": 0, "limit": 2}


@pytest.mark.asyncio
async def test_a_failed_turn_is_counted_as_an_error(ops):
    async def broken(turn, identity):
        raise RuntimeError("boom")

    app, adapter, service, _ = build(1, 0.2, broken)
    conversation = await service.create_conversation(owner_user_id=STUDENT)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        reply = await post(client, adapter, conversation.id, "lỗi")
    assert "message.failed" in reply.text
    minute = only_minute(ops)
    assert minute["turns"] == 1 and sum(minute["errors"].values()) == 1 and minute["ok"] == 0
    assert "boom" not in json.dumps(ops.snapshot())


@pytest.mark.asyncio
async def test_a_busy_refusal_is_counted_and_not_as_a_turn(ops):
    release = asyncio.Event()

    async def blocked(turn, identity):
        await release.wait()
        return answer()

    app, adapter, service, gate = build(1, 0.1, blocked)
    first = await service.create_conversation(owner_user_id=STUDENT)
    second = await service.create_conversation(owner_user_id=STUDENT)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        running = asyncio.create_task(post(client, adapter, first.id, "một"))
        await asyncio.sleep(0.1)
        assert ops.gauges["in_flight"] == 1
        assert (await post(client, adapter, second.id, "hai")).status_code == 503
        release.set()
        await running
    minute = only_minute(ops)
    assert minute["admission_rejected"] == 1 and minute["turns"] == 1


@pytest.mark.asyncio
async def test_a_client_that_leaves_before_the_end_is_not_counted_as_a_failure(ops):
    async def runner(turn, identity):
        return answer()

    app, adapter, service, gate = build(1, 0.2, runner)
    conversation = await service.create_conversation(owner_user_id=STUDENT)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        token = adapter.mint_token(STUDENT)
        async with client.stream("POST", f"/v1/conversations/{conversation.id}/messages:stream",
                                 headers={"Authorization": f"Bearer {token}"}, json={"content": "x"}) as response:
            async for _ in response.aiter_text():
                break  # read the first chunk only, then close the stream
    await asyncio.sleep(0.05)
    assert gate.in_flight == 0
    assert sum(m["errors"].get("OTHER", 0) for m in ops.snapshot()["minutes"]) == 0


def test_the_loop_watchdog_reports_a_finished_block(ops):
    async def scenario():
        loop = asyncio.get_running_loop()
        watchdog = LoopWatchdog(loop, threshold_s=0.2, beat_s=0.05, name="test").start()
        try:
            await asyncio.sleep(0.2)
            time.sleep(0.9)  # block the loop on purpose
            await asyncio.sleep(0.6)
        finally:
            watchdog.stop()

    asyncio.run(scenario())
    minute = only_minute(ops)
    assert minute["loop_blocked"] >= 1 and minute["loop_blocked_max_ms"] >= 500


def test_a_rate_limited_request_is_counted_by_route_group(ops):
    from campus247.presentation.middleware.abuse_limits import (
        AbuseLimiterMiddleware,
        InMemoryRateLimiterStore,
        RateLimitRule,
    )
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.add_middleware(AbuseLimiterMiddleware, store=InMemoryRateLimiterStore(),
                       rules=[RateLimitRule(path_prefix="/v1/auth", max_requests=1, window_seconds=60)])

    @app.get("/v1/auth/ping")
    def ping():
        return {"ok": True}

    with TestClient(app) as client:
        assert client.get("/v1/auth/ping").status_code == 200
        assert client.get("/v1/auth/ping").status_code == 429
        assert client.get("/v1/auth/ping").status_code == 429
    assert only_minute(ops)["rate_limited"] == {"auth": 2}


@pytest.mark.parametrize(("prefix", "group"), [
    ("/v1/conversations", "chat"), ("/v1/assistant/conversations", "chat"), ("/v1/auth", "auth"),
    ("/v1/knowledge/platform/session", "auth"), ("/v1/knowledge-operations", "knowledge"),
    ("/v1/knowledge", "knowledge"), ("/v1/learning", "learning"), ("/health", "other"),
])
def test_route_groups(prefix, group):
    assert route_group(prefix) == group


def test_the_process_wide_instance_is_the_one_the_modules_use():
    assert chat_module.OPS is ops_metrics.OPS
