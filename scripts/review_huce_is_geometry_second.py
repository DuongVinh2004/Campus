"""Retain73 source-exact71IS cells; do not admit unresolved credit capabilities."""
from datetime import UTC, datetime

from continue_huce_completion_20261025 import OUT, ROOT, checked, read, save, sha

IS = "f9d9cac7-6525-7e61-8039-ccce15a5c635"
PREREQUISITES = [
    ("446601", "446602", [244, 262]), ("446602", "446603", [245, 263]),
    ("446603", "446604", [246, 264]), ("401712", "461716", [247, 268]),
    ("461716", "462105", [248, 269]), ("250101", "250102", [249, 276]),
    ("450101", "461727", [250, 277]), ("461730", "471733", [251, 278]),
    ("461727", "478801", [252, 279]), ("390121", "396602", [253, 288]),
    ("396602", "400101", [286, 287]),
]
COREQUISITES = [
    ("462113", "462114", [258, 259, 260]), ("471756", "471757", [265, 266, 267]),
    ("461730", "461731", [270, 271, 272]), ("467705", "467704", [273, 274, 275]),
    ("471733", "471734", [280, 281, 282]), ("461785", "462109", [283, 284, 285]),
]


def main():
    receipt_file = checked(OUT / "black-border-tables-02" / IS / "receipt.json")
    receipt = read(receipt_file)
    page = receipt["pages"][0]
    assert len(receipt["pages"]) == 1 and page["cell_count"] == page["centre_agreement"] == page["bounded_agreement"] == 73
    geometry_file = checked(ROOT / page["geometry"])
    assert sha(geometry_file.read_bytes()) == page["geometry_sha256"]
    assert sha(checked(ROOT / page["image"]).read_bytes()) == page["image_sha256"]
    geometry = read(geometry_file)
    original = read(checked(ROOT / geometry["derivation"]["raw_geometry"]))
    assert geometry["shapes"] == original["shapes"] and geometry["text"] == original["text"]
    total = "Tổng: 180 TC (không tính HP Giáo dục thể chất và Giáo dục quốc phòng)"
    assert total in geometry["text"]
    cells = []
    for c in page["cells"]:
        assert c["course_code_credit_pairs"] or c["text"].startswith(("48011x", "Giáo dục TC"))
        cells.append({"id": f"p1t{c['table']}r{c['row']}c{c['column']}", "page": 1,
            **{k: c[k] for k in ("table", "row", "column", "bbox", "text", "semester", "header")},
            "text_sha256": c["text_sha256"], "semester_header": c["header"]["text"],
            "course_codes": [code for code, _ in c["course_code_credit_pairs"]],
            "unlabelled_credits": c["text"].startswith("Giáo dục TC")})
    def one(code):
        found = [c for c in cells if code in c["course_codes"]]
        assert len(found) == 1, code
        return found[0]["id"]
    shapes = {s["object_index"]: s for s in geometry["shapes"]}
    edges = []
    for kind, links in (("PREREQUISITE", PREREQUISITES), ("COREQUISITE", COREQUISITES)):
        for a, b, indices in links:
            edges.append({"id": f"e{len(edges)}", "page": 1, "kind": kind, "from_cell": one(a), "to_cell": one(b),
                "arrow_objects": [shapes[n] for n in indices], "legend_verified": True})
    duplicate_cells = {code: [c["id"] for c in cells if code in c["course_codes"]] for code in ("428802", "462112")}
    assert all(len(v) == 2 for v in duplicate_cells.values())
    deferred_target = next(c for c in cells if "428802" in c["course_codes"] and c["semester"] == 3)
    save(checked(OUT / "is-71-reviewed-geometry-01.json"), {"at": datetime.now(UTC), "source_id": IS,
        "original_sha256": receipt["original_sha256"], "image": page["image"], "image_sha256": page["image_sha256"],
        "geometry": page["geometry"], "geometry_sha256": page["geometry_sha256"], "programme_printed": "71IS", "cohort": "K71",
        "semesters_admitted": list(range(1, 10)), "cells": cells, "edges": edges, "printed_total": total,
        "duplicate_code_cells": duplicate_cells,
        "deferred_edges": [{"from_cell": one("428801"), "to_cell": deferred_target["id"],
            "arrow_objects": [shapes[n] for n in (243, 261)],
            "reason": "Arrow physically targets the semester3 economics cell. Code428802 is also printed for semester4 CNXH; keep the drawn line as evidence, do not resolve an unqualified code-based relationship."}],
        "legend_objects": [s for s in shapes.values() if s["top"] > geometry["tables"][0]["bbox"][3]
            and s.get("non_stroking_color") not in (0.0, [0.0, 0.0, 0.0])],
        "native_glyph_crosscheck": {"file": str(receipt_file.relative_to(ROOT)), "sha256": sha(receipt_file.read_bytes()),
            "cells": 73, "centre_matches": 73, "bounded_matches": 73},
        "reviewer": "coding agent technical visual transcription; no official HUCE approval claimed",
        "method": "Full original diagram read:73 physical cells in nine semesters,12 prerequisite lines and six double-headed corequisites.17 relationships proposed as unambiguous; one duplicate-code relation retained separately. Both decoders agree73/73, original drawings/text/image untouched.",
        "notes": ["Preserve428802 in both semester3 and4 with their different names, and462112 for two different semester7 names. No silent code/name correction or unique lookup.",
            "Giáo dục TC1/2/3 print no credits.48011x remains an unresolved defence placeholder with8 printed separately from1,2,3,4.",
            "Each of the two semester8 elective groups lists2/3-credit options but no printed group total or selection count. The separate catalogue referenced in the legend is absent; do not sum options or infer choice rules.",
            "Preserve literal ƯD and abbreviations.180TC and its exclusions are printed, not computed; no personal eligibility or later amendment inferred."],
        "full_source_review_complete": True, "source_semantics_resolved": False, "serving_scope_expanded": False,
        "admission_blockers": ["Verify explicit guard coverage for unlabelled elective-group totals and abbreviated Giáo dụcTC labels before admission; do not rely on the name's digits as a credit value."]})
    print({"cells": len(cells), "semesters": 9, "unambiguous_edges": len(edges), "deferred_edge": 1, "activated": False})


if __name__ == "__main__":
    main()
