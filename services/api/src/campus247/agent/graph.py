from __future__ import annotations

from collections.abc import Callable
import asyncio
import dataclasses
from functools import partial
from typing import Any

from langgraph.graph import END, START, StateGraph

from campus247.agent.nodes.definitions import (
    authorize_tool_node,
    await_confirmation_node,
    build_action_preview_node,
    compose_grounded_node,
    compose_tool_response_node,
    evidence_gate_node,
    execute_handover_node,
    execute_read_tool_node,
    execute_write_tool_node,
    finalize_node,
    merge_safety_node,
    normalize_input_node,
    output_guard_node,
    pre_safety_rules_node,
    prepare_handover_node,
    prepare_tool_candidate_node,
    rerank_evidence_node,
    retrieve_evidence_node,
    revalidate_confirmation_node,
    route_intent_node,
    sensitive_classifier_node,
)
from campus247.agent.state import (
    AgentState,
    DraftResponse,
    NormalizedTurn,
    Route,
    SafetySeverity,
    Terminal,
    ToolPhase,
)
from campus247.domain.shared.values import generate_uuid7
from campus247.domain.retrieval import RetrievalContext
from campus247.infrastructure.llm.fake import DeterministicFakeProvider
from campus247.ports.llm import LlmGateway
from campus247.agent.nodes import async_io


def build_agent_graph(
    search_fn: Callable[[str], list[dict[str, Any]]] | None = None,
    gateway: LlmGateway | None = None,
    checkpointer: Any | None = None,
    *,
    context_search_fn: Callable[[str, RetrievalContext], list[dict[str, Any]]] | None = None,
    retrieval_context: RetrievalContext | None = None,
    require_retrieval_context: bool = False,
    async_mode: bool = False,
    evidence_support_threshold: float | None = None,
    claim_verifier: Any | None = None,
    multi_agent_node: Any | None = None,
    service_draft_node: Any | None = None,
    knowledge_only: bool = False,
    rag_v2_node: Any | None = None,
    parallel_classify: bool = False,
) -> Any:
    """Builds and compiles the 21-node LangGraph StateGraph with all conditional routes."""
    if retrieval_context is not None and not isinstance(retrieval_context, RetrievalContext):
        raise ValueError("typed server-created retrieval context required")
    if evidence_support_threshold is not None:
        from campus247.application.retrieval.profile import load_retrieval_profile
        if evidence_support_threshold != load_retrieval_profile().evidence_support_threshold:
            raise ValueError("accepted evidence support threshold required")
    builder = StateGraph(AgentState)

    # Bind context to this invocation, never to shared workflow state/checkpoints.
    # A legacy callback cannot silently drop an established authorization scope.
    def search_with_context(query: str) -> list[dict[str, Any]]:
        if retrieval_context is not None:
            if context_search_fn is None:
                raise ValueError("context-aware retrieval binding required")
            return context_search_fn(query, retrieval_context)
        if require_retrieval_context:
            raise ValueError("trusted retrieval context unavailable")
        return search_fn(query) if search_fn is not None else []

    # 1. Register all 21 nodes
    builder.add_node("normalize_input", normalize_input_node)
    builder.add_node("pre_safety_rules", pre_safety_rules_node)
    builder.add_node(
        "sensitive_classifier",
        partial(async_io.sensitive_classifier_node if async_mode else sensitive_classifier_node, gateway=gateway),
    )
    builder.add_node("merge_safety", merge_safety_node)
    intent = partial(async_io.route_intent_node if async_mode else route_intent_node, gateway=gateway)
    def constrain_intent(state):
        if knowledge_only and rag_v2_node is None and state.route == Route.GROUNDED_FAQ and state.terminal is None:
            from campus247.application.knowledge.question_scope import tuition_clarification
            from campus247.agent.state import DraftResponse
            clarification=tuition_clarification(state.request.query)
            if clarification:
                return dataclasses.replace(state,terminal=Terminal.ABSTAINED,
                    draft=DraftResponse(text=clarification,is_grounded=True),
                    errors=(*state.errors,"AI_CLARIFICATION_REQUIRED"))
        if knowledge_only and state.route in {Route.PERSONAL_SCHEDULE, Route.TICKET_CREATE,
                Route.DOCUMENT_REQUEST, Route.ROOM_BOOKING}:
            from campus247.agent.state import DraftResponse
            return dataclasses.replace(state,terminal=Terminal.ABSTAINED,
                draft=DraftResponse(text="Chức năng này chưa kết nối dữ liệu hoặc hệ thống xử lý HUCE. Tôi chưa đọc lịch cá nhân, tạo hồ sơ hay gửi yêu cầu. Bạn cần dùng cổng HUCE chính thức.",is_grounded=True),
                errors=(*state.errors,"OPERATIONAL_CAPABILITY_UNAVAILABLE"))
        return state
    async def operational_async_intent(state):
        return constrain_intent(await intent(state))
    def operational_intent(state):
        return constrain_intent(intent(state))
    builder.add_node("route_intent", operational_async_intent if async_mode else operational_intent)

    builder.add_node(
        "retrieve_evidence",
        partial(async_io.retrieve_evidence_node if async_mode else retrieve_evidence_node,
            search_fn=search_with_context, context=retrieval_context),
    )
    builder.add_node("rerank_evidence", lambda state: rerank_evidence_node(state, context=retrieval_context))
    builder.add_node(
        "compose_grounded",
        partial(async_io.compose_grounded_node if async_mode else compose_grounded_node,
            gateway=gateway, context=retrieval_context,
            **({"support_threshold": evidence_support_threshold} if async_mode and evidence_support_threshold is not None else {}),
            **({"claim_verifier": claim_verifier} if async_mode else {})),
    )
    builder.add_node("evidence_gate", partial(evidence_gate_node, context=retrieval_context,
        **({"support_threshold": evidence_support_threshold} if evidence_support_threshold is not None else {})))

    builder.add_node("prepare_tool_candidate", prepare_tool_candidate_node)
    builder.add_node("authorize_tool", authorize_tool_node)
    builder.add_node("execute_read_tool", execute_read_tool_node)
    builder.add_node("build_action_preview", build_action_preview_node)
    builder.add_node("await_confirmation", await_confirmation_node)
    builder.add_node("revalidate_confirmation", revalidate_confirmation_node)
    builder.add_node("execute_write_tool", execute_write_tool_node)
    builder.add_node("compose_tool_response", compose_tool_response_node)

    builder.add_node("prepare_handover", prepare_handover_node)
    if multi_agent_node is not None or knowledge_only:
        def checked_handover(state):
            from campus247.application.multi_agent.service_adapter import prepare_unavailable_handover
            result = execute_handover_node(state)
            if knowledge_only and result.terminal == Terminal.HANDED_OVER:
                if state.safety.is_crisis or state.safety.severity in {SafetySeverity.HIGH,SafetySeverity.CRITICAL}:
                    return dataclasses.replace(result,terminal=Terminal.ABSTAINED,
                        errors=(*result.errors,"AI_HANDOVER_CAPABILITY_UNAVAILABLE"))
                return prepare_unavailable_handover(result)
            return prepare_unavailable_handover(result) if (result.terminal == Terminal.HANDED_OVER and
                not state.safety.is_crisis and state.safety.severity == SafetySeverity.NORMAL) else result
        builder.add_node("execute_handover", checked_handover)
    else:
        builder.add_node("execute_handover", execute_handover_node)

    builder.add_node("output_guard", output_guard_node)
    builder.add_node("finalize", finalize_node)
    if rag_v2_node is not None:
        async def answer_v2(state):
            return await rag_v2_node(state, context=retrieval_context)
        builder.add_node("rag_v2", answer_v2)
        # Only the verified v2 discipline exception skips a duplicate legacy
        # rejection. RagV2Node already checked every other shared output rule.
        builder.add_conditional_edges("rag_v2",
            lambda state: "finalize" if (state.terminal == Terminal.ANSWERED
                and "RAG_V2_DISCIPLINE_RULE_VERIFIED" in state.errors) else "output_guard",
            {"finalize": "finalize", "output_guard": "output_guard"})
    if multi_agent_node is not None:
        if not async_mode:
            raise ValueError("multi-agent execution requires the API async loop")
        builder.add_node("multi_agent", multi_agent_node)
        builder.add_edge("multi_agent", "output_guard")
    if service_draft_node is not None:
        builder.add_node("service_draft", service_draft_node)
        builder.add_edge("service_draft", "output_guard")

    # 2. Linear Pipeline Edges
    # Optional: issue the safety-classifier and intent calls concurrently (same node functions, same
    # decisions; the intent result is dropped when safety hands the turn over).
    parallel = bool(parallel_classify and async_mode and gateway is not None)
    builder.add_edge(START, "normalize_input")
    builder.add_edge("normalize_input", "pre_safety_rules")
    if parallel:
        async def classify_route(state):
            if rag_v2_node is not None and hasattr(rag_v2_node, "prefetch"):
                rag_v2_node.prefetch(state)  # embed the question while the safety and routing calls run
            result = await async_io.classify_and_route(state, gateway)
            return result if _handover_needed(result) else constrain_intent(result)
        builder.add_node("classify_route", classify_route)
        builder.add_edge("pre_safety_rules", "classify_route")
    else:
        builder.add_edge("pre_safety_rules", "sensitive_classifier")
        builder.add_edge("sensitive_classifier", "merge_safety")

    def _handover_needed(state: AgentState) -> bool:
        return (state.route == Route.SENSITIVE_CASE or state.safety.is_crisis
                or state.safety.severity in (SafetySeverity.CRITICAL, SafetySeverity.HIGH))

    # 3. Conditional Branch from merge_safety
    def _route_after_safety(state: AgentState) -> str:
        if (
            state.route == Route.SENSITIVE_CASE
            or state.safety.is_crisis
            or state.safety.severity in (SafetySeverity.CRITICAL, SafetySeverity.HIGH)
        ):
            return "prepare_handover"
        return "route_intent"

    if not parallel:
        builder.add_conditional_edges(
            "merge_safety",
            _route_after_safety,
            {
                "prepare_handover": "prepare_handover",
                "route_intent": "route_intent",
            },
        )

    # 4. Conditional Branch from route_intent (8 routes)
    def _route_intent_branch(state: AgentState) -> str:
        if state.terminal == Terminal.ABSTAINED:
            return "output_guard"
        route = state.route
        if route == Route.GROUNDED_FAQ:
            if rag_v2_node is not None:
                return "rag_v2"
            return "multi_agent" if multi_agent_node is not None else "retrieve_evidence"
        if service_draft_node is not None and (route == Route.DOCUMENT_REQUEST or
                multi_agent_node is not None and route in {Route.TICKET_CREATE, Route.ROOM_BOOKING, Route.PERSONAL_SCHEDULE}):
            return "service_draft"
        if route in (
            Route.PERSONAL_SCHEDULE,
            Route.TICKET_CREATE,
            Route.DOCUMENT_REQUEST,
            Route.ROOM_BOOKING,
        ):
            return "prepare_tool_candidate"
        if route in (Route.HUMAN_HANDOVER, Route.SENSITIVE_CASE):
            return "prepare_handover"
        if route == Route.UNSUPPORTED:
            return "output_guard"
        return "retrieve_evidence"

    intent_targets = {
        "retrieve_evidence": "retrieve_evidence",
        "prepare_tool_candidate": "prepare_tool_candidate",
        "prepare_handover": "prepare_handover",
        "output_guard": "output_guard",
        "compose_grounded": "compose_grounded",
        **({"rag_v2": "rag_v2"} if rag_v2_node is not None else {}),
        **({"multi_agent": "multi_agent"} if multi_agent_node is not None else {}),
        **({"service_draft": "service_draft"} if service_draft_node is not None else {}),
    }
    if parallel:
        builder.add_conditional_edges(
            "classify_route",
            lambda state: "prepare_handover" if _route_after_safety(state) == "prepare_handover"
            else _route_intent_branch(state),
            intent_targets,
        )
    else:
        builder.add_conditional_edges("route_intent", _route_intent_branch, intent_targets)

    # 5. Retrieval Conditional Edges
    def _route_after_retrieve(state: AgentState) -> str:
        if state.terminal == Terminal.ABSTAINED:
            return "output_guard"
        return "rerank_evidence"

    builder.add_conditional_edges(
        "retrieve_evidence",
        _route_after_retrieve,
        {
            "output_guard": "output_guard",
            "rerank_evidence": "rerank_evidence",
        },
    )

    # 5b. Conditional edge from rerank_evidence: check bundle sufficiency
    def _route_after_rerank(state: AgentState) -> str:
        if state.terminal == Terminal.ABSTAINED:
            return "output_guard"
        # Check bundle sufficiency — require at least one candidate
        flow = state.tool_flow
        candidates = getattr(flow, "candidates", []) if flow else []
        if not candidates:
            return "output_guard"
        return "compose_grounded"

    builder.add_conditional_edges(
        "rerank_evidence",
        _route_after_rerank,
        {
            "output_guard": "output_guard",
            "compose_grounded": "compose_grounded",
        },
    )

    # 5c. Conditional edge from compose_grounded: check draft validity
    def _route_after_compose(state: AgentState) -> str:
        if state.terminal in {Terminal.ABSTAINED, Terminal.SAFE_FAILURE}:
            return "output_guard"
        if state.draft is None or not state.draft.text:
            return "output_guard"
        return "evidence_gate"

    builder.add_conditional_edges(
        "compose_grounded",
        _route_after_compose,
        {
            "output_guard": "output_guard",
            "evidence_gate": "evidence_gate",
        },
    )
    builder.add_edge("evidence_gate", "output_guard")

    # 6. Tool Flow Edges
    builder.add_edge("prepare_tool_candidate", "authorize_tool")

    def _route_after_authorize(state: AgentState) -> str:
        if state.tool_phase == ToolPhase.FAILED:
            return "compose_tool_response"
        if state.route == Route.PERSONAL_SCHEDULE:
            return "execute_read_tool"
        return "build_action_preview"

    builder.add_conditional_edges(
        "authorize_tool",
        _route_after_authorize,
        {
            "compose_tool_response": "compose_tool_response",
            "execute_read_tool": "execute_read_tool",
            "build_action_preview": "build_action_preview",
        },
    )

    builder.add_edge("execute_read_tool", "compose_tool_response")
    builder.add_edge("build_action_preview", "await_confirmation")
    builder.add_edge("await_confirmation", "revalidate_confirmation")

    def _route_after_revalidate(state: AgentState) -> str:
        if state.tool_phase == ToolPhase.CONFIRMED:
            return "execute_write_tool"
        return "compose_tool_response"

    builder.add_conditional_edges(
        "revalidate_confirmation",
        _route_after_revalidate,
        {
            "execute_write_tool": "execute_write_tool",
            "compose_tool_response": "compose_tool_response",
        },
    )

    builder.add_edge("execute_write_tool", "compose_tool_response")
    builder.add_edge("compose_tool_response", "output_guard")

    # 7. Handover Flow Edges
    builder.add_edge("prepare_handover", "execute_handover")
    builder.add_edge("execute_handover", "output_guard")

    # 8. Output Guard to Finalize to END
    builder.add_edge("output_guard", "finalize")
    builder.add_edge("finalize", END)

    interrupt_nodes = ["await_confirmation"] if checkpointer is not None else None
    return builder.compile(checkpointer=checkpointer, interrupt_before=interrupt_nodes)


class CampusAgentWorkflow:
    """Compiled, controlled state machine workflow coordinating 21 agent nodes across 8 routes."""

    def __init__(
        self,
        search_fn: Callable[[str], list[dict[str, Any]]] | None = None,
        llm_gateway: LlmGateway | None = None,
        checkpointer: Any | None = None,
        max_steps: int = 24,
        budget: Any | None = None,
        *,
        context_search_fn: Callable[[str, RetrievalContext], list[dict[str, Any]]] | None = None,
        require_retrieval_context: bool = False,
        evidence_support_threshold: float | None = None,
        claim_verifier: Any | None = None,
        knowledge_only: bool = False,
        rag_engine: str = "v1",
        rag_v2_node: Any | None = None,
        parallel_classify: bool = False,
    ) -> None:
        from campus247.agent.budget import BudgetTracker, RunBudget
        self._search_fn = search_fn or (lambda q: [])
        self._gateway = llm_gateway or DeterministicFakeProvider.default()
        self._checkpointer = checkpointer
        self._max_steps = max_steps
        self._budget = budget or RunBudget()
        self._context_search_fn = context_search_fn
        self._require_retrieval_context = require_retrieval_context
        self._evidence_support_threshold = evidence_support_threshold
        self._claim_verifier = claim_verifier
        self._knowledge_only = knowledge_only
        if rag_engine not in {"v1", "v2"} or rag_engine == "v2" and rag_v2_node is None:
            raise ValueError("configured v2 engine requires its initialized service binding")
        self._rag_v2_node = rag_v2_node if rag_engine == "v2" else None
        self._parallel_classify = parallel_classify
        self._app = build_agent_graph(
            search_fn=self._search_fn,
            gateway=self._gateway,
            checkpointer=self._checkpointer,
            context_search_fn=self._context_search_fn,
            require_retrieval_context=self._require_retrieval_context,
            evidence_support_threshold=self._evidence_support_threshold,
            claim_verifier=self._claim_verifier,
            knowledge_only=self._knowledge_only,
            rag_v2_node=self._rag_v2_node,
        )

    def _prepare(self, input_val, retrieval_context, *, async_mode=False, gateway=None, multi_agent_node=None, service_draft_node=None):
        if isinstance(input_val, str):
            turn = NormalizedTurn(
                session_id=str(generate_uuid7()),
                turn_id=str(generate_uuid7()),
                user_id=str(generate_uuid7()),
                query=input_val,
            )
        else:
            turn = input_val

        if retrieval_context is not None:
            if not isinstance(retrieval_context, RetrievalContext):
                raise ValueError("typed server-created retrieval context required")
            if retrieval_context.authorized_scope.actor_id != turn.user_id:
                raise ValueError("retrieval context actor does not match turn")
            # Revalidate bypassed constructors without replacing the original object.
            RetrievalContext.from_dict(retrieval_context.to_dict())
        initial_state = AgentState(request=turn, trusted_context_ref=(
            retrieval_context.trace_id if retrieval_context is not None else None
        ))
        app = self._app if retrieval_context is None and not async_mode and multi_agent_node is None else build_agent_graph(
            search_fn=self._search_fn, gateway=gateway or self._gateway, checkpointer=self._checkpointer,
            context_search_fn=self._context_search_fn, retrieval_context=retrieval_context,
            require_retrieval_context=self._require_retrieval_context,
            async_mode=async_mode,
            evidence_support_threshold=self._evidence_support_threshold,
            claim_verifier=self._claim_verifier,
            multi_agent_node=multi_agent_node,
            service_draft_node=service_draft_node,
            knowledge_only=self._knowledge_only,
            rag_v2_node=self._rag_v2_node,
            parallel_classify=self._parallel_classify,
        )
        return turn, initial_state, app

    def run(self, input_val: NormalizedTurn | str, *, retrieval_context: RetrievalContext | None = None) -> AgentState:
        """Retained synchronous worker/fixture entrypoint; API uses arun."""
        if self._rag_v2_node is not None:
            return asyncio.run(self.arun(input_val, retrieval_context=retrieval_context))
        turn, initial_state, app = self._prepare(input_val, retrieval_context)

        try:
            raw_res = app.invoke(
                initial_state,
                config={"recursion_limit": self._max_steps},
            )
            return self._finish(raw_res, initial_state, turn)
        except Exception:
            return self._failure(initial_state)

    async def arun(self, input_val: NormalizedTurn | str, *, retrieval_context: RetrievalContext | None = None) -> AgentState:
        """Run every provider/retrieval await on the owning API loop."""
        turn, initial_state, app = self._prepare(input_val, retrieval_context, async_mode=True)
        try:
            async with asyncio.timeout(self._budget.max_latency_seconds):
                raw_res = await app.ainvoke(initial_state, config={"recursion_limit": self._max_steps})
            return self._finish(raw_res, initial_state, turn)
        except Exception:
            return self._failure(initial_state)

    def _finish(self, raw_res, initial_state, turn):
        if isinstance(raw_res, dict):
            final_state = AgentState(**raw_res)
        elif isinstance(raw_res, AgentState):
            final_state = raw_res
        else:
            final_state = initial_state
        if final_state.step_count >= self._max_steps:
            return dataclasses.replace(final_state, terminal=Terminal.SAFE_FAILURE,
                errors=(*final_state.errors, "Max step limit reached"))
        try:
            from campus247.observability.agent_trace import AgentTracer
            AgentTracer().record(trace_id=f"tr-{turn.turn_id}", span_id=f"sp-{turn.turn_id}",
                session_id=turn.session_id, turn_id=turn.turn_id, raw_user_id=turn.user_id,
                event_type="terminal_transition", route=str(final_state.route) if final_state.route else None,
                decision=str(final_state.terminal) if final_state.terminal else None,
                tool_phase=str(final_state.tool_phase) if final_state.tool_phase else None)
        except Exception:
            pass
        return final_state

    @staticmethod
    def _failure(initial_state):
        return dataclasses.replace(initial_state, terminal=Terminal.SAFE_FAILURE,
            errors=(*initial_state.errors, "AI_WORKFLOW_UNAVAILABLE"),
            draft=DraftResponse(text="Đã xảy ra sự cố trong quá trình xử lý yêu cầu.", is_grounded=False))
