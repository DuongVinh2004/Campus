"""Retain the inspected71HK cells, nested elective options and native arrows."""
import re
from datetime import UTC, datetime

from continue_huce_completion_20261025 import OUT, ROOT, read, save, sha

BUILDING_SERVICES = "d08053e2-2f34-7c3a-8d9e-46a1652f1866"
PREREQUISITES = [
    ("446601", "446602", [270, 300]), ("446602", "446603", [271, 301]),
    ("446603", "446604", [272, 302]), ("390121", "398803", [273, 303]),
    ("250101", "250102", [274, 304]), ("108813", "107702", [275, 305]),
    ("250102", "258806", [279, 312]), ("258806", "108811", [281, 315]),
    ("108808", "107716", [282, 316]), ("240131", "248803", [286, 323]),
    ("278808", "108811", [287, 326]), ("118800", "118801", [324, 325]),
    ("108803", "108840", [289, 329]), ("108840", "108841", [290, 330]),
    ("198802", "108803", [291, 331]), ("107707", "107717", [293, 334]),
]
COREQUISITES = [
    ("088804", "088805", [276, 306, 307]), ("108815", "108816", [277, 308, 309]),
    ("108822", "108823", [278, 310, 311]), ("250101", "250103", [280, 313, 314]),
    ("258806", "258807", [283, 317, 318]), ("108808", "108837", [284, 319, 320]),
    ("318820", "318821", [285, 321, 322]), ("240131", "240102", [288, 327, 328]),
    ("108841", "108807", [292, 332, 333]), ("108813", "108814", [294, 335, 336]),
    ("107708", "107720", [295, 337, 338]),
]


def main():
    source = next(s for s in read(OUT / "curriculum-cell-candidates-01.json")["sources"] if s["source_id"] == BUILDING_SERVICES)
    assert len(source["pages"]) == 1
    page = source["pages"][0]; geometry = read(ROOT / page["evidence"])
    assert sha((ROOT / page["image"]).read_bytes()) == page["image_sha256"]
    assert sha((ROOT / page["evidence"]).read_bytes()) == page["evidence_sha256"]
    total = "Tổng: 180 TC (không tính HP Giáo dục thể chất và Giáo dục quốc phòng)"
    assert total in geometry["text"]
    cells = []
    for c in page["cells"]:
        if c["text"].isdigit():
            continue
        assert c["course_code_credit_pairs"] or c["text"].startswith(("Thể chất", "4801xx"))
        cells.append({"id": f"p1t{c['table']}r{c['row']}c{c['column']}", "page": 1,
            **{k: c[k] for k in ("table", "row", "column", "bbox", "text", "semester", "header")},
            "text_sha256": sha(c["text"].encode()), "semester_header": c["header"]["text"],
            "course_codes": [code for code, _ in c["course_code_credit_pairs"]],
            "unlabelled_credits": c["text"].startswith("Thể chất")})
    assert len(cells) == 79
    nested = []
    for child in page["ambiguous_course_cells"]:
        x0, top, x1, bottom = child["bbox"]
        containers = [c for c in cells if c["semester"] == 8 and c["bbox"][0] <= x0 and x1 <= c["bbox"][2]
            and c["bbox"][1] <= top and bottom <= c["bbox"][3]
            and re.sub(r"\s+", "", child["text"]) in re.sub(r"\s+", "", c["text"])]
        assert len(containers) == 1
        nested.append({"nested_native_cell": child, "admitted_outer_cell_id": containers[0]["id"], "counted_separately": False})
    assert len(nested) == 3
    codes = {code: c for c in cells for code in c["course_codes"]}
    shapes = {s["object_index"]: s for s in geometry["shapes"]}
    edges = []
    for kind, links in [("PREREQUISITE", PREREQUISITES), ("COREQUISITE", COREQUISITES)]:
        for a, b, indices in links:
            edges.append({"id": f"e{len(edges)}", "page": 1, "kind": kind, "from_cell": codes[a]["id"],
                "to_cell": codes[b]["id"], "arrow_objects": [shapes[n] for n in indices], "legend_verified": True})
    detail = OUT / "building-services-bl2-detail-01.png"
    save(OUT / "building-services-71-reviewed-geometry-01.json", {"at": datetime.now(UTC), "source_id": BUILDING_SERVICES,
        "original_sha256": source["original_sha256"], "image": page["image"], "image_sha256": page["image_sha256"],
        "geometry": page["evidence"], "geometry_sha256": page["evidence_sha256"], "programme_printed": "71HK", "cohort": "K71",
        "semesters_admitted": list(range(1, 10)), "cells": cells, "edges": edges, "printed_total": total,
        "nested_cell_membership": nested, "legend_objects": [shapes[n] for n in [267, 268, 296, 297, 298, 299]],
        "detail_image": {"file": str(detail.relative_to(ROOT)), "sha256": sha(detail.read_bytes()),
            "observation": "Enlarged original and PDFium bounded text both print BL2), without an opening parenthesis. Preserve it."},
        "reviewer": "coding agent technical visual transcription; no official HUCE approval claimed",
        "method": "Full original rendering read:79 outer cells, nine semesters,16 prerequisites including bent/downward links and11 double-headed corequisites. Three option code subcells belong to one semester8 outer elective cell, not additional courses.",
        "notes": ["Preserve literal Đai số tuyến tính, BL2), REVITS and leading08 in the internship credit. Do not silently repair typography or expand abbreviations.",
            "Physical education1/2/3 has no printed credit value.4801xx is an unresolved printed defence placeholder; its8 is separate from the1234 course name.",
            "Keep the semester8 elective4TC group and all three2-credit options. Do not infer how many options must be selected; the separately referenced elective catalogue is absent.",
            "Keep BL1/BL2 labels without interpreting their block rules. No absent relationship, personal eligibility or later amendment is inferred.",
            "Keep180TC total and its exclusions without summing semester/course values."],
        "full_source_review_complete": True, "source_semantics_resolved": False, "serving_scope_expanded": False})
    print({"cells": len(cells), "semesters": 9, "edges": len(edges), "nested_cells_reconciled": len(nested), "activated": False})


if __name__ == "__main__":
    main()
