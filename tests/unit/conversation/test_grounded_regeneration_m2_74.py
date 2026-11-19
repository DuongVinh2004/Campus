"""All regeneration controls use deterministic fakes and the real claim gate."""
import asyncio
import json
from dataclasses import replace

import pytest
from campus247.application.conversation.generation_policy import (
    REGENERATION_MARKER,
    generate_with_regeneration,
)
from campus247.application.retrieval.citations import CitationBundle
from campus247.ports.llm import LlmRequest, LlmResponse, LlmResponseStatus, TokenUsage

from tests.unit.retrieval.test_context_propagation import CHUNKS, turn_and_context


def bundle():
    _, context = turn_and_context()
    return CitationBundle.build(CHUNKS, context=context)


def response(text, used=5, status=LlmResponseStatus.COMPLETED):
    return LlmResponse(status, "fake", "fake", output_text=text, usage=TokenUsage(output_tokens=used))


def supported():
    return response(json.dumps({"claims": [{"text": CHUNKS[0]["content_text"],
        "citation_ids": ["CIT-001"], "claim_type": "policy"}]}))


def request(deadline=5000):
    return LlmRequest("t1", "grounded_faq", "default", "SOURCE_ONLY", (),
        deadline_ms=deadline, max_output_tokens=1000)


class Fake:
    def __init__(self, *values):
        self.values = list(values)
        self.requests = []

    async def generate(self, item):
        self.requests.append(item)
        value = self.values.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ['{"claims":[]}', '{"claims":[{}]}', " ",
    '{"claims":[{"text":"unrelated unsupported invented vocabulary","citation_ids":["CIT-001"],"claim_type":"policy"}]}'])
async def test_one_regeneration_preserves_deadline_total_output_and_same_evidence(bad):
    gateway = Fake(response(bad, 17), supported())
    initial = request()
    final = await generate_with_regeneration(gateway, initial, bundle(), support_threshold=.78)
    assert final == supported() and len(gateway.requests) == 2
    retry = gateway.requests[1]
    assert REGENERATION_MARKER in retry.system_instructions
    assert retry.input_items == initial.input_items and retry.request_id == initial.request_id
    assert 0 < retry.deadline_ms <= initial.deadline_ms and retry.max_output_tokens == 983


@pytest.mark.asyncio
async def test_second_invalid_output_is_returned_for_rejection_without_third_call():
    gateway = Fake(response('{"claims":[]}'), response('{"claims":[]}'), supported())
    result = await generate_with_regeneration(gateway, request(), bundle(), support_threshold=.78)
    assert result.output_text == '{"claims":[]}' and len(gateway.requests) == 2


@pytest.mark.asyncio
async def test_supported_first_response_does_not_regenerate():
    gateway = Fake(supported())
    assert await generate_with_regeneration(gateway, request(), bundle(), support_threshold=.78) == supported()
    assert len(gateway.requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", [RuntimeError("transport"), TimeoutError(),
    response("", status=LlmResponseStatus.FAILED)])
async def test_transport_error_or_failed_status_never_retries(fault):
    gateway = Fake(fault, supported())
    if isinstance(fault, BaseException):
        with pytest.raises(type(fault)):
            await generate_with_regeneration(gateway, request(), bundle(), support_threshold=.78)
    else:
        await generate_with_regeneration(gateway, request(), bundle(), support_threshold=.78)
    assert len(gateway.requests) == 1


@pytest.mark.asyncio
async def test_output_budget_exhaustion_prevents_second_call():
    gateway = Fake(response('{"claims":[]}', used=1000), supported())
    await generate_with_regeneration(gateway, request(), bundle(), support_threshold=.78)
    assert len(gateway.requests) == 1


@pytest.mark.asyncio
async def test_paid_reservation_failure_cannot_be_retried_or_converted_to_answer():
    from evals.runners.paid_budget import BudgetExceeded
    gateway = Fake(response('{"claims":[]}'), BudgetExceeded("HARD_CAP"), supported())
    with pytest.raises(BudgetExceeded):
        await generate_with_regeneration(gateway, request(), bundle(), support_threshold=.78)
    assert len(gateway.requests) == 2


@pytest.mark.asyncio
async def test_phase_deadline_and_cancellation_join_waiting_call():
    entered, stopped = asyncio.Event(), asyncio.Event()
    class Waiting:
        calls = 0
        async def generate(self, item):
            self.calls += 1
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()
    gateway = Waiting()
    with pytest.raises(TimeoutError):
        await generate_with_regeneration(gateway, request(10), bundle(), support_threshold=.78)
    assert gateway.calls == 1 and stopped.is_set()
    entered.clear()
    stopped.clear()
    gateway = Waiting()
    task = asyncio.create_task(generate_with_regeneration(gateway, request(), bundle(), support_threshold=.78))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert gateway.calls == 1 and stopped.is_set()


@pytest.mark.asyncio
async def test_graph_history_scope_is_checked_before_paid_generation():
    from campus247.agent.nodes import async_io
    from campus247.agent.state import AgentState, Terminal, ToolFlowState

    from tests.unit.conversation.test_followup_question_m2 import QUESTION, history
    turn, context = turn_and_context()
    wrong = replace(history(("user", "Theo REF-FAC-99?")), actor_id=turn.user_id,
        conversation_id="another-conversation")
    state = AgentState(request=replace(turn, query=QUESTION, history=wrong),
        trusted_context_ref=context.trace_id, tool_flow=ToolFlowState(candidates=CHUNKS))
    gateway = Fake(supported())
    result = await async_io.compose_grounded_node(state, gateway, context=context, support_threshold=.78)
    assert result.terminal == Terminal.SAFE_FAILURE and not gateway.requests
