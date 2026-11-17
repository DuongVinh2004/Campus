"""Retain the independently decoded and visually read69-cell71PM diagram."""
from datetime import UTC, datetime

from continue_huce_completion_20261025 import OUT, ROOT, checked, read, save, sha

PM = "87d97124-36a4-7429-84cb-577020679a34"
LINKS = [
    ("446603", "446604", [258, 275]), ("461716", "608807", [259, 276]),
    ("471792", "477717", [260, 277]), ("428801", "428802", [261, 278]),
    ("446601", "446602", [262, 279]), ("446602", "446603", [263, 280]),
    ("390121", "396602", [264, 281]), ("396602", "400101", [265, 282]),
    ("250101", "250102", [266, 283]), ("461762", "461706", [267, 284]),
    ("467714", "477714", [268, 285]), ("941726", "471754", [269, 286]),
    ("471754", "471755", [270, 287]),
]


def main():
    receipt_file = checked(OUT / "black-border-tables-02" / PM / "receipt.json")
    receipt = read(receipt_file)
    page = receipt["pages"][0]
    assert len(receipt["pages"]) == 1 and page["cell_count"] == page["centre_agreement"] == page["bounded_agreement"] == 69
    geometry = read(checked(ROOT / page["geometry"]))
    assert sha(checked(ROOT / page["geometry"]).read_bytes()) == page["geometry_sha256"]
    assert sha(checked(ROOT / page["image"]).read_bytes()) == page["image_sha256"]
    original_geometry = read(checked(ROOT / geometry["derivation"]["raw_geometry"]))
    assert geometry["shapes"] == original_geometry["shapes"] and geometry["text"] == original_geometry["text"]
    total = "Tổng: 180TC (Không tính HP giáo dục thể chất, Giáo dục quốc phòng)"
    assert total in geometry["text"]
    cells = []
    for c in page["cells"]:
        assert c["semester"] in range(1, 10)
        assert c["course_code_credit_pairs"] or c["text"].startswith("48011x")
        cells.append({"id": f"p1t{c['table']}r{c['row']}c{c['column']}", "page": 1,
            **{k: c[k] for k in ("table", "row", "column", "bbox", "text", "semester", "header")},
            "text_sha256": c["text_sha256"], "semester_header": c["header"]["text"],
            "course_codes": [code for code, _ in c["course_code_credit_pairs"]], "unlabelled_credits": False})
    codes = {code: c for c in cells for code in c["course_codes"]}
    assert len(codes) == sum(len(c["course_codes"]) for c in cells)
    shapes = {s["object_index"]: s for s in geometry["shapes"]}
    edges = [{"id": f"e{i}", "page": 1, "kind": "PREREQUISITE", "from_cell": codes[a]["id"],
        "to_cell": codes[b]["id"], "arrow_objects": [shapes[n] for n in indices], "legend_verified": True}
        for i, (a, b, indices) in enumerate(LINKS)]
    raw = next(s for s in read(OUT / "curriculum-cell-candidates-01.json")["sources"] if s["source_id"] == PM)["pages"][0]
    reconciled = []
    for child in raw["ambiguous_course_cells"]:
        a, b, c, d = child["bbox"]
        parents = [p for p in cells if p["bbox"][0] <= a and c <= p["bbox"][2]
            and p["bbox"][1] <= b and d <= p["bbox"][3] and p["semester"] == 8
            and all(code in p["course_codes"] for code, _ in child["course_code_credit_pairs"])]
        assert len(parents) == 1
        reconciled.append({"raw_cell": child, "physical_parent": parents[0]["id"], "counted_separately": False})
    assert len(reconciled) == 2
    save(checked(OUT / "pm-71-reviewed-geometry-01.json"), {"at": datetime.now(UTC), "source_id": PM,
        "original_sha256": receipt["original_sha256"], "image": page["image"], "image_sha256": page["image_sha256"],
        "geometry": page["geometry"], "geometry_sha256": page["geometry_sha256"], "programme_printed": "71PM", "cohort": "K71",
        "semesters_admitted": list(range(1, 10)), "cells": cells, "edges": edges, "printed_total": total,
        "legend_objects": [s for s in shapes.values() if s["top"] > 480 and s.get("non_stroking_color") not in (0.0, [0.0, 0.0, 0.0])],
        "native_glyph_crosscheck": {"file": str(receipt_file.relative_to(ROOT)), "sha256": sha(receipt_file.read_bytes()),
            "course_cells": 69, "centre_matches": 69, "bounded_matches": 69},
        "raw_ambiguous_cell_reconciliation": reconciled,
        "reviewer": "coding agent technical visual transcription; no official HUCE approval claimed",
        "method": "Read full original diagram and both complete semester8 blue groups.69 physical outer cells and13 single-headed prerequisite arrows reconciled with native objects; no course corequisite drawn. New black-border extraction avoids artificial divisions made by coloured arrow paths while retaining every original character, drawing and image. Independent PDFium bounded text and glyph centres both agree69/69. Raw geometry and failed derivative attempt remain retained.",
        "notes": ["The two semester8 groups each print6TC and two3-credit options. Preserve all values and whole groups; no selection count or extra catalogue rule inferred.",
            "Keep420102,430120,430103 and their printed1-credit values, plus the unresolved48011x defence placeholder with8. Preserve block1/block2 and abbreviations without interpreting block rules.",
            "Keep180TC with its exclusions; do not sum values or infer personal completion, absent prerequisites/corequisites, or later amendments.",
            "This review is only71PM K71. The six unscoped historical IT originals remain unscoped; no cohort transfer is authorized."],
        "full_source_review_complete": True, "source_semantics_resolved": False, "serving_scope_expanded": False})
    print({"cells": len(cells), "semesters": 9, "edges": len(edges), "activated": False})


if __name__ == "__main__":
    main()
