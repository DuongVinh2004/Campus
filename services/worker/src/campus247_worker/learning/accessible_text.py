"""Build one unreviewed accessible-text candidate from an immutable PDF page."""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import uuid4
from xml.etree import ElementTree

MAX_SOURCE_BYTES = 50 * 1024**2
MAX_ARTIFACT_BYTES = 8 * 1024**2
MAX_RASTER_PIXELS = 2700**2
MAX_LINES = 1200
MAX_TEXT = 40_000
LANGUAGES = {"vie", "vie+eng"}
PIPELINE_REVISION = "learning-accessible-text-v1"


class OcrCandidateError(ValueError):
    """A stable error suitable for an OCR job checkpoint."""

    def __init__(self, code: str, *, retryable: bool = False):
        super().__init__(code)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class OcrSource:
    path: Path
    sha256: str
    byte_size: int
    page_count: int
    version_id: str
    rendition_id: str | None = None


@dataclass(frozen=True)
class PageGeometry:
    width: float
    height: float
    rotation: int

    def __post_init__(self):
        if (not all(math.isfinite(value) and 0 < value <= 14_400 for value in (self.width, self.height))
                or type(self.rotation) is not int or self.rotation not in {0, 90, 180, 270}):
            raise OcrCandidateError("OCR_PAGE_GEOMETRY_INVALID")


@dataclass(frozen=True)
class OcrPageArtifacts:
    geometry: PageGeometry
    native_xml: bytes
    ocr_tsv: bytes | None = None
    raster_width: int | None = None
    raster_height: int | None = None
    raster_sha256: str | None = None


@dataclass(frozen=True)
class OcrPageCandidate:
    payload: dict
    sha256: str
    retained_bytes: int = 0

    def to_bytes(self) -> bytes:
        return canonical_json(self.payload)


class OfflineOcrRunner(Protocol):
    network_disabled: bool
    resource_limits_enforced: bool
    profile: dict

    async def process(self, source: OcrSource, page: int, scope: Path, language: str) -> OcrPageArtifacts: ...


def canonical_json(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def scoped_path(path: Path, workspace: Path, *, must_exist: bool = True) -> Path:
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts or not path.is_relative_to(workspace) or path == workspace:
        raise OcrCandidateError("OCR_PATH_OUTSIDE_WORKSPACE")
    for candidate in (path, *path.parents):
        if (candidate.is_symlink() or getattr(candidate, "is_junction", lambda: False)()
                or candidate.exists() and getattr(candidate.stat(), "st_file_attributes", 0) & 0x400):
            raise OcrCandidateError("OCR_PATH_REPARSE_POINT")
        if candidate == workspace:
            break
    resolved = path.resolve(strict=must_exist)
    if resolved != path:
        raise OcrCandidateError("OCR_PATH_OUTSIDE_WORKSPACE")
    return resolved


def verify_source(source: OcrSource) -> None:
    if not source.path.is_file() or source.path.stat().st_size != source.byte_size:
        raise OcrCandidateError("OCR_SOURCE_CHANGED")
    with source.path.open("rb") as stream:
        if not stream.read(5) == b"%PDF-":
            raise OcrCandidateError("OCR_SOURCE_NOT_PDF")
        stream.seek(0)
        if hashlib.file_digest(stream, "sha256").hexdigest() != source.sha256:
            raise OcrCandidateError("OCR_SOURCE_CHANGED")


def normalized_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())


def _rect(values: tuple[float, float, float, float], width: float, height: float, rotation: int) -> dict:
    left, top, right, bottom = values
    if (not all(math.isfinite(value) for value in values)
            or not 0 <= left < right <= width or not 0 <= top < bottom <= height):
        raise OcrCandidateError("OCR_BLOCK_GEOMETRY_INVALID")
    x1, x2, y1, y2 = left / width, right / width, top / height, bottom / height
    if rotation == 90:
        x1, y1, x2, y2 = y1, 1 - x2, y2, 1 - x1
    elif rotation == 180:
        x1, y1, x2, y2 = 1 - x2, 1 - y2, 1 - x1, 1 - y1
    elif rotation == 270:
        x1, y1, x2, y2 = 1 - y2, x1, 1 - y1, x2
    return {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1}


def _native_xml_page(raw: bytes):
    if len(raw) > MAX_ARTIFACT_BYTES or re.search(br"<!ENTITY\b|<!DOCTYPE[^>]*\[", raw, re.IGNORECASE):
        raise OcrCandidateError("OCR_NATIVE_RESULT_INVALID")
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError as exc:
        raise OcrCandidateError("OCR_NATIVE_RESULT_INVALID") from exc
    pages = [element for element in root.iter() if element.tag.rsplit("}", 1)[-1] == "page"]
    if len(pages) != 1:
        raise OcrCandidateError("OCR_NATIVE_RESULT_INVALID")
    return pages[0]


def native_is_usable(raw: bytes) -> bool:
    """Require at least one meaningful native line, rather than a page number."""
    page = _native_xml_page(raw)
    for line in page.iter():
        if line.tag.rsplit("}", 1)[-1] == "line" and sum(char.isalpha() for char in "".join(line.itertext())) >= 8:
            return True
    return False


def _native_lines(raw: bytes, geometry: PageGeometry) -> list[dict]:
    page = _native_xml_page(raw)
    try:
        width, height = (float(page.attrib[key]) for key in ("width", "height"))
        expected = geometry.width, geometry.height
        if not all(math.isclose(a, b, rel_tol=0.002, abs_tol=0.5) for a, b in zip((width, height), expected, strict=True)):
            raise OcrCandidateError("OCR_PAGE_GEOMETRY_MISMATCH")
        # Poppler reports the unrotated CropBox size and emits line coordinates in the rotated page space.
        if geometry.rotation in {90, 270}:
            width, height = height, width
        lines = []
        for element in page.iter():
            if element.tag.rsplit("}", 1)[-1] != "line":
                continue
            words = ("".join(word.itertext()) for word in element if word.tag.rsplit("}", 1)[-1] == "word")
            text = normalized_text(" ".join(words))
            if not text:
                continue
            bounds = tuple(float(element.attrib[key]) for key in ("xMin", "yMin", "xMax", "yMax"))
            if not all(math.isfinite(value) for value in bounds):
                raise OcrCandidateError("OCR_BLOCK_GEOMETRY_INVALID")
            # CropBox clipping is expected on documents whose text crosses the page edge.
            bounds = (max(0, bounds[0]), max(0, bounds[1]), min(width, bounds[2]), min(height, bounds[3]))
            if bounds[0] >= bounds[2] or bounds[1] >= bounds[3]:
                continue
            lines.append({"text": text, "anchor": _rect(bounds, width, height, geometry.rotation),
                          "confidence": None, "provenance": "NATIVE"})
        return lines
    except (TypeError, ValueError, KeyError) as exc:
        if isinstance(exc, OcrCandidateError):
            raise
        raise OcrCandidateError("OCR_NATIVE_RESULT_INVALID") from exc


def _raster_lines(artifacts: OcrPageArtifacts) -> list[dict]:
    if artifacts.ocr_tsv is None:
        if any(value is not None for value in (artifacts.raster_width, artifacts.raster_height, artifacts.raster_sha256)):
            raise OcrCandidateError("OCR_RASTER_RESULT_INVALID")
        return []
    width, height = artifacts.raster_width, artifacts.raster_height
    if (type(width) is not int or type(height) is not int or not 0 < width <= 2700 or not 0 < height <= 2700
            or width * height > MAX_RASTER_PIXELS or len(artifacts.ocr_tsv) > MAX_ARTIFACT_BYTES
            or not re.fullmatch(r"[0-9a-f]{64}", artifacts.raster_sha256 or "")):
        raise OcrCandidateError("OCR_RASTER_RESULT_INVALID")
    geometry = artifacts.geometry
    page_ratio = geometry.height / geometry.width if geometry.rotation in {90, 270} else geometry.width / geometry.height
    if not math.isclose(width / height, page_ratio, rel_tol=0.02):
        raise OcrCandidateError("OCR_PAGE_GEOMETRY_MISMATCH")
    grouped = {}
    try:
        records = iter(artifacts.ocr_tsv.decode("utf-8").splitlines())
        if next(records, "") != "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext":
            raise ValueError("header")
        word_count = 0
        for row in records:
            parts = row.split("\t", 11)
            if len(parts) != 12:
                raise ValueError("columns")
            if parts[0] != "5" or not parts[11].strip():
                continue
            word_count += 1
            if word_count > 12_000 or parts[1] != "1":
                raise ValueError("words")
            group = tuple(int(value) for value in parts[2:5])
            left, top, span, rise = map(int, parts[6:10])
            right, bottom = left + span, top + rise
            confidence = float(parts[10])
            if not 0 <= left < right <= width or not 0 <= top < bottom <= height or not 0 <= confidence <= 100:
                raise ValueError("word bounds")
            grouped.setdefault(group, []).append((normalized_text(parts[11]), left, top, right, bottom, confidence))
        result = []
        for words in grouped.values():
            bounds = (min(word[1] for word in words), min(word[2] for word in words),
                      max(word[3] for word in words), max(word[4] for word in words))
            result.append({
                "text": " ".join(word[0] for word in words),
                "anchor": _rect(bounds, width, height, geometry.rotation),
                "confidence": round(min(word[5] for word in words), 2),
                "provenance": "OCR",
            })
        return result
    except (TypeError, ValueError) as exc:
        if isinstance(exc, OcrCandidateError):
            raise
        raise OcrCandidateError("OCR_RASTER_RESULT_INVALID") from exc


def _duplicate_line(native: dict, ocr: dict) -> bool:
    a, b = native["anchor"], ocr["anchor"]
    intersection = (max(0, min(a["x"] + a["width"], b["x"] + b["width"]) - max(a["x"], b["x"]))
                    * max(0, min(a["y"] + a["height"], b["y"] + b["height"]) - max(a["y"], b["y"])))
    return intersection >= 0.65 * b["width"] * b["height"]


def build_page_candidate(source: OcrSource, page: int, profile_sha256: str, artifacts: OcrPageArtifacts) -> OcrPageCandidate:
    native = _native_lines(artifacts.native_xml, artifacts.geometry)
    ocr = _raster_lines(artifacts)
    if ocr and native:
        ocr = [line for line in ocr if not any(_duplicate_line(base, line) for base in native)]
    lines = native + ocr
    if len(lines) > MAX_LINES or sum(len(line["text"]) for line in lines) > MAX_TEXT:
        raise OcrCandidateError("OCR_PAGE_TEXT_LIMIT")
    if native and ocr:
        lines.sort(key=lambda line: (line["anchor"]["y"], line["anchor"]["x"]))
    left_column = any(line["anchor"]["x"] + line["anchor"]["width"] < 0.55 for line in lines)
    right_column = any(line["anchor"]["x"] > 0.45 for line in lines)
    blocks = []
    for order, line in enumerate(lines, 1):
        reasons = ["READING_ORDER_REVIEW"]
        if line["provenance"] == "OCR":
            reasons.append("OCR_TEXT_REVIEW")
            if line["confidence"] < 80:
                reasons.append("LOW_CONFIDENCE")
        if re.search(r"[=∑√±×÷−²³₀-₉]|\w\^\d|(?<!\w)-\s*\d", line["text"]):
            reasons.append("POSSIBLE_FORMULA")
        if len(re.findall(r"\b\d+(?:[.,]\d+)?\b", line["text"])) >= 2:
            reasons.append("POSSIBLE_TABLE")
        if left_column and right_column:
            reasons.append("MULTI_COLUMN_LAYOUT")
        blocks.append({"id": f"p{page}-b{order}", "type": "PARAGRAPH", "order": order,
                       "needs_review": True, "review_reasons": reasons, **line})
    payload = {
        "schema": PIPELINE_REVISION,
        "version_id": source.version_id,
        "rendition_id": source.rendition_id,
        "source_sha256": source.sha256,
        "profile_sha256": profile_sha256,
        "page_no": page,
        "geometry": {"width": artifacts.geometry.width, "height": artifacts.geometry.height,
                     "rotation": artifacts.geometry.rotation, "anchor_space": "UNROTATED_CROP_NORMALIZED"},
        "raster_sha256": artifacts.raster_sha256,
        "status": "NEEDS_REVIEW",
        "blocks": blocks,
    }
    return OcrPageCandidate(payload, hashlib.sha256(canonical_json(payload)).hexdigest())


class LearningOcrPipeline:
    def __init__(self, *, workspace: Path, work_root: Path, runner: OfflineOcrRunner, language: str = "vie"):
        self.workspace = workspace.resolve(strict=True)
        self.work_root = scoped_path(work_root, self.workspace)
        if not self.work_root.is_dir() or runner.network_disabled is not True or runner.resource_limits_enforced is not True:
            raise OcrCandidateError("OCR_SANDBOX_UNVERIFIED")
        if language not in LANGUAGES:
            raise OcrCandidateError("OCR_LANGUAGE_INVALID")
        self.runner = runner
        self.language = language
        self.profile_sha256 = hashlib.sha256(canonical_json({
            "pipeline": PIPELINE_REVISION, "language": language, "runner": runner.profile,
            "pipeline_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        })).hexdigest()
        self._slots = asyncio.Semaphore(2)

    async def process_page(self, source: OcrSource, page_no: int) -> OcrPageCandidate:
        if (type(source.page_count) is not int or not 1 <= source.page_count <= 500 or type(page_no) is not int
                or not 1 <= page_no <= source.page_count or type(source.byte_size) is not int
                or not 5 <= source.byte_size <= MAX_SOURCE_BYTES or not isinstance(source.sha256, str)
                or not re.fullmatch(r"[0-9a-f]{64}", source.sha256)
                or not isinstance(source.version_id, str) or not source.version_id or len(source.version_id) > 128
                or source.rendition_id is not None and (not isinstance(source.rendition_id, str) or len(source.rendition_id) > 128)):
            raise OcrCandidateError("OCR_SOURCE_INVALID")
        async with self._slots:
            scoped_path(source.path, self.workspace)
            await asyncio.to_thread(verify_source, source)
            scope = scoped_path(self.work_root / uuid4().hex, self.workspace, must_exist=False)
            scope.mkdir(exist_ok=False)
            artifacts = await self.runner.process(source, page_no, scope, self.language)
            scoped_path(source.path, self.workspace)
            await asyncio.to_thread(verify_source, source)
            candidate = build_page_candidate(source, page_no, self.profile_sha256, artifacts)
            retained = sum(checked.stat().st_size for path in scope.rglob("*")
                           if (checked := scoped_path(path, self.workspace)).is_file())
            if retained + len(candidate.to_bytes()) > 40 * 1024**2:
                raise OcrCandidateError("OCR_OUTPUT_LIMIT")
            return OcrPageCandidate(candidate.payload, candidate.sha256, retained)
