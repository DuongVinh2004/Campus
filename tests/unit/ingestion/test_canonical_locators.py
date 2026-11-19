"""Citation offsets must round-trip to the canonical source, including overlap."""
from dataclasses import replace
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "services/worker/src"))
from campus247_worker.ingestion.parse import DocumentParser
from campus247_worker.ingestion.chunk import SemanticChunker


@pytest.mark.parametrize("raw", [
    "\n\n# Synthetic policy\n\n## Section 1\n\n   first paragraph\n\nsecond paragraph  \n\n",
    "# Policy\r\n\r\n## First\r\n\r\nRepeated text repeated text.\r\n\r\n## Second\r\nRepeated text repeated text.",
    "# Policy\n## One\n  repeated words " * 3,
    "plain text\n\nwith paragraphs and trailing spaces    ",
    "# Tiếng Việt\n\n## Điều 1\n\nTrường Đại học\n\nNội dung mô phỏng.",
])
def test_sections_and_overlapping_chunks_are_exact_source_slices(raw):
    doc = DocumentParser().parse(raw)
    for section in doc.sections:
        assert doc.canonical_text[section.char_start:section.char_end] == section.content
    chunks = SemanticChunker(max_chars=20, overlap_chars=3).chunk(doc, "synthetic-version")
    assert chunks
    for chunk in chunks:
        assert 0 <= chunk.char_start < chunk.char_end <= len(doc.canonical_text)
        assert doc.canonical_text[chunk.char_start:chunk.char_end] == chunk.content


def test_parser_preserves_internal_paragraph_boundaries():
    doc = DocumentParser().parse("# Policy\n\n## Section\n\nfirst paragraph\n\nsecond paragraph")
    assert doc.sections[0].content == "first paragraph\n\nsecond paragraph"


def test_chunker_rejects_invented_source_locator():
    doc = DocumentParser().parse("# Policy\n\n## Section\n\nsynthetic content")
    bad = replace(doc, sections=(replace(doc.sections[0], char_start=0),))
    with pytest.raises(ValueError, match="locator"):
        SemanticChunker().chunk(bad, "synthetic-version")


def test_source_metadata_title_labels_plain_text_without_changing_provenance():
    raw = "  Nội dung mô phỏng.\r\n\r\nĐoạn thứ hai.  "
    parser = DocumentParser()
    original = parser.parse(raw)
    metadata = {"title": "  Quy định mô phỏng  ", "source_id": "synthetic-source"}
    titled = parser.parse(raw, metadata)
    assert titled.title == "Quy định mô phỏng"
    assert titled.canonical_text == original.canonical_text
    assert titled.canonical_hash == original.canonical_hash
    assert titled.metadata == metadata
    for chunk in SemanticChunker(max_chars=20, overlap_chars=3).chunk(titled, "synthetic-version"):
        assert chunk.section_path == titled.title
        assert titled.canonical_text[chunk.char_start:chunk.char_end] == chunk.content


def test_document_heading_takes_precedence_over_metadata_title():
    doc = DocumentParser().parse("# Source title\n\nLiteral source content", {"title": "Catalog title"})
    assert doc.title == "Source title"
    assert doc.sections[0].section_path == "Source title"


@pytest.mark.parametrize("title", [None, "", "   ", 12, ["title"]])
def test_missing_or_invalid_metadata_title_keeps_explicit_unknown_label(title):
    doc = DocumentParser().parse("Literal source content", {"title": title})
    assert doc.title == "Untitled Document"
    assert doc.sections[0].content == doc.canonical_text
