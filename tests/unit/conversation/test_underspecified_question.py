import pytest
from campus247.application.conversation.history import HistoryContext, TurnItem
from campus247.application.conversation.understanding import (
    UNDERSPECIFIED_RESPONSE,
    conversational_response,
    underspecified_question,
)


@pytest.mark.parametrize("question", [
    "quy định", "thủ tục", "giúp em với", "xin hỏi", "khi nào", "ở đâu", "bao nhiêu", "được không",
    "Cho em hỏi", "Thủ tục thế nào ạ?", "điểm", "thi", "Em muốn hỏi một chút",
])
def test_questions_without_a_subject_ask_for_the_topic_with_suggestions(question):
    assert underspecified_question(question)
    assert conversational_response(question) == UNDERSPECIFIED_RESPONSE
    assert "học phí" in UNDERSPECIFIED_RESPONSE and "thôi học" in UNDERSPECIFIED_RESPONSE


@pytest.mark.parametrize("question", [
    "phúc khảo", "bảo lưu", "thôi học", "tốt nghiệp", "học phí", "Quy định về học phí",
    "Thủ tục xin bảng điểm", "K64", "428802", "ktx", "Điểm rèn luyện tính thế nào?", "thi lại",
    "Sinh viên bị cảnh báo học vụ khi nào?",
])
def test_questions_with_any_subject_are_looked_up_not_clarified_by_this_rule(question):
    assert not underspecified_question(question)
    assert conversational_response(question) != UNDERSPECIFIED_RESPONSE


def test_history_means_a_short_question_may_continue_the_prior_topic():
    history = [{"role": "user", "content": "Học phí K64 kỹ sư là bao nhiêu?"}]
    assert conversational_response("thủ tục", history) != UNDERSPECIFIED_RESPONSE


def _context(*turns):
    return HistoryContext("actor", "conversation", tuple(turns), 0, "estimate")


def test_an_empty_history_context_object_does_not_count_as_prior_topic():
    assert conversational_response("quy định", _context()) == UNDERSPECIFIED_RESPONSE


def test_a_history_context_with_turns_does_not_trigger_the_rule():
    history = _context(TurnItem("m1", "user", "Học phí K64 kỹ sư là bao nhiêu?", True))
    assert conversational_response("thủ tục", history) != UNDERSPECIFIED_RESPONSE
