"""Retain the visually inspected71DS native cells and direct arrows."""
from datetime import UTC, datetime

from continue_huce_completion_20261025 import OUT, ROOT, read, save, sha

DATA_SCIENCE = "e863a710-acbe-7871-885d-f98cf5b8dd69"
LINKS = [
    ("428801", "428802", [168, 185]),
    ("446601", "446602", [176, 193]),
    ("446602", "446603", [177, 194]),
    ("446603", "446604", [178, 195]),
    ("400101", "407701", [170, 187]),
    ("941714", "941715", [171, 188]),
    ("390121", "396602", [172, 189]),
    ("941723", "941712", [173, 190]),
    ("941712", "941721", [174, 191]),
    ("941713", "941722", [175, 192]),
    ("471706", "941706", [169, 186]),
    ("941707", "941708", [179, 196]),
    ("471754", "471755", [180, 197]),
]


def main():
    source = next(s for s in read(OUT / "curriculum-cell-candidates-01.json")["sources"] if s["source_id"] == DATA_SCIENCE)
    assert len(source["pages"]) == 1
    page = source["pages"][0]
    geometry = read(ROOT / page["evidence"])
    assert sha((ROOT / page["image"]).read_bytes()) == page["image_sha256"]
    assert sha((ROOT / page["evidence"]).read_bytes()) == page["evidence_sha256"]
    assert not page["ambiguous_course_cells"]
    total = "Tổng: 130TC (Không tính HP giáo dục thể chất, Giáo dục quốc phòng)"
    assert total in geometry["text"]
    cells = []
    for c in page["cells"]:
        if c["text"].isdigit():
            continue
        assert c["course_code_credit_pairs"] or c["text"].startswith(("GD thể chất", "48xxxx"))
        cells.append({"id": f"p1t{c['table']}r{c['row']}c{c['column']}", "page": 1,
            **{k: c[k] for k in ("table", "row", "column", "bbox", "text", "semester", "header")},
            "text_sha256": sha(c["text"].encode()), "semester_header": c["header"]["text"],
            "course_codes": [code for code, _ in c["course_code_credit_pairs"]],
            "unlabelled_credits": c["text"].startswith("GD thể chất")})
    assert len(cells) == 54
    codes = {code: c for c in cells for code in c["course_codes"]}
    shapes = {s["object_index"]: s for s in geometry["shapes"]}
    edges = [{"id": f"e{i}", "page": 1, "kind": "PREREQUISITE", "from_cell": codes[a]["id"],
        "to_cell": codes[b]["id"], "arrow_objects": [shapes[n] for n in indices], "legend_verified": True}
        for i, (a, b, indices) in enumerate(LINKS)]
    edges.append({"id": "e13", "page": 1, "kind": "COREQUISITE", "from_cell": codes["941708"]["id"],
        "to_cell": codes["941709"]["id"], "arrow_objects": [shapes[n] for n in [198, 199, 200]], "legend_verified": True})
    save(OUT / "data-science-71-reviewed-geometry-01.json", {"at": datetime.now(UTC), "source_id": DATA_SCIENCE,
        "original_sha256": source["original_sha256"], "image": page["image"], "image_sha256": page["image_sha256"],
        "geometry": page["evidence"], "geometry_sha256": page["evidence_sha256"], "programme_printed": "71DS", "cohort": "K71",
        "semesters_admitted": list(range(1, 8)), "cells": cells, "edges": edges, "printed_total": total,
        "legend_objects": [shapes[n] for n in [167, 181, 182, 183, 184]],
        "reviewer": "coding agent technical visual transcription; no official HUCE approval claimed",
        "method": "Full original rendering read, including54 non-total cells, seven semester columns,13 prerequisite arrows and one vertical double-headed corequisite. Each cell and arrow reconciled to native objects.",
        "notes": ["Keep all printed abbreviations, code leading zeroes and exact semester placement; do not infer additional relationships.",
            "GD thể chất1/2/3 has no printed credit value.48xxxx remains an unresolved defence-code placeholder, with8 printed separately from1,2,3,4.",
            "941708 and941709 are linked as corequisites in semester4, not a directed prerequisite.",
            "Keep130TC total and its exclusions. No personal eligibility, separate catalogue or later amendment supplied."],
        "full_source_review_complete": True, "source_semantics_resolved": False, "serving_scope_expanded": False})
    print({"cells": len(cells), "semesters": 7, "edges": len(edges), "activated": False})


if __name__ == "__main__":
    main()
