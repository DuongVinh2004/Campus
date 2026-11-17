"""The parallel classify_route node issues the safety and intent calls together without changing decisions."""
import asyncio
import json
from types import SimpleNamespace

import pytest
from campus247.agent.graph import CampusAgentWorkflow
from campus247.agent.nodes.rag_v2 import RagV2Node
from campus247.agent.state import NormalizedTurn
from campus247.application.conversation.stream_result import prepare_chat_result
from campus247.domain.shared.values import generate_uuid7
from campus247.ports.llm import LlmResponse, LlmResponseStatus
from campus247.rag_v2.service import RagV2Service

from tests.rag_v2.test_graph_integration import ACTOR, context, setup
from tests.rag_v2.test_service import QUESTION, FakeGateway, Reranker, UnitIndex


class TimedGateway(FakeGateway):
    """Records when each classification call starts and ends; classifier severity is configurable."""

    def __init__(self, *, severity="normal", crisis=False, fail_classifier=False, fail_intent=False, **kwargs):
        super().__init__(**kwargs)
        self.severity, self.crisis = severity, crisis
        self.fail_classifier, self.fail_intent = fail_classifier, fail_intent
        self.events = []

    async def generate(self, request):
        route = getattr(request, "route_id", "")
        if route in {"sensitive_classifier", "route_intent"}:
            self.events.append(("start", route))
            await asyncio.sleep(0.05)
            self.events.append(("end", route))
            if (route == "sensitive_classifier" and self.fail_classifier) or (route == "route_intent" and self.fail_intent):
                raise RuntimeError("provider failed")
            value = ({"severity": self.severity, "is_crisis": self.crisis, "confidence": 0.9}
                     if route == "sensitive_classifier" else {"route": "grounded_faq"})
            return LlmResponse(LlmResponseStatus.COMPLETED, "fake", "fake", structured_output=value,
                               output_text=json.dumps(value))
        return await super().generate(request)


def build(gateway, parallel):
    stack = setup(gateway=gateway)
    workflow = CampusAgentWorkflow(llm_gateway=gateway, rag_engine="v2", rag_v2_node=stack.node,
        require_retrieval_context=True, parallel_classify=parallel,
        context_search_fn=lambda *args: pytest.fail("v1 retrieval must not run"))
    return SimpleNamespace(workflow=workflow, gateway=gateway, turn=stack.turn)


async def run(parallel, **options):
    stack = build(TimedGateway(**options), parallel)
    state = await stack.workflow.arun(stack.turn, retrieval_context=context())
    final = prepare_chat_result(state)
    return stack, state, final


@pytest.mark.asyncio
async def test_both_classification_calls_overlap_and_the_answer_is_unchanged():
    sequential, _, expected = await run(False)
    parallel, _, final = await run(True)
    starts = [i for i, (kind, _) in enumerate(parallel.gateway.events) if kind == "start"]
    first_end = next(i for i, (kind, _) in enumerate(parallel.gateway.events) if kind == "end")
    assert len(starts) == 2 and max(starts) < first_end          # both started before either finished
    assert [e for e in sequential.gateway.events if e[0] == "start"] == [("start", "sensitive_classifier"), ("start", "route_intent")]
    assert (final.status, final.response_class, final.content) == (expected.status, expected.response_class, expected.content)


@pytest.mark.asyncio
@pytest.mark.parametrize("options", [{"severity": "high"}, {"severity": "critical", "crisis": True}])
async def test_safety_handover_wins_and_the_intent_result_is_not_used(options):
    _, sequential_state, expected = await run(False, **options)
    stack, state, final = await run(True, **options)
    assert (final.status, final.response_class) == (expected.status, expected.response_class)
    assert state.route == sequential_state.route
    assert not any(r.request_id.startswith("rag_v2_") for r in stack.gateway.requests)


@pytest.mark.asyncio
@pytest.mark.parametrize("options", [{"fail_classifier": True}, {"fail_intent": True}])
async def test_a_failed_call_falls_back_exactly_as_the_sequential_graph(options):
    _, _, expected = await run(False, **options)
    _, _, final = await run(True, **options)
    assert (final.status, final.response_class, final.content) == (expected.status, expected.response_class, expected.content)


@pytest.mark.asyncio
async def test_default_graph_is_sequential():
    stack = build(TimedGateway(), parallel=False)
    await stack.workflow.arun(stack.turn, retrieval_context=context())
    assert [e for e in stack.gateway.events if e[0] == "start"] == [("start", "sensitive_classifier"), ("start", "route_intent")]
    assert stack.gateway.events.index(("end", "sensitive_classifier")) < stack.gateway.events.index(("start", "route_intent"))
