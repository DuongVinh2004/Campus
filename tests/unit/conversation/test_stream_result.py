from __future__ import annotations

from dataclasses import replace
import json

import pytest

from campus247.agent.state import AgentState, DraftResponse, NormalizedTurn, Route, Terminal, ToolFlowState
from campus247.agent.streaming import StreamValidationResult
from campus247.application.conversation.messages import ConversationMessageService
from campus247.application.conversation.stream_result import (
    FinalChatResult, StreamFailure, apply_stream_validation, prepare_chat_result,
)

ACTOR = "4b419a1b-6d41-7dfb-8943-2edd9f071385"


def grounded_state():
    turn = NormalizedTurn("synthetic-session", "synthetic-turn", ACTOR, "Synthetic query")
    candidate = {
        "source_id": "01923456-789a-7def-8123-456789abcdef",
        "document_version_id": "01923456-789a-7def-8123-456789abcdea",
        "chunk_id": "01923456-789a-7def-8123-456789abcdeb",
        "title": "Synthetic regulation", "canonical_uri": "synthetic://stream/regulation",
        "version_label": "synthetic-v1", "source_status": "SYNTHETIC",
        "locator": {"section_path": "Synthetic section"}, "content_text": "Synthetic supported policy.",
    }
    return AgentState(turn, route=Route.GROUNDED_FAQ, terminal=Terminal.ANSWERED,
        draft=DraftResponse("Synthetic supported policy. [CIT-001]", is_grounded=True, gate_decision="pass"),
        tool_flow=ToolFlowState(candidates=[candidate]))


def test_grounded_mapping_preserves_turn_reference_and_real_metadata():
    result = prepare_chat_result(grounded_state())
    assert result.status == "answered" and result.response_class == "grounded_answer"
    mapping = result.citations[0].to_dict()
    assert mapping["turn_citation_id"] == "CIT-001"
    assert mapping["citation"]["citation_id"] != "CIT-001"
    assert mapping["citation"]["source_title"] == "Synthetic regulation"
    from tests.api.test_chat_sse import validate_events
    validate_events([{"id": mapping["citation"]["citation_id"], "event": "message.completed", "data": {
        "conversation_id": ACTOR, "message_id": ACTOR, "status": result.status,
        "response_class": result.response_class, "content": result.content, "citations": [mapping],
    }}])


@pytest.mark.parametrize("field", ["source_id", "document_version_id", "title", "canonical_uri", "version_label", "source_status", "locator"])
def test_missing_provenance_abstains_instead_of_inventing_metadata(field):
    state = grounded_state()
    del state.tool_flow.candidates[0][field]
    result = prepare_chat_result(state)
    assert result.status == "abstained" and result.citations == ()
    assert "Synthetic supported policy" not in result.content


@pytest.mark.parametrize("change", [
    {"source_status": "EXPIRED"}, {"locator": {}}, {"locator": {"page_end": 2}},
    {"locator": {"page_start": 4, "page_end": 2}}, {"source_id": "invented-source"},
])
def test_invalid_citation_metadata_never_becomes_grounded_answer(change):
    state = grounded_state()
    state.tool_flow.candidates[0].update(change)
    assert prepare_chat_result(state).status == "abstained"


def test_unknown_claim_citation_and_rejected_draft_abstain():
    state = grounded_state()
    unknown = replace(state, draft=replace(state.draft, text="Synthetic policy [CIT-999]"))
    assert prepare_chat_result(unknown).status == "abstained"
    rejected = replace(state, draft=replace(state.draft, gate_decision="reject"))
    assert prepare_chat_result(rejected).status == "abstained"


def test_guard_rejection_withdraws_text_and_citations():
    result = prepare_chat_result(grounded_state())
    replacement = apply_stream_validation(result, StreamValidationResult(False, "abstained", "Safe fallback", "PRIVATE_PATTERN"))
    assert replacement == FinalChatResult("abstained", "safe_refusal", "Safe fallback")


def test_rejected_supplement_is_a_safe_terminal_without_raw_draft_or_citations():
    state = replace(grounded_state(), terminal=Terminal.SAFE_FAILURE,
        errors=("AI_AGENT_UNNECESSARY_TASK",), draft=DraftResponse("UNTRUSTED RAW OUTPUT"))
    result = prepare_chat_result(state)
    assert result.response_class == "system_error" and result.citations == ()
    assert "UNTRUSTED" not in result.content and "Kế hoạch" in result.content


@pytest.mark.asyncio
async def test_reserved_message_and_immutable_citation_map_are_persisted():
    from campus247.domain.shared.values import generate_uuid7
    service = ConversationMessageService()
    conv = await service.create_conversation(owner_user_id=ACTOR)
    result = prepare_chat_result(grounded_state())
    message_id = generate_uuid7()
    message = await service.append_message(conv.id, "ASSISTANT", result.content,
        message_id=message_id, final_result=result)
    assert message.id == message_id and message.citation_set_id
    assert message.citations == result.citations and message.finish_status == result.status
    # Mutating a JSON render cannot mutate the saved mapping.
    rendered = message.citations[0].to_dict()
    rendered["citation"]["source_title"] = "Tampered render"
    assert message.citations[0].to_dict()["citation"]["source_title"] == "Synthetic regulation"
    with pytest.raises(ValueError, match="already persisted"):
        await service.append_message(conv.id, "ASSISTANT", result.content, message_id=message_id, final_result=result)
    assert len(await service.list_messages(conv.id)) == 1
