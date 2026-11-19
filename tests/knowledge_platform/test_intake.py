import asyncio
import io
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from starlette.requests import Request

from campus247.application.knowledge.platform_models import IntakeMetadata, PlatformError
from campus247.infrastructure.knowledge.multipart import parse_upload
from campus247.infrastructure.knowledge.storage import FileKnowledgeStorage, checked_path
from campus247_worker.knowledge import chunks_for_pages
from campus247_worker.knowledge_parse import extract

from .conftest import ROOT


def multipart(payload, *, filename="source.txt", mime="text/plain", finish=True):
    content = b'--test\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n{}\r\n'
    content += f'--test\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n'.encode()
    content += payload + (b'\r\n--test--\r\n' if finish else b'')
    chunks = [content[i:i+13] for i in range(0,len(content),13)]
    async def receive():
        data = chunks.pop(0)
        return {"type":"http.request", "body":data, "more_body":bool(chunks)}
    return Request({"type":"http","method":"POST","path":"/", "headers":[(b"content-type",b"multipart/form-data; boundary=test")]}, receive)


def test_streamed_upload_and_integrity(retained_directory):
    storage = FileKnowledgeStorage(ROOT, retained_directory / "artifacts")
    payload = "Đối chiếu số tiền 250.000 đồng và hạn 15/10/2026.".encode()
    upload, artifact, metadata = asyncio.run(parse_upload(multipart(payload), storage))
    assert upload.filename == "source.txt"
    assert metadata == b"{}"
    assert storage.read(artifact.__dict__) == payload
    assert len(list(storage.root.iterdir())) == 1
    # No filename or request locator becomes a physical artifact key.
    with pytest.raises(ValueError):
        storage.path("../../outside")
    with pytest.raises(ValueError):
        checked_path(ROOT.parent / "outside", ROOT)


@pytest.mark.parametrize("payload,filename,mime,code", [
    (b"not a PDF", "source.pdf", "application/pdf", "MIME_MISMATCH"),
    (b"\x00binary", "source.txt", "text/plain", "MIME_MISMATCH"),
    (b"", "source.txt", "text/plain", "EMPTY_FILE"),
])
def test_mime_rejected_files_preserved(retained_directory,payload,filename,mime,code):
    storage = FileKnowledgeStorage(ROOT, retained_directory / "artifacts")
    with pytest.raises(PlatformError, match=code):
        asyncio.run(parse_upload(multipart(payload,filename=filename,mime=mime), storage))
    assert len(list(storage.root.iterdir())) == 1


def test_interrupted_upload_retained_not_accepted(retained_directory):
    storage = FileKnowledgeStorage(ROOT, retained_directory / "artifacts")
    with pytest.raises(PlatformError, match="INCOMPLETE_MULTIPART"):
        asyncio.run(parse_upload(multipart(b"partially received input",finish=False), storage))
    assert len(list(storage.root.iterdir())) == 1


def test_metadata_dates_and_explicit_scope():
    common = {"title":"Tài liệu", "owner_unit":"Đào tạo", "canonical_uri":"urn:test:document",
              "programs":["PUBLIC"],"audiences":["STUDENT"]}
    with pytest.raises(ValidationError):
        IntakeMetadata(**common, effective_from="2026-10-01T00:00:00")
    with pytest.raises(ValidationError):
        IntakeMetadata(**{**common,"programs":[]})
    metadata = IntakeMetadata(**common, effective_from="2026-10-01T07:00:00+07:00")
    assert metadata.model_dump(mode="json")["effective_from"] == "2026-10-01T00:00:00Z"


def test_scan_and_text_locators():
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=300,height=400)
    output = io.BytesIO(); writer.write(output)
    result = extract(output.getvalue(), "application/pdf")
    assert result["page_count"] == 1
    assert result["issues"] == [{"page":1,"block":1,"code":"TEXT_REQUIRES_REVIEW"}]
    pages = [{"page":4,"text":"# Điều kiện\nSinh viên nộp hồ sơ trước 15/10/2026. Ngoại lệ: hồ sơ bổ sung nộp trước 20/10/2026."}]
    chunks = chunks_for_pages(pages,"0196a001-0010-7000-8000-000000000001","Tài liệu")
    assert all(c["page"] == 4 for c in chunks)
    assert "Ngoại lệ" in chunks[0]["text"]
    assert chunks == chunks_for_pages(pages,"0196a001-0010-7000-8000-000000000001","Tài liệu")
    assert extract("Một đoạn văn bản đủ dài để chia đoạn.".encode(),"text/plain")["pages"][0]["page"] is None


def test_text_citation_locator_matches_serialized_contract():
    from campus247.infrastructure.knowledge.runtime import source_locator
    from campus247.application.conversation.stream_result import CitationLocator
    row = {"section_path":"Local / block 1","page_start":None,"page_end":None}
    assert source_locator(row) == CitationLocator(**row).model_dump(exclude_none=True)
    row.update(page_start=2,page_end=3)
    assert source_locator(row) == CitationLocator(**row).model_dump(exclude_none=True)


def test_citation_checks_full_evidence_hash_not_only_visible_quote():
    from datetime import UTC, datetime, timedelta
    from campus247.application.conversation.citation_source import CitationSourceService, CitationSourceUnavailable
    from campus247.ports.citation_source import CitationSourceExcerpt
    from campus247.application.knowledge.platform_models import digest
    source = CitationSourceExcerpt("source","version","chunk","Title","urn:test","v1","CURRENT",
        {"section_path":"Block 1"},"Test issuer",datetime.now(UTC)-timedelta(days=1),None,
        "Same visible quote. Altered hidden remainder.",digest(b"Same visible quote. Altered hidden remainder."))
    citation = {"source_id":"source","document_version_id":"version","chunk_id":"chunk","source_title":"Title",
        "canonical_uri":"urn:test","version_label":"v1","source_status":"CURRENT",
        "locator":{"section_path":"Block 1"},"quote":"Same visible quote.","evidence_sha256":"f"*64}
    with pytest.raises(CitationSourceUnavailable):
        CitationSourceService._validate(source,citation,datetime.now(UTC))
    citation["evidence_sha256"] = source.content_sha256
    CitationSourceService._validate(source,citation,datetime.now(UTC))
