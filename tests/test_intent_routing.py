from __future__ import annotations

from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "services" / "api" / "src"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))

from campus247.agent.nodes.definitions import route_intent_node
from campus247.agent.nodes.intent import IntentRouterNode
from campus247.agent.state import AgentState, NormalizedTurn, Route, SafetyDecision, SafetySeverity
from campus247.infrastructure.llm.fake import DeterministicFakeProvider


def make_turn_state(query: str, safety: SafetyDecision | None = None) -> AgentState:
    turn = NormalizedTurn(
        session_id="sess_test",
        turn_id="turn_test",
        user_id="user_test",
        query=query,
    )
    return AgentState(
        request=turn,
        safety=safety or SafetyDecision(severity=SafetySeverity.NORMAL, is_crisis=False),
    )


@pytest.fixture
def fake_llm() -> DeterministicFakeProvider:
    return DeterministicFakeProvider.default()


@pytest.mark.parametrize(
    ("query", "expected_route"),
    [
        ("Học phí kỳ này bao nhiêu tiền một tín chỉ?", Route.GROUNDED_FAQ),
        ("Quy chế đào tạo theo tín chỉ của trường thế nào?", Route.GROUNDED_FAQ),
        ("Điều kiện để xét học bổng khuyến khích học tập?", Route.GROUNDED_FAQ),
        ("Xem thời khóa biểu tuần này của tôi", Route.PERSONAL_SCHEDULE),
        ("Lịch học ngày mai có những môn nào?", Route.PERSONAL_SCHEDULE),
        ("Tôi muốn làm đơn xin cấp bảng điểm và giấy xác nhận sinh viên", Route.DOCUMENT_REQUEST),
        ("Thủ tục xin hoãn nghĩa vụ quân sự cần giấy tờ gì?", Route.GROUNDED_FAQ),
        ("Đăng ký mượn phòng học H1 để làm việc nhóm", Route.ROOM_BOOKING),
        ("Tôi muốn tạo ticket khiếu nại điểm thi môn sức bền", Route.TICKET_CREATE),
        ("Tôi muốn báo cáo sự cố cơ sở vật chất phòng học", Route.TICKET_CREATE),
        ("Tôi muốn gặp cán bộ tư vấn trực tiếp", Route.HUMAN_HANDOVER),
        ("Chuyển người trực giúp tôi", Route.HUMAN_HANDOVER),
        ("Dự báo thời tiết Hà Nội hôm nay thế nào?", Route.UNSUPPORTED),
        ("Hướng dẫn nấu món phở bò truyền thống", Route.UNSUPPORTED),
    ],
)
def test_intent_routing_with_fake_llm(
    query: str,
    expected_route: Route,
    fake_llm: DeterministicFakeProvider,
) -> None:
    state = make_turn_state(query)
    routed_state = route_intent_node(state, gateway=fake_llm)
    assert routed_state.route == expected_route


def test_intent_routing_sensitive_case_priority(fake_llm: DeterministicFakeProvider) -> None:
    # When safety flags crisis or critical severity, route must be SENSITIVE_CASE
    crisis_safety = SafetyDecision(
        severity=SafetySeverity.CRITICAL,
        is_crisis=True,
        reason="self_harm_imminent",
    )
    state = make_turn_state("Tôi muốn tự tử nhảy lầu", safety=crisis_safety)
    routed_state = route_intent_node(state, gateway=fake_llm)
    assert routed_state.route == Route.SENSITIVE_CASE


def test_intent_routing_fallback_to_keyword_when_gateway_none() -> None:
    state = make_turn_state("Xem thời khóa biểu ngày mai")
    routed_state = route_intent_node(state, gateway=None)
    assert routed_state.route == Route.PERSONAL_SCHEDULE
