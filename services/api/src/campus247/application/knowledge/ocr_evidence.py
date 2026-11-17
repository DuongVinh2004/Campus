"""Image-bound OCR occurrences, never a verified semantic dependency graph."""
from __future__ import annotations

import json
import math
import struct
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from campus247.application.knowledge.document_identity import StrictModel
from campus247.application.knowledge.evidence_units import EvidenceLocator, EvidenceUnit, lexical_occurrences
from campus247.application.knowledge.platform_models import digest

SCHEMA = "ocr-evidence-occurrences-v1"


def configuration_hash():
    return digest({"schema": SCHEMA, "code": digest(Path(__file__).read_bytes()),
        "occurrence_code": digest(Path(__file__).with_name("evidence_units.py").read_bytes())})


class OcrContext(StrictModel):
    unit_id: str
    depends_on: str
    kind: Literal["OCR_PAGE_CONTEXT", "OCR_BLOCK_CONTEXT", "OCR_PARAGRAPH_CONTEXT", "OCR_LINE_CONTEXT"]
    verification: Literal["CANDIDATE"] = "CANDIDATE"


class OcrEvidenceManifest(StrictModel):
    schema_revision: Literal["ocr-evidence-occurrences-v1"] = SCHEMA
    tenant_id: str = Field(min_length=1)
    original_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    image_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    ocr_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    ocr_config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    page: int = Field(ge=1)
    image_width: int = Field(gt=0)
    image_height: int = Field(gt=0)
    coordinate_space: Literal["RENDERED_IMAGE_PIXELS"] = "RENDERED_IMAGE_PIXELS"
    units: tuple[EvidenceUnit, ...] = Field(default=(), max_length=30000)
    dependencies: tuple[OcrContext, ...] = Field(default=(), max_length=30000)
    semantics_verified: Literal[False] = False
    dependency_graph_verified: Literal[False] = False
    admission_granted: Literal[False] = False

    @model_validator(mode="after")
    def check_graph(self):
        ids = {unit.id for unit in self.units}
        if len(ids) != len(self.units):
            raise ValueError("OCR occurrences must be unique")
        for unit in self.units:
            if unit.locator.page != self.page or unit.locator.page_index != self.page - 1:
                raise ValueError("OCR occurrence page mismatch")
            bbox = unit.locator.bbox
            if bbox and not (0 <= bbox[0] < bbox[2] <= self.image_width and 0 <= bbox[1] < bbox[3] <= self.image_height):
                raise ValueError("OCR occurrence outside its image")
        if any(edge.unit_id not in ids or edge.depends_on not in ids or edge.unit_id == edge.depends_on for edge in self.dependencies):
            raise ValueError("OCR context must stay within the bound page")
        return self


def build_manifest(raw_ocr, image_bytes, *, tenant_id, original_sha256, image_sha256, ocr_sha256, ocr_config_sha256, page):
    if digest(raw_ocr) != ocr_sha256 or digest(image_bytes) != image_sha256:
        raise ValueError("OCR or image hash mismatch")
    if len(image_bytes) < 24 or image_bytes[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Bound PNG image required")
    width, height = struct.unpack(">II", image_bytes[16:24])
    payload = json.loads(raw_ocr)
    if not isinstance(payload, dict) or not isinstance(payload.get("automation_profile"), dict):
        raise ValueError("Bound OCR object and profile required")
    if (payload.get("source_sha256") != original_sha256 or payload.get("image_sha256") != image_sha256
        or payload.get("page") != page or type(page) is not int or page < 1
        or (payload.get("image_width"), payload.get("image_height")) != (width, height)
        or not 0 < width * height <= 2700**2 or payload.get("index_status") != "not_admitted"
        or payload.get("review_status") != "OCR_unreviewed"
        or digest(payload.get("automation_profile")) != ocr_config_sha256
        or payload.get("automation_profile", {}).get("semantics_verified") is not False):
        raise ValueError("OCR source, profile, page or image binding mismatch")
    binding = dict(tenant_id=tenant_id, original_sha256=original_sha256, image_sha256=image_sha256,
        ocr_sha256=ocr_sha256, ocr_config_sha256=ocr_config_sha256, page=page)
    units, edges = [], []

    def add(node, path, parent=None, parent_kind="OCR_PAGE_CONTEXT"):
        text = node.get("text")
        if text is None:
            return parent
        if not isinstance(text, str):
            raise ValueError("OCR occurrence text must remain literal")
        if not text:
            return parent
        box = node.get("bbox")
        bbox = None
        if box is not None:
            if not isinstance(box, dict) or not {"x0", "y0", "x1", "y1"} <= box.keys():
                raise ValueError("OCR pixel box must retain all four coordinates")
            values = tuple(box[key] for key in ("x0", "y0", "x1", "y1"))
            if any(type(value) not in (int, float) or not math.isfinite(value) for value in values):
                raise ValueError("OCR geometry must be finite pixels")
            bbox = values
        locator = EvidenceLocator(page_index=page-1, page=page, rendition_path=path+("text",),
            char_start=0, char_end=len(text), bbox=bbox)
        identifier = digest({**binding, "locator": locator.model_dump(mode="json")})
        units.append(EvidenceUnit(id=identifier, kind="TEXT", locator=locator, verbatim=text,
            text_sha256=digest(text.encode()), material_occurrences=lexical_occurrences(text)))
        if len(units) > 30000:
            raise ValueError("OCR occurrence limit exceeded; no truncation")
        if parent:
            edges.append(OcrContext(unit_id=identifier, depends_on=parent, kind=parent_kind))
        return identifier

    page_id = add(payload, ())
    # These are OCR engine groupings, not independently verified table cells,
    # source reading order or semantic dependencies. Never search for a word
    # in flat page text to invent its offset when the same word is repeated.
    def walk(nodes, path, parent, level):
        if nodes is None:
            return
        if not isinstance(nodes, list) or len(nodes) > 30000:
            raise ValueError("Bounded OCR groups required")
        fields = (("paragraphs", "OCR_BLOCK_CONTEXT"), ("lines", "OCR_PARAGRAPH_CONTEXT"), ("words", "OCR_LINE_CONTEXT"))
        for index, node in enumerate(nodes):
            if not isinstance(node, dict):
                raise ValueError("OCR group must be an object")
            node_path = path+(index,)
            own_id = add(node, node_path, parent, "OCR_PAGE_CONTEXT" if level == 0 else fields[level-1][1])
            if level < len(fields):
                field = fields[level][0]
                walk(node.get(field), node_path+(field,), own_id, level+1)
    walk(payload.get("blocks"), ("blocks",), page_id, 0)
    return OcrEvidenceManifest(**binding, image_width=width, image_height=height, units=tuple(units), dependencies=tuple(edges))


def verify_manifest(manifest, raw_ocr, image_bytes, **binding):
    expected = build_manifest(raw_ocr, image_bytes, **binding)
    if manifest != expected:
        raise ValueError("OCR evidence differs from the bound engine output")
    return manifest
