"""A bare topic asks for intent before source/model work; specific questions still search."""
import pytest

from campus247.agent.graph import CampusAgentWorkflow
from campus247.agent.state import Terminal
from campus247.application.conversation.understanding import conversational_response


@pytest.mark.parametrize("question", ["học bổng", "Học bổng?", "hoc bong", "Tôi muốn biết về học bổng",
    "cho em hỏi học bổng", "tư vấn học bổng HUCE"])
def test_bare_scholarship_topic_clarifies_without_calling_retrieval(question):
    def forbidden(_):
        pytest.fail("An underspecified topic should clarify before retrieval")
    state = CampusAgentWorkflow(knowledge_only=True, search_fn=forbidden).run(question)
    assert state.terminal == Terminal.ABSTAINED and "AI_CLARIFICATION_REQUIRED" in state.errors
    assert "điều kiện xét" in state.draft.text and "năm học" in state.draft.text


@pytest.mark.parametrize("question", ["Điều kiện xét học bổng khuyến khích học tập là gì?",
    "Học bổng có cần điểm rèn luyện không?", "Học bổng năm học 2026–2027", "Mức học bổng là bao nhiêu?",
    "Học bổng và học phí", "Tôi muốn biết về học bổng cho sinh viên năm nhất"])
def test_specific_scholarship_requests_are_not_replaced_with_generic_clarification(question):
    assert conversational_response(question) is None
