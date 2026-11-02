from __future__ import annotations

from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "services" / "api" / "src"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))

from campus247.agent.graph import CampusAgentWorkflow
from campus247.agent.state import NormalizedTurn, Route, Terminal, ToolPhase
from campus247.infrastructure.llm.fake import DeterministicFakeProvider


@pytest.fixture
def fake_llm() -> DeterministicFakeProvider:
    return DeterministicFakeProvider.default()


@pytest.fixture
def sample_search_fn():
    knowledge_db = {
        "học phí": [
            {
                "chunk_id": "chunk_fee_01",
                "source_id": "src_fee",
                "document_version_id": "ver_01",
                "title": "Học phí năm học 2026-2027",
                "content_text": "Mức học phí năm học 2026-2027 là 480.000 VNĐ một tín chỉ.",
                "score": 0.95,
            }
        ]
    }
    return lambda q: knowledge_db.get("học phí", []) if "học phí" in q.lower() else []


def test_full_graph_execution_faq_with_fake_llm(sample_search_fn, fake_llm: DeterministicFakeProvider) -> None:
    workflow = CampusAgentWorkflow(
        search_fn=sample_search_fn,
        llm_gateway=fake_llm,
    )
    turn = NormalizedTurn(
        session_id="sess_001",
        turn_id="turn_001",
        user_id="std_1001",
        query="Mức học phí năm học này là bao nhiêu?",
    )

    final_state = workflow.run(turn)

    assert final_state.route == Route.GROUNDED_FAQ
    assert final_state.terminal == Terminal.ANSWERED
    assert final_state.draft is not None
    assert final_state.draft.is_grounded is True
    assert "[CIT-001]" in final_state.draft.text
    assert final_state.step_count > 0


def test_graph_callable_with_raw_query_string(sample_search_fn, fake_llm: DeterministicFakeProvider) -> None:
    workflow = CampusAgentWorkflow(
        search_fn=sample_search_fn,
        llm_gateway=fake_llm,
    )

    final_state = workflow.run("Mức học phí là bao nhiêu?")

    assert final_state.route == Route.GROUNDED_FAQ
    assert final_state.terminal == Terminal.ANSWERED
    assert final_state.draft is not None
    assert "480.000 VNĐ" in final_state.draft.text or "[CIT-001]" in final_state.draft.text


def test_graph_execution_personal_schedule(fake_llm: DeterministicFakeProvider) -> None:
    workflow = CampusAgentWorkflow(
        search_fn=lambda q: [],
        llm_gateway=fake_llm,
    )

    final_state = workflow.run("Cho tôi xem thời khóa biểu tuần này")

    assert final_state.route == Route.PERSONAL_SCHEDULE
    assert final_state.terminal == Terminal.ANSWERED
    assert final_state.tool_phase == ToolPhase.SUCCEEDED
    assert final_state.draft is not None
    assert "chưa kết nối dữ liệu lịch học cá nhân" in final_state.draft.text


def test_graph_execution_ticket_create_write_flow(fake_llm: DeterministicFakeProvider) -> None:
    workflow = CampusAgentWorkflow(
        search_fn=lambda q: [],
        llm_gateway=fake_llm,
    )

    final_state = workflow.run("Tôi muốn tạo ticket khiếu nại điểm thi môn toán")

    assert final_state.route == Route.TICKET_CREATE
    # Without a checkpointer, the graph does not suspend.
    # It passes through await_confirmation to revalidate_confirmation.
    # Because there is no user confirmation_context, it must fail closed.
    assert final_state.tool_phase == ToolPhase.FAILED
    assert final_state.terminal == Terminal.CANCELLED
    assert final_state.draft is not None


def test_graph_execution_crisis_emergency_handover(fake_llm: DeterministicFakeProvider) -> None:
    workflow = CampusAgentWorkflow(
        search_fn=lambda q: [],
        llm_gateway=fake_llm,
    )

    final_state = workflow.run("Tôi muốn tự tử, tôi quá bế tắc")

    assert final_state.route == Route.SENSITIVE_CASE
    assert final_state.terminal == Terminal.HANDED_OVER
    assert final_state.draft is not None
    assert "khẩn cấp" in final_state.draft.text or "bảo trì" in final_state.draft.text


def test_graph_execution_unsupported_abstains(fake_llm: DeterministicFakeProvider) -> None:
    workflow = CampusAgentWorkflow(
        search_fn=lambda q: [],
        llm_gateway=fake_llm,
    )

    final_state = workflow.run("Dự báo thời tiết ngày mai thế nào")

    assert final_state.route == Route.UNSUPPORTED
    assert final_state.terminal == Terminal.ABSTAINED
    assert final_state.draft is not None
    assert "chưa hỗ trợ" in final_state.draft.text or "chưa tìm thấy" in final_state.draft.text
