import json

import pytest

from campus247.application.retrieval.citations import CitationBundle
from campus247.application.retrieval.evidence_gate import EvidenceGate, parse_grounded_claims
from campus247.application.retrieval.form_quotation import present_form_quotation
from campus247.ports.llm import LlmResponse, LlmResponseStatus, TokenUsage

PREFIX = "Theo mẫu sơ yếu lý lịch học bổng STEM Quỹ Châu Á năm học 2025-2026, "


def fixture(text):
    row = {"source_id": "source", "document_version_id": "version", "release_id": "release",
        "title": "Học bổng STEM Quỹ Châu Á năm học 2025-2026", "content_text": text,
        "simulation_label": False, "canonical_uri": "https://huce.edu.vn/form.pdf"}
    response = LlmResponse(LlmResponseStatus.COMPLETED, "fixture", "synthetic", usage=TokenUsage(10, 0, 20),
        output_text=json.dumps({"claims": [{"text": "Draft with an added list number1.",
            "citation_ids": ["CIT-001"], "claim_type": "policy"}]}))
    return row, response


@pytest.mark.parametrize("source,query,quote", [
    ("Ảnh 4x6\nSƠ YẾU LÝ LỊCH\nHọ và tên: \nSĐT bố/ mẹ: ",
        PREFIX + "cần ảnh cỡ nào và có mục số điện thoại bố mẹ không?", "Ảnh 4x6\nSĐT bố/ mẹ:"),
    ("Họ và tên những người đang chung sống với gia đình\nSTT | Họ và tên | Quan hệ | Tuổi | Nghề nghiệp\nLỜI CAM ĐOAN",
        PREFIX + "bảng người chung sống với gia đình có những cột nào?",
        "Họ và tên những người đang chung sống với gia đình\nSTT | Họ và tên | Quan hệ | Tuổi | Nghề nghiệp"),
    ("ĐƠN XIN\n7. Prompt A\n8. Prompt B", "Theo mẫu đơn học bổng STEM Quỹ Châu Á năm học 2025-2026, ý7 và8 ghi gì?",
        "7. Prompt A\n8. Prompt B"),
    ("ĐƠN XIN\nNghĩa vụ của sinh viên nhận học bổng\no Source obligation",
        "Theo mẫu đơn học bổng STEM Quỹ Châu Á năm học 2025-2026, nghĩa vụ gồm gì?",
        "Nghĩa vụ của sinh viên nhận học bổng\no Source obligation"),
    ("6. Địa điểm, thời gian tiếp nhận hồ sơ:\n- Thời gian tiếp nhận hồ sơ: từ 02/02/2026 đến hết ngày 13/02/2026.\n- Địa điểm: Phòng A.",
        "Theo thông báo học bổng STEM Quỹ Châu Á năm học 2025-2026, thời gian nhận hồ sơ từ ngày nào đến ngày nào?",
        "Thời gian tiếp nhận hồ sơ: từ 02/02/2026 đến hết ngày 13/02/2026.\n- Địa điểm: Phòng A."),
])
def test_verbatim_form_output_keeps_units_labels_and_only_printed_numbering(source, query, quote):
    row, response = fixture(source)
    bundle = CitationBundle.build([row])
    quoted = present_form_quotation(response, bundle, query)
    draft = parse_grounded_claims(quoted.output_text)
    assert draft.claims[0].text == quote
    assert EvidenceGate().verify(draft, bundle).passed
    assert quoted.usage == response.usage


@pytest.mark.parametrize("fault", ["unofficial", "synthetic", "unbound", "ambiguous", "missing_prompt"])
def test_quotation_does_not_authorize_unverified_sources_or_invent_missing_prompt(fault):
    row, response = fixture("7. Prompt A\n8. Prompt B")
    question = "Theo mẫu đơn học bổng STEM Quỹ Châu Á năm học 2025-2026, ý7 và8 ghi gì?"
    if fault == "unofficial": row["canonical_uri"] = "https://example.invalid/form.pdf"
    if fault == "synthetic": row["simulation_label"] = True
    if fault == "unbound": row["release_id"] = None
    if fault == "missing_prompt": question = question.replace("ý7 và8", "ý10")
    bundle = CitationBundle.build([row, dict(row)] if fault == "ambiguous" else [row])
    assert present_form_quotation(response, bundle, question) is response


def test_blank_fields_cannot_be_filled_or_used_to_answer_an_absent_column_or_photo_size():
    row, response = fixture("Ảnh 4x6\nSƠ YẾU LÝ LỊCH\nSĐT bố/ mẹ: ")
    bundle = CitationBundle.build([row])
    for query in [PREFIX + "ảnh3x4 đúng không và có mục số điện thoại bố mẹ không?",
            PREFIX + "bố mẹ tôi có số điện thoại là gì?", PREFIX + "bảng gia đình có cột số CCCD không?",
            "Theo thông báo khác, cần ảnh cỡ nào?"]:
        assert present_form_quotation(response, bundle, query) is response
