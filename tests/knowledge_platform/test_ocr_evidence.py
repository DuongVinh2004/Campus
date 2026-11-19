"""OCR occurrence contracts; synthetic payloads do not establish OCR accuracy."""
from copy import deepcopy
import json
import struct

import pytest
from pydantic import ValidationError

from campus247.application.knowledge.ocr_evidence import OcrEvidenceManifest, build_manifest, verify_manifest
from campus247.application.knowledge.platform_models import digest


def fixture(page=3):
    # Only the immutable image-header/dimension binding is under test here.
    image = b"\x89PNG\r\n\x1a\n" + b"\x00"*8 + struct.pack(">II", 100, 100)
    box = {"x0": 1, "y0": 2, "x1": 30, "y1": 20}
    payload = {"source_sha256": "a"*64, "image_sha256": digest(image), "page": page,
        "image_width": 100, "image_height": 100, "text": " 001234 001234\n",
        "review_status": "OCR_unreviewed", "index_status": "not_admitted",
        "automation_profile": {"schema": "synthetic-contract-fixture", "semantics_verified": False},
        "blocks": [{"text": "001234 001234\n", "bbox": box, "paragraphs": [{
            "text": "001234 001234\n", "bbox": box, "lines": [{"text": "001234 001234\n", "bbox": box,
                "words": [{"text": "001234", "bbox": box}, {"text": "001234", "bbox": {**box, "x0": 40, "x1": 70}}]}]}]}]}
    return image, payload


def bind(image, payload, tenant="synthetic-contract"):
    raw = json.dumps(payload, ensure_ascii=False).encode()
    binding = dict(tenant_id=tenant, original_sha256=payload["source_sha256"], image_sha256=digest(image),
        ocr_sha256=digest(raw), ocr_config_sha256=digest(payload["automation_profile"]), page=payload["page"])
    return raw, binding, build_manifest(raw, image, **binding)


def test_repeated_words_keep_literal_nested_offsets_and_pixel_geometry():
    image, payload = fixture()
    raw, binding, manifest = bind(image, payload)
    assert len(manifest.units) == 6 and len(manifest.dependencies) == 5
    assert len({u.id for u in manifest.units}) == 6
    for unit in manifest.units:
        value = payload
        for key in unit.locator.rendition_path:
            value = value[key]
        assert value[unit.locator.char_start:unit.locator.char_end] == unit.verbatim
        assert unit.locator.page == 3 and unit.locator.page_index == 2
    first, second = manifest.units[-2:]
    assert first.verbatim == second.verbatim == "001234" and first.id != second.id
    assert first.locator.bbox != second.locator.bbox
    assert not first.material_occurrences[0]["semantic_pairing_verified"]
    assert {edge.kind for edge in manifest.dependencies} == {
        "OCR_PAGE_CONTEXT", "OCR_BLOCK_CONTEXT", "OCR_PARAGRAPH_CONTEXT", "OCR_LINE_CONTEXT"}
    assert verify_manifest(manifest, raw, image, **binding) == manifest
    assert not manifest.admission_granted and not manifest.dependency_graph_verified


@pytest.mark.parametrize("field,value", [("source_sha256", "c"*64), ("image_sha256", "c"*64),
    ("image_width", 200), ("page", 4), ("index_status", "admitted"), ("review_status", "APPROVED")])
def test_payload_rebinding_cannot_inherit_an_existing_evidence_identity(field, value):
    image, payload = fixture()
    raw, binding, _ = bind(image, payload)
    changed = {**payload, field: value}
    altered = json.dumps(changed).encode()
    with pytest.raises(ValueError):
        build_manifest(altered, image, **(binding | {"ocr_sha256": digest(altered)}))


@pytest.mark.parametrize("bbox", [{"x0": 0, "y0": 1, "x1": 101, "y1": 5},
    {"x0": -1, "y0": 1, "x1": 20, "y1": 5}, {"x0": 2, "y0": 1, "x1": 2, "y1": 5},
    {"x0": 0, "y0": 1, "x1": float("nan"), "y1": 5}])
def test_invalid_pixel_regions_cannot_become_locators(bbox):
    image, payload = fixture()
    payload["blocks"][0]["bbox"] = bbox
    with pytest.raises(ValueError):
        bind(image, payload)


def test_forged_manifest_and_cross_tenant_reuse_are_rejected():
    image, payload = fixture()
    raw, binding, manifest = bind(image, payload)
    assert build_manifest(raw, image, **(binding | {"tenant_id": "other"})).units[0].id != manifest.units[0].id
    with pytest.raises(ValueError):
        verify_manifest(manifest, raw, image, **(binding | {"tenant_id": "other"}))
    changed = deepcopy(manifest.model_dump())
    changed["units"][0]["verbatim"] = "Invented extra condition"
    changed["units"][0]["text_sha256"] = digest(changed["units"][0]["verbatim"].encode())
    with pytest.raises(ValueError):
        verify_manifest(OcrEvidenceManifest.model_validate(changed), raw, image, **binding)
    with pytest.raises(ValidationError):
        OcrEvidenceManifest.model_validate(manifest.model_dump() | {"admission_granted": True})


def test_empty_ocr_remains_an_empty_candidate_manifest():
    image, payload = fixture()
    payload.update(text="", blocks=[])
    _, _, manifest = bind(image, payload)
    assert not manifest.units and not manifest.dependencies and not manifest.admission_granted


@pytest.mark.parametrize("box", [[], {}, {"x0": 0, "y0": 0, "x1": 3}])
def test_malformed_pixel_objects_fail_as_validation_errors(box):
    image, payload = fixture()
    payload["blocks"][0]["bbox"] = box
    with pytest.raises(ValueError):
        bind(image, payload)
