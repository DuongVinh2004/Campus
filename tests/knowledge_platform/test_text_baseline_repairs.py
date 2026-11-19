"""Regression checks for discovery/routing; doubles are not live answer acceptance."""
import hashlib
import json
from pathlib import Path

import pytest

from campus247.agent.nodes.intent import IntentRouterNode, is_personal_schedule_request
from campus247.agent.state import AgentState, NormalizedTurn, Route, Terminal
from campus247.application.retrieval.candidate_selection import select_parent_spans

ROOT = Path(__file__).resolve().parents[2]
SCOPE = ROOT / "infra/local/knowledge-automation-20261026"


@pytest.mark.parametrize("question", [
    "Ngày mai tài khoản sinh viên HUCE của em phải học ở phòng nào?",
    "Sáng thứ hai em học ở đâu?",
    "Tối nay tôi thi phòng mấy?",
    "Buổi học của mình bắt đầu lúc nào?",
    "Tuan sau em phai hoc tiet nao?",
    "Cho em xem lịch thi ngày mai",
])
def test_personal_slot_requests_do_not_require_the_word_schedule(question):
    assert is_personal_schedule_request(question)
    state = AgentState(NormalizedTurn("session", "turn", "actor", question))
    assert IntentRouterNode().route(state).route == Route.PERSONAL_SCHEDULE


@pytest.mark.parametrize("question", [
    "Quy chế quy định em phải học ở phòng nào?",
    "Hướng dẫn xem lịch học của em ở đâu?",
    "Thủ tục đổi phòng thi của tôi là gì?",
    "Tôi muốn đặt phòng để học nhóm tối nay?",
    "Học phần tiên quyết được hiểu thế nào?",
])
def test_procedures_and_room_booking_do_not_become_personal_data_lookups(question):
    assert not is_personal_schedule_request(question)


def test_operational_schedule_explains_missing_connection_and_never_searches_documents():
    from campus247.agent.graph import CampusAgentWorkflow
    def forbidden_search(_):
        pytest.fail("A personal schedule must not be answered from public documents")
    result = CampusAgentWorkflow(knowledge_only=True, search_fn=forbidden_search).run(
        "Sáng thứ hai em học ở đâu?")
    assert result.terminal == Terminal.ABSTAINED
    assert "OPERATIONAL_CAPABILITY_UNAVAILABLE" in result.errors
    assert "chưa kết nối" in result.draft.text and "lịch cá nhân" in result.draft.text
    assert not result.tool_candidate


def test_adjacent_action_words_survive_distractors_with_the_same_scattered_syllables():
    def row(identifier, text):
        return {"id": identifier, "source_id": "source", "document_version_id": "version",
            "content_checksum": identifier, "rerank_text": text}
    target = row("target", "Hồ sơ chuyển đổi được công nhận tối đa theo quy định.")
    distractors = [row(str(i), "Hồ mới và sơ đồ. Chuyển hướng và đổi mới. Công việc, nhận xét. Tối nay, đa dạng.") for i in range(5)]
    chosen = select_parent_spans(distractors + [target], [], "Chuyển đổi được công nhận tối đa thế nào?")
    assert target in chosen and len(chosen) == 3


def test_retained_transfer_failure_keeps_the_original_ceiling_clause_in_three_slots():
    raw = (SCOPE / "retrieval-diagnostic-20261026T143636783197/receipt.json").read_bytes()
    case = json.loads(raw)["cases"][0]
    branches = case["branches"]
    chosen = select_parent_spans(branches[0]["rows"], branches[1]["rows"], case["question"])
    ceiling = next(row for row in chosen if row["section_path"] == "Quy chế 1486 — Điều 12, khoản 3 — PDF 18")
    assert len(chosen) == 3
    assert hashlib.sha256(ceiling["content_text"].encode()).hexdigest() == ceiling["content_checksum"]
    assert "50%" in ceiling["content_text"] and "tối thiểu" in ceiling["content_text"]


def test_bounded_lexical_replay_retains_the_full_negated_warning_condition():
    report = json.loads((SCOPE / "retrieval-diagnostic-20261026T143850203597/receipt.json").read_text(encoding="utf-8"))
    case = next(c for c in report["cases"] if c["name"] == "fresh_no_registration_reason")
    chosen = select_parent_spans(case["branches"][0]["rows"], [], case["question"])
    target = next(row for row in chosen if row["section_path"] == "Quy chế 1486 — Điều 19, khoản 5 — PDF 24")
    assert "nếu không có lý do chính đáng" in target["content_text"]
    assert hashlib.sha256(target["content_text"].encode()).hexdigest() == target["content_checksum"]
