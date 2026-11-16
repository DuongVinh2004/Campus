"""Retain a source-specific visual review of K71KTE; never activate it."""
from datetime import UTC, datetime

from continue_huce_completion_20261025 import OUT, ROOT, checked, read, save, sha

SOURCE = "878730a5-2e55-75f3-8395-16c8da02b5ab"
PREREQUISITES = [
    ("396602", "400101", [294, 307]),
    ("060223", "030211", [295, 308]),
    ("420103", "420112", [311, 312]),
    ("361304", "361456", [315, 316]),
    ("010213", "060223", [317, 318]),
    ("060223", "050211", [319, 320]),
    ("390121", "396602", [321, 322]),
]
COREQUISITES = [
    ("310702", "310703", [296, 309, 310]),
    ("361456", "361457", [297, 313, 314]),
    ("381463", "381305", [298, 323, 324]),
    ("381325", "381307", [299, 325, 326]),
    ("361802", "361803", [300, 327, 328]),
    ("040212", "040213", [301, 329, 330]),
    ("511802", "511803", [302, 331, 332]),
]


def main():
    source = next(s for s in read(OUT / "curriculum-cell-candidates-01.json")["sources"] if s["source_id"] == SOURCE)
    assert len(source["pages"]) == 1
    page = source["pages"][0]
    geometry = read(checked(ROOT / page["evidence"]))
    assert sha(checked(ROOT / page["image"]).read_bytes()) == page["image_sha256"]
    assert sha(checked(ROOT / page["evidence"]).read_bytes()) == page["evidence_sha256"]
    assert not page["ambiguous_course_cells"]
    total = "Tổng: 190TC (Không tính HP giáo dục thể chất, Giáo dục quốc phòng và An ninh)"
    assert total in geometry["text"]
    cells = []
    for cell in page["cells"]:
        if cell["text"].isdigit():
            continue
        assert cell["course_code_credit_pairs"] or cell["text"].startswith("4801xx")
        cells.append({"id": f"p1t{cell['table']}r{cell['row']}c{cell['column']}", "page": 1,
            **{k: cell[k] for k in ("table", "row", "column", "bbox", "text", "semester", "header")},
            "text_sha256": sha(cell["text"].encode()), "semester_header": cell["header"]["text"],
            "course_codes": [code for code, _ in cell["course_code_credit_pairs"]], "unlabelled_credits": False})
    assert len(cells) == 87
    duplicate = [c for c in cells if "511802" in c["course_codes"]]
    assert len(duplicate) == 2 and all(c["semester"] == 8 for c in duplicate)

    def endpoint(code, *, target=False):
        matches = [c for c in cells if code in c["course_codes"]]
        if code == "511802":
            # Two different printed titles share the code. This arrow physically
            # meets the lower cell; a code dictionary would silently hide one.
            matches = [c for c in matches if c["row"] == 9 and "Tổ chức triển khai" in c["text"]]
        assert len(matches) == 1, (code, target)
        return matches[0]["id"]

    shapes = {s["object_index"]: s for s in geometry["shapes"]}
    edges = []
    for kind, links in (("PREREQUISITE", PREREQUISITES), ("COREQUISITE", COREQUISITES)):
        for a, b, indices in links:
            edges.append({"id": f"e{len(edges)}", "page": 1, "kind": kind,
                "from_cell": endpoint(a), "to_cell": endpoint(b, target=True),
                "arrow_objects": [shapes[n] for n in indices], "legend_verified": True})
    centres_path = checked(OUT / "native-cell-centres-02" / f"{SOURCE}.json")
    centres = read(centres_path)["pages"][0]["cells"]
    relevant = [c for c in centres if any((c["table"], c["row"], c["column"]) ==
        (r["table"], r["row"], r["column"]) for r in cells)]
    exceptions = [c for c in relevant if not c["centre_glyph_agreement"]]
    assert len(relevant) == 87
    assert {(c["row"], c["column"]) for c in exceptions} == {(2, 6), (4, 6)}
    assert all(c["centre_header_agreement"] for c in relevant)
    detail = checked(OUT / "construction-economics-english-detail-01.png")
    save(checked(OUT / "construction-economics-english-71-reviewed-geometry-01.json"), {
        "at": datetime.now(UTC), "source_id": SOURCE, "original_sha256": source["original_sha256"],
        "image": page["image"], "image_sha256": page["image_sha256"],
        "geometry": page["evidence"], "geometry_sha256": page["evidence_sha256"],
        "programme_printed": "K71KTE", "cohort": "K71", "semesters_admitted": list(range(1, 10)),
        "cells": cells, "edges": edges, "printed_total": total,
        "legend_objects": [shapes[n] for n in (293, 303, 304, 305, 306)],
        "native_glyph_crosscheck": {"file": str(centres_path.relative_to(ROOT)),
            "sha256": sha(centres_path.read_bytes()), "cells": 87, "centre_matches": 85,
            "header_matches": 87, "exceptions": exceptions,
            "resolution": "PDFium character772 is the period in upper ngh.vụ; its ink centre crosses the row border. Original enlarged rendering and native text sequence retain that period in361456, with no added period before361457. Both exact native cell texts retained.",
            "detail_image": str(detail.relative_to(ROOT)), "detail_sha256": sha(detail.read_bytes())},
        "duplicate_code_cells": [c["id"] for c in duplicate],
        "reviewer": "coding agent technical visual transcription; no official HUCE approval claimed",
        "method": "Read whole original rendering, all87 course/placeholder cells and nine semester headers. Checked seven prerequisites including four bent paths, seven double-headed corequisites and the printed legend against exact native objects. Detailed upper/lower semester6 cells inspected separately for glyph overhang.",
        "notes": ["Preserve literal Đai số TT, GiảI tích1, block1/Block2 wording, abbreviations, leading zeroes and printed placement. No silent spelling repair or interpretation of block rules.",
            "511802 is printed twice in semester8 with two different names. Preserve both cells; no unique name/credit lookup from this code. The corequisite511802↔511803 is bound to the lower Tổ chức triển khai cell only.",
            "430101/430102/430103 each explicitly print1 credit.4801xx remains an unresolved defence placeholder with8 printed separately from its1,2,3,4 name.",
            "Keep190TC and all printed exclusions. Do not sum values, infer absent prerequisite links, personal eligibility or later amendments."],
        "full_source_review_complete": True, "source_semantics_resolved": False, "serving_scope_expanded": False})
    print({"cells": len(cells), "semesters": 9, "edges": len(edges), "glyph_exceptions_visually_resolved": 2, "activated": False})


if __name__ == "__main__":
    main()
