import asyncio

import pytest
from campus247.rag_v2.retrieval.hybrid import rerank_excerpt, retrieve
from campus247.rag_v2.types import Scope, Unit
from campus247.rag_v2.understanding.analyze import analyze


def unit(i, *, document=None, path="Điều 1 > Khoản 1", scope=None, text=None):
    return Unit(str(i), (f"chunk-{i}",), document or f"doc-{i}", "v1", "Quy chế", "quy_che",
                "clause", path, 1, text or f"Điều kiện bảo lưu học tập {i}.", scope=scope or Scope())


@pytest.mark.parametrize(("programs", "allowed"), [
    (("7480201", "chất lượng cao"), True), (("7480201", "đại trà"), False),
    (("7480202", "chất lượng cao"), False), (("7480201",), True),
    (("chất lượng cao",), True), ((), True),
])
def test_major_and_explicit_fee_track_are_both_respected(programs, allowed):
    from campus247.rag_v2.retrieval.hybrid import scope_allows
    u = analyze("Quy định học phí CNTT chất lượng cao K64", ())
    assert scope_allows(u, unit(1, scope=Scope(programs=programs))) == allowed


class Index:
    def __init__(self, units, lexical=None, vector=None):
        self.units = {u.unit_id: u for u in units}
        self.lexical_rows = lexical if lexical is not None else [(u.unit_id, 100 - i) for i, u in enumerate(units)]
        self.vector_rows = vector if vector is not None else list(reversed(self.lexical_rows))
        self.allowed_seen = []

    def get(self, uid):
        return self.units.get(uid)

    def all_ids(self):
        return tuple(self.units)

    def lexical(self, query, limit, *, allowed=None):
        self.allowed_seen.append(allowed)
        return [r for r in self.lexical_rows if r[0] in allowed][:limit]

    async def vector(self, query, limit, *, allowed=None):
        self.allowed_seen.append(allowed)
        return [r for r in self.vector_rows if r[0] in allowed][:limit]


class Reranker:
    def __init__(self, *, error=None, scores=None, delay=0):
        self.error, self.scores, self.delay = error, scores, delay
        self.texts = None
        self.deadline = None

    async def rerank(self, query, texts, *, deadline_s):
        self.texts, self.deadline = texts, deadline_s
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return self.scores if self.scores is not None else [float(i) for i in range(len(texts))]


U = analyze("Điều kiện bảo lưu là gì?", ())


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [TimeoutError(), RuntimeError("private message"), ValueError()])
async def test_reranker_failure_returns_rrf_without_applying_logit_threshold(error):
    index = Index([unit(i) for i in range(15)])
    result = await retrieve(U, index, Reranker(error=error), rerank_deadline_s=1, min_rerank_logit=1000)
    assert result.fallback_used
    assert len(result.candidates) == 8
    assert all(c.rerank_score is None for c in result.candidates)
    assert [c.fused_score for c in result.candidates] == sorted((c.fused_score for c in result.candidates), reverse=True)
    assert [c.final_rank for c in result.candidates] == list(range(1, 9))
    assert "private" not in str(result.trace) and U.original not in str(result.trace)


@pytest.mark.asyncio
async def test_deadline_is_enforced_even_when_reranker_ignores_argument():
    reranker = Reranker(delay=5)
    result = await asyncio.wait_for(retrieve(U, Index([unit(i) for i in range(13)]), reranker,
                                             rerank_deadline_s=0.01), timeout=0.5)
    assert result.fallback_used and result.trace["status"] == "RRF_TIMEOUT"
    assert reranker.deadline == 0.01


@pytest.mark.asyncio
async def test_zero_deadline_does_not_invoke_reranker():
    reranker = Reranker()
    result = await retrieve(U, Index([unit(1)]), reranker, rerank_deadline_s=0)
    assert result.fallback_used and reranker.texts is None


@pytest.mark.asyncio
@pytest.mark.parametrize("final_limit", [6, 12])
async def test_disabled_reranker_keeps_high_ranked_clauses_before_other_documents(final_limit):
    # The two parts of an answer share a document. A diverse shortlist used to
    # evict the second part in favour of any of the unrelated documents below.
    units = [unit(i, document="policy", path=f"Điều {i + 1}") for i in range(12)]
    units += [unit(i) for i in range(12, 25)]
    rows = [(u.unit_id, 100 - i) for i, u in enumerate(units)]
    reranker = Reranker()
    result = await retrieve(U, Index(units, lexical=rows, vector=rows), reranker,
                            rerank_deadline_s=0, final_limit=final_limit)
    assert [c.unit_id for c in result.candidates] == [str(i) for i in range(final_limit)]
    assert [c.final_rank for c in result.candidates] == list(range(1, final_limit + 1))
    assert result.fallback_used and result.trace["status"] == "RRF_TIMEOUT"
    assert reranker.texts is None


@pytest.mark.asyncio
async def test_disabled_reranker_still_filters_scope_before_fused_limit():
    units = [unit(0, scope=Scope(cohorts=("K65",))), unit(1), unit(2)]
    rows = [(u.unit_id, 100 - i) for i, u in enumerate(units)]
    result = await retrieve(analyze("Điều kiện bảo lưu K64", ()),
                            Index(units, lexical=rows, vector=rows), Reranker(),
                            rerank_deadline_s=0, final_limit=1)
    assert [c.unit_id for c in result.candidates] == ["1"]


@pytest.mark.asyncio
async def test_preselection_at_least_10_diverse_documents_even_if_request_is_smaller():
    units = [unit(i, document="dominant") for i in range(30)] + [unit(i) for i in range(30, 41)]
    rows = [(u.unit_id, 100 - i) for i, u in enumerate(units)]
    reranker = Reranker()
    result = await retrieve(U, Index(units, lexical=rows, vector=rows), reranker,
                            lexical_k=50, vector_k=50, preselect=4, rerank_deadline_s=1)
    assert len(reranker.texts) == 10
    assert result.trace["documents"] == 10
    assert len(result.candidates) == 8


@pytest.mark.asyncio
async def test_articles_are_diverse_within_one_document():
    units = [unit(i, document="one", path="Điều 1 > Khoản " + str(i)) for i in range(20)]
    units += [unit(i, document="one", path=f"Điều {i} > Khoản 1") for i in range(20, 31)]
    rows = [(u.unit_id, 100 - i) for i, u in enumerate(units)]
    result = await retrieve(U, Index(units, lexical=rows, vector=rows), Reranker(), rerank_deadline_s=1)
    assert result.trace["preselected"] == 10 and result.trace["articles"] == 10


@pytest.mark.asyncio
async def test_balanced_rrf_uses_ranks_not_score_scale():
    index = Index([unit(i) for i in range(3)], lexical=[("0", 1e9), ("1", 1)], vector=[("2", 1), ("1", 0.1)])
    result = await retrieve(U, index, Reranker(error=TimeoutError()), rerank_deadline_s=1)
    assert [c.unit_id for c in result.candidates] == ["1", "0", "2"]
    assert result.candidates[0].fused_score == pytest.approx(2 / 62)
    assert result.candidates[1].fused_score == result.candidates[2].fused_score


@pytest.mark.asyncio
async def test_filter_before_limit_keeps_generic_scope_and_matches_program_name_to_code():
    units = [unit(0), unit(1, scope=Scope(cohorts=("K64",), programs=("công nghệ thông tin",), academic_years=("2026-2027",))),
             unit(2, scope=Scope(cohorts=("K65",))), unit(3, scope=Scope(programs=("7480202",))),
             unit(4, scope=Scope(academic_years=("2025-2026",))), unit(5, scope=Scope(programs=("đại trà",)))]
    u = analyze("Quy định CNTT K64 năm học 26-27", ())
    index = Index(units)
    result = await retrieve(u, index, Reranker(error=TimeoutError()), lexical_k=1, vector_k=6, rerank_deadline_s=1)
    assert {c.unit_id for c in result.candidates} == {"0", "1", "5"}
    assert index.allowed_seen == [{"0", "1", "5"}] * 2


@pytest.mark.asyncio
async def test_success_applies_logit_threshold_and_orders_scores():
    index = Index([unit(i) for i in range(4)])
    result = await retrieve(U, index, Reranker(scores=[-2, -1, -0.5, 3]), rerank_deadline_s=1)
    assert not result.fallback_used
    assert [c.rerank_score for c in result.candidates] == [3, -0.5]


@pytest.mark.asyncio
@pytest.mark.parametrize("scores", [[1], [float("nan")] * 3, [float("inf")] * 3, [True] * 3])
async def test_malformed_reranking_uses_fallback(scores):
    result = await retrieve(U, Index([unit(i) for i in range(3)]), Reranker(scores=scores), rerank_deadline_s=1)
    assert result.fallback_used and len(result.candidates) == 3


def test_relevance_window_near_end_is_exact_and_bounded():
    source = "Thông tin không liên quan. " * 100 + "Điều kiện bảo lưu học tập: nộp hồ sơ hợp lệ. " * 4
    excerpt = rerank_excerpt(source, U.search_query)
    assert len(excerpt) <= 320 and excerpt in source and "Điều kiện bảo lưu" in excerpt


@pytest.mark.asyncio
async def test_only_bounded_excerpts_are_sent_and_units_stay_intact():
    source = "Không liên quan. " * 100 + "Điều kiện bảo lưu học tập."
    index = Index([unit(1, text=source)])
    reranker = Reranker()
    await retrieve(U, index, reranker, rerank_deadline_s=1)
    assert len(reranker.texts[0]) <= 320 and "bảo lưu" in reranker.texts[0]
    assert index.get("1").text == source


@pytest.mark.asyncio
async def test_empty_skipped_and_vector_error_paths():
    reranker = Reranker()
    empty = await retrieve(U, Index([]), reranker, rerank_deadline_s=1)
    assert not empty.candidates and not empty.fallback_used
    for u in (analyze("?", ()), analyze("thời tiết", ())):
        result = await retrieve(u, Index([unit(1)]), reranker, rerank_deadline_s=1)
        assert not result.candidates and result.trace["status"] == "SKIPPED"
    index = Index([unit(1)])
    async def broken(*args, **kwargs):
        raise ValueError("embedding unavailable")
    index.vector = broken
    result = await retrieve(U, index, Reranker(), rerank_deadline_s=1)
    assert result.trace["vector_failed"] and len(result.candidates) == 1


def test_excerpt_never_bisects_amount_or_document_code():
    text = ("Nội dung khác " * 30 + "580.500 đồng/tín chỉ theo 924/QĐ-ĐHXDHN. "
            + "Điều kiện bảo lưu học tập. " * 20)
    excerpt = rerank_excerpt(text, "học phí 580.500 924/QĐ-ĐHXDHN", limit=90)
    start = text.index(excerpt)
    assert len(excerpt) <= 90 and (start == 0 or text[start - 1].isspace())
    assert start + len(excerpt) == len(text) or text[start + len(excerpt)].isspace()
    assert "580.500" in excerpt and "924/QĐ-ĐHXDHN" in excerpt


@pytest.mark.asyncio
async def test_measured_default_pair_count_and_deadline():
    reranker = Reranker()
    await retrieve(U, Index([unit(i) for i in range(15)]), reranker)
    assert len(reranker.texts) == 10 and reranker.deadline == 4.5
    assert all(len(text) <= 320 for text in reranker.texts)


@pytest.mark.asyncio
async def test_stalled_vector_preserves_lexical_fallback():
    index = Index([unit(1)])
    async def stalled(*args, **kwargs):
        await asyncio.sleep(30)
    index.vector = stalled
    result = await asyncio.wait_for(retrieve(U, index, Reranker()), timeout=1.5)
    assert result.trace["vector_failed"] and len(result.candidates) == 1



def test_strong_lexical_hit_is_kept_inside_the_packing_window():
    from campus247.rag_v2.retrieval import hybrid
    units = [unit(i, document=f"doc-{i}") for i in range(30)]
    ids = [u.unit_id for u in units]
    # Unit "20" is fourth for BM25 and absent from the vector list, so RRF alone leaves it far down.
    lexical = [(ids[i], 100 - n) for n, i in enumerate((1, 2, 3, 20, 4, 5, 6, 7, 8, 9))]
    vector = [(ids[i], 100 - n) for n, i in enumerate((10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 1, 2, 3))]
    u = analyze("Quy định bảo lưu học tập", ())
    result = asyncio.run(retrieve(u, Index(units, lexical, vector), Reranker(), rerank_deadline_s=0, final_limit=12))
    assert "20" in [c.unit_id for c in result.candidates][:hybrid.PACK_WINDOW]
    previous, hybrid.LEXICAL_PIN = hybrid.LEXICAL_PIN, 0
    try:
        result = asyncio.run(retrieve(u, Index(units, lexical, vector), Reranker(), rerank_deadline_s=0, final_limit=12))
    finally:
        hybrid.LEXICAL_PIN = previous
    assert "20" not in [c.unit_id for c in result.candidates][:hybrid.PACK_WINDOW]
