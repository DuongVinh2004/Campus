"""Cross-check every table candidate against the original PDF's second decoder.

This records exact glyph/column evidence; it does not admit a source or claim
that a condition, elective rule or graph relationship has been resolved.
"""
import json
import re
import sys
import unicodedata

import pypdfium2 as pdfium

from continue_huce_completion_20261025 import OUT, ROOT, checked, read, save, sha


def compact(text):
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", text or ""))


def main():
    manifest = read(OUT / "original-geometry-manifest-01.json")
    folder = checked(OUT / "native-cell-reconciliation-01"); folder.mkdir(exist_ok=False)
    reports = []
    for source in manifest["sources"]:
        if source.get("kind") != "COHORT_SNAPSHOT" or source["source_id"] == "c2454951-46ce-7a56-8421-ca4927bf3339":
            continue
        original = checked(ROOT / source["original"]).read_bytes()
        assert sha(original) == source["original_sha256"]
        pages = []
        with pdfium.PdfDocument(original) as pdf:
            for info in source["pages"]:
                page = read(ROOT / info["evidence"])
                assert sha((ROOT/info["evidence"]).read_bytes()) == info["sha256"]
                p = pdf[info["page"]-1]; textpage = p.get_textpage(); width, height = p.get_size()
                dimensions_match = abs(width-page["width"]) < .5 and abs(height-page["height"]) < .5
                cells = []
                for table in page["tables"]:
                    headers = [(c, re.fullmatch(r"Học kỳ\s*(\d+)(?:\s*\(\d+\s*TC\))?", c["text"] or "", re.I))
                        for row in table["rows"] for c in row]
                    headers = [(c, int(m[1])) for c, m in headers if m]
                    for row in table["rows"]:
                        for cell in row:
                            if not (cell["text"] or "").strip(): continue
                            x0, top, x1, bottom = cell["bbox"]
                            second = textpage.get_text_bounded(x0, height-bottom, x1, height-top) if dimensions_match else ""
                            matching_headers = [(h, n) for h, n in headers if h["bbox"][0] <= x0+1
                                and x1 <= h["bbox"][2]+1 and h["bbox"][3] <= top+1]
                            header_witness = None
                            if len(matching_headers) == 1:
                                h, n = matching_headers[0]; a,b,c,d = h["bbox"]
                                header_text = textpage.get_text_bounded(a, height-d, c, height-b)
                                header_witness = {"semester": n, "native": h, "pdfium_text": header_text,
                                    "glyph_agreement": compact(header_text) == compact(h["text"])}
                            agreement = dimensions_match and compact(second) == compact(cell["text"])
                            cells.append({"table": table["index"], **cell, "pdfium_text": second,
                                "pdfium_text_sha256": sha(second.encode()), "glyph_agreement": agreement,
                                "semester_header": header_witness,
                                "geometry_and_glyphs_reconciled": bool(agreement and header_witness and header_witness["glyph_agreement"]),
                                "admitted": False})
                textpage.close(); p.close()
                pages.append({"page": info["page"], "geometry_file": info["evidence"], "geometry_sha256": info["sha256"],
                    "image": info["image"], "image_sha256": info["image_sha256"], "dimensions_match": dimensions_match,
                    "cells": cells, "condition_markers_require_review": bool(re.search(r"\*|BL[12]|\b(?:nếu|tùy|tuỳ|phụ thuộc)\b", page["text"], re.I)),
                    "relations_admitted": False})
        target = checked(folder / (source["source_id"]+".json"))
        report = {"source_id": source["source_id"], "original_sha256": source["original_sha256"],
            "original": source["original"], "pages": pages, "serving_scope_expanded": False}
        save(target, report)
        count = sum(len(p["cells"]) for p in pages)
        agreed = sum(c["glyph_agreement"] for p in pages for c in p["cells"])
        mapped = sum(c["geometry_and_glyphs_reconciled"] for p in pages for c in p["cells"])
        reports.append({"source_id": source["source_id"], "file": str(target.relative_to(ROOT)), "sha256": sha(target.read_bytes()),
            "cells_checked": count, "glyph_agreement": agreed, "unique_semester_and_glyph_agreement": mapped,
            "condition_pages": [p["page"] for p in pages if p["condition_markers_require_review"]]})
        print(json.dumps({"sources": len(reports), "cells_checked": count, "glyph_agreement": agreed, "mapped": mapped}), flush=True)
    save(OUT / "native-cell-reconciliation-summary-01.json", {"sources": reports,
        "source_count": len(reports), "cells_checked": sum(r["cells_checked"] for r in reports),
        "glyph_agreement": sum(r["glyph_agreement"] for r in reports),
        "unique_semester_and_glyph_agreement": sum(r["unique_semester_and_glyph_agreement"] for r in reports),
        "admitted_by_this_run": 0, "all_content_complete": False})


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
