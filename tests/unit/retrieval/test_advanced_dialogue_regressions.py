"""Dialogue continuity tests; passive history is never policy evidence."""
import json

import pytest
from campus247.application.conversation.context import TurnItem
from campus247.application.conversation.followup import (
    prepare_followup_question,
    question_topics,
)
from campus247.application.conversation.history import HistoryContext
from campus247.application.conversation.understanding import (
    dated_calendar_request,
    retrieval_subqueries,
)


def history(*goals):
    return HistoryContext("actor", "session", tuple(
        TurnItem(str(index), role, text) for index, (role, text) in enumerate(goals)
    ), 100, "test")


def test_elliptical_turn_attaches_to_latest_explicit_subject_even_after_con_prefix():
    prior = history(("user", "Điều kiện xét học bổng?"),
                    ("assistant", "UNTRUSTED 999 điểm"),
                    ("user", "Còn học phí cho năm nhất thì bao nhiêu?"))
    result = json.loads(prepare_followup_question("Vậy đóng ở đâu?", history=prior))
    assert result["reference_target"]["prior_user_goal"] == "Còn học phí cho năm nhất thì bao nhiêu?"
    assert result["current_request"] == "Vậy đóng ở đâu?"
    assert "học bổng" not in str(result) and "UNTRUSTED" not in str(result)
    assert result["reference_is_evidence"] is False


def test_latest_named_goal_retains_year_and_new_quantity_without_older_conditions():
    prior = history(("user", "Điều kiện học bổng cho năm cuối?"),
                    ("user", "Còn học bổng cho năm nhất?"),
                    ("user", "Vậy GPA cần bao nhiêu?"))
    result = json.loads(prepare_followup_question("Nếu đạt 3,0 thì sao?", history=prior))
    assert "năm nhất" in result["reference_target"]["prior_user_goal"]
    assert "năm cuối" not in str(result)
    assert "GPA" in result["reference_target"]["prior_user_goal"]
    assert result["current_request"] == "Nếu đạt 3,0 thì sao?"


def test_unknown_topic_boundary_prevents_inheriting_an_older_named_subject():
    prior = history(("user", "Điều kiện xét học bổng?"),
                    ("user", "Còn về chuyện khác chưa rõ?"))
    assert prepare_followup_question("Vậy năm nhất thì sao?", history=prior) is None


@pytest.mark.parametrize("question", [
    "Một tín chỉ cần bao nhiêu giờ tự học?",
    "Bao nhiêu giờ tự nghiên cứu cho mỗi tín chỉ?",
])
def test_academic_self_study_is_not_scoped_to_library_rooms(question):
    assert question_topics(question) == frozenset({"khoi luong hoc tap"})
    assert len(retrieval_subqueries(question)) == 1


def test_specialization_and_transfer_remain_distinct_after_accent_folding():
    assert "chuyen nganh" not in question_topics("Sinh viên chuyên ngành kiến trúc học gì?")
    assert "chuyen nganh" in question_topics("Sinh viên muốn chuyển ngành thì làm gì?")
    assert "chuyen nganh" in question_topics("Chuyen nganh co dieu kien gi?")


def test_credit_limit_is_not_mistaken_for_study_hours_by_a_partial_word_match():
    assert "khoi luong hoc tap" not in question_topics("Giới hạn tín chỉ đăng ký là bao nhiêu?")


def test_multi_topic_subqueries_preserve_original_conditions_and_numbers():
    question = "Thư viện có phòng tự học ở đâu và chương trình thứ hai cần GPA 2,0 cho năm nhất?"
    queries = retrieval_subqueries(question)
    assert len(queries) == 2
    assert {query.split(":", 1)[0] for query in queries} == {"thu vien", "hai chuong trinh"}
    assert all(question in query for query in queries)
    assert all("năm thứ nhất" in query for query in queries)


def test_too_many_explicit_subjects_keep_a_combined_query_instead_of_discarding_some():
    question = "Học bổng, học phí, thư viện và ký túc xá cho năm nhất có quy định gì?"
    assert retrieval_subqueries(question) == (question + "\nThuật ngữ tra cứu: năm thứ nhất",)
    assert retrieval_subqueries("Học bổng và học phí?", limit=1) == ("Học bổng và học phí?",)


@pytest.mark.parametrize("limit", [0, 4, True, 1.5])
def test_query_planner_rejects_unbounded_or_untyped_call_limits(limit):
    with pytest.raises(ValueError, match="bounded"):
        retrieval_subqueries("Học bổng?", limit=limit)


@pytest.mark.parametrize("question,event", [
    ("Lịch nghỉ Tết năm 2030 bắt đầu và kết thúc chính xác ngày nào?", "tet"),
    ("lich nghi tet nam2030 bat dau ngay nao", "tet"),
    ("Lịch thi học kỳ I năm 2030 diễn ra khi nào?", "exam"),
])
def test_only_explicit_dated_event_reads_supply_a_calendar_constraint(question, event):
    value = dated_calendar_request(question)
    assert value is not None and value.years == frozenset({"2030"}) and value.event == event


@pytest.mark.parametrize("question", [
    "Quy chế đào tạo năm 2023 quy định tốt nghiệp thế nào?",
    "Học phí năm 2030 phải đóng qua kênh nào?",
    "Quy định hoãn thi năm 2023, nếu ốm ngày thi thì nộp đơn khi nào?",
    "Lịch nghỉ Tết bắt đầu ngày nào?",
    "Quy chế đào tạo năm 2023\nLịch nghỉ Tết bắt đầu ngày nào?",
    "Lịch nghỉ Tết năm 2027 bắt đầu ngày nào?\nVậy thời hạn phúc khảo là bao nhiêu ngày?",
])
def test_general_policies_and_years_in_passive_history_do_not_restrict_source_year(question):
    assert dated_calendar_request(question) is None
