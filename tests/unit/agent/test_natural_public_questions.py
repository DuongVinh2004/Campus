"""Regression cases from the screen and everyday Vietnamese, with explicit write intent."""
from dataclasses import replace
import json

import pytest

from campus247.agent.nodes.definitions import route_intent_node
from campus247.agent.nodes.intent import IntentRouterNode
from campus247.agent.state import AgentState, NormalizedTurn, Route
from campus247.ports.llm import LlmResponse, LlmResponseStatus


def state(question):
    return AgentState(request=NormalizedTurn("session", "turn", "actor", question))


@pytest.mark.parametrize("question", [
    "Thủ tục xin cấp bảng điểm Một cửa",
    "Cho em hỏi xin bảng điểm ở đâu và cần làm gì ạ?",
    "Tra cứu phòng tự học thư viện",
    "Thư viện có chỗ để em tự học với nhóm bạn không?",
    "Quy chế hoãn thi học kỳ",
    "Quy chế chuyển ngành",
    "hoc bong can dieu kien gi vay",
])
def test_natural_information_questions_are_reads(question):
    assert IntentRouterNode().route(state(question)).route == Route.GROUNDED_FAQ


@pytest.mark.parametrize("route,question", [
    ("document_request", "Thủ tục xin cấp bảng điểm"),
    ("room_booking", "Tra cứu phòng tự học thư viện"),
    ("human_handover", "Còn lịch hẹn gửi cho em qua đâu?"),
])
def test_model_topic_classification_cannot_turn_procedure_question_into_write(route, question):
    response = LlmResponse(LlmResponseStatus.COMPLETED, "fake", "fake",
        output_text=json.dumps({"route": route}))
    assert route_intent_node(state(question), _response=response).route == Route.GROUNDED_FAQ


def test_explicit_booking_request_remains_an_action():
    assert IntentRouterNode().route(state("Đăng ký mượn phòng học H1 để sinh hoạt CLB")).route == Route.ROOM_BOOKING


def test_explicit_handover_question_remains_handover():
    response = LlmResponse(LlmResponseStatus.COMPLETED, "fake", "fake",
        output_text=json.dumps({"route": "human_handover"}))
    assert route_intent_node(state("Cho em gặp cán bộ trực tiếp được không?"), _response=response).route == Route.HUMAN_HANDOVER
