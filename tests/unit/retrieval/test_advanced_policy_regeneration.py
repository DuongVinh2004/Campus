"""Bounded answer verification uses offline doubles and unchanged public-rule guards."""
import asyncio
import json
import logging
from datetime import UTC, datetime
from html import unescape
from itertools import pairwise
from functools import lru_cache
from pathlib import Path

import pytest
from campus247.agent.nodes import async_io
from campus247.agent.nodes.compose import OutputGuardNode
from campus247.agent.nodes.definitions import evidence_gate_node
from campus247.agent.state import (
    AgentState,
    DraftResponse,
    NormalizedTurn,
    Route,
    Terminal,
    ToolFlowState,
)
from campus247.application.conversation.generation_policy import (
    generate_with_regeneration,
)
from campus247.application.conversation.stream_result import prepare_chat_result
from campus247.application.retrieval.citations import CitationBundle
from campus247.application.retrieval.evidence_gate import parse_grounded_claims
from campus247.application.retrieval.prompt_evidence import (
    compose_bounded_inputs,
    evidence_prompt_blocks,
)
from campus247.application.retrieval.semantic_support import SemanticClaimVerifier
from campus247.domain.retrieval import (
    AuthorizedScope,
    RetrievalContext,
    SimulationPolicy,
)
from campus247.infrastructure.llm.egress_policy import EgressPolicy
from campus247.infrastructure.llm.openai_adapter import OpenAICompatibleAdapter
from campus247.infrastructure.retrieval.public_knowledge import PublicKnowledgeStore
from campus247.ports.llm import (
    LlmRequest,
    LlmResponse,
    LlmResponseStatus,
    TokenUsage,
    ToolCandidate,
)

ROOT = Path(__file__).resolve().parents[3]
GOOD = ("Sinh viên được xin nghỉ học tạm thời vì lý do cá nhân khác nhưng đã phải học tối thiểu "
        "01 học kỳ ở Trường và không thuộc các trường hợp bị xem xét buộc thôi học hoặc xem xét kỷ luật.")
BAD = GOOD.replace("không thuộc các trường hợp", "không thuộc nhóm đối tượng")


@lru_cache(maxsize=1)
def public_rows():
    store = PublicKnowledgeStore(ROOT / "data/huce-public-20261013", tenant_id="HUCE", campus_id="HUCE")
    return store.rows


def retained_source(section):
    matches = [row for row in public_rows() if row["source_id"] == "672d3a51-085e-7a46-818c-d741c4f05af9"
        and row["section_path"] == section]
    assert len(matches) == 1
    return matches[0]


@pytest.fixture
def source():
    return retained_source("Điều 14. Nghỉ học tạm thời, thôi học")


def context():
    return RetrievalContext(AuthorizedScope("HUCE", "HUCE", "actor", frozenset({"STUDENT"}),
        frozenset({"STUDENT"}), frozenset({"PUBLIC"}), frozenset({"PUBLIC"})),
        "vi", datetime(2026, 10, 13, tzinfo=UTC), SimulationPolicy.DENY, "1" * 32)


def state(source):
    return AgentState(NormalizedTurn("session", "turn", "actor", "Xin nghỉ học tạm thời vì lý do cá nhân?"),
        route=Route.GROUNDED_FAQ, trusted_context_ref="1" * 32, tool_flow=ToolFlowState(candidates=[source]))


def claim(text=GOOD, *, used=10, status=LlmResponseStatus.COMPLETED, citation="CIT-001", tools=()):
    return LlmResponse(status, "offline-double", "offline-double", output_text=json.dumps({"claims": [
        {"text": text, "citation_ids": [citation], "claim_type": "policy"}]}),
        usage=TokenUsage(output_tokens=used), tool_candidates=tools)


def verdict(used=80):
    return LlmResponse(LlmResponseStatus.COMPLETED, "offline-double", "offline-double",
        output_text=json.dumps({"answers_question": True,
            "verdicts": [{"claim_id": "CLM-001", "status": "SUPPORTED"}]}),
        usage=TokenUsage(output_tokens=used))


def request():
    return LlmRequest("turn", "grounded_faq", "default", "source-only", (),
        max_output_tokens=1000, deadline_ms=5000)


class Gateway:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    async def generate(self, item):
        self.requests.append(item)
        assert self.responses, "No additional model call is authorized by this test"
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_policy_regeneration_passes_unchanged_guards_with_shared_total_budget(source):
    gateway = Gateway(claim(BAD, used=500), claim(used=400), verdict())
    result = await async_io.compose_grounded_node(state(source), gateway, context=context(),
        support_threshold=.78, claim_verifier=SemanticClaimVerifier(gateway))
    assert result.terminal is None
    verified = evidence_gate_node(result, context=context(), support_threshold=.78)
    guarded = OutputGuardNode().execute(verified)
    assert guarded.terminal == Terminal.ANSWERED
    assert GOOD in guarded.draft.text and "01 học kỳ" in guarded.draft.text
    assert [r.route_id for r in gateway.requests] == ["grounded_faq", "grounded_faq", "grounded_semantic_verification"]
    assert [r.max_output_tokens for r in gateway.requests] == [1000, 500, 100]
    assert all(0 < r.deadline_ms <= 5000 and not r.allowed_tools for r in gateway.requests)
    assert gateway.requests[1].input_items == gateway.requests[0].input_items
    assert "AI_POLICY_CLAIM_FORMAT" in gateway.requests[1].system_instructions
    assert json.dumps(source["content_text"], ensure_ascii=False) in unescape(gateway.requests[2].input_items[0]["content"])


@pytest.mark.asyncio
@pytest.mark.parametrize("has_verifier", [True, False])
async def test_second_unverified_policy_is_still_rejected_without_paid_verification_or_third_regeneration(source, has_verifier):
    gateway = Gateway(claim(BAD), claim(BAD), verdict())
    result = await async_io.compose_grounded_node(state(source), gateway, context=context(),
        support_threshold=.78, claim_verifier=SemanticClaimVerifier(gateway) if has_verifier else None)
    verified = evidence_gate_node(result, context=context(), support_threshold=.78)
    guarded = OutputGuardNode().execute(verified)
    final = prepare_chat_result(guarded)
    assert final.status == "abstained" and final.response_class == "safe_refusal"
    assert "AI_POLICY_CLAIM_FORMAT" in guarded.errors and BAD not in final.content and not final.citations
    assert len(gateway.requests) == 2


def test_unverified_policy_still_cannot_pass_the_existing_output_guard_directly(source):
    from dataclasses import replace
    draft = parse_grounded_claims(claim(BAD).output_text)
    candidate = replace(state(source), draft=DraftResponse(text=draft.response_text,
        claim_count=len(draft.claims), is_grounded=True, grounded_claims=draft.claims))
    verified = evidence_gate_node(candidate, context=context(), support_threshold=.78)
    assert verified.draft.gate_decision == "grounded"
    assert OutputGuardNode().execute(verified).terminal == Terminal.SAFE_FAILURE


@pytest.mark.asyncio
@pytest.mark.parametrize("status,tools", [
    (LlmResponseStatus.FAILED, ()), (LlmResponseStatus.INCOMPLETE, ()),
    (LlmResponseStatus.COMPLETED, (ToolCandidate("call", "unexpected_action"),)),
])
async def test_failed_or_tool_output_never_runs_policy_preflight_or_semantic_verification(source, status, tools):
    response = claim(status=status, tools=tools)
    gateway = Gateway(response)
    def forbidden_preflight(_):
        pytest.fail("Non-deliverable model output cannot enter policy preflight")
    actual = await generate_with_regeneration(gateway, request(), CitationBundle.build([source]),
        support_threshold=.78, draft_preflight=forbidden_preflight)
    assert actual is response and len(gateway.requests) == 1
    gateway = Gateway(response)
    result = await async_io.compose_grounded_node(state(source), gateway, context=context(),
        support_threshold=.78, claim_verifier=SemanticClaimVerifier(gateway))
    assert result.terminal == Terminal.SAFE_FAILURE and len(gateway.requests) == 1


@pytest.mark.asyncio
async def test_remaining_output_budget_cannot_be_reused_for_verification(source):
    gateway = Gateway(claim(used=950), verdict())
    result = await async_io.compose_grounded_node(state(source), gateway, context=context(),
        support_threshold=.78, claim_verifier=SemanticClaimVerifier(gateway))
    assert result.terminal == Terminal.ABSTAINED and "AI_SEMANTIC_SUPPORT_REJECTED" in result.errors
    assert len(gateway.requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("draft", [claim(citation="CIT-999"), claim(status=LlmResponseStatus.INCOMPLETE),
    LlmResponse(LlmResponseStatus.COMPLETED, "offline-double", "offline-double", output_text="malformed"),
    LlmResponse(LlmResponseStatus.COMPLETED, "offline-double", "offline-double", output_text='{"claims":[]}')])
async def test_semantic_verification_rejects_invalid_drafts_before_model_call(source, draft):
    gateway = Gateway(verdict())
    assert not await SemanticClaimVerifier(gateway).verify(request(), draft, CitationBundle.build([source]),
        deadline_ms=500, output_tokens=100)
    assert not gateway.requests


@pytest.mark.asyncio
async def test_semantic_verification_has_its_own_deadline_and_joins_cancelled_io(source):
    stopped = asyncio.Event()
    class Waiting:
        async def generate(self, _):
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()
    with pytest.raises(TimeoutError):
        await SemanticClaimVerifier(Waiting()).verify(request(), claim(), CitationBundle.build([source]),
            deadline_ms=10, output_tokens=100)
    assert stopped.is_set()


@pytest.mark.asyncio
async def test_semantic_response_exceeding_remaining_output_budget_is_rejected(source):
    gateway = Gateway(verdict(used=101))
    assert not await SemanticClaimVerifier(gateway).verify(request(), claim(), CitationBundle.build([source]),
        deadline_ms=500, output_tokens=100)
    assert gateway.requests[0].max_output_tokens == 100


def ascii_source():
    # A formatting fixture: generated text is never presented as quality evidence.
    prefix, suffix = "Offline formatting fixture.\n", "\nThe final condition must remain."
    text = prefix + "A" * (12537 - len(prefix) - len(suffix)) + suffix
    return {"source_id": "offline-source", "chunk_id": "offline-chunk", "title": "Offline prompt fixture",
        "section_path": "Full source", "content_text": text, "simulation_label": True}


def outbound_size(item):
    # Build and validate a payload without a configured credential or HTTP call.
    adapter = OpenAICompatibleAdapter("deepseek", "https://api.deepseek.com", None,
        "deepseek-flash", disable_thinking=True)
    payload = EgressPolicy().validate_and_minimize({"purpose": "FAQ_ANSWERING", **adapter._build_payload(item)})
    assert all(len(message["content"]) <= 12000 for message in payload["messages"])
    assert len(payload["messages"]) <= 32
    return len(json.dumps(payload, ensure_ascii=False).encode()) + 512


def test_large_ascii_source_preserves_every_character_and_keeps_existing_message_and_payload_bounds():
    import re

    from campus247.agent.nodes.definitions import grounded_request
    row = ascii_source()
    bundle = CitationBundle.build([row])
    blocks = evidence_prompt_blocks(bundle)
    parts, end = [], 0
    for block in blocks:
        match = re.search(r"Phần nguồn tại vị trí (\d+):(\d+)", block.content)
        start, stop = map(int, match.groups())
        part = block.content.split("Nội dung: ", 1)[1]
        assert start == end and row["content_text"][start:stop] == part
        assert "[CIT-001] Nguồn: Offline prompt fixture (Full source)" in block.content
        parts.append(part)
        end = stop
    assert len(blocks) > 1 and "".join(parts) == row["content_text"] and end == 12537
    original = AgentState(NormalizedTurn("session", "turn", "actor", "Find the final condition."), route=Route.GROUNDED_FAQ)
    generated = grounded_request(original, bundle)
    assert row["content_text"] not in generated.system_instructions
    assert outbound_size(generated) <= 28000
    assert "The final condition must remain." in generated.input_items[-1]["content"]


@pytest.mark.asyncio
async def test_semantic_large_source_has_valid_json_parts_exact_offsets_and_complete_content():
    row = ascii_source()
    bundle = CitationBundle.build([row])
    blocks = evidence_prompt_blocks(bundle, semantic=True)
    parts = [json.loads(block.content)[0] for block in blocks]
    assert len(parts) > 1 and {part["citation_id"] for part in parts} == {"CIT-001"}
    assert all(part["source_title"] == row["title"] and part["section_path"] == row["section_path"] for part in parts)
    assert "".join(part["source"] for part in parts) == row["content_text"]
    assert parts[0]["start"] == 0 and parts[-1]["end"] == 12537
    assert all(part["end"] == following["start"] for part, following in pairwise(parts))
    assert all(row["content_text"][part["start"]:part["end"]] == part["source"] for part in parts)
    gateway = Gateway(verdict())
    assert await SemanticClaimVerifier(gateway).verify(request(), claim("Offline formatting fixture."), bundle,
        deadline_ms=500, output_tokens=384)
    checked = gateway.requests[0]
    assert outbound_size(checked) <= 28000 and len(checked.input_items) > 1
    assert "The final condition must remain." in unescape(checked.input_items[-1]["content"])


def test_source_splitting_cannot_bypass_global_prompt_block_count():
    from campus247.agent.prompts.composer import PromptBlock, TrustDomain
    with pytest.raises(ValueError, match="block count"):
        compose_bounded_inputs([PromptBlock(TrustDomain.USER_INPUT, "bounded") for _ in range(33)])


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["prompt", "generation", "verification"])
async def test_generation_diagnostics_are_finite_and_never_include_exception_message(source, monkeypatch, caplog, phase):
    private = "PRIVATE_RAW_EXCEPTION_MESSAGE"
    gateway = Gateway(claim())
    verifier = None
    if phase == "prompt":
        def fail_prompt(*_):
            raise ValueError(private)
        monkeypatch.setattr(async_io.nodes, "grounded_request", fail_prompt)
    elif phase == "generation":
        class Failing:
            async def generate(self, _):
                raise ValueError(private)
        gateway = Failing()
    else:
        class Failing:
            async def verify(self, *_args, **_kwargs):
                raise ValueError(private)
        verifier = Failing()
    with caplog.at_level(logging.WARNING, logger="campus247.generation"):
        result = await async_io.compose_grounded_node(state(source), gateway, context=context(),
            support_threshold=.78, claim_verifier=verifier)
    assert f"AI_GENERATION_{phase.upper()}_VALUE_ERROR" in result.errors
    assert private not in caplog.text and private not in str(result)
    assert f"phase={phase} exception_kind=VALUE_ERROR" in caplog.text
    assert prepare_chat_result(result).response_class == "safe_refusal"


@pytest.mark.asyncio
async def test_missing_parenthetical_condition_gets_only_one_regeneration_with_same_source_budget(caplog):
    row = retained_source("Điều 9. Đánh giá và tính điểm học phần")
    omitted = ("Sinh viên đã có điểm học phần đạt thì được đăng ký học lại hoặc học đổi sang học phần khác "
        "để cải thiện điểm trung bình chung tích lũy cuối khóa.")
    qualifier = " (là học phần tương đương hoặc thay thế trong trường hợp học phần bắt buộc)"
    preserved = omitted.replace("học phần khác", "học phần khác" + qualifier)
    gateway = Gateway(claim(omitted, used=137), claim(preserved, used=221))
    with caplog.at_level(logging.WARNING, logger="campus247.generation"):
        result = await generate_with_regeneration(gateway, request(), CitationBundle.build([row]), support_threshold=.78)
    assert result.output_text == claim(preserved, used=221).output_text and len(gateway.requests) == 2
    original, retry = gateway.requests
    assert retry.input_items == original.input_items and retry.max_output_tokens == 863
    assert 0 < retry.deadline_ms <= original.deadline_ms == 5000
    assert "MISSING_MATERIAL_CONDITION" in retry.system_instructions and "MISSING_MATERIAL_CONDITION" in caplog.text
    assert omitted not in caplog.text and preserved not in caplog.text


@pytest.mark.parametrize("question", [
    "Điểm D có phải học lại không?", "Điểm F có bắt buộc học lại không?",
    "diem D co phai hoc lai khong?", "Phòng học nhóm thư viện ở đâu?",
    "Một tín chỉ cần bao nhiêu giờ tự học?",
])
def test_direct_fact_request_shapes_one_conclusion_without_adding_facts_or_dropping_source_conditions(question):
    from campus247.agent.nodes.definitions import grounded_request
    row = retained_source("Điều 9. Đánh giá và tính điểm học phần")
    turn = AgentState(NormalizedTurn("session", "turn", "actor", question), route=Route.GROUNDED_FAQ)
    item = grounded_request(turn, CitationBundle.build([row]))
    assert "answer_scope=single_fact" in item.system_instructions and "đúng một claim" in item.system_instructions
    assert "không mở rộng" in item.system_instructions and "không cắt điều kiện" in item.system_instructions
    assert question not in item.system_instructions and row["content_text"] not in item.system_instructions
    body = unescape("\n".join(value["content"] for value in item.input_items))
    assert question in body and row["content_text"] in body
    assert "trường hợp học\nphần bắt buộc" in body
    assert item.deadline_ms == 5000 and item.max_output_tokens == 1000 and not item.allowed_tools


@pytest.mark.parametrize("question", [
    "Điểm D có phải học lại không? Nếu muốn cải thiện điểm thì đăng ký thế nào?",
    "Điểm D có phải học lại không và thủ tục phúc khảo là gì?",
    "Điều kiện xin nghỉ học tạm thời gồm những trường hợp nào?",
    "Thủ tục xin nghỉ học tạm thời như thế nào?",
    "Nêu các điều kiện học bổng và ngoại lệ cho sinh viên năm thứ nhất.",
])
def test_procedure_or_multiple_part_request_keeps_full_answer_scope_and_complete_leave_conditions(question):
    from campus247.agent.nodes.definitions import grounded_request
    row = retained_source("Điều 14. Nghỉ học tạm thời, thôi học")
    turn = AgentState(NormalizedTurn("session", "turn", "actor", question), route=Route.GROUNDED_FAQ)
    item = grounded_request(turn, CitationBundle.build([row]))
    assert "answer_scope=single_fact" not in item.system_instructions
    body = unescape("\n".join(value["content"] for value in item.input_items))
    assert row["content_text"] in body and "a) Được điều động" in body and "d) Vì lý do cá nhân" in body
    assert "xem xét kỷ luật" in body and question in body


@pytest.mark.asyncio
async def test_numeric_regeneration_preserves_single_fact_scope_without_introducing_unasked_policy_topics():
    from dataclasses import replace

    row = retained_source("Điều 9. Đánh giá và tính điểm học phần")
    initial = replace(request(), system_instructions="source-only answer_scope=single_fact")
    gateway = Gateway(claim("Điểm D dưới 4,0 là loại đạt.", used=137), claim("Điểm D từ 4,0 đến 4,9 là loại đạt.", used=100))
    final = await generate_with_regeneration(gateway, initial, CitationBundle.build([row]), support_threshold=.78)
    assert final.output_text == claim("Điểm D từ 4,0 đến 4,9 là loại đạt.", used=100).output_text
    assert len(gateway.requests) == 2 and gateway.requests[1].max_output_tokens == 863
    retry = gateway.requests[1]
    assert retry.input_items == initial.input_items and 0 < retry.deadline_ms <= 5000
    assert "Giữ nguyên answer_scope=single_fact" in retry.system_instructions and "đúng một claim" in retry.system_instructions
    assert "Không thêm tình huống" in retry.system_instructions and "kỷ luật" not in retry.system_instructions


def incomplete_verdict(issue="INCOMPLETE", *, supported=True, used=80):
    return LlmResponse(LlmResponseStatus.COMPLETED, "offline-double", "offline-double",
        output_text=json.dumps({"answers_question": False, "question_issue": issue,
            "verdicts": [{"claim_id": "CLM-001", "status": "SUPPORTED" if supported else "INSUFFICIENT"}]}),
        usage=TokenUsage(output_tokens=used))


@pytest.mark.asyncio
async def test_verified_but_incomplete_answer_is_shown_as_a_labelled_partial_answer(source):
    gateway = Gateway(claim(GOOD, used=300), incomplete_verdict(), claim(GOOD, used=300), incomplete_verdict())
    result = await async_io.compose_grounded_node(state(source), gateway, context=context(),
        support_threshold=.78, claim_verifier=SemanticClaimVerifier(gateway))
    assert "AI_PARTIAL_COVERAGE" in result.errors and result.draft.partial_note == async_io.PARTIAL_COMPLETENESS_NOTE
    verified = evidence_gate_node(result, context=context(), support_threshold=.78)
    final = prepare_chat_result(OutputGuardNode().execute(verified))
    assert final.status == "answered" and final.response_class == "partial_answer" and final.citations
    assert GOOD in final.content and async_io.PARTIAL_COMPLETENESS_NOTE in final.content
    assert len(gateway.requests) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("issue,supported", [("WRONG_COHORT", True), ("WRONG_PROGRAM", True), ("WRONG_YEAR", True),
    ("WRONG_UNIT", True), ("OTHER", True), ("INCOMPLETE", False)])
async def test_wrong_scope_other_or_unsupported_verdicts_still_abstain_without_a_partial_answer(source, issue, supported):
    gateway = Gateway(claim(GOOD, used=300), incomplete_verdict(issue, supported=supported),
        claim(GOOD, used=300), incomplete_verdict(issue, supported=supported))
    result = await async_io.compose_grounded_node(state(source), gateway, context=context(),
        support_threshold=.78, claim_verifier=SemanticClaimVerifier(gateway))
    assert result.terminal == Terminal.ABSTAINED and "AI_PARTIAL_COVERAGE" not in result.errors
    final = prepare_chat_result(result)
    assert final.status == "abstained" and final.response_class == "safe_refusal" and not final.citations
    assert GOOD not in final.content
