"""Resolve nested-cell membership and preserve the actually rendered số2 label."""
import re
from datetime import UTC, datetime

from continue_huce_completion_20261025 import OUT, ROOT, read, save, sha
from review_huce_network_geometry_second import NETWORK


def compact(text):
    return re.sub(r"\s+", "", text)


def main():
    previous_file = OUT / "network-71-reviewed-geometry-01.json"
    review = read(previous_file)
    source = next(s for s in read(OUT / "curriculum-cell-candidates-01.json")["sources"] if s["source_id"] == NETWORK)
    page = source["pages"][0]
    detail = OUT / "network-semester8-cell-detail-01.png"
    assert sha((ROOT / page["image"]).read_bytes()) == page["image_sha256"]
    assert sha((ROOT / page["evidence"]).read_bytes()) == page["evidence_sha256"]
    cells = []
    for c in page["cells"]:
        if c["text"].isdigit():
            continue
        assert c["course_code_credit_pairs"] or "48011x" in c["text"]
        cells.append({"id": f"p1t{c['table']}r{c['row']}c{c['column']}", "page": 1,
            **{k: c[k] for k in ("table", "row", "column", "bbox", "text", "semester", "header")},
            "text_sha256": sha(c["text"].encode()), "semester_header": c["header"]["text"],
            "course_codes": [code for code, _ in c["course_code_credit_pairs"]], "unlabelled_credits": False})
    nested = []
    for child in page["ambiguous_course_cells"]:
        x0, top, x1, bottom = child["bbox"]
        containers = [c for c in cells if c["semester"] == 8 and c["bbox"][0] <= x0 and x1 <= c["bbox"][2]
            and c["bbox"][1] <= top and bottom <= c["bbox"][3] and compact(child["text"]) in compact(c["text"])]
        assert len(containers) == 1
        nested.append({"nested_native_cell": child, "admitted_outer_cell_id": containers[0]["id"], "counted_separately": False})
    assert len(cells) == 68 and len(nested) == 4
    assert any("Bảo vệ bản quyền số2" in c["text"] for c in cells)
    review.update(at=datetime.now(UTC), cells=cells, semesters_admitted=list(range(1, 10)),
        deferred_semester_8_cells=[], deferred_nested_table_cells=[], nested_cell_membership=nested,
        previous_review_file=str(previous_file.relative_to(ROOT)), previous_review_sha256=sha(previous_file.read_bytes()),
        detail_image={"file": str(detail.relative_to(ROOT)), "sha256": sha(detail.read_bytes()),
            "original_image": page["image"], "original_image_sha256": page["image_sha256"],
            "crop_pdf_bbox": [595, 245, 684, 380], "observation": "Agent inspected the enlarged original rendering: số2 is printed on the same baseline. Preserve it verbatim."},
        method="Full original image and enlarged semester8 rendering read. All68 outer cells and14 direct arrows reconciled. Four nested cells are contained in their semester8 outer groups and are not additional courses.",
        notes=["All nine semester columns and14 directly printed prerequisite links; no absent corequisite inferred.",
            "Preserve the actually rendered Bảo vệ bản quyền số2 label. Do not remove its2 or reinterpret it as credits/a footnote.",
            "467710 is printed in both Chuyên đề tổng hợp and Bảo vệ bản quyền số2 cells. Preserve both when listing the source; reject a unique code/name or code-credit lookup for that repeated code.",
            "Elective1 prints4TC, with option values2 and3. Elective2 prints4TC, with option values2 and2. Do not infer a selection requirement, repair values or sum them into a programme requirement.",
            "Retain physical-education codes430120,420102,430103 and the literal Giáo dục TC1/TC2/TC3 names without silent correction or abbreviation expansion.",
            "48011x remains an unresolved printed defence-code placeholder. Keep its8 separate from the1,2,3,4 name.",
            "Retain the printed180TC total and exclusions. Separate elective catalogue/block rules/personal eligibility are not supplied."],
        full_source_review_complete=True, source_semantics_resolved=False, serving_scope_expanded=False)
    save(OUT / "network-71-reviewed-geometry-02.json", review)
    print({"cells": len(cells), "semesters": 9, "edges": len(review["edges"]), "nested_cells_reconciled": len(nested), "repeated_code_unresolved": "467710"})


if __name__ == "__main__":
    main()
