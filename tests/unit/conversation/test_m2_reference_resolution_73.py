"""Structured reference, failure and continuing budget regressions, all offline."""
import copy
import json
import time
from dataclasses import replace

import pytest
from campus247.agent.nodes import async_io, definitions
from campus247.agent.state import AgentState, Terminal, ToolFlowState
from campus247.application.conversation.followup import prepare_followup_question
from campus247.application.conversation.generation_output import invalid_output_code
from campus247.application.conversation.generation_policy import REGENERATION_MARKER
from campus247.application.conversation.stream_result import prepare_chat_result
from campus247.ports.llm import LlmResponse, LlmResponseStatus, TokenUsage

from tests.unit.conversation.test_followup_question_m2 import QUESTION, history
from tests.unit.retrieval.test_context_propagation import CHUNKS, turn_and_context


def test_resolved_request_preserves_current_conditions_and_uses_only_user_goal():
    current = QUESTION + " Nếu đặt cho 20 người vào thứ Sáu thì sao?"
    resolved = json.loads(prepare_followup_question(current, history=history(
        ("user", "Theo REF-FAC-99, sức chứa là bao nhiêu người?"),
        ("assistant", "Tôi không có đủ thông tin REF-OTHER-77"))))
    assert resolved["current_request"] == current
    assert resolved["resolved_request"] == current.replace("quy định đó", "văn bản REF-FAC-99")
    assert resolved["reference_target"]["document_id"] == "REF-FAC-99"
    assert not resolved["reference_is_evidence"]
    assert "REF-OTHER-77" not in str(resolved)


@pytest.mark.parametrize("goals", [
    [("user", "Theo REF-FAC-99 hay REF-EXM-88?")],
    [("user", QUESTION)],
])
def test_ambiguous_or_reference_only_history_does_not_select_a_document(goals):
    assert prepare_followup_question(QUESTION, history=history(*goals)) is None


def test_latest_topic_wins_over_older_document_and_topic_switch_does_not_inherit():
    prior = history(("user", "Theo REF-FAC-99?"), ("user", "Giờ mở cửa thư viện?"))
    result = json.loads(prepare_followup_question(QUESTION, history=prior))
    assert result["reference_target"]["document_id"] is None
    assert "REF-FAC-99" not in str(result)
    assert prepare_followup_question("Chuyển sang thư viện, " + QUESTION, history=prior) is None


def test_refusal_history_ablation_has_identical_generation_payload():
    turn, ctx = turn_and_context()
    a = history(("user", "Theo REF-FAC-99, sức chứa là bao nhiêu?"))
    a = replace(a, actor_id=turn.user_id, conversation_id=turn.session_id)
    b = replace(a, turns=(*a.turns, *history(("assistant", "Không có đủ nguồn 999" )).turns))
    from campus247.application.retrieval.citations import CitationBundle
    bundle = CitationBundle.build(CHUNKS, context=ctx)
    one = AgentState(request=replace(turn, query=QUESTION, history=a))
    two = replace(one, request=replace(one.request, history=b))
    first, second = definitions.grounded_request(one, bundle), definitions.grounded_request(two, bundle)
    assert first == second
    assert "conversation-history" not in first.input_items[0]["content"]
    assert "Không có đủ nguồn" not in str(first)


@pytest.mark.parametrize("output,code", [
    ('{"claims":[]}', "AI_GENERATION_EMPTY_CLAIMS"),
    ('{"claims":[{}]}', "AI_GENERATION_INVALID_SCHEMA"),
    ('```json invalid', "AI_GENERATION_INVALID_SCHEMA"),
    ("", "AI_GENERATION_EMPTY_OUTPUT"),
])
@pytest.mark.asyncio
async def test_invalid_output_has_one_bounded_regeneration_and_safe_persistable_final(output, code):
    turn, ctx = turn_and_context()
    state = AgentState(request=turn, trusted_context_ref=ctx.trace_id, tool_flow=ToolFlowState(candidates=CHUNKS))
    class Fake:
        def __init__(self):
            self.requests = []
            self.started = []
            self.usage = []

        async def generate(self, request):
            self.requests.append(request)
            self.started.append(time.perf_counter())
            used = 137 if len(self.requests) == 1 else 221
            assert used <= request.max_output_tokens
            self.usage.append(used)
            return LlmResponse(LlmResponseStatus.COMPLETED, "fake", "fake", output_text=output,
                usage=TokenUsage(output_tokens=used))
    gateway = Fake()
    result = await async_io.compose_grounded_node(state, gateway, context=ctx)
    assert len(gateway.requests) == 2 and result.terminal == Terminal.SAFE_FAILURE
    original, retry = gateway.requests
    assert original.max_output_tokens == 1000 and retry.max_output_tokens == 1000 - gateway.usage[0]
    assert sum(gateway.usage) <= original.max_output_tokens
    assert retry.request_id == original.request_id and retry.route_id == original.route_id
    assert retry.input_items == original.input_items and retry.allowed_tools == original.allowed_tools == ()
    assert REGENERATION_MARKER in retry.system_instructions
    assert 0 < retry.deadline_ms <= original.deadline_ms == 5000
    assert (gateway.started[1] - gateway.started[0]) * 1000 + retry.deadline_ms <= original.deadline_ms + 1
    assert code in result.errors and not result.draft.is_grounded
    final = prepare_chat_result(result)
    assert final.status == "abstained" and final.response_class == "safe_refusal" and final.content
    assert not final.citations and "[CIT-" not in final.content
    if output:
        assert output not in final.content
    assert all(chunk["content_text"] not in final.content for chunk in CHUNKS)
    assert invalid_output_code(output) == code


@pytest.mark.asyncio
async def test_timeout_is_distinct_from_empty_output_and_has_no_retry():
    turn, ctx = turn_and_context()
    class Fake:
        calls = 0
        async def generate(self, request):
            self.calls += 1
            raise TimeoutError()
    gateway = Fake()
    result = await async_io.compose_grounded_node(AgentState(request=turn, trusted_context_ref=ctx.trace_id,
        tool_flow=ToolFlowState(candidates=CHUNKS)), gateway, context=ctx)
    assert "AI_GENERATION_TIMEOUT" in result.errors and gateway.calls == 1


def test_authorized_cap_migration_preserves_unknown_cost_and_rejects_changed_record():
    import m2_completion_20261012_73 as registry
    from m2_budget_20261012_73 import ConservativeBudget

    from evals.runners.paid_budget import BudgetExceeded
    migration = registry.load(registry.MASTER / "cap-migration.json")
    snapshot, records = migration["after"], migration["pending_reservation_records"]
    budget = ConservativeBudget.resume_full_records(snapshot, records)
    assert budget.snapshot() == snapshot
    with pytest.raises(ValueError, match="STAYS_FULLY_CHARGED"):
        budget.settle_verified(budget.pending[581], 0, 0)
    with pytest.raises(BudgetExceeded):
        budget.reserve(4000000, 0)
    bad = copy.deepcopy(records)
    bad["581"]["input_cap"] += 1
    with pytest.raises(ValueError, match="UNBOUND_HISTORICAL"):
        ConservativeBudget.resume_full_records(snapshot, bad)
