from copy import deepcopy

import pytest
from pydantic import ValidationError

from campus247.application.knowledge.evidence_units import (
    EvidenceLocator, EvidenceManifest, build_manifest, selection_diagnostic, verify_manifest,
)
from campus247.application.knowledge.platform_models import digest


def build(pages, tenant="one"):
    extracted = {"pages": pages, "issues": [], "page_count": len(pages)}
    binding = dict(tenant_id=tenant, original_sha256="a"*64, extraction_sha256=digest(extracted), parser_config_sha256="b"*64)
    return extracted, binding, build_manifest(extracted, **binding)


def test_preserves_leading_zero_repeated_codes_and_exact_spans():
    text = "  Điều kiện học phần\n\n001234 — 3 tín chỉ.\n\n001234 — chưa ghi tín chỉ.  "
    extracted, binding, manifest = build([{"page": 1, "text": text}])
    occurrences = [unit for unit in manifest.units if "001234" in unit.verbatim]
    assert len(occurrences) == 2 and occurrences[0].id != occurrences[1].id
    assert occurrences[1].material_occurrences[0]["verbatim"] == "001234"
    for unit in manifest.units:
        assert text[unit.locator.char_start:unit.locator.char_end] == unit.verbatim
    assert verify_manifest(manifest, extracted, **binding) == manifest
    assert not selection_diagnostic(manifest, [occurrences[1].id])["admissible"]
    assert all(not value["semantic_pairing_verified"] for unit in manifest.units for value in unit.material_occurrences)


def test_page_boundary_context_is_transitive_and_cannot_publish_a_clause_alone():
    _, _, manifest = build([{"page": 1, "text": "Điều kiện: sinh viên phải đáp ứng"},
        {"page": 2, "text": "cả hai yêu cầu. Ngoại lệ chỉ áp dụng khi có xác nhận."}])
    result = selection_diagnostic(manifest, [manifest.units[1].id])
    assert result["required_context_unit_ids"] == [manifest.units[0].id]
    assert not result["admissible"]
    assert any(issue["code"] == "PAGE_BOUNDARY_CONTEXT_UNVERIFIED" for issue in manifest.issues)


def test_cells_keep_independent_occurrences_without_inventing_header_units_or_credits():
    cells = [{"bbox": [10, index*20+10, 90, index*20+30], "text": value, "row": index, "column": 0}
        for index, value in enumerate(("Tín chỉ", "001234", "GDTC", "001234"))]
    _, _, manifest = build([{"page": 2, "text": "Bảng chương trình", "layout": {"tables": [{"cells": cells}]}}])
    units = [unit for unit in manifest.units if unit.kind == "TABLE_CELL"]
    assert len(units) == 4 and len({unit.id for unit in units}) == 4
    assert units[2].verbatim == "GDTC" and not units[2].material_occurrences
    assert len(selection_diagnostic(manifest, [units[2].id])["required_context_unit_ids"]) == 3
    assert all(unit.verification == "CANDIDATE" for unit in units)


def test_image_and_ambiguous_arrow_remain_unknown_despite_native_header():
    _, _, manifest = build([{"page": 1, "text": "Native heading for an image-only diagram", "layout": {
        "route": "RASTER_OR_MIXED", "images": [{"bbox": [0, 20, 200, 200]}], "lines": [[1, 1, 20, 20]]}}])
    image = next(unit for unit in manifest.units if unit.kind == "IMAGE_REGION")
    assert image.verbatim == "" and not image.material_occurrences
    assert any(issue["code"] == "IMAGE_CONTENT_UNVERIFIED" for issue in manifest.issues)
    assert not manifest.admission_granted and not manifest.dependency_graph_verified
    with pytest.raises(ValidationError):
        EvidenceManifest.model_validate(manifest.model_dump() | {"admission_granted": True})


def test_tenant_source_rendition_and_shifted_pages_never_reuse_old_occurrence_ids():
    pages = [{"page": 1, "text": "Same native text without independent authorization."}]
    extracted, binding, manifest = build(pages)
    for field in ("tenant_id", "original_sha256", "extraction_sha256", "parser_config_sha256"):
        changed = binding | {field: "two" if field == "tenant_id" else "c"*64}
        assert build_manifest(extracted, **changed).units[0].id != manifest.units[0].id
        with pytest.raises(ValueError, match="bound extraction"):
            verify_manifest(manifest, extracted, **changed)
    _, _, inserted = build([{"page": 1, "text": "Inserted first page"}, {"page": 2, "text": pages[0]["text"]}])
    assert inserted.units[1].id != manifest.units[0].id and inserted.units[1].locator.page == 2


def test_manifest_rejects_altered_hidden_evidence_even_when_text_hash_is_recomputed():
    extracted, binding, manifest = build([{"page": None, "text": "Amount 250000 đồng. Exception retained."}])
    payload = deepcopy(manifest.model_dump())
    payload["units"][0]["verbatim"] += " Invented extra rule."
    payload["units"][0]["text_sha256"] = digest(payload["units"][0]["verbatim"].encode())
    with pytest.raises(ValueError, match="bound extraction"):
        verify_manifest(EvidenceManifest.model_validate(payload), extracted, **binding)


@pytest.mark.parametrize("value",[float("nan"),float("inf"),float("-inf")])
def test_nonfinite_pdf_geometry_cannot_become_an_evidence_locator(value):
    with pytest.raises(ValidationError):
        EvidenceLocator(page_index=0,page=1,rendition_path=("pages",0,"layout"),bbox=(0,0,value,100))
