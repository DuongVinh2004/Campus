import json

from campus247.application.retrieval.citations import CitationBundle
from campus247.application.retrieval.evidence_gate import parse_grounded_claims
from campus247.application.retrieval.policy_quotation import present_policy_quotation
from campus247.ports.llm import LlmResponse, LlmResponseStatus, TokenUsage


def test_quotation_keeps_common_subject_complete_selected_branch_and_exclusions():
    source = ("Điều 14. Nghỉ học tạm thời, thôi học\n1. Sinh viên được xin nghỉ học tạm thời và bảo lưu kết quả đã học trong các trường hợp sau:\n"
        "a) Được điều động vào lực lượng vũ trang;\n"
        "d) Vì lý do cá nhân khác nhưng đã phải học tối thiểu 01 học kỳ ở Trường và không thuộc các trường hợp bị xem xét buộc thôi học hoặc xem xét kỷ luật.")
    bundle = CitationBundle.build([{"content_text": source}])
    response = LlmResponse(LlmResponseStatus.COMPLETED, "fixture", "synthetic",
        output_text=json.dumps({"claims": [{"text": "Sinh viên cần đủ điều kiện để nghỉ vì lý do cá nhân, không bị xem xét kỷ luật.",
            "citation_ids": ["CIT-001"], "claim_type": "policy"}]}), usage=TokenUsage(10, 0, 25))
    normalized = present_policy_quotation(response, bundle, "Theo Quy chế 1486, nghỉ học vì lý do cá nhân cần điều kiện gì?")
    claim = parse_grounded_claims(normalized.output_text).claims[0]
    assert claim.text.startswith("Sinh viên được xin nghỉ học tạm thời")
    assert "tối thiểu 01 học kỳ" in claim.text and "buộc thôi học hoặc xem xét kỷ luật" in claim.text
    assert "lực lượng vũ trang" not in claim.text
    assert normalized.usage == response.usage and claim.citation_ids == ("CIT-001",)
    assert present_policy_quotation(response, bundle, "Tôi có được nghỉ không?") is response
