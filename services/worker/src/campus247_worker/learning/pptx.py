"""Fail-closed PPTX conversion boundary.

No office program is auto-discovered or installed. A configured, hash-pinned
converter and a resource-limited, network-isolated executor are both required.
Artifacts are immutable and retained. Conversion is not PDF safety validation
or layout-fidelity acceptance; the ordinary PDF validation pipeline must follow.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import posixpath
import re
import stat
import zipfile
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Protocol
from uuid import uuid4
from xml.etree import ElementTree


class PptxConversionError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _sha256(source: Path) -> str:
    result = hashlib.sha256()
    with source.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            result.update(block)
    return result.hexdigest()


def _checked(path: Path, workspace: Path, *, exists: bool = False) -> Path:
    if not path.is_absolute() or ".." in path.parts:
        raise PptxConversionError("PPTX_PATH_INVALID")
    resolved = path.resolve(strict=exists)
    if resolved == workspace or not resolved.is_relative_to(workspace):
        raise PptxConversionError("PPTX_PATH_OUTSIDE_WORKSPACE")
    for parent in (path, *path.parents):
        if parent.is_symlink() or getattr(parent, "is_junction", lambda: False)():
            raise PptxConversionError("PPTX_PATH_REPARSE_POINT")
        if parent == workspace:
            break
    return resolved


@dataclass(frozen=True)
class ConverterLimits:
    timeout_seconds: int = 120
    memory_mib: int = 512
    cpu_seconds: int = 90
    max_output_bytes: int = 50 * 1024 * 1024
    max_input_bytes: int = 50 * 1024 * 1024
    max_expanded_bytes: int = 200 * 1024 * 1024
    max_part_bytes: int = 20 * 1024 * 1024
    max_xml_bytes: int = 4 * 1024 * 1024
    max_entries: int = 10000
    max_slides: int = 500
    max_compression_ratio: int = 200

    def __post_init__(self) -> None:
        if any(type(value) is not int or value <= 0 for value in asdict(self).values()):
            raise ValueError("Converter limits must be positive integers")


@dataclass(frozen=True)
class PptxConverterConfig:
    workspace: Path
    output_root: Path
    executable: Path | None = None
    executable_sha256: str | None = None
    converter_version: str = "unconfigured"
    limits: ConverterLimits = ConverterLimits()


DEFAULT_CONVERTER_LIMITS = ConverterLimits()


@dataclass(frozen=True)
class SandboxJob:
    command: tuple[str, ...]
    cwd: Path
    environment: Mapping[str, str]
    limits: ConverterLimits
    source_path: Path
    output_directory: Path
    network_allowed: bool = False


@dataclass(frozen=True)
class ProcessResult:
    returncode: int


class IsolatedConverterExecutor(Protocol):
    """Implemented by the configured platform sandbox, never by a bare shell.

    The executor must enforce CPU, memory, output-file size, process-tree cleanup,
    a job-local writable filesystem and denied network. Environment flags and
    LibreOffice headless switches alone do not meet this contract. cancel must
    terminate only the process tree owned by this exact job.
    """
    network_disabled: bool
    resource_limits_enforced: bool

    async def run(self, job: SandboxJob) -> ProcessResult: ...
    async def cancel(self, job: SandboxJob) -> None: ...


@dataclass(frozen=True)
class ValidatedPptx:
    source_sha256: str
    source_bytes: int
    expanded_bytes: int
    slide_count: int


@dataclass(frozen=True)
class PptxRendition:
    rendition_id: str
    pdf_path: str
    pdf_sha256: str
    pdf_bytes: int
    source_sha256: str
    source_bytes: int
    slide_count: int
    converter_sha256: str
    converter_version: str
    conversion_profile: str = "impress-static-pdf-v1"
    status: str = "CONVERTED_PENDING_PDF_VALIDATION"
    ready_for_publication: bool = False
    fidelity_verified: bool = False


def _safe_xml(data: bytes, limits: ConverterLimits):
    if len(data) > limits.max_xml_bytes:
        raise PptxConversionError('PPTX_XML_LIMIT')
    normalized = data.replace(b'\x00', b'').upper()
    if b'<!DOCTYPE' in normalized or b'<!ENTITY' in normalized:
        raise PptxConversionError('PPTX_XML_ENTITY_REJECTED')
    return ElementTree.fromstring(data)


def _chart_workbooks(archive, limits):
    """Only internal XLSX packages referenced as data by a real chart are eligible."""
    targets = set()
    for name in archive.namelist():
        if not re.fullmatch(r'ppt/(?:slides/)?charts/chart\d+\.xml', name):
            continue
        member = archive.getinfo(name)
        if member.file_size > limits.max_xml_bytes:
            raise PptxConversionError('PPTX_XML_LIMIT')
        xml = _safe_xml(archive.read(name), limits)
        if xml.tag != '{http://schemas.openxmlformats.org/drawingml/2006/chart}chartSpace':
            continue
        referenced = {element.attrib.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
            for element in xml.iter() if element.tag == '{http://schemas.openxmlformats.org/drawingml/2006/chart}externalData'}
        referenced.discard(None)
        rel_name = posixpath.join(posixpath.dirname(name), '_rels', posixpath.basename(name) + '.rels')
        if not referenced or rel_name not in archive.namelist():
            continue
        if archive.getinfo(rel_name).file_size > limits.max_xml_bytes:
            raise PptxConversionError('PPTX_XML_LIMIT')
        for rel in _safe_xml(archive.read(rel_name), limits):
            if rel.attrib.get('Id') not in referenced:
                continue
            if rel.attrib.get('TargetMode', '').lower() == 'external' or rel.attrib.get('Type') != 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/package':
                raise PptxConversionError('PPTX_EXTERNAL_RELATIONSHIP_REJECTED')
            target = posixpath.normpath(posixpath.join(posixpath.dirname(name), rel.attrib.get('Target', '')))
            if not re.fullmatch(r'ppt/embeddings/[a-zA-Z0-9_.-]+\.xlsx', target):
                raise PptxConversionError('PPTX_ACTIVE_CONTENT_REJECTED')
            targets.add(target)
    return targets


def _validate_chart_workbook(data, limits):
    """Permit literal chart data, while retaining the macro/OLE/external-data ban."""
    expanded, seen = 0, set()
    allowed = re.compile(r'(?:\[Content_Types\]\.xml|_rels/\.rels|docProps/(?:core|app)\.xml|xl/(?:workbook\.xml|_rels/workbook\.xml\.rels|styles\.xml|sharedStrings\.xml|worksheets/sheet\d+\.xml|theme/theme\d+\.xml))')
    with zipfile.ZipFile(BytesIO(data)) as workbook:
        if len(workbook.infolist()) > 2000:
            raise PptxConversionError('PPTX_CHART_DATA_LIMIT')
        for part in workbook.infolist():
            if part.is_dir():
                continue
            if not allowed.fullmatch(part.filename) or part.filename.casefold() in seen or part.flag_bits & 1 or stat.S_ISLNK(part.external_attr >> 16):
                raise PptxConversionError('PPTX_CHART_DATA_REJECTED')
            seen.add(part.filename.casefold())
            expanded += part.file_size
            if expanded > limits.max_part_bytes or part.file_size > limits.max_xml_bytes or part.file_size / max(1, part.compress_size) > limits.max_compression_ratio:
                raise PptxConversionError('PPTX_CHART_DATA_LIMIT')
            xml = _safe_xml(workbook.read(part), limits)
            for element in xml.iter():
                tag = element.tag.rsplit('}', 1)[-1]
                if tag in {'f', 'definedName', 'externalReference', 'hyperlink', 'connection'}:
                    raise PptxConversionError('PPTX_CHART_FORMULA_REJECTED')
                if tag == 'Relationship':
                    target = element.attrib.get('Target', '')
                    if element.attrib.get('TargetMode', '').lower() == 'external' or re.match(r'[a-z][a-z0-9+.-]*:', target, re.IGNORECASE) or target.startswith(('/', '\\')):
                        raise PptxConversionError('PPTX_EXTERNAL_RELATIONSHIP_REJECTED')
                content_type = element.attrib.get('ContentType', '').lower()
                if any(value in content_type for value in ('macroenabled', 'vbaproject', 'oleobject', 'activex')):
                    raise PptxConversionError('PPTX_ACTIVE_CONTENT_REJECTED')
        if not {'[content_types].xml', 'xl/workbook.xml', '_rels/.rels'}.issubset(seen):
            raise PptxConversionError('PPTX_CHART_DATA_REJECTED')
    return expanded


def validate_pptx(source: Path, expected_sha256: str, limits: ConverterLimits = DEFAULT_CONVERTER_LIMITS) -> ValidatedPptx:
    if source.suffix.lower() != ".pptx" or not source.is_file():
        raise PptxConversionError("PPTX_TYPE_UNSUPPORTED")
    size = source.stat().st_size
    if not 0 < size <= limits.max_input_bytes:
        raise PptxConversionError("PPTX_INPUT_LIMIT")
    source_hash = _sha256(source)
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256) or source_hash != expected_sha256:
        raise PptxConversionError("PPTX_SOURCE_HASH_MISMATCH")
    total, slides = 0, 0
    seen: set[str] = set()
    try:
        with zipfile.ZipFile(source) as archive:
            entries = archive.infolist()
            if len(entries) > limits.max_entries:
                raise PptxConversionError("PPTX_ZIP_ENTRY_LIMIT")
            # Bound all decompression before the chart-reference XML prepass.
            if sum(entry.file_size for entry in entries) > limits.max_expanded_bytes or any(
                entry.file_size > limits.max_part_bytes or entry.file_size / max(1, entry.compress_size) > limits.max_compression_ratio
                for entry in entries):
                raise PptxConversionError('PPTX_ZIP_EXPANSION_LIMIT')
            chart_data = _chart_workbooks(archive, limits)
            for entry in entries:
                name = entry.filename
                member = PurePosixPath(name)
                if (not name or "\\" in name or ":" in name or member.is_absolute()
                        or ".." in member.parts or name.casefold() in seen
                        or stat.S_ISLNK(entry.external_attr >> 16)):
                    raise PptxConversionError("PPTX_ZIP_PATH_INVALID")
                seen.add(name.casefold())
                if entry.flag_bits & 1:
                    raise PptxConversionError("PPTX_ZIP_ENCRYPTED")
                lower = name.lower()
                if ("vbaproject" in lower or ("/embeddings/" in lower and name not in chart_data) or "/activex/" in lower
                        or lower.endswith((".bin", ".exe", ".dll", ".vbs", ".js", ".ole"))):
                    raise PptxConversionError("PPTX_ACTIVE_CONTENT_REJECTED")
                total += entry.file_size
                if (entry.file_size > limits.max_part_bytes or total > limits.max_expanded_bytes
                        or entry.file_size / max(1, entry.compress_size) > limits.max_compression_ratio):
                    raise PptxConversionError("PPTX_ZIP_EXPANSION_LIMIT")
                if name in chart_data:
                    total += _validate_chart_workbook(archive.read(entry), limits)
                    if total > limits.max_expanded_bytes:
                        raise PptxConversionError('PPTX_ZIP_EXPANSION_LIMIT')
                if re.fullmatch(r"ppt/slides/slide\d+\.xml", name):
                    slides += 1
                if not lower.endswith((".xml", ".rels")):
                    continue
                if entry.file_size > limits.max_xml_bytes:
                    raise PptxConversionError("PPTX_XML_LIMIT")
                with archive.open(entry) as stream:
                    data = stream.read(limits.max_xml_bytes + 1)
                if len(data) != entry.file_size or len(data) > limits.max_xml_bytes:
                    raise PptxConversionError("PPTX_XML_LIMIT")
                upper = data.replace(b"\x00", b"").upper()
                if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
                    raise PptxConversionError("PPTX_XML_ENTITY_REJECTED")
                xml = ElementTree.fromstring(data)
                for element in xml.iter():
                    if element.tag.rsplit("}", 1)[-1] == "Relationship":
                        target = element.attrib.get("Target", "")
                        if (element.attrib.get("TargetMode", "").lower() == "external"
                                or re.match(r"[a-z][a-z0-9+.-]*:", target, re.IGNORECASE)
                                or target.startswith(("//", "\\"))):
                            raise PptxConversionError("PPTX_EXTERNAL_RELATIONSHIP_REJECTED")
                    content_type = element.attrib.get("ContentType", "").lower()
                    if any(token in content_type for token in ("macroenabled", "vbaproject", "oleobject", "activex")):
                        raise PptxConversionError("PPTX_ACTIVE_CONTENT_REJECTED")
            if not {"[content_types].xml", "ppt/presentation.xml", "_rels/.rels"}.issubset(seen):
                raise PptxConversionError("PPTX_PACKAGE_INVALID")
            if not 1 <= slides <= limits.max_slides:
                raise PptxConversionError("PPTX_SLIDE_LIMIT")
    except (zipfile.BadZipFile, ElementTree.ParseError, RuntimeError, NotImplementedError) as exc:
        raise PptxConversionError("PPTX_PACKAGE_INVALID") from exc
    return ValidatedPptx(source_hash, size, total, slides)


class PptxConverter:
    def __init__(self, config: PptxConverterConfig, runner: IsolatedConverterExecutor | None = None):
        self.config = config
        self.runner = runner

    @property
    def available(self) -> bool:
        executable, runner = self.config.executable, self.runner
        return bool(executable and executable.is_absolute() and executable.is_file()
                    and self.config.executable_sha256 and self.config.converter_version != "unconfigured"
                    and runner and runner.network_disabled and runner.resource_limits_enforced)

    async def convert(self, source: Path, expected_sha256: str) -> PptxRendition:
        if not self.available:
            raise PptxConversionError("PPTX_CONVERTER_UNAVAILABLE")
        config, runner = self.config, self.runner
        assert config.executable is not None and runner is not None
        workspace = config.workspace.resolve(strict=True)
        source = _checked(source, workspace, exists=True)
        output_root = _checked(config.output_root, workspace, exists=True)
        if not output_root.is_dir():
            raise PptxConversionError("PPTX_OUTPUT_ROOT_INVALID")
        if _sha256(config.executable) != config.executable_sha256:
            raise PptxConversionError("PPTX_CONVERTER_HASH_MISMATCH")
        source_info = validate_pptx(source, expected_sha256, config.limits)
        rendition_id = uuid4().hex
        scope = _checked(output_root / rendition_id, workspace)
        scope.mkdir(exist_ok=False)
        work_input, output, profile = scope / "source.pptx", scope / "pdf", scope / "office-profile"
        output.mkdir(exist_ok=False)
        profile.mkdir(exist_ok=False)
        with source.open("rb") as original, work_input.open("xb") as copy:
            while block := original.read(1024 * 1024):
                copy.write(block)
        if _sha256(work_input) != source_info.source_sha256:
            raise PptxConversionError("PPTX_SOURCE_HASH_MISMATCH")
        command = (str(config.executable), f"-env:UserInstallation={profile.as_uri()}", "--headless", "--nologo",
                   "--nodefault", "--convert-to", 'pdf:impress_pdf_Export:{"ExportHiddenSlides":{"type":"boolean","value":"true"}}', "--outdir", str(output), str(work_input))
        # Profile/TEMP are task-local. Network denial comes from the executor,
        # not from these environment values or office command-line switches.
        job = SandboxJob(command, scope, {"TEMP": str(scope), "TMP": str(scope), "HOME": str(profile),
                         "USERPROFILE": str(profile), "XDG_CACHE_HOME": str(scope / "cache")}, config.limits, work_input, output)
        try:
            result = await asyncio.wait_for(runner.run(job), timeout=config.limits.timeout_seconds)
        except TimeoutError as exc:
            await runner.cancel(job)
            raise PptxConversionError("PPTX_CONVERSION_TIMEOUT") from exc
        except asyncio.CancelledError:
            await runner.cancel(job)
            raise
        if result.returncode:
            raise PptxConversionError("PPTX_CONVERSION_FAILED")
        pdf = _checked(output / "source.pdf", workspace)
        if not pdf.is_file():
            raise PptxConversionError("PPTX_OUTPUT_MISSING")
        if not 8 <= pdf.stat().st_size <= config.limits.max_output_bytes:
            raise PptxConversionError("PPTX_OUTPUT_LIMIT")
        with pdf.open("rb") as stream:
            if not stream.read(8).startswith(b"%PDF-"):
                raise PptxConversionError("PPTX_OUTPUT_NOT_PDF")
        if _sha256(source) != expected_sha256 or _sha256(work_input) != expected_sha256:
            raise PptxConversionError("PPTX_SOURCE_CHANGED")
        rendition = PptxRendition(rendition_id, str(pdf), _sha256(pdf), pdf.stat().st_size,
                                 source_info.source_sha256, source_info.source_bytes, source_info.slide_count,
                                 config.executable_sha256, config.converter_version)
        manifest = _checked(scope / "rendition.json", workspace)
        with manifest.open("x", encoding="utf-8") as stream:
            json.dump(asdict(rendition), stream, ensure_ascii=False, indent=2)
        return rendition
