"""Occurrence-preserving evidence from a pinned extraction, never admission.

Native text and cell characters are witnesses of a rendition. They do not
establish a course's credits, a table header's scope, legal effect, or an arrow.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from campus247.application.knowledge.document_identity import StrictModel
from campus247.application.knowledge.platform_models import digest

SCHEMA = "evidence-occurrences-v1"
VALIDATOR = "evidence-closure-v1"


def configuration_hash():
    from pathlib import Path
    return digest({"code": digest(Path(__file__).read_bytes()), "schema": SCHEMA, "validator": VALIDATOR})


class EvidenceLocator(StrictModel):
    page_index: int = Field(ge=0)
    page: int | None = Field(default=None, ge=1)
    rendition_path: tuple[str | int, ...] = Field(min_length=1)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)
    bbox: tuple[float, float, float, float] | None = None

    @model_validator(mode="after")
    def check_range(self):
        import math
        if (self.char_start is None) != (self.char_end is None):
            raise ValueError("Both character offsets are required")
        if self.char_end is not None and self.char_end <= self.char_start:
            raise ValueError("Character range must be nonempty")
        if self.bbox and (not all(math.isfinite(value) for value in self.bbox) or self.bbox[0] >= self.bbox[2] or self.bbox[1] >= self.bbox[3]):
            raise ValueError("Bounding box must be nonempty and ordered")
        return self


class EvidenceUnit(StrictModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=False)
    id: str = Field(pattern=r"^[0-9a-f]{64}$")
    kind: Literal["TEXT", "TABLE_CELL", "IMAGE_REGION", "GRAPHIC_OBJECT"]
    locator: EvidenceLocator
    verbatim: str
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    # Lexical occurrences only; codes remain strings including leading zeros.
    material_occurrences: tuple[dict, ...] = ()
    verification: Literal["CANDIDATE"] = "CANDIDATE"

    @model_validator(mode="after")
    def check_text(self):
        if self.text_sha256 != digest(self.verbatim.encode()):
            raise ValueError("Evidence text hash mismatch")
        if self.kind == "TEXT" and not self.verbatim:
            raise ValueError("Text unit cannot be empty")
        for occurrence in self.material_occurrences:
            start, end = occurrence.get("start"), occurrence.get("end")
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(self.verbatim):
                raise ValueError("Material occurrence must have exact local offsets")
            if self.verbatim[start:end] != occurrence.get("verbatim"):
                raise ValueError("Material occurrence does not match the witness")
        return self


class EvidenceDependency(StrictModel):
    unit_id: str
    depends_on: str
    kind: Literal["PAGE_BOUNDARY_CONTEXT", "TABLE_CONTEXT", "GRAPHIC_CONTEXT"]
    verification: Literal["CANDIDATE"] = "CANDIDATE"


class EvidenceManifest(StrictModel):
    schema_revision: Literal["evidence-occurrences-v1"] = SCHEMA
    validator_revision: Literal["evidence-closure-v1"] = VALIDATOR
    tenant_id: str = Field(min_length=1)
    original_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    extraction_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parser_config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    units: tuple[EvidenceUnit, ...] = ()
    dependencies: tuple[EvidenceDependency, ...] = ()
    issues: tuple[dict, ...] = ()
    dependency_graph_verified: Literal[False] = False
    admission_granted: Literal[False] = False

    @model_validator(mode="after")
    def check_graph(self):
        ids = {unit.id for unit in self.units}
        if len(ids) != len(self.units) or len(ids) > 30000:
            raise ValueError("Evidence occurrences must be unique and bounded")
        if any(edge.unit_id not in ids or edge.depends_on not in ids or edge.unit_id == edge.depends_on for edge in self.dependencies):
            raise ValueError("Evidence dependency points outside the rendition")
        return self


def lexical_occurrences(text):
    pattern = r"(?<!\d)\d{6}(?!\d)|\d[\d.,]*(?:\s*(?:tín chỉ|đồng|VNĐ|%|ngày|tháng|năm))?"
    return tuple({"start": match.start(), "end": match.end(), "verbatim": match.group(),
                  "semantic_pairing_verified": False} for match in re.finditer(pattern, text, re.I))


def build_manifest(extracted, *, tenant_id, original_sha256, extraction_sha256, parser_config_sha256):
    units, edges = [], []
    issues = list(extracted.get("issues", ()))
    previous_last = None
    def add(kind, locator, text):
        identifier = digest({"tenant": tenant_id, "original": original_sha256, "extraction": extraction_sha256,
            "parser": parser_config_sha256, "kind": kind, "locator": locator.model_dump(mode="json")})
        unit = EvidenceUnit(id=identifier, kind=kind, locator=locator, verbatim=text,
            text_sha256=digest(text.encode()), material_occurrences=lexical_occurrences(text))
        units.append(unit)
        if len(units) > 30000:
            raise ValueError("Evidence occurrence limit exceeded; no truncated manifest")
        return unit.id

    for index, page in enumerate(extracted["pages"]):
        page_text_ids = []
        text = page["text"]
        # Keep exact rendition offsets, whitespace, punctuation and repeated
        # occurrences. Paragraph detection never claims semantic independence.
        for match in re.finditer(r"\S[\s\S]*?(?=\n\s*\n|\Z)", text):
            page_text_ids.append(add("TEXT", EvidenceLocator(page_index=index, page=page["page"],
                rendition_path=("pages", index, "text"), char_start=match.start(), char_end=match.end()), match.group()))
        if previous_last and page_text_ids:
            edges.append(EvidenceDependency(unit_id=page_text_ids[0], depends_on=previous_last, kind="PAGE_BOUNDARY_CONTEXT"))
            edges.append(EvidenceDependency(unit_id=previous_last, depends_on=page_text_ids[0], kind="PAGE_BOUNDARY_CONTEXT"))
            issues.append({"code": "PAGE_BOUNDARY_CONTEXT_UNVERIFIED", "page": page["page"], "unit_ids": [previous_last, page_text_ids[0]]})
        previous_last = page_text_ids[-1] if page_text_ids else None
        layout = page.get("layout") or {}
        for table_index, table in enumerate(layout.get("tables", ())):
            table_units = []
            for cell_index, cell in enumerate(table["cells"]):
                table_units.append(add("TABLE_CELL", EvidenceLocator(page_index=index, page=page["page"],
                    rendition_path=("pages", index, "layout", "tables", table_index, "cells", cell_index), bbox=tuple(cell["bbox"])), cell["text"]))
            # An unverified table cannot be split into individually publishable
            # cells. Retain a compact connected context, not invented row units.
            for first, second in zip(table_units, table_units[1:]):
                edges.extend((EvidenceDependency(unit_id=first, depends_on=second, kind="TABLE_CONTEXT"),
                              EvidenceDependency(unit_id=second, depends_on=first, kind="TABLE_CONTEXT")))
            issues.append({"code": "TABLE_CONTEXT_UNVERIFIED", "page": page["page"], "unit_ids": table_units})
        for image_index, image in enumerate(layout.get("images", ())):
            image_id = add("IMAGE_REGION", EvidenceLocator(page_index=index, page=page["page"],
                rendition_path=("pages", index, "layout", "images", image_index), bbox=tuple(image["bbox"])), "")
            issues.append({"code": "IMAGE_CONTENT_UNVERIFIED", "page": page["page"], "unit_ids": [image_id]})
        graphic_ids = []
        for shape_index, shape in enumerate(layout.get("shapes", ())):
            box = tuple(shape["bbox"])
            # A zero-width shaft is legitimate PDF geometry, not a nonempty
            # image crop. Its exact points stay at the source-bound path.
            crop = box if box[0] < box[2] and box[1] < box[3] else None
            graphic_ids.append(add("GRAPHIC_OBJECT", EvidenceLocator(page_index=index, page=page["page"],
                rendition_path=("pages", index, "layout", "shapes", shape_index), bbox=crop), ""))
        if graphic_ids:
            context = graphic_ids + page_text_ids
            for first, second in zip(context, context[1:]):
                edges.extend((EvidenceDependency(unit_id=first, depends_on=second, kind="GRAPHIC_CONTEXT"),
                              EvidenceDependency(unit_id=second, depends_on=first, kind="GRAPHIC_CONTEXT")))
            issues.append({"code": "GRAPHIC_CONTEXT_UNVERIFIED", "page": page["page"], "unit_ids": context})
    return EvidenceManifest(tenant_id=tenant_id, original_sha256=original_sha256, extraction_sha256=extraction_sha256,
        parser_config_sha256=parser_config_sha256, units=tuple(units), dependencies=tuple(edges), issues=tuple(issues))


def verify_manifest(manifest, extracted, *, tenant_id, original_sha256, extraction_sha256, parser_config_sha256):
    expected = build_manifest(extracted, tenant_id=tenant_id, original_sha256=original_sha256,
        extraction_sha256=extraction_sha256, parser_config_sha256=parser_config_sha256)
    if manifest != expected:
        raise ValueError("Evidence manifest differs from the bound extraction or scope")
    return manifest


def selection_diagnostic(manifest, selected_ids):
    """Report transitive context without treating candidate evidence as usable."""
    selected = set(selected_ids)
    ids = {unit.id for unit in manifest.units}
    if not selected or not selected <= ids:
        raise ValueError("Select explicit evidence occurrences in this manifest")
    closure = set(selected)
    adjacency = {}
    for edge in manifest.dependencies:
        adjacency.setdefault(edge.unit_id, set()).add(edge.depends_on)
    pending = list(selected)
    while pending:
        unit = pending.pop()
        for dependency in adjacency.get(unit, ()):
            if dependency not in closure:
                closure.add(dependency)
                pending.append(dependency)
    return {"selected_unit_ids": sorted(selected), "required_context_unit_ids": sorted(closure-selected),
        "admissible": False, "reason": "EVIDENCE_AND_DEPENDENCIES_UNVERIFIED", "validator_revision": VALIDATOR}
