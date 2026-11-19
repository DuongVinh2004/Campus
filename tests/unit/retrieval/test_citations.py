from __future__ import annotations

from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[3]
API_SRC = ROOT / "services" / "api" / "src"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))

from campus247.application.retrieval.citations import CitationBundle, CitationRecord


def test_citation_bundle_build_and_resolve() -> None:
    chunks = [
        {
            "chunk_id": "chunk_101",
            "source_id": "src_1",
            "document_version_id": "ver_1",
            "source_status": "SYNTHETIC",
            "title": "Quy chế Học phí HUCE",
            "issuer": "Phòng Đào tạo",
            "canonical_uri": "https://demo.huce.example/policy/hoc-phi",
            "section_path": "Điều 1. Mức học phí",
            "content_text": "Mức học phí là 480.000 VNĐ / tín chỉ.",
            "page_start": 1,
            "page_end": 1,
        }
    ]

    bundle = CitationBundle.build(chunks)
    assert len(bundle.citations) == 1
    assert "CIT-001" in bundle.citations

    cit = bundle.resolve("CIT-001")
    assert isinstance(cit, CitationRecord)
    assert cit.citation_id == "CIT-001"
    assert cit.title == "Quy chế Học phí HUCE"
    assert cit.simulation_label is True
    assert cit.quote_span_hash.startswith("sha256:")

    # Prompt context contains citation label
    prompt_ctx = bundle.to_prompt_context()
    assert "[CIT-001]" in prompt_ctx
    assert "480.000 VNĐ" in prompt_ctx


def test_citation_bundle_resolve_unknown_returns_none() -> None:
    bundle = CitationBundle.build([])
    assert bundle.resolve("CIT-999") is None


@pytest.mark.parametrize("metadata", [{}, {"source_status": "CURRENT"}, {"simulation_label": False}])
def test_citation_bundle_does_not_invent_simulation_metadata(metadata) -> None:
    bundle = CitationBundle.build([{"content_text": "Nguồn công khai", **metadata}])
    assert bundle.resolve("CIT-001").simulation_label is False
