"""Public eligibility rules pass only after evidence verification, never personal verdicts."""
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from campus247.agent.nodes.compose import OutputGuardNode
from campus247.agent.nodes.definitions import evidence_gate_node
from campus247.agent.state import AgentState, DraftResponse, NormalizedTurn, Route, Terminal, ToolFlowState
from campus247.application.retrieval.evidence_gate import GroundedClaim
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy
from campus247.infrastructure.retrieval.public_knowledge import PublicKnowledgeStore

ROOT = Path(__file__).resolve().parents[3]


def context():
    return RetrievalContext(AuthorizedScope("HUCE", "HUCE", "actor", frozenset({"STUDENT"}),
        frozenset({"STUDENT"}), frozenset({"PUBLIC"}), frozenset({"PUBLIC"})),
        "vi", datetime.now(timezone.utc), SimulationPolicy.DENY, "1" * 32)


@pytest.fixture
def source():
    store = PublicKnowledgeStore(ROOT / "data/huce-public-20261013", tenant_id="HUCE", campus_id="HUCE")
    return next(row for row in store.rows if row["page_start"] == 111)


def state(source, text="Sinh viên không bị kỷ luật từ mức khiển trách trở lên.", citation="CIT-001", kind="policy"):
    claim = GroundedClaim("CLM-001", text, (citation,), kind)
    return AgentState(request=NormalizedTurn("session", "turn", "actor", "Điều kiện xét học bổng"),
        route=Route.GROUNDED_FAQ, trusted_context_ref="1" * 32, tool_flow=ToolFlowState(candidates=[source]),
        draft=DraftResponse(text=text + f" [{citation}]", claim_count=1, is_grounded=True, grounded_claims=(claim,)))


def test_real_scholarship_condition_passes_existing_evidence_threshold_then_output_guard(source):
    verified = evidence_gate_node(state(source), context=context(), support_threshold=.78)
    assert verified.draft.gate_decision == "grounded"
    result = OutputGuardNode().execute(verified)
    assert result.terminal == Terminal.ANSWERED
    assert "kỷ luật" in result.draft.text


def test_real_graduation_condition_passes_without_deciding_about_an_individual():
    store = PublicKnowledgeStore(ROOT / "data/huce-public-20261013", tenant_id="HUCE", campus_id="HUCE")
    row = next(r for r in store.rows if r["section_path"].startswith("Điều 13."))
    text = "Tại thời điểm xét tốt nghiệp không bị truy cứu trách nhiệm hình sự hoặc không đang trong thời gian bị kỷ luật ở mức đình chỉ học tập."
    verified = evidence_gate_node(state(row, text), context=context(), support_threshold=.78)
    assert verified.draft.gate_decision == "grounded"
    assert OutputGuardNode().execute(verified).terminal == Terminal.ANSWERED


def test_ungated_policy_is_still_rejected(source):
    assert OutputGuardNode().execute(state(source)).terminal == Terminal.SAFE_FAILURE


def test_forged_citation_and_low_support_are_rejected_before_exception(source):
    for candidate in (state(source, citation="CIT-999"), state(source, text="Sinh viên không bị kỷ luật được nhận học bổng tự động 999 triệu đồng.")):
        result = evidence_gate_node(candidate, context=context(), support_threshold=.78)
        assert result.terminal == Terminal.ABSTAINED
        assert result.draft.gate_decision == "reject"


@pytest.mark.parametrize("text", [
    "Bạn đã bị kỷ luật và không được học bổng.",
    "Em không bị kỷ luật nên chắc chắn được học bổng.",
    "Sinh viên Nguyễn Văn An bị kỷ luật.",
    "Sinh viên SV240000 không bị kỷ luật từ mức khiển trách trở lên.",
    "Sinh viên này không bị kỷ luật từ mức khiển trách trở lên.",
    "Sinh viên đã bị kỷ luật từ mức cảnh cáo trở lên.",
])
def test_individual_verdict_rejected_even_with_forged_grounded_marker(source, text):
    # Deliberately give the fake assertion perfect lexical support: source
    # similarity alone must never authorize an individual disciplinary verdict.
    candidate = state(dict(source, content_text=source["content_text"] + "\n" + text), text)
    candidate = replace(candidate, draft=replace(candidate.draft, gate_decision="grounded"))
    assert OutputGuardNode().execute(candidate).terminal == Terminal.SAFE_FAILURE


@pytest.mark.parametrize("change", ["simulation", "nonofficial", "personal_data", "wrong_route", "uncited_prose"])
def test_exception_remains_bound_to_verified_public_rules(source, change):
    candidate = state(source)
    candidate = replace(candidate, draft=replace(candidate.draft, gate_decision="grounded"))
    if change == "simulation":
        candidate = replace(candidate, tool_flow=ToolFlowState(candidates=[dict(source, simulation_label=True)]))
    elif change == "nonofficial":
        candidate = replace(candidate, tool_flow=ToolFlowState(candidates=[dict(source, canonical_uri="https://example.com/policy")]))
    elif change == "personal_data":
        candidate = replace(candidate, draft=replace(candidate.draft,
            grounded_claims=(replace(candidate.draft.grounded_claims[0], claim_type="personal_data"),)))
    elif change == "wrong_route":
        candidate = replace(candidate, route=Route.DOCUMENT_REQUEST)
    else:
        candidate = replace(candidate, draft=replace(candidate.draft, text=candidate.draft.text + "\nBạn bị kỷ luật."))
    assert OutputGuardNode().execute(candidate).terminal == Terminal.SAFE_FAILURE
