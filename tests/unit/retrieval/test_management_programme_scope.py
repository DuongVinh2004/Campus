"""Named degree totals keep their programme instead of a shared course name."""
import pytest

from campus247.application.conversation.followup import question_topics
from campus247.application.retrieval.programme_scope import matches_programme_scope


@pytest.mark.parametrize("query", ["Quản lý dự án K71 cần bao nhiêu tín chỉ?", "qlda K71 can may tin?",
                                  "Quản lý xây dựng K71 tổng tín chỉ là bao nhiêu?"])
def test_named_management_degrees_are_programme_total_questions(query):
    assert "tin chi tot nghiep" in question_topics(query)


def test_incidental_course_in_other_degree_does_not_cover_total():
    source = {"title": "K71 — Quản lý Xây dựng/Kiểm toán đầu tư xây dựng",
              "content_text": "Học phần quản lý dự án. Tổng: 130TC"}
    assert not matches_programme_scope("Quản lý dự án K71 cần bao nhiêu tín chỉ?", source)


def test_correct_programme_and_cohort_are_required():
    source = {"title": "K71 — Quản lý dự án", "content_text": "Tổng: 131TC"}
    assert matches_programme_scope("qlda K71 can may tin?", source)
    assert not matches_programme_scope("Quản lý dự án K70 cần bao nhiêu tín chỉ?", source)


@pytest.mark.parametrize("query", ["Quản lý dự án K71 học kỳ 1 có môn gì?", "học phí QLDA một tín chỉ bao nhiêu tiền?",
                                  "Môn Quản lý dự án K71 có bao nhiêu tín chỉ?"])
def test_other_questions_do_not_become_degree_total_queries(query):
    assert "tin chi tot nghiep" not in question_topics(query)


@pytest.mark.parametrize("query", ["Em muốn rút học phần thì phải làm thế nào?", "rut bot hoc phan", "hủy đăng ký học phần"])
def test_withdrawal_is_an_explicit_topic_instead_of_generic_course_vocabulary(query):
    assert "rut hoc phan" in question_topics(query)


def test_consent_withdrawal_is_not_course_withdrawal():
    assert "rut hoc phan" not in question_topics("Tôi muốn rút consent lịch sử hội thoại")
