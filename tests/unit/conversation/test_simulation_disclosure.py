"""Disclosure is server provenance, not an instruction the model can omit."""
from dataclasses import replace

from campus247.application.conversation.stream_result import prepare_chat_result
from campus247.application.retrieval.simulation import (
    SIMULATION_NOTICE,
    label_grounded_answer,
)

from tests.unit.conversation.test_stream_result import grounded_state


def test_missing_disclosure_is_rendered_without_changing_claim_or_citation():
    state = grounded_state()
    result = prepare_chat_result(state)
    assert result.content == SIMULATION_NOTICE + "\n" + state.draft.text
    assert result.status == "answered" and len(result.citations) == 1
    assert result.citations[0].to_dict()["citation"]["quote"] == "Synthetic supported policy."
    assert state.draft.text == "Synthetic supported policy. [CIT-001]"


def test_only_cited_sources_determine_disclosure():
    state = grounded_state()
    state.tool_flow.candidates[0]["source_status"] = "CURRENT"
    state.tool_flow.candidates.append({**state.tool_flow.candidates[0], "source_status": "SYNTHETIC"})
    assert prepare_chat_result(state).content == state.draft.text


def test_mixed_citations_are_disclosed_and_prefix_is_idempotent():
    text = "Thông tin đã kiểm chứng. [CIT-001]"
    labeled = label_grounded_answer(text, cited_statuses=("CURRENT", "SYNTHETIC"))
    assert labeled.startswith(SIMULATION_NOTICE)
    assert label_grounded_answer(labeled, cited_statuses=("SYNTHETIC",)) == labeled


def test_model_cannot_suppress_disclosure_with_a_denial():
    state = grounded_state()
    state = replace(state, draft=replace(state.draft, text="Đây không phải mô phỏng. [CIT-001]"))
    assert prepare_chat_result(state).content.startswith(SIMULATION_NOTICE)


def test_unknown_or_rejected_citations_still_abstain_without_a_disclosure_repair():
    state = grounded_state()
    for draft in (replace(state.draft, text="Policy [CIT-999]"),
                  replace(state.draft, gate_decision="reject")):
        result = prepare_chat_result(replace(state, draft=draft))
        assert result.status == "abstained" and not result.citations
        assert not result.content.startswith(SIMULATION_NOTICE)
