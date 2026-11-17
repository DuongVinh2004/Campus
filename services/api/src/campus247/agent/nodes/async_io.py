"""API-loop I/O nodes; parsing and deterministic policies stay shared."""
from __future__ import annotations

import asyncio
import dataclasses
import inspect
import logging
import time

from campus247.agent.nodes import definitions as nodes
from campus247.agent.state import (
    AgentState,
    DraftResponse,
    Route,
    SafetySeverity,
    Terminal,
)
from campus247.application.conversation.generation_policy import (
    generate_with_regeneration,
    output_problem,
)
from campus247.application.retrieval.citations import CitationBundle
from campus247.application.retrieval.evidence_gate import parse_grounded_claims
from campus247.domain.retrieval import RetrievalContext
from campus247.ports.llm import LlmGateway, LlmRequest, LlmResponse, LlmResponseStatus


async def _generate(gateway: LlmGateway, request: LlmRequest):
    async with asyncio.timeout(request.deadline_ms / 1000):
        return await gateway.generate(request)


async def sensitive_classifier_node(state: AgentState, gateway: LlmGateway | None = None) -> AgentState:
    if gateway is None or state.safety.is_crisis or state.safety.severity == SafetySeverity.CRITICAL:
        return nodes.sensitive_classifier_node(state)
    try:
        response = await _generate(gateway, nodes.classifier_request(state))
    except Exception:
        return nodes.sensitive_classifier_node(state)
    return nodes.sensitive_classifier_node(state, _response=response)


async def route_intent_node(state: AgentState, gateway: LlmGateway | None = None) -> AgentState:
    from campus247.application.conversation.understanding import conversational_response
    if conversational_response(state.request.query, state.request.history) is not None:
        return nodes.route_intent_node(state)
    if gateway is None or state.route == Route.SENSITIVE_CASE or state.safety.is_crisis:
        return nodes.route_intent_node(state)
    try:
        response = await _generate(gateway, nodes.intent_request(state))
    except Exception:
        return nodes.route_intent_node(state)
    return nodes.route_intent_node(state, _response=response)


async def retrieve_evidence_node(state: AgentState, search_fn=None,
                                 *, context: RetrievalContext | None = None) -> AgentState:
    try:
        nodes._validate_retrieval_context(state, context)
        candidates = search_fn(nodes.retrieval_query(state)) if search_fn is not None else []
        if inspect.isawaitable(candidates):
            candidates = await candidates
    except Exception as error:
        if getattr(error,"code",None)=="MODEL_BUDGET_UNAVAILABLE":
            result=nodes.RetrieveEvidenceNode._abstain(state,"AI_MODEL_BUDGET_UNAVAILABLE")
            return dataclasses.replace(result,draft=DraftResponse(
                text="Nguồn HUCE vẫn được lưu, nhưng ngân sách mô hình hiện tại không đủ cho lượt tra cứu. Chưa có câu trả lời được xác nhận; vui lòng chờ quản trị viên xử lý ngân sách.",
                is_grounded=True,gate_decision="abstain"))
        return nodes.RetrieveEvidenceNode._abstain(state, "AI_RETRIEVAL_UNAVAILABLE")
    return nodes.retrieve_evidence_node(state, search_fn=lambda _: candidates, context=context)


# Fixed server text, never model-authored.
PARTIAL_COMPLETENESS_NOTE = ("Câu trả lời trên chỉ nêu một phần nội dung liên quan trong tài liệu. "
    "Bạn nên mở tài liệu được trích dẫn để xem đầy đủ các điều kiện và trường hợp.")


async def compose_grounded_node(state: AgentState, gateway: LlmGateway | None = None,
                                *, context: RetrievalContext | None = None,
                                support_threshold: float | None = None, claim_verifier=None) -> AgentState:
    if state.terminal == Terminal.ABSTAINED:
        return dataclasses.replace(state, step_count=state.step_count + 1)
    nodes._validate_retrieval_context(state, context)
    if gateway is None:
        return nodes.generation_unavailable(state)
    candidates = getattr(state.tool_flow, "candidates", ()) if state.tool_flow else ()
    if not candidates:
        return nodes.generation_unavailable(state)
    phase = "prompt"
    try:
        bundle = CitationBundle.build(candidates, context=context)
        request = nodes.grounded_request(state, bundle)
        started, used = time.perf_counter(), []
        partial = False
        from campus247.application.retrieval.fee_presentation import present_verified_fee
        def normalize_response(response):
            response = present_verified_fee(response, bundle, nodes.retrieval_query(state), threshold=support_threshold)
            from campus247.application.retrieval.policy_quotation import present_policy_quotation
            response = present_policy_quotation(response, bundle, nodes.retrieval_query(state))
            from campus247.application.retrieval.curriculum_quotation import present_curriculum_quotation
            response = present_curriculum_quotation(response, bundle, nodes.retrieval_query(state))
            from campus247.application.retrieval.form_quotation import present_form_quotation
            response = present_form_quotation(response, bundle, nodes.retrieval_query(state))
            from campus247.application.retrieval.notice_quotation import present_notice_quotation
            return present_notice_quotation(response, bundle, nodes.retrieval_query(state))
        def policy_preflight(draft):
            from campus247.application.knowledge.question_scope import tuition_answer_scope_issue
            scope_issue = tuition_answer_scope_issue(nodes.retrieval_query(state), draft, bundle)
            if scope_issue:
                return scope_issue
            if "kỷ luật" not in draft.response_text.casefold():
                return None
            from campus247.agent.nodes.compose import _verified_general_discipline_rule
            preview = dataclasses.replace(state, draft=DraftResponse(text=draft.response_text,
                claim_count=len(draft.claims), is_grounded=True, gate_decision="grounded", grounded_claims=draft.claims))
            return None if _verified_general_discipline_rule(preview) else "AI_POLICY_CLAIM_FORMAT"
        async with asyncio.timeout(request.deadline_ms / 1000):
            phase = "generation"
            response = await generate_with_regeneration(gateway, request, bundle,
                support_threshold=support_threshold, usage_sink=used.append, draft_preflight=policy_preflight,
                response_normalizer=normalize_response)
            if (isinstance(response, LlmResponse)
                    and response.status == LlmResponseStatus.COMPLETED and not response.tool_candidates
                    and output_problem(response, bundle, support_threshold) is None):
                preflight_issue = policy_preflight(parse_grounded_claims(response.output_text or ""))
                if preflight_issue is not None:
                    return dataclasses.replace(state, terminal=Terminal.ABSTAINED,
                        draft=DraftResponse(text="Tôi đã tìm được nguồn nhưng chưa xác minh được đầy đủ điều kiện áp dụng. "
                            "Bạn có thể hỏi một phần cụ thể hơn hoặc mở tài liệu để kiểm tra.", gate_decision="reject"),
                        errors=(*state.errors, preflight_issue), step_count=state.step_count + 1)
                if claim_verifier is not None:
                    if any(type(count) is not int or count < 0 for count in used):
                        raise ValueError("invalid generation usage")
                    remaining_ms = int(request.deadline_ms - (time.perf_counter() - started) * 1000)
                    phase = "verification"
                    from campus247.application.conversation.followup import active_question
                    verification_question = active_question(state.request.query, history=state.request.history)
                    from campus247.application.retrieval.semantic_support import SemanticClaimVerifier
                    supported = False
                    check = checked_response = None
                    if isinstance(claim_verifier, SemanticClaimVerifier):
                        check = await claim_verifier.check(request, response, bundle,
                            deadline_ms=remaining_ms, output_tokens=request.max_output_tokens - sum(used),
                            question=verification_question)
                        checked_response = response
                        # A valid negative verdict can use the existing single
                        # regeneration only if deterministic checks did not use
                        # it already. Failed/malformed verification has zero
                        # accounted verdict tokens and cannot request a repair.
                        # Both semantic calls share the original phase budget;
                        # every repaired claim must pass verification again.
                        supported = check.claims_supported and check.answers_question
                        may_rephrase = len(used) == 1 and check.output_tokens > 0 and not supported
                        used.append(check.output_tokens)
                        remaining_ms = int(request.deadline_ms - (time.perf_counter() - started) * 1000)
                        remaining_tokens = request.max_output_tokens - sum(used)
                        if may_rephrase and remaining_ms > 0 and remaining_tokens >= 128:
                            from campus247.application.conversation.generation_policy import REGENERATION_MARKER
                            reason = "AI_ANSWER_RELEVANCE" if check.claims_supported else "AI_SEMANTIC_SUPPORT"
                            feedback = ("Phát biểu có căn cứ nhưng chưa trả lời trực tiếp câu hỏi. " if check.claims_supported else
                                "Phát biểu chưa được nguồn hỗ trợ đầy đủ. Đối chiếu lại đúng dòng và bỏ kết luận không được nguồn hỗ trợ. ")
                            retry = dataclasses.replace(request,
                                system_instructions=request.system_instructions +
                                    f" {REGENERATION_MARKER}: lần tái tạo duy nhất vì {reason}. " + feedback +
                                    "Làm rõ hệ đào tạo, chương trình và khoảng khóa đang hỏi bằng đúng nguồn; "
                                    "trả lời trực tiếp yêu cầu, giữ đủ điều kiện. Không lặp câu trả lời chung chung, "
                                    "không thêm trường hợp hoặc dữ kiện ngoài nguồn. Giữ answer_scope và output contract.",
                                deadline_ms=remaining_ms, max_output_tokens=remaining_tokens)
                            logging.getLogger("campus247.generation").warning(
                                "grounded_regeneration reason_code=%s remaining_ms=%d output_tokens=%d",
                                reason, remaining_ms, remaining_tokens)
                            phase = "generation"
                            response = await gateway.generate(retry)
                            if isinstance(response, LlmResponse):
                                used.append(response.usage.output_tokens)
                                if any(type(count) is not int or count < 0 for count in used) or sum(used) > request.max_output_tokens:
                                    raise ValueError("invalid shared generation usage")
                            response = normalize_response(response)
                            if (isinstance(response, LlmResponse) and response.status == LlmResponseStatus.COMPLETED
                                    and not response.tool_candidates and output_problem(response, bundle, support_threshold) is None
                                    and policy_preflight(parse_grounded_claims(response.output_text or "")) is None):
                                phase = "verification"
                                check = await claim_verifier.check(request, response, bundle,
                                    deadline_ms=int(request.deadline_ms - (time.perf_counter() - started) * 1000),
                                    output_tokens=request.max_output_tokens - sum(used), question=verification_question)
                                checked_response = response
                                used.append(check.output_tokens)
                                supported = check.claims_supported and check.answers_question
                    else:
                        supported = await claim_verifier.verify(request, response, bundle,
                            deadline_ms=remaining_ms, output_tokens=request.max_output_tokens - sum(used),
                            question=verification_question)
                    # Every claim was verified against its source; only completeness is missing. Show the
                    # verified claims as a labelled partial answer instead of discarding them. Wrong
                    # program/cohort/year/unit and unsupported claims still abstain.
                    if (not supported and check is not None and checked_response is response
                            and check.claims_supported and not check.answers_question
                            and check.question_issue == "INCOMPLETE"):
                        partial = True
                        supported = True
                    if not supported:
                        return dataclasses.replace(state, terminal=Terminal.ABSTAINED,
                            draft=DraftResponse(text="Tôi đã tìm được nguồn nhưng chưa xác minh được phát biểu đủ điều kiện. "
                                "Bạn có thể hỏi một phần cụ thể hơn hoặc mở tài liệu để kiểm tra.", gate_decision="reject"),
                            errors=(*state.errors, "AI_SEMANTIC_SUPPORT_REJECTED"), step_count=state.step_count + 1)
    except TimeoutError:
        return nodes.generation_unavailable(state, "AI_GENERATION_TIMEOUT")
    except Exception as exc:
        # Only finite classifications cross the diagnostic boundary. Never log
        # exception messages, provider payloads, raw drafts or tracebacks.
        kinds = {"ValueError": "VALUE_ERROR", "TypeError": "TYPE_ERROR", "KeyError": "KEY_ERROR",
            "EgressViolationError": "EGRESS_REJECTED", "BudgetExceeded": "BUDGET_EXCEEDED",
            "RuntimeError": "RUNTIME_ERROR", "HTTPStatusError": "HTTP_STATUS_ERROR",
            "ConnectError": "CONNECT_ERROR", "ReadError": "READ_ERROR"}
        kind = kinds.get(type(exc).__name__, "UNKNOWN")
        logging.getLogger("campus247.generation").warning("generation_failure phase=%s exception_kind=%s", phase, kind)
        failure = nodes.generation_unavailable(state)
        return dataclasses.replace(failure, errors=(*failure.errors, f"AI_GENERATION_{phase.upper()}_{kind}"))
    if not isinstance(response, LlmResponse):
        return nodes.generation_unavailable(state)
    composed = nodes.compose_grounded_node(state, context=context, _response=response)
    if partial and composed.draft is not None and composed.terminal != Terminal.ABSTAINED:
        composed = dataclasses.replace(composed, errors=(*composed.errors, "AI_PARTIAL_COVERAGE"),
            draft=dataclasses.replace(composed.draft, partial_note=PARTIAL_COMPLETENESS_NOTE))
    return composed


async def classify_and_route(state: AgentState, gateway: LlmGateway | None = None) -> AgentState:
    """Safety classification and intent routing with their two model calls issued together.

    The node functions and their order are those of the sequential graph (classifier, merge_safety,
    route_intent); only the waiting overlaps. When safety hands the turn over, the intent response is
    discarded without being used.
    """
    from campus247.application.conversation.understanding import conversational_response

    def handover(current: AgentState) -> bool:
        return (current.route == Route.SENSITIVE_CASE or current.safety.is_crisis
                or current.safety.severity in (SafetySeverity.CRITICAL, SafetySeverity.HIGH))

    if (gateway is None or state.safety.is_crisis or state.safety.severity == SafetySeverity.CRITICAL
            or conversational_response(state.request.query, state.request.history) is not None):
        merged = nodes.merge_safety_node(await sensitive_classifier_node(state, gateway))
        return merged if handover(merged) else await route_intent_node(merged, gateway)
    classified, routed = await asyncio.gather(
        _generate(gateway, nodes.classifier_request(state)),
        _generate(gateway, nodes.intent_request(state)), return_exceptions=True)
    for outcome in (classified, routed):
        if isinstance(outcome, BaseException) and not isinstance(outcome, Exception):
            raise outcome
    after_classifier = (nodes.sensitive_classifier_node(state) if isinstance(classified, Exception)
                        else nodes.sensitive_classifier_node(state, _response=classified))
    merged = nodes.merge_safety_node(after_classifier)
    if handover(merged):
        return merged
    return (nodes.route_intent_node(merged) if isinstance(routed, Exception)
            else nodes.route_intent_node(merged, _response=routed))
