"""Resolve boundary-overlap diagnostics using original glyph centres, never guessed text."""
import json
import sys

import pypdfium2 as pdfium

from continue_huce_completion_20261025 import OUT, ROOT, checked, read, save, sha
from reconcile_huce_native_cells_second import compact


def main():
    baseline = read(OUT / "native-cell-reconciliation-summary-01.json")
    folder = checked(OUT / "native-cell-centres-02"); folder.mkdir(exist_ok=False)
    results = []
    for entry in baseline["sources"]:
        previous = read(ROOT / entry["file"])
        original = (ROOT/previous["original"]).read_bytes(); assert sha(original) == previous["original_sha256"]
        pages = []
        with pdfium.PdfDocument(original) as pdf:
            for old_page in previous["pages"]:
                p = pdf[old_page["page"]-1]; tp = p.get_textpage(); count = tp.count_chars()
                text = tp.get_text_range(0, count); width, height = p.get_size()
                exact_indexing = len(text) == count
                glyphs = []
                if exact_indexing:
                    for i, char in enumerate(text):
                        if char.isspace(): continue
                        x0,y0,x1,y1 = tp.get_charbox(i)
                        glyphs.append((i, char, (x0+x1)/2, height-(y0+y1)/2))
                cells = []
                for cell in old_page["cells"]:
                    x0, top, x1, bottom = cell["bbox"]
                    selected = [g for g in glyphs if x0 <= g[2] < x1 and top <= g[3] < bottom]
                    centre_text = "".join(g[1] for g in selected)
                    agreement = exact_indexing and compact(centre_text) == compact(cell["text"])
                    header = cell["semester_header"]
                    h_agreement = False
                    if header:
                        a,b,c,d = header["native"]["bbox"]
                        header_text = "".join(g[1] for g in glyphs if a <= g[2] < c and b <= g[3] < d)
                        h_agreement = compact(header_text) == compact(header["native"]["text"])
                    cells.append({**cell, "centre_text": centre_text, "centre_text_sha256": sha(centre_text.encode()),
                        "glyph_indices": [g[0] for g in selected], "centre_glyph_agreement": agreement,
                        "centre_header_agreement": h_agreement,
                        "geometry_and_glyphs_reconciled": bool(agreement and h_agreement), "admitted": False})
                tp.close(); p.close()
                pages.append({**old_page, "cells": cells, "pdfium_char_index_exact": exact_indexing,
                    "original_page_text_sha256": sha(text.encode()), "original_char_count": count})
        report = {**previous, "pages": pages, "method": "PDFium original glyph centres in exact pdfplumber cell and header rectangles; Unicode and punctuation unchanged"}
        target = folder/(entry["source_id"]+".json"); save(target, report)
        result = {"source_id": entry["source_id"], "file": str(target.relative_to(ROOT)), "sha256": sha(target.read_bytes()),
            "cells_checked": sum(len(p["cells"]) for p in pages),
            "glyph_agreement": sum(c["centre_glyph_agreement"] for p in pages for c in p["cells"]),
            "mapped": sum(c["geometry_and_glyphs_reconciled"] for p in pages for c in p["cells"])}
        results.append(result)
    save(OUT / "native-cell-centres-summary-02.json", {"sources": results, "source_count": len(results),
        "cells_checked": sum(r["cells_checked"] for r in results), "glyph_agreement": sum(r["glyph_agreement"] for r in results),
        "mapped": sum(r["mapped"] for r in results), "admitted_by_this_run": 0, "all_content_complete": False})
    print(json.dumps({k:v for k,v in read(OUT/"native-cell-centres-summary-02.json").items() if k != "sources"}))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
