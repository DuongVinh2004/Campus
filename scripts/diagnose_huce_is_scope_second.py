"""Offline admission diagnostic for retained 71IS geometry; no serving writes."""
from datetime import UTC, datetime

from knowledge_platform import ROOT
from continue_huce_completion_20261025 import OUT, checked, read, save, sha
from campus247.application.knowledge.curriculum_geometry import geometry_allows, geometry_scopes
from campus247.application.knowledge.platform_models import digest


def main():
    review_file = checked(OUT / "is-71-reviewed-geometry-01.json")
    review = read(review_file)
    geometry_file = checked(ROOT / review["geometry"])
    assert sha(geometry_file.read_bytes()) == review["geometry_sha256"]
    assert sha(checked(ROOT / review["image"]).read_bytes()) == review["image_sha256"]
    assert review["serving_scope_expanded"] is False and review["admission_blockers"]
    cells = review["cells"]
    groups = [{"id": f"s{n}", "semester": n, "cell_ids": [c["id"] for c in cells if c["semester"] == n]}
        for n in review["semesters_admitted"]]
    witness = {"schema": "reviewed-curriculum-geometry-v1", "reviewed": True,
        "original_sha256": review["original_sha256"], "programme_code": review["programme_printed"],
        "cells": cells, "edges": review["edges"], "ambiguous_course_cells": [],
        "geometry_pages": {"1": read(geometry_file)}, "semester_groups": groups,
        "printed_total": review["printed_total"]}
    blocks, pages = [], []

    def add(text, kind, identifier):
        block_id = str(len(blocks))
        blocks.append({"block_id": block_id, "page": 1, "text": text,
            "geometry_binding": {"kind": kind, "id": identifier}})
        pages.append({"block_id": block_id, "page": 1, "text": text, "text_sha256": sha(text.encode())})

    for group in groups:
        roster = [c for c in cells if c["id"] in group["cell_ids"]]
        add("71IS\n" + roster[0]["semester_header"] + "\n" + "\n\n".join(c["text"] for c in roster)
            + "\n" + review["printed_total"], "semester", group["id"])
    for cell in cells:
        add("71IS\n" + cell["semester_header"] + "\n" + cell["text"], "cell", cell["id"])
    by_id = {c["id"]: c for c in cells}
    for edge in review["edges"]:
        a, b = by_id[edge["from_cell"]], by_id[edge["to_cell"]]
        label, symbol = ("Học phần tiên quyết", "→") if edge["kind"] == "PREREQUISITE" else ("Học phần song hành", "↔")
        add("71IS\n" + label + ":\n" + a["text"] + "\n" + symbol + "\n" + b["text"], "edge", edge["id"])
    extracted = {"curriculum_geometry": witness, "blocks": blocks}
    rendition = {"original_sha256": review["original_sha256"], "pages": pages,
        "applicability": {"kind": "COHORT_SNAPSHOT", "geometry_witness_sha256": digest(witness)}}
    caps, parents = geometry_scopes(rendition, extracted)
    queries = []
    for number in (1, 2, 3):
        for label in (f"Giáo dục TC{number}", f"Giáo dục thể chất {number}"):
            queries.append((f"Theo 71IS K71, {label} có bao nhiêu tín chỉ?", False))
    for number in (1, 2):
        queries.extend([(f"Theo 71IS K71, tổng tín chỉ nhóm tự chọn {number} là bao nhiêu?", False),
            (f"Theo 71IS K71, nhóm tự chọn {number} phải chọn mấy môn?", False)])
    queries.extend([(f"Theo 71IS K71, mã {code} có tên và tín chỉ gì?", False) for code in ("428802", "462112")])
    queries.extend([("Theo 71IS K71, mã 446601 có bao nhiêu tín chỉ?", True),
        ("Theo 71IS K71, học kỳ 8 gồm những học phần nào?", True),
        ("Theo 71IS K71, 446601 là tiên quyết của 446602 không?", True),
        ("Theo 71IS K71, 428801 là tiên quyết của 428802 không?", False)])
    rows = []
    for question, expected in queries:
        global_allowed = geometry_allows(question, caps)
        allowed = [p["block_id"] for p in pages if geometry_allows(question, parents[p["text_sha256"]])]
        actual = global_allowed and bool(allowed)
        rows.append({"question": question, "expected_allowed": expected, "global_allowed": global_allowed,
            "allowed_parent_ids": allowed, "actual_allowed": actual, "matched_expected": actual == expected})
    output = {"at": datetime.now(UTC), "review": str(review_file.relative_to(ROOT)),
        "review_sha256": sha(review_file.read_bytes()), "geometry_sha256": review["geometry_sha256"],
        "production_geometry_code_sha256": sha(checked(ROOT / "services/api/src/campus247/application/knowledge/curriculum_geometry.py").read_bytes()),
        "geometry_validation_completed": True, "validated_cells": len(cells), "validated_edges": len(review["edges"]),
        "cases": rows, "count": len(rows), "matched_expected": sum(r["matched_expected"] for r in rows),
        "admission_ready": all(r["matched_expected"] for r in rows), "activated": False,
        "method": "In-memory original-bound cell/semester/edge capabilities only. No model, database, source grant, release, runtime file or threshold changed. This is an admission diagnostic, not a passing QA or an official academic interpretation."}
    save(OUT / "is-71-scope-diagnostic-01.json", output)
    print({k: output[k] for k in ("validated_cells", "validated_edges", "count", "matched_expected", "admission_ready", "activated")})
    for row in rows:
        if not row["matched_expected"]:
            print({k: row[k] for k in ("question", "expected_allowed", "actual_allowed")})


if __name__ == "__main__":
    main()
