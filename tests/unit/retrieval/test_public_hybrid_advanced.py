"""Orchestration/security tests; deterministic model doubles are not quality evidence."""
import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from campus247.application.retrieval.citations import CitationBundle
from campus247.application.retrieval.semantic_support import SemanticClaimVerifier
from campus247.domain.retrieval import (
    AuthorizedScope,
    RetrievalContext,
    SimulationPolicy,
)
from campus247.infrastructure.retrieval.public_hybrid import (
    PublicHybridKnowledgeStore,
    PublicRetrievalPolicy,
)
from campus247.ports.embedding import EmbeddingProfile, validate_embedding_vector
from campus247.ports.llm import LlmRequest, LlmResponse, LlmResponseStatus
from campus247.ports.reranker import RerankerProfile, RerankResult, RerankScore


def context(tenant="HUCE"):
    return RetrievalContext(AuthorizedScope(tenant, "HUCE", "actor", frozenset({"STUDENT"}),
        frozenset({"STUDENT"}), frozenset({"PUBLIC"}), frozenset({"PUBLIC"})),
        "vi", datetime(2026, 10, 15, tzinfo=UTC), SimulationPolicy.DENY, "1" * 32)


@pytest.fixture
def store(tmp_path):
    manifest = {"public_only": True, "acquired_at": "2026-10-13T01:00:00+07:00", "chunks": [
        {"url": "https://huce.edu.vn/hoc-bong", "title": "Học bổng", "page": 1, "section": "Điều kiện",
         "text": "Điều kiện học bổng: cần điểm học tập và điểm rèn luyện.\n" + "Quy định về xét học bổng. " * 45
                 + "\nNgoại lệ: năm thứ nhất dùng quy định riêng."},
        {"url": "https://huce.edu.vn/hoc-phi", "title": "Học phí", "page": 2, "section": "Mức thu",
         "text": "Học phí được tính theo số tín chỉ."},
    ]}
    (tmp_path / "corpus.json").write_text(json.dumps(manifest), encoding="utf-8")
    calls = []
    profile = EmbeddingProfile("test-embedding", "test-revision", 2)
    async def embed(text):
        calls.append("embed")
        return validate_embedding_vector((1.0, 0.0), profile)
    class Ranking:
        profile = RerankerProfile("test-reranker", "test-revision", 20, 100)
        def __init__(self):
            self.requests = []
        async def rerank(self, request):
            self.requests.append(request)
            calls.append(request.context)
            return RerankResult(tuple(RerankScore(c.chunk_id, 5.0 if "học bổng" in c.content_text else 1.0)
                for c in request.candidates), self.profile.model_id, self.profile.model_revision, 1)
    value = PublicHybridKnowledgeStore(tmp_path, tenant_id="HUCE", campus_id="HUCE", embed_query=embed,
        embedding_profile=profile, embedding_artifact_sha256="1" * 64, reranker=Ranking())
    return value, calls


@pytest.mark.asyncio
async def test_retrieval_expands_to_original_parent_and_citation_hash_readback(store):
    value, calls = store
    await value.build_vectors()
    rows = await value.search("Điều kiện học bổng", context())
    assert rows and "Ngoại lệ" in rows[0]["content_text"]
    assert rows[0]["content_text"] == value.rows[0]["content_text"]
    source = await value.read(rows[0]["source_id"], rows[0]["document_version_id"], rows[0]["chunk_id"], context=context())
    assert source.content_sha256 == rows[0]["quote_span_hash"]
    assert any(isinstance(call, RetrievalContext) for call in calls)


@pytest.mark.asyncio
async def test_wrong_scope_rejects_before_any_model_or_cache_call(store):
    value, calls = store
    with pytest.raises(ValueError):
        await value.search("Học bổng", context("OTHER"))
    assert not calls


@pytest.mark.asyncio
async def test_expired_parent_never_reaches_reranker_or_output_even_with_cached_vectors(store):
    value, _ = store
    await value.build_vectors()
    value.rows[0]["effective_until"] = "2026-10-14T00:00:00+00:00"
    rows = await value.search("Học bổng", context())
    assert all(row["canonical_uri"] != "https://huce.edu.vn/hoc-bong" for row in rows)


@pytest.mark.asyncio
async def test_corpus_or_model_drift_rejects_cached_index(store):
    value, _ = store
    manifest = await value.build_vectors()
    with pytest.raises(ValueError, match="mismatch"):
        value.load_vectors(dict(manifest, fingerprint="changed-corpus"))
    with pytest.raises(ValueError, match="mismatch"):
        value.load_vectors(dict(manifest, model_revision="other-model"))


@pytest.mark.asyncio
async def test_source_withdrawn_during_embedding_never_reaches_cross_encoder(store):
    value, calls = store
    await value.build_vectors()
    calls.clear()
    original_embed = value.embed_query
    async def withdrawing_embed(query):
        vector = await original_embed(query)
        value.rows[0]["source_status"] = "EXPIRED"
        return vector
    value.embed_query = withdrawing_embed
    assert await value.search("Học bổng", context()) == []
    assert calls == ["embed"] and not value.reranker.requests


@pytest.mark.asyncio
async def test_no_eligible_sources_requires_no_model_call(store):
    value, calls = store
    await value.build_vectors()
    calls.clear()
    for row in value.rows:
        row["source_status"] = "EXPIRED"
    assert await value.search("Học bổng và học phí", context()) == []
    assert not calls


@pytest.mark.asyncio
async def test_source_withdrawn_during_reranking_never_becomes_returned_evidence(store):
    value, _ = store
    await value.build_vectors()
    original_rerank = value.reranker.rerank
    async def withdrawing_rerank(request):
        result = await original_rerank(request)
        value.rows[0]["source_status"] = "EXPIRED"
        return result
    value.reranker.rerank = withdrawing_rerank
    assert await value.search("Học bổng", context()) == []


@pytest.mark.asyncio
async def test_multi_topic_queries_share_total_candidate_budget_and_keep_both_parents(tmp_path):
    chunks = [{"url": f"https://huce.edu.vn/{slug}-{index}", "title": topic, "page": index + 1,
               "section": topic, "text": f"{topic}: mục {index}, áp dụng theo quy định hiện hành."}
              for topic, slug in (("Học bổng", "hoc-bong"), ("Học phí", "hoc-phi")) for index in range(8)]
    manifest = {"public_only": True, "acquired_at": "2026-10-13T01:00:00+07:00", "chunks": chunks}
    (tmp_path / "corpus.json").write_text(json.dumps(manifest), encoding="utf-8")
    profile = EmbeddingProfile("test-embedding", "test-revision", 2)
    async def embed(query):
        return validate_embedding_vector((1.0, 0.0), profile)
    requests, diagnostics = [], []
    class Ranking:
        profile = RerankerProfile("test-reranker", "test-revision", 20, 100)
        async def rerank(self, request):
            requests.append(request)
            return RerankResult(tuple(RerankScore(candidate.chunk_id, 1.0) for candidate in request.candidates),
                                self.profile.model_id, self.profile.model_revision, 1)
    value = PublicHybridKnowledgeStore(tmp_path, tenant_id="HUCE", campus_id="HUCE", embed_query=embed,
        embedding_profile=profile, embedding_artifact_sha256="1" * 64, reranker=Ranking(), diagnostics=diagnostics.append)
    await value.build_vectors()
    question = "Học bổng và học phí cho năm nhất?"
    ctx = context()
    rows = await value.search(question, ctx)
    assert [len(request.candidates) for request in requests] == [6, 6]
    assert all(request.context is ctx and question in request.query.text for request in requests)
    assert {row["title"] for row in rows} == {"Học bổng", "Học phí"}
    assert diagnostics[0]["rerank_candidates"] == value.policy.fusion_k == 12
    assert all(row["content_text"] == next(parent["content_text"] for parent in value.rows
        if parent["chunk_id"] == row["chunk_id"]) for row in rows)


@pytest.mark.asyncio
async def test_stalled_first_query_cannot_consume_the_whole_multi_query_deadline(store):
    value, _ = store
    await value.build_vectors()
    value.policy = replace(PublicRetrievalPolicy(), deadline_seconds=0.1)
    requests = []
    async def stalled_rerank(request):
        requests.append(request)
        await asyncio.Event().wait()
    value.reranker.rerank = stalled_rerank
    with pytest.raises(TimeoutError):
        await value.search("Học bổng và học phí?", context())
    assert len(requests) == 1  # No transport retry or new call after timeout.


@pytest.fixture
def calendar_store(tmp_path):
    manifest = {"public_only": True, "acquired_at": "2026-10-13T01:00:00+07:00", "chunks": [
        {"url": "https://huce.edu.vn/tet-2027", "title": "Lịch nghỉ Tết", "page": 1, "section": "Lịch 2027",
         "text": "Lịch nghỉ Tết năm 2027 bắt đầu ngày 01/02/2027 và kết thúc ngày 12/02/2027."},
        {"url": "https://huce.edu.vn/different-paragraphs", "title": "Thông báo tổng hợp", "page": 2, "section": "Lịch",
         "text": "Kế hoạch học phí năm 2030 sẽ được công bố riêng.\n\n"
                 "Lịch nghỉ Tết năm 2027 bắt đầu ngày 01/02/2027 và kết thúc ngày 12/02/2027."},
        {"url": "https://huce.edu.vn/exam-2030", "title": "Lịch thi", "page": 3, "section": "Lịch 2030",
         "text": "Lịch thi học kỳ I năm 2030 bắt đầu ngày 03/01/2030 và kết thúc ngày 10/01/2030."},
        {"url": "https://huce.edu.vn/metadata-not-evidence", "title": "Lịch nghỉ Tết năm 2030", "page": 4, "section": "Lịch",
         "text": "Lịch nghỉ Tết năm 2027 được thông báo riêng."},
    ]}
    (tmp_path / "corpus.json").write_text(json.dumps(manifest), encoding="utf-8")
    calls = []
    profile = EmbeddingProfile("test-embedding", "test-revision", 2)
    async def embed(query):
        calls.append("embed")
        return validate_embedding_vector((1.0, 0.0), profile)
    class Ranking:
        profile = RerankerProfile("test-reranker", "test-revision", 20, 100)
        def __init__(self):
            self.requests = []
        async def rerank(self, request):
            calls.append("rerank")
            self.requests.append(request)
            return RerankResult(tuple(RerankScore(candidate.chunk_id, 1.0) for candidate in request.candidates),
                                self.profile.model_id, self.profile.model_revision, 1)
    value = PublicHybridKnowledgeStore(tmp_path, tenant_id="HUCE", campus_id="HUCE", embed_query=embed,
        embedding_profile=profile, embedding_artifact_sha256="1" * 64, reranker=Ranking())
    return value, calls


@pytest.mark.asyncio
async def test_missing_future_calendar_has_no_embedding_or_reranking_even_with_other_year_and_event(calendar_store):
    value, calls = calendar_store
    await value.build_vectors()
    calls.clear()
    fingerprint = value.fingerprint
    query = "Lịch nghỉ Tết năm 2030 bắt đầu và kết thúc chính xác ngày nào?"
    assert await value.search(query, context()) == []
    assert not calls and not value.reranker.requests and not value._query_vectors
    assert value.fingerprint == fingerprint


@pytest.mark.asyncio
async def test_actual_calendar_year_and_event_are_eligible_and_only_matching_passages_are_reranked(calendar_store):
    value, calls = calendar_store
    await value.build_vectors()
    calls.clear()
    rows = await value.search("Lịch nghỉ Tết năm 2027 bắt đầu ngày nào?", context())
    assert rows and all("2027" in row["content_text"] for row in rows)
    assert all(row["canonical_uri"] != "https://huce.edu.vn/exam-2030" for row in rows)
    assert calls == ["embed", "rerank"]
    assert all("Tết năm 2027" in candidate.content_text and "2030" not in candidate.content_text
               for request in value.reranker.requests for candidate in request.candidates)


@pytest.mark.asyncio
async def test_calendar_event_must_match_as_well_as_year(calendar_store):
    value, _ = calendar_store
    await value.build_vectors()
    rows = await value.search("Lịch thi năm 2030 diễn ra khi nào?", context())
    assert [row["canonical_uri"] for row in rows] == ["https://huce.edu.vn/exam-2030"]


@pytest.mark.asyncio
async def test_general_policy_with_a_year_preserves_ordinary_retrieval(calendar_store):
    value, _ = calendar_store
    await value.build_vectors()
    rows = await value.search("Học phí năm 2027 cần nộp qua đâu?", context())
    assert rows and rows[0]["canonical_uri"] == "https://huce.edu.vn/different-paragraphs"


@pytest.mark.asyncio
@pytest.mark.parametrize("verdict", [
    {"answers_question": True, "verdicts": [{"claim_id": "CLM-001", "status": "SUPPORTED"}]},
    {"answers_question": False, "verdicts": [{"claim_id": "CLM-001", "status": "SUPPORTED"}]},
    {"answers_question": True, "verdicts": [{"claim_id": "FOREIGN", "status": "SUPPORTED"}]},
    {"answers_question": True, "verdicts": [{"claim_id": "CLM-001", "status": "CONTRADICTED"}]},
])
async def test_semantic_verdict_must_cover_exact_claims_and_actual_question(verdict):
    requests = []
    class Checking:
        async def generate(self, request):
            requests.append(request)
            return LlmResponse(LlmResponseStatus.COMPLETED, "test", "test", output_text=json.dumps(verdict))
    source = "Điều kiện học bổng: điểm rèn luyện từ 80."
    bundle = CitationBundle.build([{"content_text": source, "source_id": "s", "chunk_id": "c"}])
    draft = LlmResponse(LlmResponseStatus.COMPLETED, "test", "test", output_text=json.dumps({"claims": [
        {"text": source, "citation_ids": ["CIT-001"], "claim_type": "policy"}]}))
    request = LlmRequest("id", "grounded_faq", "default", "source only", (), max_output_tokens=1000)
    actual = await SemanticClaimVerifier(Checking()).verify(request, draft, bundle, deadline_ms=500,
        output_tokens=100, question="Điều kiện học bổng?")
    assert actual is (verdict["answers_question"] and verdict["verdicts"][0] == {"claim_id": "CLM-001", "status": "SUPPORTED"})
    assert requests[0].max_output_tokens == 100 and requests[0].deadline_ms == 500
    assert not requests[0].allowed_tools and source in requests[0].input_items[0]["content"]
