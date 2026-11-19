"""A cohort written as a range in the source ("K70 trở về trước", "từ K69") covers the cohorts inside it."""
import pytest

from campus247.rag_v2.retrieval.hybrid import scope_allows
from campus247.rag_v2.scope_ranges import covers
from campus247.rag_v2.types import Scope, Statement, Unit
from campus247.rag_v2.understanding.analyze import analyze
from campus247.rag_v2.verification.deterministic import check_statement

SURCHARGE = ("Mức phụ thu đối với chương trình Anh ngữ, Pháp ngữ (tính theo thời gian đào tạo chuẩn): "
             "- K70 trở về trước: 15.000.000 đ/năm - K71: 17.000.000 đ/năm")


@pytest.mark.parametrize("text, cohort, expected", [
    ("K70 trở về trước: 15.000.000", "K69", True),
    ("K70 trở về trước: 15.000.000", "K70", True),
    ("K70 trở về trước: 15.000.000", "K71", False),
    ("Từ K69 | 592.500", "K70", True),
    ("Từ K69 | 592.500", "K68", False),
    ("K65 đến K68 | 592.500", "K66", True),
    ("K65 đến K68 | 592.500", "K69", False),
    ("K66 trở về trước (ĐVHT) | 336.000", "K60", True),
    ("không có khóa nào", "K69", False),
    ("Từ K69 | 592.500", "", False),
])
def test_ranges_in_source_text(text, cohort, expected):
    assert covers(text, cohort) is expected


def unit(text, cohorts):
    return Unit("a" * 16, ("c",), "d", "v", "t", "f", "table_row", "p", None, text, scope=Scope(cohorts=tuple(cohorts)))


def test_retrieval_keeps_a_row_whose_range_contains_the_asked_cohort():
    u = analyze("phụ thu chương trình Anh ngữ K69 một năm bao nhiêu", ())
    assert u.cohort == "K69"
    assert scope_allows(u, unit(SURCHARGE, ["K70", "K71"]))
    other = unit("Học phí K71: 17.000.000", ["K71"])
    assert not scope_allows(u, other)  # K71 alone never covers K69


def test_verification_accepts_the_cohort_a_stated_range_contains_and_rejects_others():
    source = unit(SURCHARGE, ["K70", "K71"])
    good = Statement("K70 trở về trước có mức phụ thu 15.000.000 đ/năm, áp dụng cho K69.", (source.unit_id,))
    assert "SCOPE_MISMATCH" not in check_statement(good, {source.unit_id: source}).reasons
    bad = Statement("K75 có mức phụ thu 15.000.000 đ/năm.", (source.unit_id,))
    assert "SCOPE_MISMATCH" in check_statement(bad, {source.unit_id: source}).reasons


@pytest.mark.asyncio
async def test_a_document_titled_after_the_asked_programme_is_boosted_over_a_wordier_neighbour():
    from campus247.rag_v2.retrieval.hybrid import retrieve
    from tests.rag_v2.test_service import Reranker, UnitIndex

    right = Unit("1" * 16, ("c1",), "d1", "v1", "K70 — Kinh tế xây dựng", "f", "curriculum_row", "p", None,
                 "Tổng 190TC không tính giáo dục thể chất", scope=Scope())
    wrong = Unit("2" * 16, ("c2",), "d2", "v2", "K70 — Xây dựng DD&CN", "f", "curriculum_row", "p", None,
                 "Tổng bao nhiêu tín chỉ có tính thể dục quốc phòng không tổng tín chỉ 180TC thể dục", scope=Scope())
    index = UnitIndex([wrong, right])
    u = analyze("ngành kinh tế xây dựng K70 tổng bao nhiêu tín chỉ", ())
    assert u.program == "7580301"
    result = await retrieve(u, index, Reranker(), rerank_deadline_s=0, final_limit=2)
    assert result.candidates[0].unit_id == right.unit_id
