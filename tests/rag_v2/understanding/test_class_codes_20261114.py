"""Students name their cohort through class codes ("71CS", "K71CD", "66XD1"); the analyzer must read them."""
import pytest

from campus247.rag_v2.understanding.analyze import analyze


@pytest.mark.parametrize("question, cohort", [
    ("Theo chương trình Khoa học máy tính 71CS, Học máy học kỳ nào?", "K71"),
    ("học phần k71cd nhánh đường b1 có mã gì", "K71"),
    ("k69kdcqc tổng bao nhiêu tín chỉ", "K69"),
    ("lớp 66xd1 thi khi nào", "K66"),
    ("học phí K69 bao nhiêu", "K69"),
])
def test_cohort_is_read_from_class_codes(question, cohort):
    assert analyze(question, ()).cohort == cohort


@pytest.mark.parametrize("question", [
    "em học 70tc một kỳ có được không",   # credits typed without a space, not a cohort
    "so sánh K70 và 71cs về học phí",     # several cohorts are never a filter
    "học phí năm 2026 là bao nhiêu",
])
def test_no_cohort_when_it_is_not_one_cohort(question):
    assert analyze(question, ()).cohort is None


@pytest.mark.parametrize("question", [
    "ngành kinh tế xây dựng khóa K70 trở xuống tổng bao nhiêu tín chỉ",
    "học phí K64 trở về trước bao nhiêu",
    "chương trình từ K69 trở đi có gì khác",
])
def test_a_cohort_range_is_not_one_cohort_filter(question):
    u = analyze(question, ())
    # a range names cohorts, so the cohort is neither filtered to one value nor asked for again
    assert u.cohort is None and "cohort|academic_year" not in u.missing_slots


def test_cohort_ranges_in_a_question_match_every_cohort_inside_them():
    from campus247.application.knowledge.source_snapshot import scope_allows
    scope = {"kind": "COHORT_SNAPSHOT", "cohorts": ["K69"], "programme_codes": [], "_verified_geometry": None}
    assert scope_allows("ngành kinh tế xây dựng khóa K70 trở xuống tổng bao nhiêu tín chỉ", scope, any_requested=True)
    assert not scope_allows("ngành kinh tế xây dựng khóa K70 tổng bao nhiêu tín chỉ", scope, any_requested=True)
    assert scope_allows("từ K68 trở đi tổng tín chỉ", scope, any_requested=True)
    assert not scope_allows("từ K70 trở đi tổng tín chỉ", scope, any_requested=True)


@pytest.mark.parametrize("question, unclear", [
    ("cái này áp dụng cho tụi em ko z?", True),     # "này" points at nothing the conversation holds
    ("tính điểm đó", True),
    ("ad ơi thông báo nói dùng usb trong phòng máy là tự do đúng ko, ko cần hỏi ai", False),   # "tự do" is no pointer
])
def test_pointer_words_without_a_subject_ask_back_but_tu_do_does_not(question, unclear):
    assert bool(analyze(question, ()).clarify_prompt) is unclear
