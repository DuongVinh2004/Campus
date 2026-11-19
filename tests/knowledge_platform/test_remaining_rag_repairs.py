"""Regression coverage for real remaining failures and provenance boundaries."""
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from campus247.agent.nodes.compose import OutputGuardNode
from campus247.agent.state import AgentState, DraftResponse, NormalizedTurn, Route, Terminal, ToolFlowState
from campus247.application.retrieval.candidate_selection import select_parent_spans
from campus247.application.retrieval.citations import CitationBundle
from campus247.application.retrieval.evidence_gate import EvidenceGate, GroundedClaim, GroundedDraft
from campus247.domain.publication import official_huce_uri
from campus247.infrastructure.knowledge import publication

ROOT = Path(__file__).resolve().parents[2]
RELEASE = "01a168c6-dce3-7b72-bcbd-b5797b9452b8"


def source():
    receipt = json.loads((ROOT / "infra/local/knowledge-platform-20261023/independent-sources-20261023T125049141884.json").read_text(encoding="utf-8"))
    doc = next(d for d in receipt["originals"] if d["version_id"].startswith("01a168c6"))
    clause = next(c for c in doc["evidence"] if c["section_path"].endswith("khoản12"))
    return {**clause, "source_id": "2d8c1b76-749f-7a7a-890b-e41c8646affe",
        "document_version_id": doc["version_id"], "canonical_uri": doc["canonical_uri"],
        "title": "Nội quy phòng máy", "issuer": "HUCE", "chunk_id": "audit-clause",
        "release_id": RELEASE, "simulation_label": False}, doc


async def attest(row, *, corrupt_original=False):
    _, doc = source()
    class Repo:
        tenant = "huce-local-public"
        async def version(self, *_):
            return {"original_id": "owned-original", "original_sha256": doc["original_sha256"],
                "rendition_id": "owned-rendition", "rendition_sha256": doc["rendition_sha256"]}
    class Conn:
        async def fetchrow(self, _, identifier, *args):
            return {"id": identifier}
    original = Path(doc["original_path"]).read_bytes()
    rendition = json.dumps(doc["rendition"], ensure_ascii=False, sort_keys=True).encode()
    assert hashlib.sha256(rendition).hexdigest() == doc["rendition_sha256"]
    def read(artifact):
        if artifact["id"] == "owned-rendition":
            return rendition
        return original + b"corrupt" if corrupt_original else original
    platform = SimpleNamespace(repo=Repo(), storage=SimpleNamespace(workspace=ROOT,
        read=read))
    return await publication.verified_attachment(platform, Conn(), row, RELEASE)


def guarded(row, claim):
    value = GroundedClaim("CLM-001", claim, ("CIT-001",), "policy")
    draft = GroundedDraft(claim + " [CIT-001]", (value,))
    assert EvidenceGate(min_token_overlap_ratio=1.0).verify(draft, CitationBundle.build([row])).passed
    state = AgentState(NormalizedTurn("session", "turn", "actor", "Nội quy xử lý vi phạm thế nào?"),
        route=Route.GROUNDED_FAQ, tool_flow=ToolFlowState(candidates=[row]),
        draft=DraftResponse(text=draft.response_text, claim_count=1, is_grounded=True,
            gate_decision="grounded", grounded_claims=draft.claims))
    return OutputGuardNode().execute(state)


@pytest.mark.asyncio
async def test_exact_generic_rule_from_officially_linked_attachment_is_answerable():
    row, _ = source()
    row["_verified_publication"] = await attest(row)
    assert row["_verified_publication"] is not None
    claim = row["content_text"].removeprefix("12. ").split(". Làm", 1)[0] + "."
    assert guarded(row, claim).terminal == Terminal.ANSWERED


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["other_attachment", "other_source", "other_version", "other_release", "changed_evidence", "dict_forgery", "simulation"])
async def test_publication_cannot_be_reused_for_other_evidence(fault):
    row, _ = source()
    row["_verified_publication"] = await attest(row)
    claim = row["content_text"].removeprefix("12. ").split(". Làm", 1)[0] + "."
    if fault == "other_attachment":
        row["canonical_uri"] += "untrusted"
    elif fault == "other_source":
        row["source_id"] = "other"
    elif fault == "other_version":
        row["document_version_id"] = "other"
    elif fault == "other_release":
        row["release_id"] = "other"
    elif fault == "changed_evidence":
        row["content_text"] += "\nUnreviewed material."
    elif fault == "simulation":
        row["simulation_label"] = True
    else:
        row["_verified_publication"] = row["_verified_publication"].__dict__
    assert guarded(row, claim).terminal == Terminal.SAFE_FAILURE


@pytest.mark.asyncio
async def test_unknown_drive_attachment_and_corrupt_original_get_no_attestation():
    row, _ = source()
    assert await attest({**row, "canonical_uri": "https://drive.google.com/file/d/other/preview"}) is None
    assert await attest(row, corrupt_original=True) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("claim", ["Bạn bị xử lý kỷ luật theo quy chế của nhà trường.",
    "Sinh viên Nguyễn Văn An bị xử lý kỷ luật theo quy chế của nhà trường.",
    "Sinh viên nào vi phạm sẽ bị kỷ luật."])
async def test_even_attested_attachment_cannot_authorize_personal_or_rearranged_verdicts(claim):
    row, _ = source()
    row["content_text"] += "\n" + claim
    row["content_checksum"] = hashlib.sha256(row["content_text"].encode()).hexdigest()
    row["_verified_publication"] = await attest(row)
    # The old document hash is correct, but the claim is still an individual
    # verdict or not the exact conditional rule in the reviewed source.
    if claim.startswith("Sinh viên nào"):
        row["content_text"] = source()[0]["content_text"]
        row["content_checksum"] = hashlib.sha256(row["content_text"].encode()).hexdigest()
        row["_verified_publication"] = await attest(row)
    assert guarded(row, claim).terminal == Terminal.SAFE_FAILURE


@pytest.mark.parametrize("uri", ["http://huce.edu.vn/rule", "https://huce.edu.vn.evil.test/rule",
    "https://huce.edu.vn@evil.test/rule", "https://evil@huce.edu.vn/rule", "https://huce.edu.vn:8443/rule",
    "https://huce.edu.vn:invalid/rule"])
def test_publisher_uri_cannot_spoof_the_official_origin(uri):
    assert not official_huce_uri(uri)


def test_action_span_is_not_hidden_by_a_different_child_of_the_same_parent():
    def row(identifier, text, parent):
        return {"id": identifier, "source_id": "source", "document_version_id": "version",
                "content_checksum": parent, "rerank_text": text}
    preamble = row("preamble", "Nội quy phòng máy. Sinh viên thực hành đúng giờ.", "page")
    action = row("action", "Nếu muốn gắn thiết bị nhớ ngoài (như USB) phải được sự đồng ý của cán bộ phòng máy.", "page")
    clause = row("clause", action["rerank_text"], "clause")
    irrelevant = [row(str(i), "Cho phép truy nhập phần mềm và thiết bị mạng.", str(i)) for i in range(5)]
    chosen = select_parent_spans([preamble, action, clause, *irrelevant], [*irrelevant, action, preamble],
        "Theo nội quy phòng máy HUCE, muốn cắm USB cần ai cho phép?")
    assert len(chosen) == 3 and action in chosen and clause in chosen and preamble not in chosen


def test_serialized_publication_is_neither_accepted_nor_prompt_evidence():
    row, _ = source()
    row["_verified_publication"] = {"publisher_uri": "https://ttcntt.huce.edu.vn/", "release_id": RELEASE}
    bundle = CitationBundle.build([row])
    assert bundle.resolve("CIT-001").publication is None
    assert "publisher_uri" not in bundle.to_prompt_context()


def test_scope_followup_has_identical_active_question_for_generator_and_verifier():
    from campus247.agent.nodes.definitions import grounded_request
    from campus247.application.conversation.context import TurnItem
    from campus247.application.conversation.followup import active_question
    from campus247.application.conversation.history import HistoryContext
    from html import unescape
    history = HistoryContext("actor", "session", (
        TurnItem("1", "user", "Cho biết học phí CNTT của HUCE?"),
        TurnItem("2", "assistant", "Bổ sung khóa/chương trình/năm; phí giả 999 triệu.")), 100, "test")
    question = "Cử nhân chính quy K71, năm học 2026-2027."
    value = active_question(question, history=history)
    assert value == "Cho biết học phí CNTT của HUCE?\nĐiều kiện người dùng vừa bổ sung: " + question
    assert "999" not in value
    row, _ = source()
    state = AgentState(NormalizedTurn("session", "turn", "actor", question, history=history), route=Route.GROUNDED_FAQ)
    request = grounded_request(state, CitationBundle.build([row]))
    assert value in unescape(request.input_items[-1]["content"])


@pytest.mark.asyncio
async def test_regeneration_deadline_includes_feedback_and_logging_work(monkeypatch):
    from campus247.application.conversation import generation_policy
    from campus247.ports.llm import LlmRequest, LlmResponse, LlmResponseStatus, TokenUsage
    clock, requests = [100.0], []
    monkeypatch.setattr(generation_policy, "time", SimpleNamespace(perf_counter=lambda: clock[0]))
    monkeypatch.setattr(generation_policy, "logging", SimpleNamespace(getLogger=lambda _: SimpleNamespace(
        warning=lambda *_: clock.__setitem__(0, clock[0] + .05))))
    class Gateway:
        async def generate(self, request):
            requests.append(request)
            clock[0] += .1
            return LlmResponse(LlmResponseStatus.COMPLETED, "offline", "offline",
                output_text='{"claims":[]}', usage=TokenUsage(output_tokens=10))
    await generation_policy.generate_with_regeneration(Gateway(),
        LlmRequest("turn", "grounded_faq", "default", "test", (), deadline_ms=5000, max_output_tokens=1000),
        CitationBundle.build([]), support_threshold=.78)
    assert len(requests) == 2 and 4849 <= requests[1].deadline_ms <= 4850


def test_unit_correction_cannot_deny_the_cohort_in_the_actual_table_row():
    from campus247.application.knowledge.question_scope import tuition_answer_scope_issue
    from tests.knowledge_platform.test_independent_audit_regressions import TABLE
    text = "Mức 592.500 đồng/tín chỉ áp dụng từ K69, không phải cho cử nhân chính quy K71."
    draft = GroundedDraft(text, (GroundedClaim("one", text, ("CIT-001",), "fee"),))
    assert tuition_answer_scope_issue("Học phí cử nhân chính quy K71 năm học 2026-2027 là 592.500 đồng/ĐVHT đúng không?",
        draft, CitationBundle.build([{"content_text": TABLE}])) == "AI_QUESTION_SCOPE_MISMATCH"


@pytest.mark.parametrize("text", [
    "Mức 592.500 đồng/tín chỉ áp dụng từ K69, không phải mức học phí cử nhân chính quy K71.",
    "Chương trình CN từ K69 có mức học phí 592.500 đồng/tín chỉ."])
def test_answer_must_match_the_question_program_not_merely_some_source_row(text):
    from campus247.application.knowledge.question_scope import tuition_answer_scope_issue
    from tests.knowledge_platform.test_independent_audit_regressions import TABLE
    question = "Học phí cử nhân chính quy K71 năm học 2026-2027?" if "không phải" in text else "Học phí kỹ sư chính quy K71 năm học 2026-2027?"
    draft = GroundedDraft(text, (GroundedClaim("one", text, ("CIT-001",), "fee"),))
    assert tuition_answer_scope_issue(question, draft, CitationBundle.build([{"content_text": TABLE}])) == "AI_QUESTION_SCOPE_MISMATCH"


@pytest.mark.parametrize("proposed", ["Nội quy phòng máy HUCE: cắm USB cần ai cho phép?",
    "Nội quy phòng máy HUCE: cắm USB không cần ai cho phép?", "Học phí K71 năm 2025-2026?", None])
def test_search_rewrite_can_only_restore_accents(proposed):
    from campus247.application.knowledge.question_scope import restored_search_question
    original = "Noi quy phong may HUCE: cam USB can ai cho phep?"
    expected = proposed if proposed == "Nội quy phòng máy HUCE: cắm USB cần ai cho phép?" else None
    assert restored_search_question(original, proposed) == expected


def test_table_unit_focus_is_an_exact_original_span_and_semantic_keeps_full_source():
    from campus247.application.retrieval.material_support import applicable_fee_row_ranges, fee_unit_span
    from campus247.application.retrieval.prompt_evidence import evidence_prompt_blocks
    from tests.knowledge_platform.test_independent_audit_regressions import TABLE
    query = "Học phí kỹ sư chất lượng cao K67 năm học 2026-2027 bao nhiêu?"
    ranges = applicable_fee_row_ranges(TABLE, query)
    start, end = fee_unit_span(TABLE, ranges)
    assert TABLE[start:end] == "tín chỉ"
    blocks = evidence_prompt_blocks(CitationBundle.build([{"content_text": TABLE}]), query=query, semantic=True)
    assert json.loads(blocks[0].content)[0]["source"] == TABLE
    assert any("table_row_focus" in block.content for block in blocks)
    assert any(block.content.endswith("tín chỉ") for block in blocks)
    focus = next(json.loads(block.content) for block in blocks if "table_row_focus" in block.content)
    assert focus["group_header"]["source"] == "I. Đại học hệ chính quy\n"
    assert all(TABLE[cell["start"]:cell["end"]] == cell["source"] for cell in focus["cells"])


def test_selected_vlvh_row_inherits_its_own_group_not_the_first_group():
    from campus247.application.retrieval.material_support import applicable_fee_row_ranges
    from tests.knowledge_platform.test_independent_audit_regressions import TABLE
    ranges = applicable_fee_row_ranges(TABLE, "Học phí cử nhân vừa làm vừa học K71 năm học 2026-2027?")
    assert TABLE[ranges[1][0]:ranges[1][1]] == "II. Đại học vừa làm vừa học\n"
    assert "I. Đại học hệ chính quy" not in TABLE[ranges[0][0]:ranges[0][1]]


@pytest.mark.asyncio
@pytest.mark.parametrize("last_answers,expected", [(True, None), (False, Terminal.ABSTAINED)])
@pytest.mark.parametrize("first_status", ["SUPPORTED", "INSUFFICIENT", "CONTRADICTED"])
async def test_negative_semantic_verdict_uses_only_the_unspent_regeneration_and_reverifies(last_answers, expected, first_status):
    from campus247.agent.nodes import async_io
    from campus247.application.retrieval.semantic_support import SemanticClaimVerifier
    from campus247.ports.llm import LlmResponse, LlmResponseStatus, TokenUsage
    from tests.knowledge_platform.test_independent_audit_regressions import TABLE
    text = "Chương trình KS/KTS từ K69 có mức học phí 547.000 đồng/tín chỉ."
    def generated():
        return LlmResponse(LlmResponseStatus.COMPLETED, "offline", "offline", output_text=json.dumps({"claims": [
            {"text": text, "citation_ids": ["CIT-001"], "claim_type": "fee"}]}), usage=TokenUsage(output_tokens=80))
    def verified(answers, status="SUPPORTED"):
        return LlmResponse(LlmResponseStatus.COMPLETED, "offline", "offline", output_text=json.dumps({
            "answers_question": answers, "verdicts": [{"claim_id": "CLM-001", "status": status}]}),
            usage=TokenUsage(output_tokens=70))
    requests, responses = [], [generated(), verified(False, first_status), generated(), verified(last_answers)]
    class Gateway:
        async def generate(self, request):
            requests.append(request)
            return responses.pop(0)
    gateway = Gateway()
    state = AgentState(NormalizedTurn("session", "turn", "actor", "Học phí kỹ sư chính quy K71 năm học 2026-2027?"),
        route=Route.GROUNDED_FAQ, tool_flow=ToolFlowState(candidates=[{"content_text": TABLE}]))
    result = await async_io.compose_grounded_node(state, gateway, support_threshold=.78,
        claim_verifier=SemanticClaimVerifier(gateway))
    assert result.terminal == expected
    assert [r.route_id for r in requests] == ["grounded_faq", "grounded_semantic_verification"] * 2
    assert requests[2].max_output_tokens == 850 and all(r.deadline_ms <= 5000 for r in requests)
    reason = "AI_ANSWER_RELEVANCE" if first_status == "SUPPORTED" else "AI_SEMANTIC_SUPPORT"
    assert reason in requests[2].system_instructions
    assert sum([80, 70, 80, 70]) <= requests[0].max_output_tokens == 1000


@pytest.mark.asyncio
async def test_invalid_semantic_verdict_does_not_authorize_a_repair():
    from campus247.agent.nodes import async_io
    from campus247.application.retrieval.semantic_support import SemanticClaimVerifier
    from campus247.ports.llm import LlmResponse, LlmResponseStatus, TokenUsage
    from tests.knowledge_platform.test_independent_audit_regressions import TABLE
    responses = [json.dumps({"claims": [{"text": "Chương trình CN từ K69 có mức học phí 592.500 đồng/tín chỉ.",
        "citation_ids": ["CIT-001"], "claim_type": "fee"}]}),
        '{"answers_question":false,"verdicts":[],"unexpected":"reject malformed schema"}']
    requests = []
    class Gateway:
        async def generate(self, request):
            requests.append(request)
            assert responses, "Invalid verification cannot request another generation"
            return LlmResponse(LlmResponseStatus.COMPLETED, "offline", "offline", output_text=responses.pop(0),
                usage=TokenUsage(output_tokens=70))
    gateway = Gateway()
    state = AgentState(NormalizedTurn("session", "turn", "actor", "Học phí cử nhân chính quy K71 năm học 2026-2027?"),
        route=Route.GROUNDED_FAQ, tool_flow=ToolFlowState(candidates=[{"content_text": TABLE}]))
    result = await async_io.compose_grounded_node(state, gateway, support_threshold=.78,
        claim_verifier=SemanticClaimVerifier(gateway))
    assert result.terminal == Terminal.ABSTAINED and len(requests) == 2


@pytest.mark.asyncio
async def test_semantic_relevance_never_gets_a_second_regeneration():
    from campus247.agent.nodes import async_io
    from campus247.application.retrieval.semantic_support import SemanticClaimVerifier
    from campus247.ports.llm import LlmResponse, LlmResponseStatus, TokenUsage
    from tests.knowledge_platform.test_independent_audit_regressions import TABLE
    good = "Chương trình CN từ K69 có mức học phí 592.500 đồng/tín chỉ."
    def generated(text):
        return LlmResponse(LlmResponseStatus.COMPLETED, "offline", "offline", output_text=json.dumps({"claims": [
            {"text": text, "citation_ids": ["CIT-001"], "claim_type": "fee"}]}), usage=TokenUsage(output_tokens=80))
    responses = [generated(good.replace("đồng/tín chỉ", "đồng/ĐVHT")), generated(good),
        LlmResponse(LlmResponseStatus.COMPLETED, "offline", "offline", output_text=json.dumps({
            "answers_question": False, "verdicts": [{"claim_id": "CLM-001", "status": "SUPPORTED"}]}),
            usage=TokenUsage(output_tokens=70))]
    requests = []
    class Gateway:
        async def generate(self, request):
            requests.append(request)
            assert responses, "A third generation cannot be authorized"
            return responses.pop(0)
    gateway = Gateway()
    state = AgentState(NormalizedTurn("session", "turn", "actor", "Học phí cử nhân chính quy K71 năm học 2026-2027?"),
        route=Route.GROUNDED_FAQ, tool_flow=ToolFlowState(candidates=[{"content_text": TABLE}]))
    result = await async_io.compose_grounded_node(state, gateway, support_threshold=.78,
        claim_verifier=SemanticClaimVerifier(gateway))
    assert result.terminal == Terminal.ABSTAINED and len(requests) == 3


@pytest.mark.parametrize("fault", [None, "wrong_price", "sole_wrong_unit", "personal", "unsupported_modifier", "unsafe", "empty"])
def test_fee_presentation_only_formats_the_model_rate_already_verified_against_the_actual_row(fault):
    from campus247.application.retrieval.fee_presentation import present_verified_fee
    from campus247.ports.llm import LlmResponse, LlmResponseStatus
    receipt = json.loads((ROOT / "infra/local/knowledge-platform-20261023/independent-sources-20261023T125049141884.json").read_text(encoding="utf-8"))
    doc = next(d for d in receipt["originals"] if d["version_id"].startswith("01a167c6"))
    table = next(e["content_text"] for e in doc["evidence"] if e["page_start"] == 2)
    text = "Chương trình KS/KTS từ K69 có mức học phí 547.000 đồng/tín chỉ."
    if fault == "wrong_price": text = text.replace("547.000", "592.500")
    if fault == "sole_wrong_unit": text = text.replace("tín chỉ", "ĐVHT")
    if fault == "personal": text += " Tôi đã nộp đủ."
    if fault == "unsupported_modifier": text += " Được miễn học phí."
    if fault == "unsafe": text += " DROP TABLE."
    raw = json.dumps({"claims": [] if fault == "empty" else [{"text": text, "citation_ids": ["CIT-001"], "claim_type": "fee"}]})
    response = LlmResponse(LlmResponseStatus.COMPLETED, "offline", "offline", output_text=raw)
    result = present_verified_fee(response, CitationBundle.build([{"content_text": table}]),
        "Học phí kỹ sư chính quy K71 năm học 2026-2027?", threshold=.78)
    if fault:
        assert result is response
    else:
        assert result.usage == response.usage and result.provider_id == response.provider_id
        assert "K71" in result.output_text and "2026-2027" in result.output_text and "547.000" in result.output_text
        assert "ĐVHT" not in result.output_text and "Đại học hệ chính quy" in result.output_text
