"""Bind both original elective catalogues, without equating their translations."""
from datetime import UTC, datetime

from knowledge_platform import ROOT
from continue_huce_completion_20261025 import CORPUS, OUT, read, save, sha
from campus247.application.knowledge.platform_models import digest
from campus247.application.knowledge.source_snapshot import validate_snapshot

ECONOMICS = "bc455d2c-2b63-734f-8f60-7796c9635290"


def main():
    source = next(s for s in read(OUT / "curriculum-cell-candidates-01.json")["sources"] if s["source_id"] == ECONOMICS)
    assert len(source["pages"]) == 2
    geometries, groups, blocks = {}, [], []
    for p in source["pages"]:
        assert sha((ROOT / p["image"]).read_bytes()) == p["image_sha256"]
        assert sha((ROOT / p["evidence"]).read_bytes()) == p["evidence_sha256"]
        geometry = read(ROOT / p["evidence"]); geometries[str(p["page"])] = geometry
        table = geometry["tables"][1]; assert len(table["rows"]) == 3
        titles = [c for row in geometry["tables"][0]["rows"] for c in row if c["text"].strip()]
        title = "\n".join(c["text"] for c in titles)
        for n in range(1, 7):
            header = next(c for c in table["rows"][0] if c["column"] == n)
            caption = next(c for c in table["rows"][0] if c["column"] == 0)
            options = [{"row_label": next(c for c in row if c["column"] == 0),
                "value": next(c for c in row if c["column"] == n)} for row in table["rows"][1:]]
            label = ("HPTCBB " if p["page"] == 1 else "REQUIRED ELECTIVE ") + str(n)
            group = {"id": f"p{p['page']}g{n}", "page": p["page"], "table": 1, "column": n,
                "header": header, "caption": caption, "title_cells": titles, "label": label, "options": options}
            groups.append(group)
            text = title + "\n" + caption["text"] + "\n" + header["text"]
            for option in options:
                text += "\n" + option["row_label"]["text"] + "\n" + option["value"]["text"]
            blocks.append({"block_id": str(len(blocks)), "page": p["page"], "text": text,
                "section": f"Kinh tế xây dựng (2025), K71 theo trang công bố — {label} — PDF {p['page']}",
                "geometry_binding": {"kind": "elective", "id": group["id"]}})
    review = {"at": datetime.now(UTC), "source_id": ECONOMICS, "original_sha256": source["original_sha256"],
        "pages": source["pages"], "elective_groups": groups,
        "method": "Agent read the two full original images and individually reconciled every catalogue header/option/row label in both tables against native cells. Diagram paths and rounded course boxes are not admitted by this review.",
        "notes": ["Keep12 language-specific group columns and24 option cells separately; each group retains both options and its printed group credit.",
            "Vietnamese group4 code381801 prints Tiêu chuẩn và định mức xây dựng; English group4 uses an Environmental and Social Impact Assessment title for the same printed code. Preserve both as their own page; no translation equivalence/correction asserted.",
            "No inferred number of required selections, individual option credits, semester membership, missing prerequisite, or total programme sum.",
            "K71 remains bound to the previously verified exact HUCE publisher row; the diagram itself prints2025, not an independent new cohort assertion."],
        "university_approval_claimed": False, "full_diagram_review_complete": False, "serving_scope_expanded": False}
    review_file = OUT / "economics-elective-columns-review-01.json"; save(review_file, review)
    # Combine only the verified MTC candidate with this column repair; retain
    # the old selected STEM notice, excluding both unverified STEM draft releases.
    plan = read(CORPUS / "candidate-plan-17.json")
    entry = next(e for e in plan["sources"] if e["source_id"] == ECONOMICS)
    assert sha((ROOT / entry["candidate"]).read_bytes()) == entry["candidate_sha256"]
    candidate = read(ROOT / entry["candidate"])
    assert candidate["original_sha256"] == source["original_sha256"] and candidate["applicability"]["cohorts"] == ["K71"]
    previous = read(CORPUS / "candidate-release-14.json")
    candidate["previous_version_id"] = next(m["version_id"] for m in previous["members"] if m["source_id"] == ECONOMICS)
    witness = {"schema": "reviewed-curriculum-geometry-v1", "reviewed": True, "source_id": ECONOMICS,
        "original_sha256": source["original_sha256"], "programme_code": "Kinh tế xây dựng (2025)",
        "cells": [], "edges": [], "ambiguous_course_cells": [], "elective_groups": groups,
        "geometry_pages": geometries, "review_file": str(review_file.relative_to(ROOT)), "review_sha256": sha(review_file.read_bytes())}
    candidate["extracted"] = {"original_sha256": source["original_sha256"], "blocks": blocks,
        "curriculum_geometry": witness, "publisher_witness": candidate["extracted"]["publisher_witness"],
        "review_witness": {"review": str(review_file.relative_to(ROOT)), "review_sha256": sha(review_file.read_bytes()),
            "full_original_images_viewed": True, "diagram_course_cells_and_edges_still_unreviewed": True}}
    candidate["pages"] = [{"block_id": b["block_id"], "page": b["page"], "char_start": 0, "char_end": len(b["text"]),
        "text": b["text"], "text_sha256": sha(b["text"].encode()), "section": b["section"]} for b in blocks]
    at = datetime.now(UTC)
    candidate["applicability"].update(reviewed_at=at.isoformat(), geometry_witness_sha256=digest(witness), limitations=review["notes"])
    validate_snapshot(candidate, candidate["extracted"], original_sha256=source["original_sha256"], effective_from=at)
    destination = OUT / "economics-elective-columns-candidate-01.json"; save(destination, candidate)
    entry.update(candidate=str(destination.relative_to(ROOT)), candidate_sha256=sha(destination.read_bytes()), parents=len(blocks))
    save(CORPUS / "candidate-plan-18.json", plan)
    print({"group_columns": len(groups), "option_cells": 24, "parents": len(blocks), "plan": "18", "activated": False})


if __name__ == "__main__":
    main()
