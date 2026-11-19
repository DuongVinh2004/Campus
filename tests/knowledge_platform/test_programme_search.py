"""Specific programme references select evidence subjects without inventing facts."""
from campus247.application.knowledge.question_scope import (
    programme_credit_question,
    programme_name_match,
    programme_reference_codes,
)
from campus247.application.knowledge.source_snapshot import scope_allows


def test_exact_programme_code_preserves_cohort_and_programme_boundaries():
    assert programme_reference_codes("K69KDMT tổng bao nhiêu tín chỉ?") == {"69kdmt"}
    scope = {"kind": "COHORT_SNAPSHOT", "cohorts": ["K69"], "programme_codes": ["69KDMT"]}
    assert scope_allows("K69KDMT tổng bao nhiêu tín chỉ?", scope)
    assert not scope_allows("K71KDMT tổng bao nhiêu tín chỉ?", scope)


def test_programme_name_does_not_select_a_different_subject_or_supply_a_cohort():
    title = "K70_and_earlier_verify_individual_row — Ngành Quản lý dự án"
    assert programme_name_match("Ngành Quản lý dự án K69 có bao nhiêu tín chỉ?", title) > 0
    assert programme_name_match("Kỹ thuật vật liệu K69 có bao nhiêu tín chỉ?", title) == 0
    assert not scope_allows("Ngành Quản lý dự án K69 có bao nhiêu tín chỉ?", {"kind": "COHORT_SNAPSHOT", "cohorts": [], "programme_codes": []})


def test_credit_focusing_retains_noncredit_and_specific_semester_questions():
    assert "TC" in programme_credit_question("K71QLDA tổng bao nhiêu tín chỉ?")
    for question in ("K71QLDA học kỳ 2 có mấy tín chỉ?", "K71QLDA môn nào tiên quyết?", "Học bổng STEM có điều kiện gì?"):
        assert programme_credit_question(question) == question


def test_missing_printed_total_does_not_turn_course_text_into_a_total():
    total_only = "K71PM tổng bao nhiêu tín chỉ?"
    assert programme_credit_question(total_only, has_total=False) == total_only
    mixed = "K71PM có các học phần và số tín chỉ gì?"
    assert programme_credit_question(mixed, has_total=False) == mixed
