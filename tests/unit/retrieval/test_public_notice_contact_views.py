"""Synthetic component fixtures; no external calls or policy exceptions."""
import hashlib
import json

import pytest

from campus247.agent.prompts.composer import PromptBlock, TrustDomain
from campus247.application.retrieval.citations import CitationBundle
from campus247.application.retrieval.evidence_gate import EvidenceGate, parse_grounded_claims
from campus247.application.retrieval.notice_quotation import present_notice_quotation
from campus247.application.retrieval.prompt_evidence import compose_bounded_inputs, evidence_prompt_blocks
from campus247.application.retrieval.public_notice_contacts import PUBLIC_NOTICE_ORIGINAL, public_notice_contact_redactor
from campus247.application.retrieval.semantic_support import SemanticClaimVerifier
from campus247.domain.publication import VerifiedPublication
from campus247.infrastructure.llm.egress_policy import EgressPolicy, EgressViolationError
from campus247.ports.llm import LlmRequest, LlmResponse, LlmResponseStatus, TokenUsage
from campus247.agent.state import AgentState, DraftResponse, NormalizedTurn, Route, Terminal, ToolFlowState
from campus247.application.conversation.history_presentation import history_policy_alternative
from campus247.application.conversation.stream_result import FinalChatResult

PHONE = "0900000000"
EMAIL = "synthetic-notice-contact@huce.edu.vn"
CONTACT = f"Mọi thắc mắc liên hệ qua Phòng CTCT&QLSV, Số điện thoại: {PHONE} hoặc qua\nEmail: {EMAIL}.\nTrân trọng./."
QUESTION = "Theo thông báo học bổng STEM Quỹ Châu Á năm học 2025-2026, thông tin liên hệ được in ở cuối thông báo là gì?"


def row(text=CONTACT, *, fault=None):
    result = {"source_id": "synthetic-source", "document_version_id": "synthetic-version", "release_id": "synthetic-release",
        "content_text": text, "title": "Học bổng STEM Quỹ Châu Á năm học 2025-2026", "section_path": "Thông báo — PDF 2",
        "canonical_uri": "https://drive.google.com/file/d/SYNTHETIC/view", "simulation_label": False}
    publication = VerifiedPublication("https://ctsv.huce.edu.vn/public-notice", result["canonical_uri"],
        result["source_id"], result["document_version_id"], hashlib.sha256(text.encode()).hexdigest(),
        "0" * 64 if fault == "different_original" else PUBLIC_NOTICE_ORIGINAL, "other-release" if fault == "different_release" else result["release_id"])
    result["_verified_publication"] = publication
    if fault == "unattested": result.pop("_verified_publication")
    if fault == "serialized": result["_verified_publication"] = {"original_sha256": PUBLIC_NOTICE_ORIGINAL}
    if fault == "synthetic": result["simulation_label"] = True
    return result


def draft(text="Nonempty model proposal"):
    return LlmResponse(LlmResponseStatus.COMPLETED, "offline", "synthetic", usage=TokenUsage(10, 0, 20),
        output_text=json.dumps({"claims": [{"text": text, "citation_ids": ["CIT-001"], "claim_type": "policy"}]}))


def validate_payload(text):
    return EgressPolicy().validate_and_minimize({"purpose": "FAQ_ANSWERING", "model": "synthetic",
        "messages": [{"role": "user", "content": text}]})


@pytest.mark.parametrize("semantic", [False, True])
def test_public_contact_values_stay_local_while_original_evidence_and_offsets_are_preserved(semantic):
    bundle = CitationBundle.build([row()])
    before = bundle.resolve("CIT-001")
    blocks = evidence_prompt_blocks(bundle, query=QUESTION, semantic=semantic)
    text = "\n".join(b.content for b in blocks)
    assert PHONE not in text and EMAIL not in text and "PUBLIC_CONTACT_PHONE_" in text and "PUBLIC_CONTACT_EMAIL_" in text
    assert "0" in text and str(len(CONTACT)) in text
    validate_payload(text)
    assert bundle.resolve("CIT-001") is before and before.content_text == CONTACT
    assert before.quote_span_hash == "sha256:" + hashlib.sha256(CONTACT.encode()).hexdigest()
    with pytest.raises(EgressViolationError):
        validate_payload(CONTACT)


@pytest.mark.parametrize("fault", ["unattested", "serialized", "synthetic", "different_original", "different_release"])
def test_attestation_gates_only_the_pinned_notice_quotation_not_contact_minimization(fault):
    # The pinned-notice redactor still refuses records that are not attested. The model view
    # never carries contact values from any served source, so these records no longer fail
    # closed at the outbound policy; the raw text itself is still denied.
    bundle = CitationBundle.build([row(fault=fault)])
    assert public_notice_contact_redactor(bundle)(CONTACT) == CONTACT
    view = "\n".join(b.content for b in evidence_prompt_blocks(bundle, query=QUESTION))
    assert PHONE not in view and EMAIL not in view
    validate_payload(view)
    with pytest.raises(EgressViolationError):
        validate_payload(CONTACT)


def test_raw_user_identifiers_and_secrets_still_reach_the_unchanged_denial_boundary():
    bundle = CitationBundle.build([row()])
    blocks = evidence_prompt_blocks(bundle, query=QUESTION)
    blocks.append(PromptBlock(TrustDomain.USER_INPUT, "My private address is user@private.invalid-domain.org"))
    _, inputs = compose_bounded_inputs(blocks)
    with pytest.raises(EgressViolationError):
        validate_payload("\n".join(x["content"] for x in inputs))
    secret = "Bearer " + "x" * 24
    assert secret in public_notice_contact_redactor(bundle)(secret)
    with pytest.raises(EgressViolationError):
        validate_payload(secret)


def test_a_matching_value_in_a_different_record_is_minimized_too():
    private = row(fault="unattested")
    private.update(source_id="private", title="Different record", content_text=f"Private contact {PHONE}")
    blocks = evidence_prompt_blocks(CitationBundle.build([row(), private]), query=QUESTION)
    text = "\n".join(b.content for b in blocks)
    assert "PUBLIC_CONTACT_PHONE_" in text and PHONE not in text
    validate_payload(text)


@pytest.mark.parametrize("text,tail,expected", [
    ("Số: 46/TB-ĐHXDHN-CTSV\nHà Nội, ngày 30 tháng 01 năm 2026", "số văn bản và ngày ban hành in trên bản gốc là gì?", "Số: 46/TB-ĐHXDHN-CTSV\nHà Nội, ngày 30 tháng 01 năm 2026"),
    (CONTACT, "thông tin liên hệ được in ở cuối thông báo là gì?", CONTACT.partition("\nTrân trọng")[0]),
    ("TL. HIỆU TRƯỞNG\nKT. TRƯỞNG PHÒNG CTCT&QLSV\nPHÓ TRƯỞNG PHÒNG\nThS. Người ký mẫu", "chức danh và họ tên in dưới chữ ký là gì?", "TL. HIỆU TRƯỞNG\nKT. TRƯỞNG PHÒNG CTCT&QLSV\nPHÓ TRƯỞNG PHÒNG\nThS. Người ký mẫu"),
])
def test_printed_fields_keep_exact_source_values_without_certifying_a_signature(text, tail, expected):
    bundle = CitationBundle.build([row(text)])
    response = draft()
    quoted = present_notice_quotation(response, bundle, QUESTION.partition(",")[0] + ", " + tail)
    claims = parse_grounded_claims(quoted.output_text)
    assert claims.claims[0].text == expected and EvidenceGate().verify(claims, bundle).passed
    assert quoted.usage == response.usage


def test_no_fallback_from_empty_or_failed_model_output_and_no_current_contact_inference():
    bundle = CitationBundle.build([row()])
    failed = LlmResponse(LlmResponseStatus.FAILED, "offline", "synthetic")
    empty = LlmResponse(LlmResponseStatus.COMPLETED, "offline", "synthetic", output_text='{"claims":[]}')
    for response in (failed, empty):
        assert present_notice_quotation(response, bundle, QUESTION) is response
    for question in (QUESTION.replace("2025-2026", "2026-2027"), QUESTION + " Còn sử dụng hiện nay không?"):
        response = draft()
        assert present_notice_quotation(response, bundle, question) is response


@pytest.mark.asyncio
@pytest.mark.parametrize("supported", [True, False])
async def test_semantic_verification_still_runs_with_matching_opaque_fields_and_its_verdict_is_enforced(supported):
    bundle = CitationBundle.build([row()])
    response = present_notice_quotation(draft(), bundle, QUESTION)
    class Gateway:
        calls = 0
        async def generate(self, request):
            self.calls += 1
            text = "\n".join(i["content"] for i in request.input_items)
            assert PHONE not in text and EMAIL not in text and QUESTION in text
            assert text.count("PUBLIC_CONTACT_PHONE_") >= 2 and text.count("PUBLIC_CONTACT_EMAIL_") >= 2
            validate_payload(text)
            return LlmResponse(LlmResponseStatus.COMPLETED, "offline", "synthetic", usage=TokenUsage(1, 0, 10),
                output_text=json.dumps({"answers_question": True, "verdicts": [{"claim_id": "CLM-001",
                    "status": "SUPPORTED" if supported else "INSUFFICIENT"}]}))
    gateway = Gateway()
    request = LlmRequest("synthetic", "grounded_faq", "default", "Check", ())
    result = await SemanticClaimVerifier(gateway).check(request, response, bundle, deadline_ms=1000, output_tokens=384, question=QUESTION)
    assert result.claims_supported is supported and gateway.calls == 1


@pytest.mark.parametrize("attested", [True, False])
def test_history_policy_alternative_references_only_an_attested_public_source_without_keeping_contact_values(attested):
    source = row(fault=None if attested else "unattested")
    source["page_start"] = 2
    state = AgentState(NormalizedTurn("session", "turn", "actor", QUESTION), route=Route.GROUNDED_FAQ,
        terminal=Terminal.ANSWERED, draft=DraftResponse(CONTACT, is_grounded=True, gate_decision="grounded"),
        tool_flow=ToolFlowState(candidates=[source]))
    result = FinalChatResult("answered", "grounded_answer", CONTACT)
    safe = history_policy_alternative(state, result)
    assert safe.status == "abstained" and safe.citations == () and safe.response_class == "safe_refusal"
    assert PHONE not in safe.content and EMAIL not in safe.content and result.content == CONTACT
    assert ("https://ctsv.huce.edu.vn/public-notice" in safe.content) is attested
    validate_payload(safe.content)
