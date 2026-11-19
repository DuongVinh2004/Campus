from campus247.application.conversation.software_answer_style import (
    software_answer_style,
)
from campus247.application.retrieval.citations import CitationBundle
from campus247.application.retrieval.prompt_evidence import evidence_prompt_blocks


def test_snapshot_scope_reaches_both_actual_generation_and_verification_paths():
    source = "Bước 1: Truy cập trang https://office.com, ấn Sign in."
    note = "Ngày đối chiếu không phải ngày hiệu lực pháp lý."
    bundle = CitationBundle.build([{"chunk_id": "snapshot", "content_text": source, "applicability_note": note}])
    for semantic in (False, True):
        blocks = evidence_prompt_blocks(bundle, query="Tải Office như thế nào?", semantic=semantic)
        assert note in "\n".join(block.content for block in blocks)
    assert bundle.resolve("CIT-001").content_text == source


def test_software_presentation_supplies_no_domain_or_button_answers():
    style = software_answer_style("Tải Office 365 bằng tài khoản trường như thế nào?")
    assert style and "nguyên tên nút" in style and "citation_ids" in style
    assert "office.com" not in style and "Sign in" not in style
    assert software_answer_style("Hạn nộp hồ sơ là ngày nào?") is None
