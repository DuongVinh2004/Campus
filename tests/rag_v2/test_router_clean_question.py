"""The intent router's restatement of a messy question is used only when every number, code and negation survives."""
import json

import pytest
from campus247.agent.nodes.definitions import intent_request, route_intent_node
from campus247.agent.state import AgentState, NormalizedTurn, Route, SafetyDecision, SafetySeverity
from campus247.ports.llm import LlmResponse, LlmResponseStatus


def state(query):
    turn = NormalizedTurn(session_id="s", turn_id="t", user_id="u", query=query)
    return AgentState(request=turn, safety=SafetyDecision(severity=SafetySeverity.NORMAL, is_crisis=False))


def response(**fields):
    value = {"route": "grounded_faq", **fields}
    return LlmResponse(LlmResponseStatus.COMPLETED, "fake", "fake", structured_output=value, output_text=json.dumps(value))


@pytest.mark.parametrize(("query", "clean", "kept"), [
    ("hp k67 bn 1 tc", "Học phí K67 bao nhiêu một tín chỉ?", True),
    ("hp k67 bn 1 tc", "Học phí K68 bao nhiêu một tín chỉ?", False),          # cohort changed
    ("sv khong duoc thi lai a", "Sinh viên được thi lại không?", False),       # negation dropped
    ("hp k67 bn", "Học phí K67 bao nhiêu? Xem https://x.vn", False),            # link
])
def test_clean_question_is_kept_only_when_it_preserves_the_original(query, clean, kept):
    routed = route_intent_node(state(query), _response=response(clean_question=clean))
    assert routed.route == Route.GROUNDED_FAQ
    assert routed.tool_flow.clean_question == (clean if kept else None)


def test_missing_or_malformed_clean_question_leaves_the_state_untouched():
    for value in ({}, {"clean_question": 7}, {"clean_question": ""}):
        routed = route_intent_node(state("Học phí K67 bao nhiêu?"), _response=response(**value))
        assert routed.tool_flow.clean_question is None


def test_router_prompt_asks_for_a_restatement_and_keeps_information_questions_on_the_read_path():
    prompt = intent_request(state("hp k67 bn")).system_instructions
    assert "clean_question" in prompt and "khuyết tật" in prompt and "sensitive_case chỉ khi" in prompt
