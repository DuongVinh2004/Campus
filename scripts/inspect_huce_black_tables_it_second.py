"""Derive physical table candidates using black borders; never admit a source."""
import argparse
import json
import re
import unicodedata
from datetime import UTC, datetime

import pdfplumber
import pypdfium2 as pdfium

from continue_huce_completion_20261025 import OUT, ROOT, checked, read, save, sha


def black(value):
    return value == 0 or value == (0, 0, 0) or value == [0, 0, 0]


def border_input(obj):
    return (obj.get("object_type") not in ("line", "rect", "curve")
        or bool(obj.get("stroke") and black(obj.get("stroking_color")))
        or bool(obj.get("fill") and black(obj.get("non_stroking_color"))))


def compact(text):
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", text or ""))


def main(source_id, attempt):
    priority = next(s for s in read(OUT / "source-execution-priorities-01.json")["sources"] if s["source_id"] == source_id)
    assert priority["group"] == "CNTT" and priority["execution_priority"] == "CURRENT_FOCUS"
    source = next(s for s in read(OUT / "original-geometry-manifest-01.json")["sources"] if s["source_id"] == source_id)
    original = checked(ROOT / source["original"])
    assert sha(original.read_bytes()) == source["original_sha256"]
    folder = checked(OUT / f"black-border-tables-{attempt}" / source_id)
    folder.mkdir(parents=True, exist_ok=False)
    pages = []
    with pdfplumber.open(original) as pdf, pdfium.PdfDocument(str(original)) as second:
        for info in source["pages"]:
            raw_file = checked(ROOT / info["evidence"])
            raw = read(raw_file)
            assert sha(raw_file.read_bytes()) == info["sha256"]
            page = pdf.pages[info["page"] - 1]
            filtered = page.filter(border_input)
            assert filtered.chars == page.chars
            native_shapes = [{"object_index": j, **{k: obj.get(k) for k in ("object_type", "x0", "top", "x1", "bottom",
                "pts", "path", "stroke", "fill", "linewidth", "dash", "stroking_color", "non_stroking_color")}}
                for j, obj in enumerate(page.lines + page.rects + page.curves)]
            assert json.loads(json.dumps(native_shapes)) == raw["shapes"]
            tables = []
            for ti, table in enumerate(filtered.find_tables()):
                values = table.extract()
                rows = [[{"row": ri, "column": ci, "bbox": list(bbox), "text": values[ri][ci],
                    "text_sha256": sha((values[ri][ci] or "").encode())}
                    for ci, bbox in enumerate(row.cells) if bbox is not None] for ri, row in enumerate(table.rows)]
                tables.append({"index": ti, "bbox": list(table.bbox), "rows": rows})
            geometry = {**raw, "tables": tables, "review_state": "UNREVIEWED_BLACK_BORDER_TABLE_DERIVATIVE",
                "relations_admitted": False, "derivation": {"original": str(original.relative_to(ROOT)),
                    "original_sha256": source["original_sha256"], "raw_geometry": str(raw_file.relative_to(ROOT)),
                    "raw_geometry_sha256": info["sha256"], "all_original_shapes_retained": True,
                    "all_original_characters_retained": True,
                    "method": "Only black-filled or black-stroked drawings participate in border detection. All original characters remain. All original drawings, including coloured arrows/backgrounds, remain unchanged in the retained shape list and original PDF/image. This is a new derivative, not a rewrite of raw geometry."}}
            geometry_file = checked(folder / f"page-{info['page']:03}-geometry.json")
            save(geometry_file, geometry)
            decoded = second[info["page"] - 1]
            textpage = decoded.get_textpage()
            glyphs = []
            for i in range(textpage.count_chars()):
                char = textpage.get_text_range(i, 1)
                if not char or char.isspace():
                    continue
                x0, y0, x1, y1 = textpage.get_charbox(i)
                glyphs.append((i, char, (x0 + x1) / 2, page.height - (y0 + y1) / 2))
            cells = []
            for table in tables:
                headers = [(c, int(m[1])) for row in table["rows"] for c in row
                    if (m := re.fullmatch(r"Học kỳ\s+(\d+)", c["text"] or ""))]
                for row in table["rows"]:
                    for cell in row:
                        text = cell["text"] or ""
                        if not text or text.isdigit() or text.startswith(("Học kỳ", "Tổng:")):
                            continue
                        x0, top, x1, bottom = cell["bbox"]
                        matching = [(h, n) for h, n in headers if h["bbox"][0] <= x0 + 1
                            and x1 <= h["bbox"][2] + 1 and h["bbox"][3] <= top + 1]
                        chosen = [g for g in glyphs if x0 <= g[2] < x1 and top <= g[3] < bottom]
                        centre_text = "".join(g[1] for g in chosen)
                        bounded = textpage.get_text_bounded(x0, page.height - bottom, x1, page.height - top)
                        cells.append({"table": table["index"], **cell, "semester": matching[0][1] if len(matching) == 1 else None,
                            "header": matching[0][0] if len(matching) == 1 else None,
                            "course_code_credit_pairs": re.findall(r"(?m)^(\d{6})\s*[-–—]\s*(\d{1,2})(?=\s|$)", text),
                            "pdfium_bounded_text": bounded, "bounded_glyph_agreement": compact(text) == compact(bounded),
                            "centre_text": centre_text, "centre_glyph_agreement": compact(text) == compact(centre_text),
                            "glyph_indices": [g[0] for g in chosen], "reviewed": False})
            textpage.close()
            decoded.close()
            pages.append({"page": info["page"], "geometry": str(geometry_file.relative_to(ROOT)),
                "geometry_sha256": sha(geometry_file.read_bytes()), "image": info["image"], "image_sha256": info["image_sha256"],
                "cells": cells, "cell_count": len(cells), "centre_agreement": sum(c["centre_glyph_agreement"] for c in cells),
                "bounded_agreement": sum(c["bounded_glyph_agreement"] for c in cells), "admitted": False})
    save(checked(folder / "receipt.json"), {"at": datetime.now(UTC), "source_id": source_id,
        "original_sha256": source["original_sha256"], "pages": pages, "admission_claimed": False,
        "serving_scope_expanded": False, "visual_review_still_required": True})
    print({"source_id": source_id, "pages": len(pages), "cells": sum(p["cell_count"] for p in pages),
        "centre_matches": sum(p["centre_agreement"] for p in pages), "admitted": False})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--attempt", default="01")
    args = parser.parse_args()
    assert re.fullmatch(r"[0-9a-f-]{36}", args.source) and re.fullmatch(r"\d{2}", args.attempt)
    main(args.source, args.attempt)
