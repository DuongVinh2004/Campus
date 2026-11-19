"""Focused evidence remains an exact excerpt; broad rules retain all conditions."""
from campus247.application.retrieval.citations import CitationBundle
from campus247.application.retrieval.excerpts import narrow_clause, question_focused_context
from campus247.infrastructure.retrieval.public_knowledge import PublicKnowledgeStore
from pathlib import Path

SOURCE = ("NỘI QUY Ở KÝ TÚC XÁ\n1. Sinh viên được cấp thẻ nội trú.\n"
          "2. Thực hiện đúng quy định về đăng ký hợp đồng ở nội trú và sự điều chuyển chỗ ở\n"
          "của ban Quản lý KTX, không được tự ý đổi chỗ ở.\n"
          "3. Tự giác giữ gìn vệ sinh phòng ở.\n4. Các vi phạm bị xử lý kỷ luật theo quy định.")


def test_permission_question_receives_only_exact_relevant_clause():
    result = narrow_clause(SOURCE, "Có được tự đổi chỗ ở với bạn trong ký túc xá không?")
    assert result in SOURCE and result.startswith("2.")
    assert "không được tự ý đổi chỗ ở" in result and "kỷ luật" not in result


def test_actual_huce_dormitory_clause_wins_over_shared_building_name():
    root = Path(__file__).resolve().parents[3]
    store = PublicKnowledgeStore(root / "data/huce-public-20261013", tenant_id="HUCE", campus_id="HUCE")
    source = next(row["content_text"] for row in store.rows if row["page_start"] == 70)
    result = narrow_clause(source, "Có được tự đổi chỗ ở với bạn trong ký túc xá không?")
    assert result in source and result.startswith("2.")
    assert "không được tự ý đổi chỗ ở" in result and "kỷ luật" not in result


def test_broad_or_ambiguous_questions_keep_the_complete_source():
    for query in ["Nội quy ký túc xá là gì?", "Điều kiện xét học bổng", "Có được ở ký túc xá không?"]:
        assert narrow_clause(SOURCE, query) == SOURCE


def test_prompt_excerpt_does_not_modify_citation_or_checksum():
    bundle = CitationBundle.build([{"content_text": SOURCE, "chunk_id": "unchanged"}])
    original = bundle.resolve("CIT-001")
    result = question_focused_context(bundle, "Có được tự đổi chỗ ở với bạn trong ký túc xá không?")
    assert "[CIT-001]" in result and "kỷ luật" not in result
    assert bundle.resolve("CIT-001") == original and original.content_text == SOURCE


def test_snapshot_scope_reaches_generation_without_becoming_source_evidence():
    note = "Bản nguồn chỉ áp dụng năm học 2025-2026; không xác nhận hạn hiện tại."
    bundle = CitationBundle.build([{"content_text": SOURCE, "chunk_id": "snapshot", "applicability_note": note}])
    prompt = question_focused_context(bundle, "Nội quy là gì?")
    assert note in prompt and "metadata" in prompt
    assert bundle.resolve("CIT-001").content_text == SOURCE
