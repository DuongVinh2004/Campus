"""Boundary tests use a fake sandbox; they do not measure conversion fidelity."""
from __future__ import annotations

import asyncio
import hashlib
from io import BytesIO
import json
import sys
import zipfile
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

WORKER = Path(__file__).resolve().parents[3] / "services" / "worker" / "src"
if str(WORKER) not in sys.path:
    sys.path.insert(0, str(WORKER))

from campus247_worker.learning.pptx import (  # noqa: E402
    ConverterLimits, PptxConversionError, PptxConverter, PptxConverterConfig,
    ProcessResult, validate_pptx,
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def presentation(root: Path, additions: dict[str, bytes] | None = None) -> Path:
    target = root / "lesson.pptx"
    parts = {
        "[Content_Types].xml": b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/></Types>',
        "_rels/.rels": b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/></Relationships>',
        "ppt/presentation.xml": b'<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>',
        "ppt/slides/slide1.xml": b'<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>',
    }
    parts.update(additions or {})
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in parts.items():
            archive.writestr(name, value)
    return target


class FakeSandbox:
    network_disabled = True
    resource_limits_enforced = True

    def __init__(self, data=b"%PDF-1.4\nSYNTHETIC BOUNDARY OUTPUT\n%%EOF", returncode=0, wait=False, omit=False):
        self.data, self.returncode, self.wait, self.omit = data, returncode, wait, omit
        self.jobs, self.cancelled = [], []

    async def run(self, job):
        self.jobs.append(job)
        if self.wait:
            await asyncio.Future()
        if not self.omit:
            with (job.output_directory / "source.pdf").open("xb") as stream:
                stream.write(self.data)
        return ProcessResult(self.returncode)

    async def cancel(self, job):
        self.cancelled.append(job)


@pytest.fixture
def configured(tmp_path):
    root = tmp_path.resolve()
    output = root / "renditions"
    output.mkdir()
    executable = root / "fake-converter.exe"
    executable.write_bytes(b"test-configured-binary-not-executed")
    return PptxConverterConfig(root, output, executable, digest(executable), "test-fixture-version")


def test_valid_package_bounded_and_hash_checked(tmp_path):
    source = presentation(tmp_path)
    metadata = validate_pptx(source, digest(source))
    assert metadata.slide_count == 1
    assert metadata.source_bytes == source.stat().st_size
    assert metadata.source_sha256 == digest(source)


def chart_workbook(additions=None):
    parts = {
        '[Content_Types].xml': b'<Types><Override ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/></Types>',
        '_rels/.rels': b'<Relationships><Relationship Target="xl/workbook.xml"/></Relationships>',
        'xl/workbook.xml': b'<workbook/>',
        'xl/worksheets/sheet1.xml': b'<worksheet><sheetData><row><c><v>12</v></c></row></sheetData></worksheet>',
    }
    parts.update(additions or {})
    data = BytesIO()
    with zipfile.ZipFile(data, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in parts.items():
            archive.writestr(name, value)
    return data.getvalue()


def chart_parts(data):
    return {
        'ppt/charts/chart1.xml': b'<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><c:externalData r:id="data1"/></c:chartSpace>',
        'ppt/charts/_rels/chart1.xml.rels': b'<Relationships><Relationship Id="data1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/package" Target="../embeddings/data.xlsx"/></Relationships>',
        'ppt/embeddings/data.xlsx': data,
    }


def test_internal_literal_chart_workbook_is_supported(tmp_path):
    source = presentation(tmp_path, chart_parts(chart_workbook()))
    metadata = validate_pptx(source, digest(source))
    assert metadata.slide_count == 1 and metadata.expanded_bytes > source.stat().st_size


@pytest.mark.parametrize(('additions', 'code'), [
    ({'xl/vbaProject.bin': b'macro'}, 'PPTX_CHART_DATA_REJECTED'),
    ({'xl/worksheets/sheet1.xml': b'<worksheet><f>WEBSERVICE("https://outside.invalid")</f></worksheet>'}, 'PPTX_CHART_FORMULA_REJECTED'),
    ({'xl/_rels/workbook.xml.rels': b'<Relationships><Relationship TargetMode="External" Target="https://outside.invalid"/></Relationships>'}, 'PPTX_EXTERNAL_RELATIONSHIP_REJECTED'),
    ({'../escape.xml': b'<x/>'}, 'PPTX_CHART_DATA_REJECTED'),
    ({'xl/styles.xml': b'<!DOCTYPE x [<!ENTITY a "text">]><x>&a;</x>'}, 'PPTX_XML_ENTITY_REJECTED'),
])
def test_chart_workbooks_keep_active_content_external_data_and_expansion_boundaries(tmp_path, additions, code):
    source = presentation(tmp_path, chart_parts(chart_workbook(additions)))
    with pytest.raises(PptxConversionError, match=code):
        validate_pptx(source, digest(source))


def test_unreferenced_embedded_workbook_is_not_accepted_as_chart_data(tmp_path):
    source = presentation(tmp_path, {'ppt/embeddings/data.xlsx': chart_workbook()})
    with pytest.raises(PptxConversionError, match='PPTX_ACTIVE_CONTENT_REJECTED'):
        validate_pptx(source, digest(source))


@pytest.mark.parametrize(("parts", "code"), [
    ({"../outside.xml": b"<x/>"}, "PPTX_ZIP_PATH_INVALID"),
    ({"C:/outside.xml": b"<x/>"}, "PPTX_ZIP_PATH_INVALID"),
    ({"ppt/vbaProject.bin": b"macro"}, "PPTX_ACTIVE_CONTENT_REJECTED"),
    ({"ppt/embeddings/item.xml": b"<x/>"}, "PPTX_ACTIVE_CONTENT_REJECTED"),
    ({"ppt/_rels/presentation.xml.rels": b'<Relationships><Relationship Target="https://example.invalid/object" TargetMode="External"/></Relationships>'}, "PPTX_EXTERNAL_RELATIONSHIP_REJECTED"),
    ({"ppt/_rels/presentation.xml.rels": b'<Relationships><Relationship Target="file:///C:/private/file"/></Relationships>'}, "PPTX_EXTERNAL_RELATIONSHIP_REJECTED"),
    ({"ppt/custom.xml": b'<!DOCTYPE x [<!ENTITY a "abc">]><x>&a;</x>'}, "PPTX_XML_ENTITY_REJECTED"),
    ({"ppt/custom.xml": '<?xml version="1.0" encoding="utf-16"?><!DOCTYPE x [<!ENTITY a "abc">]><x>&a;</x>'.encode("utf-16")}, "PPTX_XML_ENTITY_REJECTED"),
    ({"ppt/custom.xml": b"<not-closed>"}, "PPTX_PACKAGE_INVALID"),
    ({"ppt/large.xml": b"x" * 30000}, "PPTX_ZIP_EXPANSION_LIMIT"),
])
def test_rejects_active_external_malformed_or_expanding_parts(tmp_path, parts, code):
    source = presentation(tmp_path, parts)
    with pytest.raises(PptxConversionError, match=code):
        validate_pptx(source, digest(source))


def test_rejects_declared_limits_and_source_mismatch(tmp_path):
    source = presentation(tmp_path)
    with pytest.raises(PptxConversionError, match="PPTX_SOURCE_HASH_MISMATCH"):
        validate_pptx(source, "0" * 64)
    with pytest.raises(PptxConversionError, match="PPTX_INPUT_LIMIT"):
        validate_pptx(source, digest(source), ConverterLimits(max_input_bytes=1))
    with pytest.raises(PptxConversionError, match="PPTX_ZIP_ENTRY_LIMIT"):
        validate_pptx(source, digest(source), ConverterLimits(max_entries=1))
    with pytest.raises(ValueError):
        ConverterLimits(timeout_seconds=0)


@pytest.mark.asyncio
async def test_unconfigured_converter_or_missing_isolation_fails_closed(configured):
    source = presentation(configured.workspace)
    for converter in [PptxConverter(configured), PptxConverter(replace(configured, executable=None), FakeSandbox())]:
        assert not converter.available
        with pytest.raises(PptxConversionError, match="PPTX_CONVERTER_UNAVAILABLE"):
            await converter.convert(source, digest(source))
    unsafe = FakeSandbox()
    unsafe.network_disabled = False
    with pytest.raises(PptxConversionError, match="PPTX_CONVERTER_UNAVAILABLE"):
        await PptxConverter(configured, unsafe).convert(source, digest(source))
    assert not list(configured.output_root.iterdir())


@pytest.mark.asyncio
async def test_pinned_binary_and_source_do_not_change(configured):
    source = presentation(configured.workspace)
    sandbox = FakeSandbox()
    with pytest.raises(PptxConversionError, match="PPTX_CONVERTER_HASH_MISMATCH"):
        await PptxConverter(replace(configured, executable_sha256="0" * 64), sandbox).convert(source, digest(source))
    assert not sandbox.jobs
    assert not list(configured.output_root.iterdir())


@pytest.mark.asyncio
async def test_retains_original_and_distinct_immutable_renditions_pending_pdf_validation(configured):
    source = presentation(configured.workspace)
    original = source.read_bytes()
    sandbox = FakeSandbox()
    converter = PptxConverter(configured, sandbox)
    first = await converter.convert(source, digest(source))
    second = await converter.convert(source, digest(source))
    assert first.rendition_id != second.rendition_id
    assert source.read_bytes() == original
    assert Path(first.pdf_path).read_bytes() == sandbox.data
    assert first.pdf_sha256 == digest(Path(first.pdf_path))
    assert not first.ready_for_publication and not first.fidelity_verified
    assert first.status == "CONVERTED_PENDING_PDF_VALIDATION"
    manifest = Path(first.pdf_path).parent.parent / "rendition.json"
    assert json.loads(manifest.read_text())['source_sha256'] == digest(source)
    with pytest.raises(FrozenInstanceError):
        first.pdf_path = "other"
    job = sandbox.jobs[0]
    assert not job.network_allowed
    assert job.limits.memory_mib == 512 and job.limits.cpu_seconds == 90
    assert "--headless" in job.command
    assert 'pdf:impress_pdf_Export:{"ExportHiddenSlides":{"type":"boolean","value":"true"}}' in job.command
    assert "--norestore" not in job.command and "--nolockcheck" not in job.command
    assert all(str(job.cwd) in value for value in job.environment.values())


@pytest.mark.asyncio
@pytest.mark.parametrize(("sandbox", "code"), [
    (FakeSandbox(returncode=2), "PPTX_CONVERSION_FAILED"),
    (FakeSandbox(omit=True), "PPTX_OUTPUT_MISSING"),
    (FakeSandbox(data=b"not a PDF file"), "PPTX_OUTPUT_NOT_PDF"),
    (FakeSandbox(data=b"%PDF-1.4\n" + b"x" * 100), "PPTX_OUTPUT_LIMIT"),
])
async def test_failed_or_invalid_output_cannot_be_published(configured, sandbox, code):
    source = presentation(configured.workspace)
    config = replace(configured, limits=ConverterLimits(max_output_bytes=80))
    with pytest.raises(PptxConversionError, match=code):
        await PptxConverter(config, sandbox).convert(source, digest(source))
    assert not list(configured.output_root.glob("*/rendition.json"))


@pytest.mark.asyncio
async def test_timeout_cancels_only_the_owned_sandbox_job_and_retains_files(configured):
    source = presentation(configured.workspace)
    sandbox = FakeSandbox(wait=True)
    with pytest.raises(PptxConversionError, match="PPTX_CONVERSION_TIMEOUT"):
        await PptxConverter(replace(configured, limits=ConverterLimits(timeout_seconds=1)), sandbox).convert(source, digest(source))
    assert sandbox.cancelled == sandbox.jobs
    assert source.is_file() and sandbox.jobs[0].source_path.is_file()
