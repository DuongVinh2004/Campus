"""Gateway sidecar and its API-side client: one owner of the paid provider, nothing reachable without it.

The sidecar is exercised with a counting stand-in for the retained Gateway; no provider call is ever made.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import gateway_sidecar as sidecar  # noqa: E402
from campus247.infrastructure.llm.gateway_wire import (  # noqa: E402
    WireError, request_from_json, request_to_json, response_from_json, response_to_json)
from campus247.infrastructure.llm.remote_gateway import (  # noqa: E402
    GatewayCallFailed, GatewayRefused, GatewayUnavailable, RemoteGateway, read_token)
from campus247.ports.llm import (  # noqa: E402
    FinishReason, LlmRequest, LlmResponse, LlmResponseStatus, ModelCapabilities, PrivacyClass, TokenUsage)

TOKEN = "t" * 64


def make_request(**overrides):
    values = dict(request_id="r1", route_id="grounded", model_profile="fast", system_instructions="sys",
                  input_items=({"role": "user", "content": "xin chào"},), max_output_tokens=300, deadline_ms=4000)
    values.update(overrides)
    return LlmRequest(**values)


class CountingGateway:
    def __init__(self, behaviour=None):
        self.calls, self.behaviour = [], behaviour

    async def generate(self, request):
        self.calls.append(request)
        if self.behaviour:
            raise self.behaviour
        return LlmResponse(LlmResponseStatus.COMPLETED, "deepseek", "deepseek-flash", output_text="ok",
                           usage=TokenUsage(input_tokens=11, output_tokens=5), latency_ms=321)

    def capabilities(self, provider_id, model_id):
        return ModelCapabilities("deepseek", "deepseek-flash")


def client_for(gateway, cap=None, token=TOKEN):
    app = sidecar.create_sidecar_app(gateway, token, cap)
    http = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8025",
                             headers={"X-Gateway-Token": token})
    return RemoteGateway("http://127.0.0.1:8025", token, client=http), app, http


# ---- wire --------------------------------------------------------------------------------------------------

def test_request_and_response_survive_the_wire():
    request = make_request(privacy_class=PrivacyClass.INTERNAL, temperature=0.2, tool_choice="auto",
                           output_schema={"type": "object"}, trace_context={"a": 1})
    assert request_from_json(json.loads(json.dumps(request_to_json(request)))) == request
    response = LlmResponse(LlmResponseStatus.INCOMPLETE, "p", "m", output_text="x", finish_reason=FinishReason.LENGTH,
                           usage=TokenUsage(1, 2, 3, 0), latency_ms=9, attempt=2)
    assert response_from_json(json.loads(json.dumps(response_to_json(response)))) == response


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(max_output_tokens="300"), lambda d: d.update(max_output_tokens=True),
    lambda d: d.update(max_output_tokens=0), lambda d: d.update(deadline_ms=-1), lambda d: d.update(extra=1),
    lambda d: d.update(privacy_class="secret"), lambda d: d.pop("request_id"), lambda d: d.update(input_items="x"),
    lambda d: d.update(input_items=["x"]), lambda d: d.update(temperature="hot"),
])
def test_wire_rejects_malformed_requests(mutate):
    data = request_to_json(make_request())
    mutate(data)
    with pytest.raises(WireError):
        request_from_json(data)


# ---- sidecar through the client ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_one_call_reaches_the_gateway_exactly_once():
    gateway = CountingGateway()
    remote, app, http = client_for(gateway)
    response = await remote.generate(make_request())
    assert response.output_text == "ok" and response.usage.input_tokens == 11
    assert len(gateway.calls) == 1 and gateway.calls[0] == make_request()
    assert app.state.counters["ok"] == 1
    await remote.aclose()


@pytest.mark.asyncio
async def test_wrong_or_missing_token_never_reaches_the_gateway():
    gateway = CountingGateway()
    app = sidecar.create_sidecar_app(gateway, TOKEN)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://x") as http:
        body = request_to_json(make_request())
        assert (await http.post("/v1/generate", json=body)).status_code == 401
        assert (await http.post("/v1/generate", json=body, headers={"X-Gateway-Token": "x" * 64})).status_code == 401
        assert (await http.get("/v1/capabilities")).status_code == 401
    assert gateway.calls == []


@pytest.mark.asyncio
async def test_invalid_and_oversized_bodies_are_refused_before_the_gateway():
    gateway = CountingGateway()
    app = sidecar.create_sidecar_app(gateway, TOKEN)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://x",
                                 headers={"X-Gateway-Token": TOKEN}) as http:
        assert (await http.post("/v1/generate", content=b"not json")).status_code == 400
        assert (await http.post("/v1/generate", json={"request_id": "r"})).status_code == 400
        assert (await http.post("/v1/generate", content=b"x" * 300_000)).status_code == 413
    assert gateway.calls == []


@pytest.mark.asyncio
async def test_operation_bound_is_a_refusal_and_provider_failure_carries_only_the_type():
    remote, _, _ = client_for(CountingGateway(ValueError("provider operation bound")))
    with pytest.raises(GatewayRefused):
        await remote.generate(make_request())
    remote, app, _ = client_for(CountingGateway(TimeoutError("secret detail about the prompt")))
    with pytest.raises(GatewayCallFailed) as raised:
        await remote.generate(make_request())
    assert raised.value.error_type == "TimeoutError" and "secret" not in str(raised.value)
    assert app.state.counters["failed"] == 1


@pytest.mark.asyncio
async def test_capabilities_come_from_the_sidecar():
    remote, _, _ = client_for(CountingGateway())
    http = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(
        200, json={key: getattr(ModelCapabilities("deepseek", "deepseek-flash"), key)
                   for key in ModelCapabilities.__dataclass_fields__})))
    # capabilities() is synchronous; point it at a stub transport through a monkeypatched httpx.get
    original = httpx.get
    httpx.get = lambda url, **kw: http.get(url, headers=kw.get("headers"))
    try:
        assert remote.capabilities("deepseek", "deepseek-flash").model_id == "deepseek-flash"
    finally:
        httpx.get = original


# ---- daily cap ---------------------------------------------------------------------------------------------

class Budget:
    def __init__(self):
        self.usd, self.calls = Decimal("65.97"), 100_000

    def snapshot(self):
        return {"conservative_charged_usd": str(self.usd), "calls": self.calls}

    def spend(self, usd, calls=1):
        self.usd += Decimal(usd)
        self.calls += calls


def test_daily_cap_counts_the_days_change_and_refuses_at_the_cap(tmp_path):
    budget, clock = Budget(), [datetime(2026, 11, 15, 10, 0, tzinfo=sidecar.ICT)]
    cap = sidecar.DailySpendCap(tmp_path / "cap.json", budget.snapshot, usd_cap=Decimal("1.00"), call_cap=0, now=lambda: clock[0])
    cap.check()                                   # the day starts here: past spend does not count
    budget.spend("0.60"); cap.check()
    budget.spend("0.40")
    with pytest.raises(sidecar.CapReached):
        cap.check()
    clock[0] += timedelta(days=1)                 # a new day resets the baseline
    cap.check()
    assert cap.today() == (Decimal("0"), 0)


def test_call_cap_and_off_switch(tmp_path):
    budget = Budget()
    cap = sidecar.DailySpendCap(tmp_path / "c.json", budget.snapshot, usd_cap=Decimal("0"), call_cap=3)
    cap.check()
    budget.spend("0", calls=3)
    with pytest.raises(sidecar.CapReached):
        cap.check()
    off = sidecar.DailySpendCap(tmp_path / "o.json", budget.snapshot, usd_cap=Decimal("0"), call_cap=0)
    budget.spend("999", calls=10_000)
    off.check()                                   # 0 and 0 mean no daily cap


@pytest.mark.asyncio
async def test_a_reached_cap_refuses_before_any_provider_call(tmp_path):
    budget, gateway = Budget(), CountingGateway()
    cap = sidecar.DailySpendCap(tmp_path / "cap.json", budget.snapshot, usd_cap=Decimal("0"), call_cap=1)
    remote, app, _ = client_for(gateway, cap)
    await remote.generate(make_request())
    budget.spend("0.01")                          # the retained budget records the first call
    with pytest.raises(GatewayRefused):
        await remote.generate(make_request())
    assert len(gateway.calls) == 1 and app.state.counters["refused"] == 1


# ---- sidecar down / misuse ---------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sidecar_down_is_a_clear_error_and_there_is_no_other_route_to_the_provider():
    remote = RemoteGateway("http://127.0.0.1:9", TOKEN)   # nothing listens on port 9
    with pytest.raises(GatewayUnavailable, match="unavailable"):
        await remote.generate(make_request())
    import inspect
    source = inspect.getsource(sys.modules[RemoteGateway.__module__])
    assert "api.deepseek" not in source and "chat/completions" not in source and "Authorization" not in source


@pytest.mark.parametrize("url", ["http://example.com:8025", "https://127.0.0.1:8025", "http://10.0.0.5:8025", "http://localhost:8025"])
def test_client_only_talks_to_loopback(url):
    with pytest.raises(ValueError):
        RemoteGateway(url, TOKEN)


def test_short_tokens_are_rejected(tmp_path):
    with pytest.raises(ValueError):
        RemoteGateway("http://127.0.0.1:8025", "short")
    (tmp_path / "t").write_text("abc", encoding="ascii")
    with pytest.raises(ValueError):
        read_token(tmp_path / "t")
    sidecar_token = sidecar.load_or_create_token(tmp_path / "gw.token")
    assert len(sidecar_token) == 64 and sidecar.load_or_create_token(tmp_path / "gw.token") == sidecar_token
