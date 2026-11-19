"""Concurrent provider accounting with synthetic usage and an offline transport."""
import asyncio
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from campus247.infrastructure.llm.openai_adapter import OpenAICompatibleAdapter
from campus247.ports.llm import LlmRequest
from evals.runners.paid_budget import PaidBudget
from scripts import run_public_rag as public


def request(content="Câu hỏi tổng hợp", **changes):
    return LlmRequest(request_id="offline", route_id="grounded_faq", model_profile="test",
        system_instructions="Trả lời theo nguồn.", input_items=({"role": "user", "content": content},),
        max_output_tokens=100, deadline_ms=5000, **changes)


def response(**changes):
    return {"id": "offline", "model": "deepseek-flash", "choices": [{"finish_reason": "stop",
        "message": {"role": "assistant", "content": '{"claims": []}'}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 5}, **changes}


@pytest.fixture
def stack(tmp_path, monkeypatch):
    monkeypatch.setattr(public, "STATE", tmp_path)

    class Budget(PaidBudget):
        def reserve(self, *args):
            assert gateway.lock.locked()
            return super().reserve(*args)

        def settle_verified(self, *args):
            assert gateway.lock.locked()
            return super().settle_verified(*args)

    def initialize(gateway):
        gateway.adapter = OpenAICompatibleAdapter("deepseek", "https://api.deepseek.com",
            "offline-placeholder", "deepseek-flash", disable_thinking=True)
        gateway.lock = asyncio.Lock()
        gateway.provider_slots = asyncio.Semaphore(getattr(public, "PROVIDER_CONCURRENCY_LIMIT", 4))
        gateway.budget = Budget(cap_usd="1", call_cap=100)

    monkeypatch.setattr(public.Gateway, "_initialize", initialize)
    gateway = public.Gateway()
    original_client = httpx.AsyncClient

    def transport(handler):
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(
            **kwargs, transport=httpx.MockTransport(handler)))

    def records(stage):
        return {int(path.name.split("-")[1]): json.loads(path.read_text(encoding="utf-8"))
                for path in tmp_path.glob(f"provider-*-{stage}.json")}

    yield SimpleNamespace(gateway=gateway, transport=transport, records=records, path=tmp_path)
    gateway.close()


@pytest.mark.asyncio
async def test_two_generate_calls_overlap_http(stack):
    entered, release = asyncio.Event(), asyncio.Event()
    active = maximum = 0

    async def handler(req):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        assert len(stack.records("reservation")) >= active
        if active == 2:
            entered.set()
        try:
            await release.wait()
            return httpx.Response(200, json=response())
        finally:
            active -= 1

    stack.transport(handler)
    tasks = [asyncio.create_task(stack.gateway.generate(request())) for _ in range(2)]
    try:
        await asyncio.wait_for(entered.wait(), 1)
        assert maximum == 2
    finally:
        release.set()
        await asyncio.gather(*tasks)


@pytest.mark.asyncio
async def test_provider_concurrency_is_limited_to_the_configured_cap(stack):
    limit = public.PROVIDER_CONCURRENCY_LIMIT
    full, release = asyncio.Event(), asyncio.Event()
    active = maximum = 0

    async def handler(req):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        if active == limit:
            full.set()
        try:
            await release.wait()
            return httpx.Response(200, json=response())
        finally:
            active -= 1

    stack.transport(handler)
    tasks = [asyncio.create_task(stack.gateway.generate(request())) for _ in range(limit + 7)]
    try:
        await asyncio.wait_for(full.wait(), 1)
        await asyncio.sleep(0)
        assert maximum == limit
    finally:
        release.set()
        await asyncio.gather(*tasks)
    assert maximum == limit
    # Raised from 4 on 2026-11-14 for 20 concurrent students (one turn issues two calls at once). A concurrency
    # limit only: the per-call 5 s deadline, token caps and the spend/call caps are unchanged and tested below.
    assert limit == 16


class ProviderAbort(BaseException):
    pass


@pytest.mark.asyncio
async def test_mixed_concurrent_calls_retain_exactly_one_result_and_charge(stack):
    cancel_entered, release = asyncio.Event(), asyncio.Event()
    attempts = []

    async def handler(req):
        mode = json.loads(req.content)["messages"][-1]["content"]
        attempts.append(mode)
        if mode == "cancel":
            cancel_entered.set()
            await release.wait()
        elif mode == "http_error":
            return httpx.Response(503)
        elif mode == "timeout":
            raise httpx.ReadTimeout("offline timeout")
        elif mode == "abort":
            raise ProviderAbort()
        else:
            await release.wait()
        return httpx.Response(200, json=response())

    stack.transport(handler)
    modes = ["cancel", "http_error", "timeout", "abort", "ok-a", "ok-b", "ok-c", "ok-d"]
    tasks = [asyncio.create_task(stack.gateway.generate(request(mode))) for mode in modes]
    try:
        await asyncio.wait_for(cancel_entered.wait(), 1)
        tasks[0].cancel()
    finally:
        release.set()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    assert [type(item) for item in results[:4]] == [asyncio.CancelledError,
        httpx.HTTPStatusError, httpx.ReadTimeout, ProviderAbort]
    assert len(attempts) == len(set(attempts)) == len(modes)
    reservations, records = stack.records("reservation"), stack.records("result")
    assert set(reservations) == set(records) == set(range(1, len(modes) + 1))
    assert sum(record["exit_code"] == 0 for record in records.values()) == 4
    failed = [reservations[key] for key, value in records.items() if value["exit_code"]]
    budget = stack.gateway.budget
    assert budget.reserved_input == 4 * 12 + sum(r["input_cap"] for r in failed)
    assert budget.reserved_output == 4 * 5 + sum(r["output_cap"] for r in failed)
    assert set(budget.pending) == {key for key, value in records.items() if value["exit_code"]}
    assert budget.charged == (budget.reserved_input * budget.input_price
        + budget.reserved_output * budget.output_price) / 1000000
    for ordinal, record in reservations.items():
        assert record["counted_before_HTTP"] and record["payload_logged"] is False
        assert record["snapshot"]["calls"] == ordinal
    for record in records.values():
        assert "payload" not in record and "output_text" not in record
        if not record["exit_code"]:
            assert record["raw_output_logged"] is False
            assert record["output_sha256"] == hashlib.sha256(b'{"claims": []}').hexdigest()
        else:
            assert record["retry"] is False


@pytest.mark.asyncio
async def test_cancel_while_waiting_for_provider_slot_keeps_result(stack):
    async def no_http(req):
        pytest.fail("Queued cancellation must not reach HTTP")

    stack.transport(no_http)
    for _ in range(public.PROVIDER_CONCURRENCY_LIMIT):
        await stack.gateway.provider_slots.acquire()
    task = asyncio.create_task(stack.gateway.generate(request()))
    try:
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        for _ in range(public.PROVIDER_CONCURRENCY_LIMIT):
            stack.gateway.provider_slots.release()
    assert set(stack.records("reservation")) == set(stack.records("result")) == {1}
    assert stack.records("result")[1]["error_type"] == "CancelledError"
    assert set(stack.gateway.budget.pending) == {1}


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["input", "output", "deadline"])
async def test_operation_bounds_reject_before_reservation(stack, change):
    async def no_http(req):
        pytest.fail("Invalid payload must not reach HTTP")

    stack.transport(no_http)
    value = request()
    if change == "input":
        value = replace(value, input_items=tuple({"role": "user", "content": "á" * 8000} for _ in range(2)))
    elif change == "output":
        value = replace(value, max_output_tokens=1001)
    else:
        value = replace(value, deadline_ms=5001)
    with pytest.raises(ValueError, match="provider operation bound"):
        await stack.gateway.generate(value)
    assert stack.gateway.budget.calls == 0
    assert not stack.records("reservation") and not stack.records("result")


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["usage", "reasoning", "model", "body", "deadline", "overusage"])
async def test_provider_validation_failure_retains_full_charge(stack, monkeypatch, fault):
    async def handler(req):
        raw = response()
        if fault == "usage":
            raw["usage"] = {}
        elif fault == "reasoning":
            raw["usage"]["completion_tokens_details"] = {"reasoning_tokens": 1}
        elif fault == "body":
            return httpx.Response(200, content=b"x" * 1_048_577)
        elif fault == "deadline":
            await asyncio.Event().wait()
        elif fault == "overusage":
            raw["usage"]["completion_tokens"] = 101
        return httpx.Response(200, json=raw)

    if fault == "model":
        normalize = stack.gateway.adapter._normalize_response
        monkeypatch.setattr(stack.gateway.adapter, "_normalize_response", lambda *args:
            replace(normalize(*args), model_id="unexpected"))
    stack.transport(handler)
    value = replace(request(), deadline_ms=10) if fault == "deadline" else request()
    with pytest.raises((ValueError, TimeoutError)):
        await stack.gateway.generate(value)
    assert stack.gateway.budget.snapshot() == stack.records("reservation")[1]["snapshot"]
    assert stack.records("result")[1]["exit_code"] == 1


@pytest.mark.asyncio
async def test_restart_uses_latest_settlement_when_calls_finish_out_of_order(stack, monkeypatch):
    entered, third_entered = asyncio.Event(), asyncio.Event()
    release, release_third = asyncio.Event(), asyncio.Event()

    async def handler(req):
        mode = json.loads(req.content)["messages"][-1]["content"]
        if mode == "first":
            entered.set()
            await release.wait()
        elif mode == "third":
            third_entered.set()
            await release_third.wait()
        return httpx.Response(200, json=response())

    stack.transport(handler)
    first = asyncio.create_task(stack.gateway.generate(request("first")))
    try:
        await asyncio.wait_for(entered.wait(), 1)
        second = asyncio.create_task(stack.gateway.generate(request("second")))
        third = asyncio.create_task(stack.gateway.generate(request("third")))
        try:
            await asyncio.wait_for(asyncio.shield(second), 1)
            await asyncio.wait_for(third_entered.wait(), 1)
            release.set()
            await first
        finally:
            release.set()
            release_third.set()
            await asyncio.gather(first, second, third)
    finally:
        release.set()
        await first
    expected = stack.gateway.budget.snapshot()
    # Exercise production initialization using synthetic settings and predecessor.
    old = stack.path / "infra/local/rag-fixture/manual-20261013-76/b001"
    old.mkdir(parents=True)
    (old / "predecessor.json").write_text('{"pending_reservation_records": {}}', encoding="utf-8")
    monkeypatch.setattr(public, "ROOT", stack.path)
    monkeypatch.setitem(sys.modules, "acceptance_live_20261006_18", SimpleNamespace(
        settings=lambda: ("https://api.deepseek.com", "offline-placeholder", None)))
    monkeypatch.setattr(public.Gateway, "_restore_budget", lambda self, snapshot, pending: (snapshot, pending))
    restored = object.__new__(public.Gateway)
    INITIALIZE(restored)
    assert restored.budget == (expected, {})
    assert restored.provider_slots._value == public.PROVIDER_CONCURRENCY_LIMIT


INITIALIZE = public.Gateway._initialize


@pytest.mark.asyncio
async def test_waiting_for_a_slot_does_not_spend_the_call_deadline(stack):
    """The 5 s deadline measures the provider call; time queued behind other calls must not count against it."""
    stack.transport(lambda req: httpx.Response(200, json=response()))
    for _ in range(public.PROVIDER_CONCURRENCY_LIMIT):
        await stack.gateway.provider_slots.acquire()
    short = replace(request(), deadline_ms=300)
    task = asyncio.create_task(stack.gateway.generate(short))
    await asyncio.sleep(0.6)  # longer than the call deadline, spent waiting for a slot
    assert not task.done()
    stack.gateway.provider_slots.release()
    result = await asyncio.wait_for(task, 2)
    assert result.output_text
    for _ in range(public.PROVIDER_CONCURRENCY_LIMIT - 1):
        stack.gateway.provider_slots.release()
