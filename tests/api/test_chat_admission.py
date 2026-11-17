"""Admission control: bounded turns in flight, quick 503 when busy, slots always returned."""
from __future__ import annotations

import asyncio
import time

import httpx
import pytest
from fastapi import FastAPI

from campus247.agent.state import AgentState, DraftResponse, Route, Terminal
from campus247.application.conversation.messages import ConversationMessageService
from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
from campus247.presentation.admission import AdmissionGate
from campus247.presentation.chat import create_chat_router
from campus247.presentation.identity import IdentityMiddleware

STUDENT = "4b419a1b-6d41-7dfb-8943-2edd9f071385"


# ---- the gate itself -------------------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gate_admits_up_to_the_limit_then_rejects_after_the_wait():
    gate = AdmissionGate(2, max_wait_s=0.1)
    first, second = await gate.acquire(), await gate.acquire()
    assert first and second and gate.in_flight == 2
    started = time.monotonic()
    assert await gate.acquire() is None
    assert 0.09 <= time.monotonic() - started < 0.5
    assert (gate.rejected, gate.in_flight, gate.waiting) == (1, 2, 0)


@pytest.mark.asyncio
async def test_released_slot_goes_to_the_longest_waiter_first():
    gate = AdmissionGate(1, max_wait_s=2)
    held = await gate.acquire()
    order = []

    async def waiter(name):
        slot = await gate.acquire()
        order.append(name)
        slot.release()

    tasks = [asyncio.create_task(waiter(name)) for name in ("a", "b", "c")]
    await asyncio.sleep(0.05)
    assert gate.waiting == 3
    held.release()
    await asyncio.gather(*tasks)
    assert order == ["a", "b", "c"] and gate.in_flight == 0


@pytest.mark.asyncio
async def test_release_is_idempotent():
    gate = AdmissionGate(1, max_wait_s=0.05)
    slot = await gate.acquire()
    slot.release()
    slot.release()
    assert gate.in_flight == 0
    assert await gate.acquire() is not None and await gate.acquire() is None


@pytest.mark.asyncio
async def test_cancelled_waiter_does_not_leak_a_slot():
    gate = AdmissionGate(1, max_wait_s=5)
    held = await gate.acquire()
    waiter = asyncio.create_task(gate.acquire())
    await asyncio.sleep(0.02)
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    held.release()
    assert gate.in_flight == 0 and gate.waiting == 0
    assert await gate.acquire() is not None


@pytest.mark.asyncio
async def test_lease_frees_a_slot_that_was_never_released():
    gate = AdmissionGate(1, max_wait_s=0.05, lease_s=0.05)
    await gate.acquire()
    await asyncio.sleep(0.12)
    assert gate.in_flight == 0


@pytest.mark.parametrize("args", [(0,), (1, -1), (1, 1, 0)])
def test_gate_rejects_invalid_configuration(args):
    with pytest.raises(ValueError):
        AdmissionGate(*args)


# ---- through the route -----------------------------------------------------------------------------------------

def build(limit: int, wait_s: float, runner):
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


@pytest.mark.asyncio
async def test_busy_turn_gets_503_quickly_and_leaves_no_message_behind():
    release = asyncio.Event()

    async def blocked_runner(turn, identity):
        await release.wait()
        return answer()

    app, adapter, service, gate = build(1, 0.2, blocked_runner)
    first_conv = await service.create_conversation(owner_user_id=STUDENT)
    second_conv = await service.create_conversation(owner_user_id=STUDENT)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        running = asyncio.create_task(post(client, adapter, first_conv.id, "câu thứ nhất"))
        await asyncio.sleep(0.1)
        assert gate.in_flight == 1
        started = time.monotonic()
        busy = await post(client, adapter, second_conv.id, "câu thứ hai")
        assert time.monotonic() - started < 1.0
        assert busy.status_code == 503
        assert busy.headers["retry-after"] == "5"
        body = busy.json()
        assert body["retryable"] is True and "đang bận" in body["detail"]
        assert await service.list_messages(second_conv.id) == []  # refused before anything was saved
        release.set()
        finished = await running
    assert finished.status_code == 200 and "message.completed" in finished.text
    assert gate.in_flight == 0


@pytest.mark.asyncio
async def test_slot_is_returned_after_a_turn_and_after_a_refused_request():
    async def runner(turn, identity):
        return answer()

    app, adapter, service, gate = build(1, 0.2, runner)
    conversation = await service.create_conversation(owner_user_id=STUDENT)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for index in range(3):
            assert (await post(client, adapter, conversation.id, f"lần {index}")).status_code == 200
            assert gate.in_flight == 0
        missing = await post(client, adapter, "01923456-789a-7def-8123-456789abcdef", "không có")
        assert missing.status_code == 404 and gate.in_flight == 0


@pytest.mark.asyncio
async def test_failed_runner_still_returns_the_slot():
    async def broken(turn, identity):
        raise RuntimeError("boom")

    app, adapter, service, gate = build(1, 0.2, broken)
    conversation = await service.create_conversation(owner_user_id=STUDENT)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        reply = await post(client, adapter, conversation.id, "lỗi")
        assert "message.failed" in reply.text
    assert gate.in_flight == 0


@pytest.mark.asyncio
async def test_unauthenticated_request_never_takes_a_slot():
    async def runner(turn, identity):
        return answer()

    app, _, _, gate = build(1, 0.2, runner)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        reply = await client.post("/v1/conversations/01923456-789a-7def-8123-456789abcdef/messages:stream",
                                  json={"content": "x"})
    assert reply.status_code == 401 and gate.admitted == 0
