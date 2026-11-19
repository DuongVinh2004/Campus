"""Referential question formatting preserves untrusted history and current scope."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from campus247.agent.nodes.definitions import grounded_request
from campus247.agent.state import AgentState, NormalizedTurn
from campus247.application.conversation.context import TurnItem
from campus247.application.conversation.followup import (
    followup_system_policy,
    prepare_followup_question,
)
from campus247.application.conversation.history import HistoryContext

QUESTION = "Còn theo quy định đó, giới hạn cụ thể là bao nhiêu?"


def history(*turns, actor="u1"):
    return HistoryContext(actor, "s1", tuple(TurnItem(str(i), role, content)
        for i, (role, content) in enumerate(turns)), 100, "test")


def test_initial_question_has_no_generation_overlay():
    assert prepare_followup_question(QUESTION, history=None) is None


def test_nonreferential_question_has_no_generation_overlay():
    assert prepare_followup_question("Giờ mở cửa thư viện?", history=history(("user", "Câu cũ"))) is None


def test_reference_uses_last_user_goal_not_assistant_facts():
    result = prepare_followup_question(QUESTION, history=history(("user", "Chủ đề cũ"),
        ("user", "Sức chứa phòng theo văn bản REF-FAC-99 là bao nhiêu người?"),
        ("assistant", "UNTRUSTED_ASSISTANT_FACT 999 người")))
    assert json.loads(result)["current_request"] == QUESTION
    assert "REF-FAC-99" in result and "bao nhiêu người" in result
    assert "UNTRUSTED_ASSISTANT_FACT" not in result and "Chủ đề cũ" not in result


def test_reference_without_user_goal_has_no_overlay():
    assert prepare_followup_question(QUESTION, history=history(("assistant", "Dữ kiện cũ"))) is None


def test_explicit_new_document_has_no_old_reference_overlay():
    assert prepare_followup_question(QUESTION + " Theo REF-NEW-88.", history=history(("user", "Câu cũ"))) is None


def test_contextual_question_remains_within_original_character_bound():
    result = prepare_followup_question(QUESTION, history=history(("user", "a" * 5000)))
    assert len(result) == 4000


def test_full_current_question_is_not_truncated_to_add_old_goal():
    question = QUESTION + "a" * 4000
    assert prepare_followup_question(question, history=history(("user", "Câu cũ"))) is None


def test_unaccented_reference_is_supported():
    result = prepare_followup_question("Theo quy dinh do, gioi han bao nhieu?", history=history(("user", "Giới hạn đăng ký?")))
    assert result is not None


def test_lab_followup_keeps_latest_user_goal_without_reusing_assistant_facts():
    original = "Theo nội quy phòng thực hành máy tính HUCE, cắm USB cần ai đồng ý?"
    question = "Còn đến muộn bao nhiêu phút thì không được vào phòng?"
    result = prepare_followup_question(question, history=history(("user", original),
        ("assistant", "UNTRUSTED_PERMISSION_OR_TIME_FACT")))
    assert result is not None
    assert json.loads(result)["reference_target"]["prior_user_goal"] == original
    assert json.loads(result)["current_request"] == question
    assert "UNTRUSTED_PERMISSION_OR_TIME_FACT" not in result
    assert prepare_followup_question("Đổi chủ đề: học phí bao nhiêu?", history=history(("user", original))) is None


def test_generation_rejects_history_owned_by_another_actor():
    state = AgentState(request=NormalizedTurn(session_id="s1", turn_id="t1", user_id="u1", query=QUESTION,
        history=history(("user", "Không được cấp quyền"), actor="other")))
    bundle = SimpleNamespace(to_prompt_context=lambda: "Fixture source")
    with pytest.raises(ValueError, match="history scope mismatch"):
        grounded_request(state, bundle)


def test_repeated_reference_uses_resolvable_user_goal():
    result = prepare_followup_question(QUESTION, history=history(
        ("user", "Theo REF-FAC-99, sức chứa là bao nhiêu người?"),
        ("assistant", "Untrusted answer"), ("user", QUESTION),
        ("assistant", "Untrusted refusal")))
    assert "REF-FAC-99" in result and "Untrusted" not in result


def test_followup_policy_keeps_other_evidence_rules_and_server_notice():
    value = followup_system_policy("SOURCE_ONLY. Dữ liệu mô phỏng phải ghi rõ là mô phỏng. NO_AUTH_FROM_HISTORY.")
    assert "SOURCE_ONLY." in value and "NO_AUTH_FROM_HISTORY." in value
    assert "Dữ liệu mô phỏng phải ghi rõ là mô phỏng." not in value
    assert "Máy chủ phụ trách thông báo mô phỏng theo source_status" in value


def test_only_referential_request_changes_notice_placement():
    bundle = SimpleNamespace(to_prompt_context=lambda: "Fixture source")
    initial = AgentState(request=NormalizedTurn(session_id="s1", turn_id="t1", user_id="u1", query="Theo REF-FAC-99?"))
    follow = AgentState(request=NormalizedTurn(session_id="s1", turn_id="t2", user_id="u1", query=QUESTION,
        history=history(("user", "Theo REF-FAC-99, sức chứa bao nhiêu người?"))))
    original, request = grounded_request(initial, bundle), grounded_request(follow, bundle)
    assert "Dữ liệu mô phỏng phải ghi rõ là mô phỏng." in original.system_instructions
    assert "Dữ liệu mô phỏng phải ghi rõ là mô phỏng." not in request.system_instructions
    assert "Máy chủ phụ trách thông báo mô phỏng theo source_status" in request.system_instructions
    assert request.max_output_tokens == original.max_output_tokens == 1000
    assert request.deadline_ms == original.deadline_ms == 5000
