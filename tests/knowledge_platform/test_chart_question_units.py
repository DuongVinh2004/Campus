"""Column labels cannot change either the question subject or quantity units."""
from campus247.application.knowledge.question_scope import (
    explicit_curriculum_reference,
    focused_curriculum_question,
    programme_credit_question,
    programme_name_match,
)
from campus247.application.retrieval.material_support import quantity_units, support_issues


def test_course_credit_question_is_not_replaced_with_whole_programme_total():
    for question in ("Xây dựng DD&CN K71 môn Triết học có bao nhiêu tín chỉ?",
        "K71 học phần Triết học mã 428801 có bao nhiêu tín chỉ?", "K71 mã HP 428801 có bao nhiêu TC?"):
        assert programme_credit_question(question) == question
    assert programme_credit_question("Xây dựng DD&CN K71 tổng bao nhiêu tín chỉ?") == "Tổng số tín chỉ (TC) là bao nhiêu?"


def test_explicit_pe_and_bare_course_codes_keep_their_subject_without_the_word_course():
    for question in ("Theo đúng kế hoạch K71KM K71, Giáo dục thể chất 2 ghi bao nhiêu TC?",
            "K71KM Giáo dục quốc phòng có bao nhiêu tín chỉ?", "K71KM 268809 có bao nhiêu TC?"):
        assert programme_credit_question(question) == question
    assert programme_credit_question("K71KM tổng số tín chỉ có tính Giáo dục thể chất không?") == "Tổng số tín chỉ (TC) là bao nhiêu?"


def test_chart_column_heading_is_not_a_unit_for_preceding_course_credit():
    assert quantity_units("Giáo dục thể chất 3\nNăm 2\nHọc kỳ 3") == []
    assert "CONTRADICTED_UNIT" not in support_issues("Triết học: 3 tín chỉ", "428801-3\nTriết học\nGiáo dục thể chất 3\nNăm 2")


def test_actual_year_units_remain_enforced_including_wrapped_units():
    for source in ("Thời gian: 3 năm", "Thời gian: 3\nnăm"):
        assert quantity_units(source)
        assert "CONTRADICTED_UNIT" in support_issues("Thời gian: 3 tín chỉ", source)


def test_bilingual_and_year_suffixes_do_not_hide_the_explicit_programme_reference():
    query = "Theo kế hoạch kỹ sư Công nghệ kỹ thuật vật liệu xây dựng K71 bản 2025, X và Y trong chú giải Mã HP-X-Y là gì?"
    title = "Kế hoạch giảng dạy chương trình đào tạo trình độ kỹ sư — Ngành Công nghệ kỹ thuật vật liệu xây dựng (2025) / Engineering program study plan — Building Materials Engineering Technology (2025)"
    assert explicit_curriculum_reference(query)
    assert focused_curriculum_question(query) == "X và Y trong chú giải Mã HP-X-Y là gì?"
    assert programme_name_match(query, title) > programme_name_match(query, "Kỹ thuật xây dựng — Chuyên ngành Vật liệu xây dựng")
    assert not explicit_curriculum_reference("Quy chế về học phí ngành Công nghệ kỹ thuật vật liệu xây dựng?")
    assert focused_curriculum_question("Theo Quy chế 1486, một tín chỉ là gì?") == "Theo Quy chế 1486, một tín chỉ là gì?"
    course = "Theo sơ đồ Xây dựng DD&CN K71, môn Triết học có bao nhiêu tín chỉ?"
    assert focused_curriculum_question(course) == course


def test_printed_numeric_credit_abbreviation_has_the_same_lexical_unit():
    from campus247.application.retrieval.evidence_gate import EvidenceGate, GroundedClaim, GroundedDraft
    from types import SimpleNamespace
    class Bundle:
        def __init__(self, text): self.record = SimpleNamespace(content_text=text, quote_span_hash="sha256:" + "a"*64)
        def resolve(self, ref): return self.record if ref == "CIT-001" else None
    claim = GroundedClaim("course", "Triết học Mác Lê Nin: 3 tín chỉ", ("CIT-001",), "policy")
    draft = GroundedDraft(claim.text, (claim,))
    gate = EvidenceGate(min_token_overlap_ratio=.78)
    assert gate.verify(draft, Bundle("Học kỳ 1 (20TC)\n428801-3\nTriết học Mác Lê Nin")).passed
    assert not gate.verify(draft, Bundle("428801-3\nTriết học Mác Lê Nin")).passed
    unsupported = GroundedClaim("course", "Triết học Mác Lê Nin: 4 tín chỉ", ("CIT-001",), "policy")
    assert not gate.verify(GroundedDraft(unsupported.text, (unsupported,)), Bundle("Học kỳ 1 (20TC)\n428801-3\nTriết học Mác Lê Nin")).passed


def test_a_chart_credit_suffix_is_not_part_of_the_course_identifier():
    source = "Học kỳ 1 (20TC)\n428801-3\nTriết học Mác - Lê Nin"
    assert "CONTRADICTED_COURSE_CODE" in support_issues("Môn Triết học có mã 428801-3 và 3 tín chỉ", source)
    assert "CONTRADICTED_COURSE_CODE" not in support_issues("Môn Triết học có mã 428801 và 3 tín chỉ", source)
    assert "CONTRADICTED_COURSE_CODE" not in support_issues("Thiết bị có mã 428801-3", "Mã thiết bị 428801-3")
