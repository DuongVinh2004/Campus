from campus247.application.knowledge.evidence_units import build_manifest, selection_diagnostic
from campus247.application.knowledge.platform_models import digest
from campus247_worker.knowledge_table_layout import closed_grid_cells


def grid():
    # Header spans both columns; the body has two columns and two rows.
    return [[0,0,200,0], [0,20,200,20], [0,40,200,40], [0,60,200,60],
        [0,0,0,60], [100,20,100,60], [200,0,200,60]]


def test_merged_header_keeps_span_occurrences_and_unverified_semantics():
    chars = [{"bbox": [1,1,10,10], "text": "Amount (VND)"},
        {"bbox": [1,21,10,30], "text": "001234"}, {"bbox": [101,21,110,30], "text": "001234"}]
    cells, issues = closed_grid_cells(grid(), chars)
    assert not issues and len(cells) == 5
    assert cells[0]["row"] == cells[0]["column"] == 0 and cells[0]["column_span"] == 2
    assert cells[0]["row_span"] == 1 and cells[0]["text"] == "Amount (VND)"
    assert cells[1]["text"] == cells[2]["text"] == "001234"
    assert cells[1]["column"] != cells[2]["column"]
    assert all(not cell["structure_verified"] for cell in cells)
    extracted = {"pages": [{"page": 1, "text": "Shared header and its conditions", "layout": {"tables": [{"cells": cells}]}}], "issues": []}
    manifest = build_manifest(extracted, tenant_id="synthetic", original_sha256="a"*64, extraction_sha256=digest(extracted), parser_config_sha256="b"*64)
    body = [unit for unit in manifest.units if unit.kind == "TABLE_CELL"]
    assert len(body) == 5
    assert body[1].id != body[2].id and body[1].verbatim == body[2].verbatim == "001234"
    selection = selection_diagnostic(manifest, [body[1].id])
    assert body[0].id in selection["required_context_unit_ids"] and not selection["admissible"]


def test_gap_to_exterior_is_not_a_merged_cell_and_partial_stroke_stays_unknown():
    lines = grid()
    lines[0] = [0,0,90,0]  # Open gap is not silently repaired.
    cells, _ = closed_grid_cells(lines, [])
    assert all(cell["row"] != 0 for cell in cells)
    partial = grid()+[[100,0,100,10]]
    # The partial segment does not span an atomic wall and cannot justify
    # splitting the header; its stroke remains a separate graphic occurrence.
    cells, _ = closed_grid_cells(partial, [])
    assert cells[0]["column_span"] == 2 and not cells[0]["structure_verified"]


def test_bent_or_irregular_cell_never_becomes_rectangular_fact():
    # In a 2x2 enclosure remove two different internal borders to make an L.
    lines = [[0,0,200,0], [0,200,200,200], [0,0,0,200], [200,0,200,200],
        [0,100,100,100], [100,100,100,200]]
    cells, issues = closed_grid_cells(lines, [])
    assert issues and all(cell["row_span"]*cell["column_span"] == 1 for cell in cells)
    assert any(issue["code"] == "TABLE_NONRECTANGULAR_REGION" for issue in issues)


def test_graphic_points_are_occurrences_and_never_nearest_endpoint_semantics():
    extracted = {"pages": [{"page": 1, "text": "001234 relates to an uncertain endpoint", "layout": {"shapes": [
        {"bbox": [10,10,10,90], "points": [[10,10], [10,90]], "kind": "LTLine"},
        {"bbox": [5,80,15,90], "points": [[5,80], [10,90], [15,80]], "kind": "LTCurve"}]}}], "issues": []}
    binding = {"tenant_id": "test", "original_sha256": "a"*64, "extraction_sha256": digest(extracted), "parser_config_sha256": "b"*64}
    manifest = build_manifest(extracted, **binding)
    shapes = [unit for unit in manifest.units if unit.kind == "GRAPHIC_OBJECT"]
    assert len(shapes) == 2 and shapes[0].locator.bbox is None
    assert not shapes[0].verbatim and not shapes[0].material_occurrences
    assert all(unit.verification == "CANDIDATE" for unit in shapes)
    selection = selection_diagnostic(manifest, [shapes[1].id])
    assert len(selection["required_context_unit_ids"]) == 2 and not selection["admissible"]


def test_real_pdfminer_preserves_merged_header_and_actual_shape_points(retained_directory):
    import io
    import json
    import os
    import subprocess
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    from campus247.infrastructure.knowledge.storage import FileKnowledgeStorage
    from .conftest import ROOT
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=400)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(b"20 100 240 200 re S 20 250 m 260 250 l S 20 175 m 260 175 l S 140 100 m 140 250 l S\n"
        b"BT /F1 10 Tf 30 280 Td (Amount VND) Tj ET\nBT /F1 10 Tf 30 220 Td (001234) Tj ET\n"
        b"BT /F1 10 Tf 150 220 Td (001234) Tj ET\n")
    page[NameObject("/Contents")] = writer._add_object(stream)
    out = io.BytesIO(); writer.write(out); raw = out.getvalue()
    storage = FileKnowledgeStorage(ROOT, retained_directory / "source")
    original = storage.write_bytes(raw, "synthetic-original", "application/pdf")
    environment = {key: value for key,value in os.environ.items() if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR"}}
    environment["PYTHONPATH"] = str(ROOT / "services/worker/src")
    child = subprocess.run([str(ROOT / ".venv/Scripts/python.exe"), "-B", "-m", "campus247_worker.knowledge_parse",
        str(storage.path(original.object_key)), "application/pdf"], env=environment, cwd=ROOT, capture_output=True,
        timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    assert child.returncode == 0, child.stdout.decode()
    result = json.loads(child.stdout)
    layout = result["pages"][0]["layout"]
    assert layout["route"] == "NATIVE_TABLE" and len(layout["tables"][0]["cells"]) == 5
    header = layout["tables"][0]["cells"][0]
    assert header["column_span"] == 2 and header["text"] == "Amount VND"
    assert len(layout["shapes"]) == 4 and all(shape["points"] for shape in layout["shapes"])
    assert result["issues"] and not layout["semantics_verified"]
