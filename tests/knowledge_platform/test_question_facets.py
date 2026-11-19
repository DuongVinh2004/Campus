import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from campus247.application.retrieval.question_facets import best_facet, question_facets, rerank_facets
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, RetrievalQuery, SimulationPolicy
from campus247.ports.reranker import RerankRequest, RerankResult, RerankScore, RerankerProfile, RerankerContractError


def test_only_independent_interrogative_clauses_split_without_added_facts():
    query = "Hồ sơ cần gửi ở đâu và thời hạn là khi nào?"
    assert question_facets(query) == ("Hồ sơ cần gửi ở đâu", "thời hạn là khi nào?")
    for value in ("Điều kiện và ngoại lệ là gì?", "Theo QĐ 17 và Quy chế 23, nộp ở đâu?", "Tôi cần nơi và thời gian nộp."):
        assert question_facets(value) == (value,)
    facets = ("Số trang có bao nhiêu?", "Mã văn bản là gì?")
    assert best_facet("Mã văn bản TEST-17", facets) == facets[1]


def request():
    from campus247.domain.retrieval import RetrievalCandidate
    from campus247.application.knowledge.platform_models import digest
    def candidate(identifier, text):
        return RetrievalCandidate("synthetic-source", "synthetic-version", identifier, text,
            "Synthetic fixture", "Synthetic", "urn:test:facets", "sha256:"+digest(text.encode()), ("Synthetic section",))
    profile = RerankerProfile("test-model", "exact-revision", 3, 1000)
    context = RetrievalContext(AuthorizedScope("tenant", "HUCE", "actor", frozenset({"STUDENT"}),
        frozenset({"STUDENT"}), frozenset({"FIT"}), frozenset({"PUBLIC"})), "vi", datetime.now(UTC), SimulationPolicy.DENY, "test")
    return RerankRequest(profile, RetrievalQuery("Nộp ở đâu và thời hạn là khi nào?"), context,
        (candidate("place", "Địa điểm nộp ở đâu: văn phòng."), candidate("time", "Thời hạn: khi nào cần nộp.")))


def test_each_candidate_is_scored_once_with_same_context_and_exact_model():
    async def run():
        original = request()
        calls = []
        async def rank(partial):
            calls.append(partial)
            return RerankResult(tuple(RerankScore(c.chunk_id, 1.0) for c in partial.candidates),
                partial.profile.model_id, partial.profile.model_revision, 1)
        result = await rerank_facets(SimpleNamespace(rerank=rank), original, question_facets(original.query.text))
        assert {row.chunk_id for row in result.ranked} == {row.chunk_id for row in original.candidates}
        assert sum(len(call.candidates) for call in calls) == len(original.candidates)
        assert len(calls) == 2
        assert all(call.context is original.context and call.profile is original.profile for call in calls)
        assert {call.query.text for call in calls}.issubset(set(question_facets(original.query.text)))
    asyncio.run(run())


def test_foreign_output_does_not_gain_permission_by_query_splitting():
    async def run():
        original = request()
        async def rank(partial):
            return RerankResult((RerankScore("foreign", 1.0),), partial.profile.model_id, partial.profile.model_revision, 1)
        with pytest.raises(RerankerContractError):
            await rerank_facets(SimpleNamespace(rerank=rank), original, question_facets(original.query.text))
    asyncio.run(run())


def test_each_facet_cannot_reset_the_shared_operation_deadline():
    async def run():
        from dataclasses import replace
        original = request()
        original = replace(original, profile=replace(original.profile, timeout_ms=30))
        async def rank(partial):
            await asyncio.sleep(.02)
            return RerankResult(tuple(RerankScore(c.chunk_id, 1.0) for c in partial.candidates),
                partial.profile.model_id, partial.profile.model_revision, 20)
        with pytest.raises(TimeoutError):
            await rerank_facets(SimpleNamespace(rerank=rank), original, question_facets(original.query.text))
    asyncio.run(run())
