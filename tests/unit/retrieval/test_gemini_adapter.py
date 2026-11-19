"""Managed HTTP contract checks, deliberately distinct from model quality evidence."""
import asyncio
import json
from dataclasses import replace

import httpx
import pytest

from campus247.infrastructure.retrieval.gemini import GeminiEmbeddingAdapter
from campus247.ports.embedding import EmbeddingContractError, EmbeddingProfile, EmbeddingTimeoutError


def fixture(*, response=None, version="2", status=200, delay=0, **limits):
    calls, clients = [], []
    profile = EmbeddingProfile("gemini-embedding-2", "provider-version:2", 768, batch_limit=3, timeout_ms=100)
    async def handler(req):
        calls.append(req)
        if req.method == "GET":
            return httpx.Response(200, json={"name": "models/gemini-embedding-2", "version": version,
                "supportedGenerationMethods": ["embedContent"]})
        if delay:
            await asyncio.sleep(delay)
        return httpx.Response(status, json=response if response is not None else {
            "embedding": {"values": [1.0] + [0.0] * 767}})
    def factory():
        client = httpx.AsyncClient(base_url="https://generativelanguage.googleapis.com",
            transport=httpx.MockTransport(handler), follow_redirects=False, trust_env=False)
        clients.append(client)
        return client
    limits = {"max_calls": 3, "max_total_input_bytes": 8192, **limits}
    return GeminiEmbeddingAdapter(profile, factory, **limits), calls, clients


@pytest.mark.asyncio
async def test_session_reuses_connection_and_distinguishes_query_document_payload():
    adapter, calls, clients = fixture()
    async with adapter:
        await adapter.initialize()
        query = await adapter.aembed_query(" synthetic question ")
        docs = await adapter.aembed_documents(["first", "second"])
        assert len(docs.vectors) == 2 and query.dimension == 768
        assert adapter.attempted_calls == 3
    assert len(clients) == 1 and clients[0].is_closed
    bodies = [json.loads(r.content) for r in calls[1:]]
    assert [b["content"]["parts"][0]["text"] for b in bodies] == [
        "task: search result | query: synthetic question", "title: none | text: first", "title: none | text: second"]
    assert all(b["embedContentConfig"] == {"outputDimensionality": 768, "autoTruncate": False} for b in bodies)
    assert all(set(b) == {"model", "content", "embedContentConfig"} for b in bodies)
    assert query.model_revision == "provider-version:2"


@pytest.mark.asyncio
@pytest.mark.parametrize("version", [None, 2, "3", "mutable-latest"])
async def test_binding_rejection_sends_no_content(version):
    adapter, calls, clients = fixture(version=version)
    async with adapter:
        with pytest.raises(EmbeddingContractError):
            await adapter.initialize()
        with pytest.raises(EmbeddingContractError):
            await adapter.aembed_query("private synthetic text")
    assert len(calls) == 1 and clients[0].is_closed


@pytest.mark.asyncio
@pytest.mark.parametrize("row", [[], [1], [True] + [0] * 767, ["1"] + [0] * 767,
    [2] + [0] * 767, [float("nan")] + [0] * 767, [float("inf")] + [0] * 767])
async def test_output_shape_dimension_norm_finite_types(row):
    adapter, _, clients = fixture(response={"embedding": {"values": row}})
    async with adapter:
        await adapter.initialize()
        with pytest.raises(EmbeddingContractError):
            await adapter.aembed_query("synthetic")
    assert clients[0].is_closed


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [302, 429, 500])
async def test_provider_errors_no_retry_no_raw_error_body(status):
    adapter, calls, _ = fixture(status=status, response={"secret": "synthetic-secret-canary"})
    async with adapter:
        await adapter.initialize()
        with pytest.raises(EmbeddingContractError) as error:
            await adapter.aembed_query("synthetic")
        assert "synthetic-secret-canary" not in str(error.value)
        assert adapter.attempted_calls == 1
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_byte_and_call_caps_reject_before_egress():
    adapter, calls, _ = fixture(max_calls=1, max_input_bytes=80)
    async with adapter:
        await adapter.initialize()
        with pytest.raises(EmbeddingContractError):
            await adapter.aembed_query("long" * 100)
        assert adapter.attempted_calls == 0
        await adapter.aembed_query("synthetic")
        with pytest.raises(EmbeddingContractError):
            await adapter.aembed_query("second")
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_total_byte_cap_counts_prefixes():
    adapter, calls, _ = fixture(max_total_input_bytes=30)
    async with adapter:
        await adapter.initialize()
        with pytest.raises(EmbeddingContractError):
            await adapter.aembed_query("synthetic")
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_deadline_releases_lock_and_counts_failed_call():
    adapter, _, clients = fixture(delay=1)
    adapter._profile = replace(adapter.profile, timeout_ms=5)
    async with adapter:
        await adapter.initialize()
        with pytest.raises(EmbeddingTimeoutError):
            await adapter.aembed_query("synthetic")
        assert not adapter._lock.locked() and adapter.attempted_calls == 1
    assert clients[0].is_closed


@pytest.mark.asyncio
async def test_cancellation_propagates_closes_stream_and_session():
    adapter, calls, clients = fixture(delay=10)
    async def work():
        async with adapter:
            await adapter.initialize()
            await adapter.aembed_query("synthetic")
    task = asyncio.create_task(work())
    while len(calls) < 2:
        await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert clients[0].is_closed and not adapter._lock.locked()
    assert adapter.attempted_calls == 1


@pytest.mark.asyncio
async def test_response_limit_and_closed_session():
    adapter, _, clients = fixture(response={"large": "x" * (256 * 1024)})
    async with adapter:
        await adapter.initialize()
        with pytest.raises(EmbeddingContractError):
            await adapter.aembed_query("synthetic")
    with pytest.raises(EmbeddingContractError):
        await adapter.aembed_query("synthetic")
    assert clients[0].is_closed


@pytest.mark.asyncio
async def test_sync_port_rejects_api_loop_before_creating_client():
    adapter, calls, clients = fixture()
    with pytest.raises(EmbeddingContractError, match="worker context"):
        adapter.embed_query("synthetic")
    assert not clients and not calls


def test_sync_worker_closes_client_and_returns_bound_vector():
    adapter, calls, clients = fixture()
    assert adapter.embed_query("synthetic").dimension == 768
    assert clients[0].is_closed and len(calls) == 2
