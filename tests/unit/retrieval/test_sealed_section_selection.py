"""A locator can aid preselection only when bound to the exact parent."""
from campus247.application.retrieval.candidate_selection import select_parent_spans


def candidates():
    return [{"id": str(i), "source_id": "source", "document_version_id": "version",
        "content_checksum": f"checksum-{i}", "rerank_text": f"Unrelated original paragraph {i}",
        "section_path": "Other section", "title": "Other document"} for i in range(4)]


def test_reviewed_locator_can_select_a_short_signatory_parent_without_changing_evidence():
    rows = candidates()
    target = rows[-1]
    target.update(rerank_text="TL. HIỆU TRƯỞNG\nPHÓ TRƯỞNG PHÒNG\nA printed signatory",
        section_path="Chức danh và họ tên in dưới chữ ký")
    query = "Chức danh và họ tên in dưới chữ ký là gì?"
    assert target not in select_parent_spans(rows, [], query)
    target["verified_sections"] = {target["section_path"]}
    selected = select_parent_spans(rows, [], query)
    assert len(selected) == 3 and any(row is target for row in selected)
    assert target["rerank_text"] == "TL. HIỆU TRƯỞNG\nPHÓ TRƯỞNG PHÒNG\nA printed signatory"
    assert target["content_checksum"] == "checksum-3"


def test_a_section_from_another_parent_does_not_reserve_a_reranker_slot():
    rows = candidates()
    target = rows[-1]
    target.update(section_path="Chức danh chữ ký", verified_sections={"Different sealed section"})
    assert target not in select_parent_spans(rows, [], "Chức danh chữ ký?")


def test_adjacent_recipient_label_beats_scattered_same_words_in_application_boilerplate():
    rows = candidates()
    for row in rows[:3]:
        row["rerank_text"] = "Nơi làm thủ tục và tiếp nhận hồ sơ. Danh sách này được gửi tới khoa."
    target = rows[-1]
    target["rerank_text"] = "Nơi nhận:\n- Như trên;\n- Ban Giám hiệu;\n- Lưu: VT."
    selected = select_parent_spans(rows, [], "Mục Nơi nhận liệt kê những nơi nào?")
    assert any(row is target for row in selected) and len(selected) == 3
    assert target["rerank_text"].startswith("Nơi nhận:")
