"""Additive unit citations keep immutable source/hash verification and v1 rules."""
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import pytest
from campus247.application.conversation.citation_source import (
    CitationSourceService,
    CitationSourceUnavailable,
)
from campus247.application.conversation.stream_result import ApiCitation
from campus247.domain.shared.values import generate_uuid7
from campus247.ports.citation_source import CitationSourceExcerpt
from jsonschema import Draft202012Validator


def evidence():
    source, version, chunk = (generate_uuid7() for _ in range(3))
    text = "Lời mở đầu.\nSinh viên nộp hồ sơ bảo lưu tại phòng đào tạo."
    original = CitationSourceExcerpt(source, version, chunk, "Quy chế", "https://huce.edu.vn/quy-che",
        "2026", "CURRENT", {"section_path": "Điều 1"}, "HUCE", datetime.now(UTC)-timedelta(days=1),
        None, text, sha256(text.encode()).hexdigest())
    citation = ApiCitation(citation_id=generate_uuid7(), source_id=source, document_version_id=version,
        chunk_id=chunk, source_title=original.title, canonical_uri=original.canonical_uri,
        version_label="2026", source_status="CURRENT", locator=original.locator,
        quote=text.splitlines()[1], unit_id="a"*16, evidence_sha256=original.content_sha256)
    return original, citation.model_dump(exclude_none=True)


def test_additive_unit_metadata_passes_public_citation_schema():
    original, citation = evidence()
    schema = json.loads((Path(__file__).resolve().parents[2] /
                         "contracts/json-schema/citations/citation.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(citation)
    CitationSourceService._validate(original, citation, datetime.now(UTC))


@pytest.mark.parametrize("change", ["quote", "hash", "source", "version", "locator", "content", "expired"])
def test_unit_citation_still_rejects_tampered_or_stale_source(change):
    original, citation = evidence()
    if change == "quote":
        citation["quote"] = "Nội dung bịa đặt."
    elif change == "hash":
        citation["evidence_sha256"] = "0"*64
    elif change == "source":
        citation["source_id"] = generate_uuid7()
    elif change == "version":
        citation["document_version_id"] = generate_uuid7()
    elif change == "locator":
        citation["locator"] = {"section_path": "Điều 2"}
    elif change == "content":
        original = replace(original, content_text="Văn bản đã đổi.")
    else:
        original = replace(original, effective_until=datetime.now(UTC)-timedelta(seconds=1))
    with pytest.raises(CitationSourceUnavailable):
        CitationSourceService._validate(original, citation, datetime.now(UTC))


def test_v1_quote_requires_original_prefix_as_before():
    original, citation = evidence()
    citation.pop("unit_id")
    with pytest.raises(CitationSourceUnavailable):
        CitationSourceService._validate(original, citation, datetime.now(UTC))
    citation["quote"] = original.content_text[:30]
    CitationSourceService._validate(original, citation, datetime.now(UTC))
