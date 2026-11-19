import json

import pytest

from campus247.application.retrieval.citations import CitationBundle
from campus247.application.retrieval.evidence_gate import parse_grounded_claims
from campus247.application.retrieval.question_scope import loan_outcome_unanswered, relation_partial_note
from campus247.application.retrieval.semantic_support import SemanticClaimVerifier
from campus247.ports.llm import LlmRequest, LlmResponse, LlmResponseStatus, TokenUsage


FACT = "Xác nhận để vay vốn chính sách xã hội cần đơn theo mẫu ngân hàng, kèm giấy xác nhận tình trạng học tập."
QUESTION = "Chỉ có giấy xác nhận là đủ để vay rồi chứ?"


def draft():
    return parse_grounded_claims(json.dumps({"claims": [{"text": FACT,
        "citation_ids": ["CIT-001"], "claim_type": "procedure"}]}))


@pytest.mark.asyncio
@pytest.mark.parametrize("answer,status,supported", [(False, "SUPPORTED", True),
    (False, "INSUFFICIENT", False), (True, "CONTRADICTED", False), ("false", "SUPPORTED", False)])
async def test_question_coverage_cannot_turn_unknown_or_unsupported_claims_into_facts(answer, status, supported):
    class Gateway:
        async def generate(self, request):
            return LlmResponse(LlmResponseStatus.COMPLETED, "scripted", "synthetic",
                output_text=json.dumps({"answers_question": answer,
                    "verdicts": [{"claim_id": "CLM-001", "status": status}]}), usage=TokenUsage(1, 0, 10))
    bundle = CitationBundle.build([{"content_text": FACT}])
    request = LlmRequest("synthetic", "grounded_faq", "default", "Check", ())
    response = LlmResponse(LlmResponseStatus.COMPLETED, "scripted", "synthetic",
        output_text=json.dumps({"claims": [{"text": FACT, "citation_ids": ["CIT-001"], "claim_type": "procedure"}]}))
    verifier = SemanticClaimVerifier(Gateway())
    checked = await verifier.check(request, response, bundle, deadline_ms=1000, output_tokens=384, question=QUESTION)
    assert checked.claims_supported is supported
    assert not await verifier.verify(request, response, bundle, deadline_ms=1000, output_tokens=384, question=QUESTION)


def test_paperwork_cannot_cover_outcome_but_document_component_question_is_distinct():
    assert loan_outcome_unanswered(QUESTION, draft())
    assert not loan_outcome_unanswered("Giấy tình trạng học tập đã đủ thành phần trong danh mục vay chưa?", draft())
    bundle = CitationBundle.build([{"content_text": FACT}])
    assert "chưa xác minh được điều kiện đủ" in relation_partial_note(QUESTION, QUESTION, draft(), bundle)
    assert relation_partial_note("Thủ tục làm lại thẻ?", "Thủ tục làm lại thẻ?", draft(), bundle) is None
