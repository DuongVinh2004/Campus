"""Acceptance examples for deterministic understanding; no eval-case tailoring."""
import ast
from pathlib import Path

import pytest
from campus247.rag_v2.understanding.analyze import analyze
from campus247.rag_v2.understanding.normalize import normalize_query


@pytest.mark.parametrize("question", [
    "hoc phi dai tra K64 HK1 nam hoc 26-27 bao nhieu?",
    "Học phí đại trà K64 kỳ 1 năm học 2026–2027 bao nhiêu?",
    "hoc phi dai tra k 64 hk 1 nam hoc 2026/2027 bao nhieu?",
])
def test_equivalent_fee_scope_and_year(question):
    u = analyze(question, [])
    assert u.cohort == "K64"
    assert u.program == "đại trà"
    assert u.academic_year == "2026-2027"
    assert "học kỳ 1" in u.search_query
    assert "học phí" in u.search_query
    assert u.question_type == "number"
    assert not u.missing_slots and u.clarify_prompt is None
    assert u.original == question


@pytest.mark.parametrize(("question", "expected"), [
    ("sv dk tc ntn", ("sinh viên", "đăng ký", "tín chỉ", "như thế nào")),
    ("sv rot mon co bi duoi hoc ko", ("không đạt học phần", "buộc thôi học", "không")),
    ("nợ môn thì rl tính ntn", ("học phần chưa đạt", "rèn luyện")),
    ("ktx lien he gv", ("ký túc xá", "liên hệ", "giảng viên")),
])
def test_slang_expansion(question, expected):
    query = analyze(question, ()).search_query
    assert all(term in query for term in expected)


def test_no_invented_diacritics_or_ambiguous_abbreviations():
    query = normalize_query("hp nam 17-18 theo 924/QĐ-ĐHXDHN xylophone")
    assert "hp" in query and "nam" in query and "17-18" in query
    assert "924/qđ-đhxdhn" in query and "xylophone" in query


@pytest.mark.parametrize("question", [
    "Điều kiện xét học bổng là gì?",
    "Quy chế cảnh báo học tập quy định thế nào?",
    "Thủ tục bảo lưu gồm những bước nào?",
    "Học phí tính như thế nào?",
    "Học phí bao nhiêu và điều kiện miễn giảm là gì?",
    "Hạn nộp học bổng và cách nộp ra sao?",
    "Tốt nghiệp cần đạt những điều kiện nào?",
])
def test_general_rules_and_partial_answers_do_not_clarify(question):
    u = analyze(question, ())
    assert u.clarify_prompt is None
    assert not u.out_of_scope


def test_fee_amount_needs_answer_changing_scope():
    u = analyze("Học phí bao nhiêu?", ())
    assert set(u.required_slots) == {"cohort|academic_year", "program"}
    assert set(u.missing_slots) == set(u.required_slots)
    assert "khóa hoặc năm học" in u.clarify_prompt
    u = analyze("Học phí K65 bao nhiêu?", ())
    assert u.missing_slots == ("program",)


@pytest.mark.parametrize("question", ["Hạn nộp học bổng?", "Khi nào đóng học phí?"])
def test_deadline_needs_period(question):
    u = analyze(question, ())
    assert u.question_type == "deadline"
    assert u.missing_slots == ("semester|academic_year",)
    assert "học kỳ hoặc năm học" in u.clarify_prompt


@pytest.mark.parametrize("period", ["HK1", "kỳ 2", "năm học 26-27"])
def test_deadline_period_can_be_semester_or_year(period):
    u = analyze("Hạn nộp học bổng " + period, ())
    assert u.required_slots == ("semester|academic_year",)
    assert not u.missing_slots and u.clarify_prompt is None


@pytest.mark.parametrize("question", ["?", "gì", "thế nào", "giúp em", "điểm", "nội dung"])
def test_vague_input_has_topic_suggestions(question):
    u = analyze(question, ())
    assert u.question_type == "unclear"
    assert "học phí" in u.clarify_prompt and "học bổng" in u.clarify_prompt


@pytest.mark.parametrize("question", [
    "Thời tiết ở HUCE ngày mai?", "Học phí Đại học Bách khoa bao nhiêu?",
    "Học bổng FPT cho khóa K64?", "Tỷ giá hôm nay?", "Quy chế của trường khác?",
])
def test_clearly_out_of_scope(question):
    u = analyze(question, ())
    assert u.out_of_scope and u.question_type == "oos"
    assert u.clarify_prompt is None


def test_history_inherits_only_relevant_followup_scope():
    history = ["Học phí đại trà K64 năm học 26-27 bao nhiêu?"]
    u = analyze("Còn K65?", history)
    assert (u.cohort, u.program, u.academic_year) == ("K65", "đại trà", "2026-2027")
    assert "hoc_phi" in u.topics and u.clarify_prompt is None
    new = analyze("Điều kiện tốt nghiệp là gì?", history)
    assert new.cohort is None and new.program is None and new.academic_year is None
    assert analyze("?", history).question_type == "unclear"
    assert analyze("quần áo", history).topics == ()


def test_mixed_school_comparison_can_still_answer_huce_part():
    u = analyze("So sánh quy định học phí HUCE và FPT", ())
    assert not u.out_of_scope and u.clarify_prompt is None


def test_deadline_of_a_named_application_still_needs_period():
    u = analyze("Hạn nộp hồ sơ học bổng là ngày nào?", ())
    assert u.missing_slots == ("semester|academic_year",)


@pytest.mark.parametrize(("question", "expected"), [
    ("Chương trình CNTT K66", "7480201"),
    ("nganh an toan thong tin", "7480202"),
    ("ngành 7580201", "7580201"),
])
def test_program_names_abbreviations_and_codes(question, expected):
    assert analyze(question, ()).program == expected


def test_pure_deterministic_core_has_no_io_or_v1_imports():
    root = Path(__file__).resolve().parents[3] / "services/api/src/campus247/rag_v2"
    for directory in (root / "understanding", root / "retrieval"):
        for path in directory.glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                    [node.module] if isinstance(node, ast.ImportFrom) else [])
                for name in names:
                    assert not name.startswith(("httpx", "campus247.infrastructure", "campus247.agent", "campus247.presentation",
                                                "campus247.application"))
    question = "hoc phi dai tra K64 nam hoc 26-27 bao nhieu?"
    assert analyze(question, ()) == analyze(question, ())


def test_vietnamese_neu_is_not_the_university_acronym():
    assert not analyze("Theo Quy chế 1486, nếu trượt học phần bắt buộc thì em học lại thế nào?").out_of_scope
    assert analyze("Học ở NEU thế nào?").out_of_scope


def test_roman_numeral_semester_counts_as_a_semester():
    understanding = analyze("Hạn nộp hồ sơ miễn giảm học phí học kỳ I năm học 2025-2026 là ngày nào?")
    assert understanding.missing_slots == () and understanding.clarify_prompt is None


def test_fee_procedure_question_is_not_asked_back_for_cohort():
    understanding = analyze("Em chốt đăng ký học phần xong thì hỏi học phí ở phòng nào?")
    assert understanding.clarify_prompt is None


def test_dangling_pronoun_without_context_is_asked_back_but_a_named_topic_is_not():
    assert analyze("Cách tính điểm đó", ()).clarify_prompt
    assert analyze("Cách tính điểm đó", ("Quy chế 1486 tính điểm tích lũy thế nào?",)).clarify_prompt is None
    assert analyze("Cách tính điểm tích lũy", ()).clarify_prompt is None


@pytest.mark.parametrize("question", [
    "Học phí cử nhân K65 đến K68 năm 2026-2027 bao nhiêu một tín chỉ?",
    "Học phí KS/KTS đã có bằng cử nhân năm 2026-2027 bao nhiêu?",
    "Quyết định 924 về học phí có hiệu lực từ ngày nào?"])
def test_degree_level_or_a_named_decision_is_enough_scope_for_a_fee_question(question):
    assert analyze(question, ()).clarify_prompt is None


def test_fee_question_without_any_scope_still_asks_back():
    assert analyze("Học phí bao nhiêu một tín chỉ?", ()).clarify_prompt
