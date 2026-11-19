"""A short follow-up is not bounced back for a topic when the conversation already holds one."""
from types import SimpleNamespace

from campus247.application.conversation.understanding import conversational_response, has_user_context

CLARIFY = "Bạn đang hỏi tiếp về học bổng, học phí hay quy định nào?"


def history(*turns):
    return SimpleNamespace(turns=[SimpleNamespace(role=role, content=text) for role, text in turns],
                           actor_id="a", conversation_id="c", block=lambda actor, conversation: "")


def test_follow_up_with_no_history_still_asks_for_a_topic():
    assert conversational_response("vậy DELF thì sao?", history()).startswith(CLARIFY)


def test_follow_up_with_an_earlier_user_question_is_left_to_the_question_rewrite():
    h = history(("user", "Chứng chỉ ngoại ngữ nộp để xét miễn có thời hạn hiệu lực bao lâu?"),
                ("assistant", "Trong thời hạn 02 năm."))
    assert conversational_response("vậy DELF thì sao?", h) is None
    assert has_user_context(h)


def test_only_assistant_turns_do_not_count_as_context():
    assert not has_user_context(history(("assistant", "Xin chào")))
    assert not has_user_context(history(("user", "   ")))
    assert not has_user_context(None)
