"""Retain the source-specific visual review of the K71CSQT diagram."""
import argparse
from datetime import UTC, datetime

from continue_huce_completion_20261025 import OUT, ROOT, checked, read, save, sha

CSQT = "9f9bf571-a71e-707e-8c1b-3bca8cfe089a"
CS = "ba2795dc-ce32-7325-8b2c-c2bb61eaff1a"
LINKS = [
    ("607715", "607711", [230, 243]), ("390121", "398803", [231, 244]),
    ("398803", "400101", [232, 245]), ("538801", "608804", [233, 246]),
    ("446601", "446602", [234, 247]), ("446602", "446603", [235, 248]),
    ("446603", "446604", [236, 249]), ("608804", "478801", [237, 250]),
    ("607712", "607713", [238, 251]), ("608825", "608807", [239, 252]),
    ("428801", "428802", [240, 253]), ("250101", "250102", [241, 254]),
]


def main(programme="K71CSQT"):
    source_id, label = (CSQT, "csqt") if programme == "K71CSQT" else (CS, "cs")
    source = next(s for s in read(OUT / "curriculum-cell-candidates-01.json")["sources"] if s["source_id"] == source_id)
    assert len(source["pages"]) == 1
    page = source["pages"][0]
    geometry = read(checked(ROOT / page["evidence"]))
    assert sha(checked(ROOT / page["image"]).read_bytes()) == page["image_sha256"]
    assert sha(checked(ROOT / page["evidence"]).read_bytes()) == page["evidence_sha256"]
    assert not page["ambiguous_course_cells"]
    total = "Tổng: 180TC (Không tính HP giáo dục thể chất, Giáo dục quốc phòng)"
    assert total in geometry["text"]
    cells = []
    for cell in page["cells"]:
        if cell["text"].isdigit():
            continue
        assert cell["course_code_credit_pairs"] or cell["text"].startswith(("GD ", "4801xx"))
        cells.append({"id": f"p1t{cell['table']}r{cell['row']}c{cell['column']}", "page": 1,
            **{k: cell[k] for k in ("table", "row", "column", "bbox", "text", "semester", "header")},
            "text_sha256": sha(cell["text"].encode()), "semester_header": cell["header"]["text"],
            "course_codes": [code for code, _ in cell["course_code_credit_pairs"]],
            "unlabelled_credits": cell["text"].startswith("GD ")})
    assert len(cells) == 66
    codes = {code: c for c in cells for code in c["course_codes"]}
    assert len(codes) == sum(len(c["course_codes"]) for c in cells)
    shapes = {s["object_index"]: s for s in geometry["shapes"]}
    edges = [{"id": f"e{i}", "page": 1, "kind": "PREREQUISITE", "from_cell": codes[a]["id"],
        "to_cell": codes[b]["id"], "arrow_objects": [shapes[n] for n in indices], "legend_verified": True}
        for i, (a, b, indices) in enumerate(LINKS)]
    glyph_file = checked(OUT / "native-cell-centres-02" / f"{source_id}.json")
    glyphs = read(glyph_file)["pages"][0]["cells"]
    for cell in cells:
        native = next(c for c in glyphs if (c["table"], c["row"], c["column"]) ==
            (cell["table"], cell["row"], cell["column"]))
        assert native["centre_glyph_agreement"] and native["centre_header_agreement"]
    save(checked(OUT / f"{label}-71-reviewed-geometry-01.json"), {"at": datetime.now(UTC), "source_id": source_id,
        "original_sha256": source["original_sha256"], "image": page["image"], "image_sha256": page["image_sha256"],
        "geometry": page["evidence"], "geometry_sha256": page["evidence_sha256"], "programme_printed": programme,
        "cohort": "K71", "semesters_admitted": list(range(1, 10)), "cells": cells, "edges": edges,
        "printed_total": total, "legend_objects": [shapes[n] for n in [242, 255, 256, 257, 258]],
        "native_glyph_crosscheck": {"file": str(glyph_file.relative_to(ROOT)), "sha256": sha(glyph_file.read_bytes()),
            "course_cells_agree": 66, "semester_headers_agree": 66},
        "reviewer": "coding agent technical visual transcription; no official HUCE approval claimed",
        "method": "Full original rendering read:66 course/placeholder cells in nine semesters and12 straight prerequisite arrows. Printed legend independently read; no double-headed course link is drawn. Every cell/header reconciled with PDFium glyph centres and every edge with its native shaft/head.",
        "notes": [f"This review is bound only to the independently viewed original for{programme}; no scope transfer to another programme/cohort. Both71CS andK71CSQT images were separately inspected despite their similar course layouts.",
            "Preserve literal GD Thế chất2, Lê Nin, course-code leading zeroes and all abbreviations/credits as printed. No spelling repair.",
            "Physical education1/2/3 has no printed credit value.4801xx remains an unresolved defence placeholder with8 printed separately from1,2,3,4.",
            "Keep180TC and its exclusions. No absence of another relation is proved, and no personal eligibility or later amendment is inferred."],
        "full_source_review_complete": True, "source_semantics_resolved": False, "serving_scope_expanded": False})
    print({"cells": len(cells), "semesters": 9, "prerequisites": len(edges), "activated": False})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--programme", choices=("K71CSQT", "71CS"), default="K71CSQT")
    main(parser.parse_args().programme)
