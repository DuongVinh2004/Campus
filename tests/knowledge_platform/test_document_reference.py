from campus247.application.knowledge.document_reference import (
    focused_lab_permission_question,
    named_form_rerank_question,
    named_notice_rerank_question,
    preferred_document_versions,
    referenced_document_groups,
    focused_multi_document_question,
    verified_form_rerank_text,
    verified_edge_rerank_text,
)
import pytest
from campus247.application.knowledge.platform_models import PlatformError

VERSIONS = [
    {"version_id": "rate", "title": "Quyết định số 924 — Mức thu học phí 2026-2027"},
    {"version_id": "waiver", "title": "Thông báo miễn giảm học phí 2026-2027"},
    {"version_id": "book", "title": "Sổ tay sinh viên 2026-2027"},
    {"version_id": "lab", "title": "Nội quy Phòng thực hành máy tính Trung tâm CNTT&CSDL"},
]


def test_explicit_document_and_rate_subject_do_not_lose_slots_to_the_handbook():
    assert preferred_document_versions("Theo QĐ 924, vừa làm vừa học thu bao nhiêu?", VERSIONS) == ["rate"]
    assert preferred_document_versions("Cử nhân K70 học phí bao nhiêu mỗi tín chỉ?", VERSIONS) == ["rate"]


def test_rate_preference_does_not_capture_waiver_or_unrelated_queries():
    assert preferred_document_versions("Hồ sơ miễn giảm học phí nộp ở đâu?", VERSIONS) is None
    assert preferred_document_versions("Điều kiện học bổng?", VERSIONS) is None
    assert preferred_document_versions("Theo QĐ 123456, học kỳ 2 có gì?", VERSIONS) is None


def test_lab_reference_is_narrower_than_a_generic_usb_question():
    assert preferred_document_versions("Cắm USB ở phòng thực hành máy tính cần xin phép ai?", VERSIONS) == ["lab"]
    assert preferred_document_versions("Tôi có thể dùng USB cá nhân không?", VERSIONS) is None


def test_permission_synonyms_add_no_actor_or_answer_and_keep_the_original_question():
    question = "Cắm USB ở phòng thực hành máy tính HUCE cần xin phép ai?"
    expanded = focused_lab_permission_question(question)
    assert expanded.startswith(question) and "thiết bị nhớ ngoài" in expanded
    assert "cán bộ" not in expanded
    for unrelated in ("USB hỏng phải bồi thường bao nhiêu?", "Dữ liệu USB cần bảo vệ thế nào?"):
        assert focused_lab_permission_question(unrelated) == unrelated


def test_form_ranking_preserves_the_full_question_and_adds_no_answer_terms():
    question = "Theo mẫu đơn học bổng STEM Quỹ Châu Á năm học 2025-2026, ý7 và8 gợi ý gì?"
    assert named_form_rerank_question(question) == question.replace("ý7", "ý 7").replace("và8", "và 8")
    assert named_form_rerank_question("Theo thông báo học bổng STEM Quỹ Châu Á năm học 2025-2026, mức học bổng bao nhiêu?") is None
    assert named_form_rerank_question("Mẫu đơn khác cần những nội dung nào?") is None


def test_form_ranking_metadata_must_match_a_section_from_the_sealed_rendition():
    text = "STT | Họ và tên | Quan hệ | Tuổi | Nghề nghiệp"
    section = "Sơ yếu lý lịch — bảng người chung sống — PDF 6"
    assert verified_form_rerank_text("Thông báo", section, text, {section}) == "Thông báo\n" + section + "\n" + text
    for wrong in ("Phần sửa không được duyệt", "", [section]):
        with pytest.raises(PlatformError, match="SOURCE_LOCATOR_MISMATCH"):
            verified_form_rerank_text("Thông báo", wrong, text, {section})


def test_edge_ranking_metadata_requires_both_reconstructed_edge_role_and_exact_sealed_locator():
    text = "71CS\nHọc phần tiên quyết:\n607712– 4\nNative first name\n→\n607713– 4\nNative second name"
    section = "71CS — Học phần tiên quyết — 607712 → 607713 — PDF 1"
    edge = {"evidence_kind": "edge", "course_codes": ["607712", "607713"]}
    result = verified_edge_rerank_text("Kế hoạch 71CS", section, text, edge, {section})
    assert result == "Kế hoạch 71CS\n" + section + "\n" + text
    assert result.endswith(text) and "tín chỉ" not in result
    for caps in (None, {}, {"evidence_kind": "semester"}, {"evidence_kind": "cell"}):
        assert verified_edge_rerank_text("Untrusted title", "Untrusted section", text, caps, set()) == text
    with pytest.raises(PlatformError, match="SOURCE_LOCATOR_MISMATCH"):
        verified_edge_rerank_text("Kế hoạch 71CS", "Invented relationship", text, edge, {section})


def test_notice_ranking_context_preserves_explicit_document_year_and_complete_question():
    question = "Theo thông báo học bổng STEM Quỹ Châu Á năm học 2025-2026, chức danh và họ tên in dưới chữ ký là gì?"
    assert named_notice_rerank_question(question) == question
    for unrelated in ("Ai ký thông báo này?", "Thông báo học bổng STEM Quỹ Châu Á do ai ký?",
            "Theo thông báo học bổng khác năm học 2025-2026, ai ký?",
            "Theo thông báo học bổng STEM Quỹ Châu Á, ai ký?",
            "Theo thông báo học bổng STEM Quỹ Châu Á năm học 2025-2026"):
        assert named_notice_rerank_question(unrelated) is None


def test_multi_document_reference_keeps_the_union_instead_of_only_tuition():
    versions = VERSIONS + [{"version_id": "regulation", "title": "Quy chế đào tạo 1486 ngày 06/11/2023"}]
    for question in ("Đối chiếu QĐ 924 và Quy chế 1486: mức học phí K71 và giới hạn đăng ký học kỳ là gì?",
                     "Quy chế số 1486 với quyết định 924 có quy định gì về đăng ký học và học phí?"):
        assert set(preferred_document_versions(question, versions)) == {"rate", "regulation"}
    assert preferred_document_versions("QĐ 924 và Quy chế 1486 về học phí?", VERSIONS) is None
    assert referenced_document_groups("QĐ 924 và Quy chế 1486", versions) == [["regulation"], ["rate"]]
    assert referenced_document_groups("QĐ 924 và Quy chế 99999", versions) is None
    assert referenced_document_groups("QĐ 924", versions) is None


def test_multi_reference_focus_removes_only_pure_preamble_and_keeps_all_requested_facts():
    question = "Tôi thuộc K68. Theo QĐ 17 và Quy chế 23, điều kiện nộp và thời hạn bổ sung hồ sơ là gì?"
    assert focused_multi_document_question(question) == "điều kiện nộp và thời hạn bổ sung hồ sơ là gì?"
    for unrelated in ("Theo QĐ 17, điều kiện là gì?", "Theo QĐ 17 và Quy chế 23 về hồ sơ, có gì?",
        "Không theo QĐ 17, tôi muốn xem văn bản khác", "K68 cần nộp gì và tới hạn nào?"):
        assert focused_multi_document_question(unrelated) == unrelated


def test_notice_reranking_does_not_require_the_probe_punctuation_or_prefix():
    questions = [
        "Thông báo học bổng STEM Quỹ Châu Á năm học 2025-2026 có số và ngày nào?",
        "Theo thông báo học bổng STEM Quỹ Châu Á năm học 2025-2026: số văn bản và ngày ban hành là gì?",
    ]
    for question in questions:
        assert named_notice_rerank_question(question) == question
