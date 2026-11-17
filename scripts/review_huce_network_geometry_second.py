"""Admit selected71MHT columns/links; explicitly defer its problematic eighth column."""
from datetime import UTC, datetime

from continue_huce_completion_20261025 import OUT, ROOT, read, save, sha

NETWORK = "3f611a4c-1a99-7dad-8880-e8e6436875a6"
LINKS = [
    ("428801", "428802", [259, 277]),
    ("446601", "446602", [253, 271]), ("446602", "446603", [254, 272]), ("446603", "446604", [255, 273]),
    ("390121", "396602", [256, 274]), ("396602", "400101", [257, 275]),
    ("250101", "250102", [260, 278]), ("461716", "608807", [258, 276]),
    ("461792", "467717", [261, 279]), ("461762", "461706", [262, 280]),
    ("461706", "461788", [263, 281]), ("467714", "477714", [264, 282]),
    ("941726", "471754", [265, 283]), ("471754", "471755", [266, 284]),
]


def main():
    source = next(s for s in read(OUT / "curriculum-cell-candidates-01.json")["sources"] if s["source_id"] == NETWORK)
    assert len(source["pages"]) == 1
    page = source["pages"][0]; geometry = read(ROOT / page["evidence"])
    assert sha((ROOT / page["image"]).read_bytes()) == page["image_sha256"]
    assert sha((ROOT / page["evidence"]).read_bytes()) == page["evidence_sha256"]
    total = "Tổng: 180TC (Không tính HP giáo dục thể chất, Giáo dục quốc phòng)"
    assert total in geometry["text"]
    cells, deferred = [], []
    for c in page["cells"]:
        if c["text"].isdigit():
            continue
        if c["semester"] == 8:
            deferred.append(c)
            continue
        assert c["course_code_credit_pairs"] or "48011x" in c["text"]
        cells.append({"id": f"p1t{c['table']}r{c['row']}c{c['column']}", "page": 1,
            **{k: c[k] for k in ("table", "row", "column", "bbox", "text", "semester", "header")},
            "text_sha256": sha(c["text"].encode()), "semester_header": c["header"]["text"],
            "course_codes": [code for code, _ in c["course_code_credit_pairs"]], "unlabelled_credits": False})
    codes = {code: c for c in cells for code in c["course_codes"]}
    assert "467710" not in codes
    shapes = {s["object_index"]: s for s in geometry["shapes"]}
    edges = [{"id": f"e{i}", "page": 1, "kind": "PREREQUISITE", "from_cell": codes[a]["id"], "to_cell": codes[b]["id"],
        "arrow_objects": [shapes[n] for n in indices], "legend_verified": True} for i, (a, b, indices) in enumerate(LINKS)]
    save(OUT / "network-71-reviewed-geometry-01.json", {"at": datetime.now(UTC), "source_id": NETWORK,
        "original_sha256": source["original_sha256"], "image": page["image"], "image_sha256": page["image_sha256"],
        "geometry": page["evidence"], "geometry_sha256": page["evidence_sha256"], "programme_printed": "71MHT", "cohort": "K71",
        "semesters_admitted": [1, 2, 3, 4, 5, 6, 7, 9], "cells": cells, "edges": edges, "printed_total": total,
        "deferred_semester_8_cells": deferred, "deferred_nested_table_cells": page["ambiguous_course_cells"],
        "legend_objects": [shapes[n] for n in [250, 251, 267, 268, 269, 270]],
        "reviewer": "coding agent technical visual transcription; no official HUCE approval claimed",
        "method": "Full original image read; each selected column/course cell and all14 visible directed links reconciled to native rectangles, shafts and arrowheads. Semester8 is explicitly withheld.",
        "notes": ["Only semesters1–7 and9 plus14 directly printed prerequisite links. No missing corequisite is interpreted as a negative fact.",
            "Semester8 prints467710 for both Chuyên đề tổng hợp and Bảo vệ bản quyền số. Do not resolve that conflict or claim a unique code/name association.",
            "Semester8 elective1 prints4TC but option values2 and3; no selection count inferred. A native-cell extraction appends an uncertain2 to Bảo vệ bản quyền số; nested table/cell reconciliation is unfinished. Hold the entire eighth column.",
            "Retain source-specific physical-education codes430120,420102,430103 and literal Giáo dục TC1/TC2/TC3 labels; do not silently correct420102 or expand abbreviations.",
            "Defence48011x is an unresolved printed placeholder. Keep its8 separate from the1,2,3,4 name.",
            "Keep180TC printed total and exclusions; do not sum semester totals or infer a separate elective catalogue, block rules or personal eligibility."],
        "full_source_review_complete": False, "serving_scope_expanded": False})
    print({"cells": len(cells), "edges": len(edges), "deferred_cells": len(deferred), "semester8_withheld": True})


if __name__ == "__main__":
    main()
