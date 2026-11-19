"""Claim serialization and safe diagnostics retain the accepted support gate."""
import json

import pytest

from campus247.application.retrieval.citations import CitationBundle
from campus247.application.retrieval.evidence_gate import EvidenceGate, parse_grounded_claims


def bundle():
    return CitationBundle.build([{"content_text": "Mức học phí tiêu chuẩn là 480.000 VNĐ mỗi tín chỉ.",
        "source_id": "synthetic-source", "chunk_id": "synthetic-chunk"}])


def test_render_only_verified_material_claims_and_citation_metadata():
    draft = parse_grounded_claims(json.dumps({"claims": [{"text": "Học phí tiêu chuẩn là 480.000 VNĐ mỗi tín chỉ.",
        "citation_ids": ["CIT-001"], "claim_type": "fee"}]}))
    assert draft.response_text.endswith("[CIT-001]")
    result = EvidenceGate(.78).verify(draft, bundle())
    assert result.passed and result.diagnostics[0]["overlap_ratio"] == 1
    assert result.diagnostics[0]["threshold"] == .78
    assert "480.000" not in json.dumps(result.diagnostics)


@pytest.mark.parametrize("text,code", [
    ("Học phí là 480.000 VNĐ.", "MISSING_CITATION"),
    ("Học phí là 480.000 VNĐ [CIT-999]", "UNKNOWN_CITATION"),
    ("Sinh viên nhận ô tô điện miễn phí [CIT-001]", "LOW_SUPPORT"),
])
def test_gate_rejects_with_safe_exact_reason(text, code):
    result = EvidenceGate(.78).verify(parse_grounded_claims(text), bundle())
    assert not result.passed and result.diagnostics[0]["reason_code"] == code
    assert text not in json.dumps(result.diagnostics)


@pytest.mark.parametrize("payload", ["```json {} ```", '{"claims":[]}',
    '{"claims":[{"text":"fee","citation_ids":[],"claim_type":"fee"}]}',
    '{"claims":[{"text":"fee","citation_ids":["CIT-001"],"claim_type":"fee","extra":"unverified"}]}',
    '{"claims":[{"text":"fee [CIT-999]","citation_ids":["CIT-001"],"claim_type":"fee"}]}',
    '{"claims":[{"text":"fee","citation_ids":["CIT-001"],"claim_type":"fee"}],"response_text":"hidden unsupported claim"}',
])
def test_no_json_repair_no_uncited_or_hidden_response(payload):
    with pytest.raises((ValueError, TypeError)):
        parse_grounded_claims(payload)


def test_citation_markup_does_not_count_as_fee_support_or_penalty():
    draft = parse_grounded_claims("Học phí tiêu chuẩn là 480.000 VNĐ mỗi tín chỉ [CIT-001]")
    result = EvidenceGate(.78).verify(draft, bundle())
    assert result.passed and result.diagnostics[0]["overlap_ratio"] == 1
