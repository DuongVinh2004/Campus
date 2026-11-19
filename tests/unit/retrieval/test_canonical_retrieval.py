"""Deterministic orchestration tests; tokenizer/model fakes are not acceptance."""
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
import hashlib

import pytest

from campus247.application.retrieval.canonical import CanonicalRetrievalError, CanonicalRetrievalService
from campus247.application.retrieval.profile import RuntimeRetrievalBinding, load_retrieval_profile
from campus247.domain.retrieval import AuthorizedScope, RetrievalCandidate, RetrievalContext, RetrievalQuery, SimulationPolicy
from campus247.ports.reranker import RerankResult, RerankScore, RerankerContractError, RerankerProfile


def fixture():
    profile = load_retrieval_profile()
    binding = RuntimeRetrievalBinding("synthetic-index", profile.profile_version,
        profile.embedding_model_id, profile.embedding_model_revision, 1024, "l2", "cosine", "1" * 64,
        profile.reranker_model_id, profile.reranker_model_revision, "2" * 64)
    context = RetrievalContext(AuthorizedScope("synthetic", "HUCE", "synthetic-actor",
        frozenset({"STUDENT"}), frozenset({"STUDENT"}), frozenset({"FIT"}), frozenset({"SYNTHETIC"})),
        "vi", datetime(2026, 10, 6, tzinfo=timezone.utc), SimulationPolicy.ALLOW_LABELED, "synthetic-trace")
    candidates = tuple(RetrievalCandidate("synthetic-source", "synthetic-version", f"chunk-{i}", f"synthetic text {i}",
        "Synthetic title", "Declared synthetic issuer", "synthetic://policy",
        hashlib.sha256(f"synthetic text {i}".encode()).hexdigest(), ("Same section",), simulation_label=True)
        for i in range(5))
    requests, scopes = [], []
    async def lexical(query, top_k, context):
        scopes.append(context)
        return candidates
    async def vector(query, top_k, context):
        scopes.append(context)
        return candidates[:2]
    reranker_profile = RerankerProfile(profile.reranker_model_id, profile.reranker_model_revision, 20, 700)
    class ModelFake:
        profile = reranker_profile
        async def rerank(self, request):
            requests.append(request)
            return RerankResult(tuple(RerankScore(c.chunk_id, float(i)) for i,c in enumerate(request.candidates)),
                self.profile.model_id, self.profile.model_revision, 1)
    config = dict(profile=profile, binding=binding, expected_index_version="synthetic-index",
        expected_embedding_artifact_sha256="1" * 64, expected_reranker_artifact_sha256="2" * 64,
        lexical=lexical, vector=vector, reranker=ModelFake(), token_counter=lambda text: len(text.split()),
        tokenizer_model_id=profile.embedding_model_id, tokenizer_model_revision=profile.embedding_model_revision)
    return config, context, candidates, requests, scopes


@pytest.mark.asyncio
async def test_fusion_real_port_call_context_provenance_and_section_bound():
    config, ctx, candidates, requests, scopes = fixture()
    result = await CanonicalRetrievalService(**config).retrieve(RetrievalQuery("synthetic query"), ctx)
    assert len(requests) == 1 and requests[0].context is ctx and scopes == [ctx, ctx]
    assert result.lexical_count == 5 and result.vector_count == 2 and result.fused_count == 5
    assert result.reranked_count == 5 and len(result.candidates) == 3
    assert result.token_count == 9 and result.index_version == "synthetic-index"
    assert [c.chunk_id for c in result.candidates] == ["chunk-4", "chunk-3", "chunk-2"]
    for c in result.candidates:
        original = next(o for o in candidates if o.chunk_id == c.chunk_id)
        assert c.content_text == original.content_text and c.canonical_uri == original.canonical_uri
        assert c.issuer == original.issuer and c.quote_span_hash == original.quote_span_hash


@pytest.mark.asyncio
async def test_cross_branch_content_or_provenance_drift_never_calls_reranker():
    config, ctx, candidates, requests, _ = fixture()
    async def vector(*args, **kwargs): return [replace(candidates[0], issuer="different issuer")]
    config["vector"] = vector
    with pytest.raises(CanonicalRetrievalError, match="drift"):
        await CanonicalRetrievalService(**config).retrieve(RetrievalQuery("synthetic"), ctx)
    assert not requests


@pytest.mark.asyncio
async def test_no_source_has_empty_context_and_no_model_call():
    config, ctx, _, requests, _ = fixture()
    async def empty(*args, **kwargs): return []
    config["lexical"] = config["vector"] = empty
    result = await CanonicalRetrievalService(**config).retrieve(RetrievalQuery("synthetic"), ctx)
    assert not result.candidates and result.token_count == 0 and not requests


@pytest.mark.asyncio
async def test_branch_failure_cancels_and_joins_sibling_without_degradation():
    config, ctx, _, requests, _ = fixture()
    entered, cancelled = asyncio.Event(), asyncio.Event()
    async def slow(*args, **kwargs):
        entered.set()
        try: await asyncio.sleep(10)
        finally: cancelled.set()
    async def fail(*args, **kwargs):
        await entered.wait()
        raise TimeoutError("synthetic failure")
    config["lexical"], config["vector"] = fail, slow
    with pytest.raises(TimeoutError):
        await CanonicalRetrievalService(**config).retrieve(RetrievalQuery("synthetic"), ctx)
    assert cancelled.is_set() and not requests


@pytest.mark.asyncio
async def test_partial_reranker_output_is_rejected():
    config, ctx, _, _, _ = fixture()
    model = config["reranker"]
    async def partial(request):
        return RerankResult((RerankScore(request.candidates[0].chunk_id, 1),), model.profile.model_id,
                            model.profile.model_revision, 1)
    model.rerank = partial
    with pytest.raises(RerankerContractError, match="every"):
        await CanonicalRetrievalService(**config).retrieve(RetrievalQuery("synthetic"), ctx)


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [901, True, -1, 0])
async def test_invalid_tokenizer_or_oversized_chunk_fails_closed(count):
    config, ctx, _, _, _ = fixture()
    config["token_counter"] = lambda text: count
    with pytest.raises(CanonicalRetrievalError):
        await CanonicalRetrievalService(**config).retrieve(RetrievalQuery("synthetic"), ctx)


def test_wrong_tokenizer_binding_rejects_before_branches():
    config, _, _, requests, scopes = fixture()
    config["tokenizer_model_revision"] = "different-tokenizer"
    with pytest.raises(CanonicalRetrievalError): CanonicalRetrievalService(**config)
    assert not requests and not scopes
