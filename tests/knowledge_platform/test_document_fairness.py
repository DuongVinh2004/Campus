"""Explicit-reference selection is bounded and never supplies relevance/admission."""
import pytest

from campus247.application.retrieval.candidate_selection import select_parent_spans


def row(identifier, version):
    return {"id": identifier, "document_version_id": version, "source_id": "source-"+version,
        "content_checksum": identifier, "rerank_text": "Synthetic term match for document selection.",
        "content_text": "Synthetic term match for document selection.", "title": "Synthetic document"}


def test_each_explicit_document_keeps_a_slot_under_one_documents_heavy_repetition():
    crowded = [row(str(i), "first") for i in range(20)]
    second = row("second", "other")
    selected = select_parent_spans(crowded+[second], crowded+[second], "Synthetic term match",
        required_version_groups=[["first"], ["other"]])
    assert len(selected) == 3 and {r["document_version_id"] for r in selected} == {"first", "other"}
    assert second in selected


def test_missing_reference_cannot_be_invented_and_bounds_do_not_silently_drop_a_reference():
    original = row("one", "first")
    assert select_parent_spans([original], [], "Synthetic", required_version_groups=[["missing"]]) == [original]
    with pytest.raises(ValueError):
        select_parent_spans([original], [], "Synthetic", required_version_groups=[[str(i)] for i in range(4)])
