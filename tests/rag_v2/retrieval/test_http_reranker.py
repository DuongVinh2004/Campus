import asyncio
import json

import httpx
import pytest
from campus247.rag_v2.adapters.http_reranker import HTTPReranker


def adapter(handler, **kwargs):
    return HTTPReranker(client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)), **kwargs)


@pytest.mark.asyncio
async def test_tei_protocol_and_sorted_response_reassembled_in_input_order():
    requests = []
    def handler(request):
        requests.append(request)
        assert request.url.host == "127.0.0.1" and request.url.port == 18082
        if request.url.path == "/info":
            return httpx.Response(200, json={"model_type": {"reranker": {}}})
        payload = json.loads(request.content)
        assert payload == {"query": "question", "texts": ["one", "two", "three"], "raw_scores": True,
                           "return_text": False, "truncate": False}
        return httpx.Response(200, json=[{"index": 2, "score": 3}, {"index": 0, "score": -2}, {"index": 1, "score": 1}])
    assert await adapter(handler).rerank("question", ["one", "two", "three"], deadline_s=1) == [-2, 1, 3]
    assert len(requests) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("capability, expected_max", [(1, 1), (2, 2)])
async def test_parallel_batches_only_when_server_allows(capability, expected_max):
    active, maximum = 0, 0
    async def handler(request):
        nonlocal active, maximum
        if request.url.path == "/info":
            return httpx.Response(200, json={"max_concurrent_requests": capability, "max_client_batch_size": 2})
        active += 1
        maximum = max(maximum, active)
        payload = json.loads(request.content)
        assert len(payload["texts"]) <= 2
        try:
            await asyncio.sleep(0.005)
            return httpx.Response(200, json=[{"index": i, "score": int(text)} for i, text in enumerate(payload["texts"])])
        finally:
            active -= 1
    scores = await adapter(handler, batch_size=12, concurrency=2).rerank("q", list(map(str, range(6))), deadline_s=1)
    assert scores == list(range(6)) and maximum == expected_max and active == 0


@pytest.mark.asyncio
async def test_deadline_includes_capability_request():
    async def handler(request):
        await asyncio.sleep(5)
        return httpx.Response(200, json={})
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(adapter(handler).rerank("q", ["text"], deadline_s=0.01), timeout=0.5)


@pytest.mark.asyncio
async def test_http_timeout_converted_to_builtin_timeout():
    def handler(request):
        raise httpx.ReadTimeout("do not expose", request=request)
    with pytest.raises(TimeoutError, match="deadline"):
        await adapter(handler).rerank("q", ["text"], deadline_s=1)


@pytest.mark.asyncio
@pytest.mark.parametrize("rows", [
    [], [{"index": 0, "score": 1}, {"index": 0, "score": 2}],
    [{"index": 0, "score": 1}, {"index": 2, "score": 1}],
    [{"index": 0, "score": True}, {"index": 1, "score": 2}],
    [{"index": 0, "score": "1"}, {"index": 1, "score": 2}],
    [{"index": False, "score": 1}, {"index": 1, "score": 2}],
    [{"index": 0, "score": 1, "text": "unexpected"}, {"index": 1, "score": 2}],
])
async def test_invalid_scores_indices_or_count_rejected(rows):
    def handler(request):
        return httpx.Response(200, json={} if request.url.path == "/info" else rows)
    with pytest.raises(ValueError):
        await adapter(handler).rerank("q", ["one", "two"], deadline_s=1)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [302, 500, 429])
async def test_http_errors_and_redirects_rejected(status):
    def handler(request):
        return httpx.Response(status, headers={"Location": "https://example.com"})
    with pytest.raises(ValueError, match="non-success"):
        await adapter(handler).rerank("q", ["text"], deadline_s=1)


@pytest.mark.asyncio
async def test_sibling_batches_cancelled_after_failure():
    active = 0
    async def handler(request):
        nonlocal active
        if request.url.path == "/info":
            return httpx.Response(200, json={"max_concurrent_requests": 2})
        active += 1
        try:
            payload = json.loads(request.content)
            if payload["texts"] == ["fail"]:
                await asyncio.sleep(0)
                return httpx.Response(500)
            await asyncio.sleep(5)
            return httpx.Response(200, json=[{"index": 0, "score": 1}])
        finally:
            active -= 1
    with pytest.raises(ValueError):
        await adapter(handler, batch_size=1, concurrency=2).rerank("q", ["fail", "wait"], deadline_s=1)
    assert active == 0


@pytest.mark.asyncio
async def test_empty_input_does_not_open_http_client():
    def handler(request):
        pytest.fail("unexpected HTTP request")
    assert await adapter(handler).rerank("q", [], deadline_s=0) == []
