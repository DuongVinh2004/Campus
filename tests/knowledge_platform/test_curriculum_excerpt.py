import pytest

from campus247.application.knowledge.curriculum_excerpt import printed_course_rerank_text, printed_elective_rerank_text, printed_total_excerpt


def test_total_excludes_boilerplate_but_keeps_all_wrapped_exceptions():
    source = "Học kỳ 1\nMôn A – 3\nTổng: 131TC (Không tính HP giáo dục thể chất,\nGiáo dục quốc phòng và An ninh)\nGhi chú và kí hiệu: mũi tên\nNgười lập"
    excerpt = printed_total_excerpt(source, "Tổng số tín chỉ (TC) là bao nhiêu?")
    assert excerpt in source
    assert excerpt == "Tổng: 131TC (Không tính HP giáo dục thể chất,\nGiáo dục quốc phòng và An ninh)"


def test_multiple_totals_and_nontotal_questions_are_not_guessed():
    assert printed_total_excerpt("Tổng: 130TC\nTổng: 180TC", "Tổng số tín chỉ?") is None
    assert printed_total_excerpt("Tổng: 130TC", "Kỳ 2 có môn gì?") is None


def test_explicit_whole_course_total_is_read_without_summing_semester_cells():
    source = "19 21 20 20 21(23) 21 20 20 18\nTổng số TC toàn khóa: 180TC\nGhi chú: tháng 5 năm 2025"
    assert printed_total_excerpt(source, "Tổng số tín chỉ TC?") == "Tổng số TC toàn khóa: 180TC"


def test_native_course_ranking_context_keeps_literal_typography_and_stops_before_next_option():
    source = "71TEST\nHọc kỳ 1\n123456 – 3\nĐai số\ntuyến tính\n234567 – 2\nAnother option\n345678 – 2\nThird option\nTổng: 7TC"
    result = printed_course_rerank_text(source, "Mã 123456 có tên nguyên văn và mấy tín chỉ?", {"course_codes": ["123456", "234567"]})
    literal = result.partition("\n")[2]
    assert literal == "123456 – 3\nĐai số\ntuyến tính" and literal in source
    assert "Đại" not in result and "234567" not in result and "Another option" not in result


def test_short_course_parents_keep_their_existing_native_ranking_context():
    assert printed_course_rerank_text("123456 – 08\nLiteral name\n\n234567 – 10\nOther name",
        "Mã 123456 tên nguyên văn và tín chỉ?", {"course_codes": ["123456", "234567"]}) is None


@pytest.mark.parametrize("query,caps", [
    ("Mã 123456 tên nguyên văn gì?", None), ("Mã 123456 tên nguyên văn gì?", {"course_codes": []}),
    ("Mã 999999 tên nguyên văn gì?", {"course_codes": ["123456"]}),
    ("Mã 123456 tên nguyên văn gì?", {"course_codes": ["123456"], "ambiguous_course_codes": ["123456"]}),
    ("123456 là tiên quyết của 234567 không?", {"course_codes": ["123456", "234567"]}),
    ("Điều kiện học môn 123456 và số tín chỉ?", {"course_codes": ["123456"]}),
    ("Tổng tín chỉ của 123456?", {"course_codes": ["123456"]}),
    ("Học kỳ 1 có những học phần nào?", {"course_codes": ["123456"]}),
])
def test_unknown_ambiguous_or_nonfield_questions_cannot_gain_course_schema_context(query, caps):
    assert printed_course_rerank_text("123456 – 3\nLiteral name", query, caps) is None


@pytest.mark.parametrize("text", ["123456 – 3", "123456 – 3\nFirst\n123456 – 3\nOther", "123456 – Literal name"])
def test_incomplete_or_repeated_native_course_cells_are_not_repaired(text):
    assert printed_course_rerank_text(text, "Mã 123456 tên nguyên văn gì?", {"course_codes": ["123456"]}) is None


def test_free_elective_ranking_context_does_not_invent_credit_or_selection_requirements():
    source = "71TEST\nHọc kỳ 5\nTự chọn tự do - 3TC\n123456 – 2\nOption A\n234567 – 3\nOption B"
    caps = {"evidence_kind": "cell", "course_codes": ["123456", "234567"]}
    result = printed_elective_rerank_text(source, "Nhóm tự chọn tự do ghi những phương án nào?", caps)
    assert result.partition("\n")[2] == source
    assert not any(word in result.partition("\n")[0] for word in ("TC", "chọn một", "chọn hai"))
    assert printed_elective_rerank_text(source, "Nhóm tự chọn tự do ghi phương án nào?", {**caps, "evidence_kind": "semester"}) is None
    assert printed_elective_rerank_text(source, "Nhóm tự chọn 2 ghi phương án nào?", caps) is None
    assert printed_elective_rerank_text(source, "Tự chọn tự do mã 123456 có bao nhiêu tín chỉ?", caps) is None
