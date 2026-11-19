"""HTTP-boundary fakes; these tests do not certify model inference or clearance."""
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
import json

import httpx
import pytest

from campus247.domain.retrieval import (
    AuthorizedScope, RetrievalCandidate, RetrievalContext, RetrievalQuery, SimulationPolicy,
)
from campus247.infrastructure.retrieval.tei import TEIEmbeddingAdapter, TEIRerankerAdapter
from campus247.ports.embedding import EmbeddingContractError, EmbeddingProfile, EmbeddingTimeoutError
from campus247.ports.reranker import RerankRequest, RerankerContractError, RerankerProfile, RerankerTimeoutError


def embedding_profile():
    # Small vector fixture is deliberate; production dimensions remain unchanged.
    return EmbeddingProfile("BAAI/bge-m3", "5617a9f61b028005a4858fdac845db406aefb181", 2, timeout_ms=100)


def request():
    profile = RerankerProfile("BAAI/bge-reranker-v2-m3", "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e", 20, 100)
    context = RetrievalContext(AuthorizedScope("SYN", "SYN", "synthetic-actor", frozenset({"STUDENT"}),
        frozenset({"STUDENT"}), frozenset({"FIT"}), frozenset({"SYN"})), "vi",
        datetime(2026, 10, 5, tzinfo=timezone.utc), SimulationPolicy.ALLOW_LABELED, "synthetic-trace")
    candidates = tuple(RetrievalCandidate("source", "version", f"chunk-{i}", f"synthetic text {i}",
        "Synthetic", "Synthetic", "synthetic://policy", "a" * 64, ("Section 1",)) for i in range(2))
    return RerankRequest(profile, RetrievalQuery("synthetic query"), context, candidates)


def factory(profile, kind, result, *, info_update=None, delay=0, status=200):
    calls, clients = [], []
    info = {"model_id": profile.model_id, "model_sha": profile.model_revision,
            "model_type": {kind: {}}, "auto_truncate": False}
    info.update(info_update or {})
    async def handler(req):
        calls.append(req)
        if delay: await asyncio.sleep(delay)
        return httpx.Response(status, json=info if req.url.path == "/info" else result)
    def create():
        client = httpx.AsyncClient(base_url="https://synthetic-runtime.invalid",
            transport=httpx.MockTransport(handler), trust_env=False, follow_redirects=False)
        clients.append(client)
        return client
    return create, calls, clients


def test_embedding_http_payload_identity_order_and_client_cleanup():
    p = embedding_profile()
    make, calls, clients = factory(p, "embedding", [[1, 0], [0, 1]])
    batch = TEIEmbeddingAdapter(p, make).embed_documents([" first ", "second"])
    assert [v.values for v in batch.vectors] == [(1.0, 0.0), (0.0, 1.0)]
    assert batch.model_revision == p.model_revision
    assert [r.url.path for r in calls] == ["/info", "/embed"]
    assert json.loads(calls[1].content) == {"inputs": ["first", "second"], "normalize": True, "truncate": False}
    assert clients[0].is_closed


@pytest.mark.parametrize("update", [{"model_id": "other"}, {"model_sha": None},
    {"model_sha": "mutable-main"}, {"model_type": {"reranker": {}}}, {"auto_truncate": True}])
def test_embedding_identity_failure_sends_no_input(update):
    p = embedding_profile()
    make, calls, clients = factory(p, "embedding", [[1, 0]], info_update=update)
    with pytest.raises(EmbeddingContractError, match="response rejected"):
        TEIEmbeddingAdapter(p, make).embed_query("sensitive-synthetic-query")
    assert len(calls) == 1 and "sensitive-synthetic" not in str(calls[0].content)
    assert clients[0].is_closed


@pytest.mark.parametrize("rows", [[], [[1, 0], [0, 1]], [[1]], [[2, 0]],
    [[True, 0]], [["1", 0]], [[float("nan"), 0]], [[float("inf"), 0]]])
def test_embedding_invalid_count_dimension_normalization_and_number(rows):
    p = embedding_profile()
    make, _, clients = factory(p, "embedding", rows)
    with pytest.raises(EmbeddingContractError): TEIEmbeddingAdapter(p, make).embed_query("synthetic")
    assert clients[0].is_closed


def test_embedding_rejects_empty_input_before_client_creation():
    p = embedding_profile()
    make, calls, clients = factory(p, "embedding", [])
    with pytest.raises(EmbeddingContractError): TEIEmbeddingAdapter(p, make).embed_documents([" "])
    assert not calls and not clients


def test_embedding_total_deadline_cancels_and_closes_client():
    p = replace(embedding_profile(), timeout_ms=5)
    make, _, clients = factory(p, "embedding", [[1, 0]], delay=1)
    with pytest.raises(EmbeddingTimeoutError): TEIEmbeddingAdapter(p, make).embed_query("synthetic")
    assert clients[0].is_closed


@pytest.mark.asyncio
async def test_sync_embedding_does_not_nest_loops_or_spawn_threads():
    p = embedding_profile()
    make, calls, clients = factory(p, "embedding", [[1, 0]])
    with pytest.raises(EmbeddingContractError, match="worker context"):
        TEIEmbeddingAdapter(p, make).embed_query("synthetic")
    assert not calls and not clients


@pytest.mark.asyncio
async def test_reranker_preserves_order_ids_text_provenance_and_context():
    req = request()
    make, calls, clients = factory(req.profile, "reranker", [{"index": 1, "score": 2.5}, {"index": 0, "score": -1}])
    original = req.candidates
    result = await TEIRerankerAdapter(req.profile, make).rerank(req)
    assert [r.chunk_id for r in result.ranked] == ["chunk-1", "chunk-0"]
    assert req.candidates is original and req.context.trace_id == "synthetic-trace"
    assert json.loads(calls[1].content) == {"query": "synthetic query", "texts": [c.content_text for c in original],
        "raw_scores": True, "return_text": False, "truncate": False}
    assert clients[0].is_closed


@pytest.mark.asyncio
@pytest.mark.parametrize("rows", [[], [{"index": 0, "score": 1}],
    [{"index": 0, "score": 1}, {"index": 0, "score": 2}],
    [{"index": 0, "score": 1}, {"index": 2, "score": 2}],
    [{"index": 0, "score": 1}, {"index": True, "score": 2}],
    [{"index": 0, "score": 1}, {"index": 1, "score": "2"}],
    [{"index": 0, "score": 1}, {"index": 1, "score": float("inf")}],
    [{"index": 0, "score": 1}, {"index": 1, "score": 2, "text": "replacement"}]])
async def test_reranker_rejects_missing_duplicate_foreign_ids_and_invalid_scores(rows):
    req = request()
    make, _, clients = factory(req.profile, "reranker", rows)
    with pytest.raises(RerankerContractError): await TEIRerankerAdapter(req.profile, make).rerank(req)
    assert clients[0].is_closed


@pytest.mark.asyncio
async def test_reranker_profile_mismatch_and_empty_input_do_not_call_runtime():
    req = request()
    make, calls, clients = factory(req.profile, "reranker", [])
    adapter = TEIRerankerAdapter(req.profile, make)
    with pytest.raises(RerankerContractError): await adapter.rerank(replace(req, profile=replace(req.profile, model_revision="other")))
    assert (await adapter.rerank(replace(req, candidates=()))).ranked == ()
    assert not calls and not clients


@pytest.mark.asyncio
async def test_reranker_model_identity_rejected_before_query_or_candidate_egress():
    req = request()
    make, calls, clients = factory(req.profile, "reranker", [], info_update={"model_sha": None})
    with pytest.raises(RerankerContractError): await TEIRerankerAdapter(req.profile, make).rerank(req)
    assert len(calls) == 1 and not calls[0].content
    assert clients[0].is_closed


@pytest.mark.asyncio
async def test_reranker_total_deadline_cancels_and_closes_client():
    req = replace(request(), profile=replace(request().profile, timeout_ms=5))
    make, _, clients = factory(req.profile, "reranker", [], delay=1)
    with pytest.raises(RerankerTimeoutError): await TEIRerankerAdapter(req.profile, make).rerank(req)
    assert clients[0].is_closed


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [302, 429, 500, 503])
async def test_redirect_and_provider_error_do_not_follow_or_retry(status):
    req = request()
    make, calls, clients = factory(req.profile, "reranker", [], status=status)
    with pytest.raises(RerankerContractError): await TEIRerankerAdapter(req.profile, make).rerank(req)
    assert len(calls) == 1 and clients[0].is_closed
