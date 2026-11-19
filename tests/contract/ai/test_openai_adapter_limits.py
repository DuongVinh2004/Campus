"""Verify route hard caps at the HTTP boundary without any live provider."""
from __future__ import annotations
import asyncio
import json
import sys
from pathlib import Path
import httpx
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "services/api/src"))
from campus247.infrastructure.llm import openai_adapter as module
from campus247.ports.llm import LlmRequest

def request(*, tokens=16, deadline=2000):
    return LlmRequest(request_id="test", route_id="grounded_faq", model_profile="answer_balanced",
        system_instructions="Synthetic fixture", input_items=({"role":"user","content":"OK"},),
        max_output_tokens=tokens, deadline_ms=deadline)

@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("tokens", [16, 128, 2048])
def test_http_request_preserves_output_cap_and_shorter_deadline(monkeypatch, stream, tokens):
    actual_client = httpx.AsyncClient
    captured = {}
    def respond(req):
        captured["payload"] = json.loads(req.content)
        if stream:
            return httpx.Response(200, text='data: {"choices":[{"delta":{"content":"OK"}}]}\n\ndata: [DONE]\n\n', headers={"Content-Type":"text/event-stream"})
        return httpx.Response(200, json={"choices":[{"message":{"content":"OK"},"finish_reason":"stop"}],"usage":{"completion_tokens":1}})
    def client(*, timeout):
        captured["timeout"] = timeout
        return actual_client(timeout=timeout, transport=httpx.MockTransport(respond), trust_env=False)
    monkeypatch.setattr(module.httpx, "AsyncClient", client)
    adapter = module.OpenAICompatibleAdapter("fixture", "https://provider.invalid", "synthetic-key", "fixture-model", default_timeout_sec=15)
    async def run():
        if stream: return [event async for event in adapter.stream(request(tokens=tokens))]
        return await adapter.generate(request(tokens=tokens))
    asyncio.run(run())
    assert captured["payload"]["max_tokens"] == tokens
    assert captured["timeout"] == 2.0

@pytest.mark.parametrize("stream", [False, True])
def test_shorter_provider_timeout_is_preserved(monkeypatch, stream):
    actual_client = httpx.AsyncClient
    captured = []
    def client(*, timeout):
        captured.append(timeout)
        return actual_client(timeout=timeout, transport=httpx.MockTransport(lambda req: httpx.Response(200,
            text='data: [DONE]\n\n' if stream else '{"choices":[]}', headers={"Content-Type":"text/event-stream"} if stream else {})), trust_env=False)
    monkeypatch.setattr(module.httpx, "AsyncClient", client)
    adapter = module.OpenAICompatibleAdapter("fixture", "https://provider.invalid", "synthetic-key", "fixture-model", default_timeout_sec=3)
    async def run():
        if stream: return [event async for event in adapter.stream(request(deadline=20000))]
        return await adapter.generate(request(deadline=20000))
    asyncio.run(run())
    assert captured == [3.0]

@pytest.mark.parametrize("stream", [False, True])
def test_total_deadline_cancels_slow_provider_and_closes_client(monkeypatch, stream):
    actual_client = httpx.AsyncClient
    clients = []
    cancelled = []
    async def respond(req):
        try: await asyncio.sleep(1)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise
        return httpx.Response(200, json={"choices":[]})
    def client(*, timeout):
        instance = actual_client(timeout=timeout, transport=httpx.MockTransport(respond), trust_env=False)
        clients.append(instance)
        return instance
    monkeypatch.setattr(module.httpx, "AsyncClient", client)
    adapter = module.OpenAICompatibleAdapter("fixture", "https://provider.invalid", "synthetic-key", "fixture-model", default_timeout_sec=15)
    async def run():
        if stream: return [event async for event in adapter.stream(request(deadline=20))]
        return await adapter.generate(request(deadline=20))
    with pytest.raises(TimeoutError): asyncio.run(run())
    assert cancelled == [True]
    assert len(clients) == 1 and clients[0].is_closed


@pytest.mark.parametrize("reasoning", [None, 0, 4, 16])
def test_reported_reasoning_usage_is_preserved_without_double_counting(reasoning):
    adapter = module.OpenAICompatibleAdapter("fixture", "https://provider.invalid", "synthetic-key", "fixture-model")
    usage = {"prompt_tokens": 47, "completion_tokens": 16,
             "prompt_tokens_details": {"cached_tokens": 8}}
    if reasoning is not None:
        usage["completion_tokens_details"] = {"reasoning_tokens": reasoning}
    response = adapter._normalize_response({
        "choices": [{"message": {"content": ""}, "finish_reason": "length"}],
        "usage": usage,
    })
    assert response.usage.reasoning_tokens == (reasoning if reasoning is not None else 0)
    assert response.usage.input_tokens == 47
    assert response.usage.cached_input_tokens == 8
    assert response.usage.output_tokens == 16
    assert response.usage.total_tokens == 63
    assert response.finish_reason.value == "length"
