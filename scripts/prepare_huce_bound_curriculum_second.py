"""Prepare a single-page candidate only from a retained source-specific review."""
import argparse
import re
from datetime import UTC, datetime

from knowledge_platform import ROOT
from continue_huce_completion_20261025 import CORPUS, OUT, checked, read, save, sha
from campus247.application.knowledge.platform_models import digest
from campus247.application.knowledge.source_snapshot import validate_snapshot


def prepare(review_file, base, number, label, include_plan=None, include_source=None, elective_cells=False, release_base=None):
    review_file = checked(ROOT / review_file); review = read(review_file)
    assert review["reviewer"] == "coding agent technical visual transcription; no official HUCE approval claimed"
    assert sha(checked(ROOT / review["image"]).read_bytes()) == review["image_sha256"]
    assert sha(checked(ROOT / review["geometry"]).read_bytes()) == review["geometry_sha256"]
    geometry = read(ROOT / review["geometry"])
    assert review["programme_printed"] in geometry["text"] and review["printed_total"] in geometry["text"]
    plan = read(CORPUS / f"candidate-plan-{base}.json")
    entry = next(e for e in plan["sources"] if e["source_id"] == review["source_id"])
    assert sha(checked(ROOT / entry["candidate"]).read_bytes()) == entry["candidate_sha256"]
    candidate = read(ROOT / entry["candidate"])
    assert candidate["original_sha256"] == review["original_sha256"] and candidate["applicability"]["cohorts"] == [review["cohort"]]
    previous = read(CORPUS / f"candidate-release-{release_base or base}.json")
    candidate["previous_version_id"] = next(m["version_id"] for m in previous["members"] if m["source_id"] == review["source_id"])
    cells, edges = review["cells"], review["edges"]
    semesters = review.get("semesters_admitted")
    if semesters is None:
        assert review.get("full_source_review_complete") is True
        semesters = sorted({c["semester"] for c in cells})
    groups = [{"id": f"s{n}", "semester": n, "cell_ids": [c["id"] for c in cells if c["semester"] == n]}
        for n in semesters]
    assert all(g["cell_ids"] for g in groups)
    witness = {"schema": "reviewed-curriculum-geometry-v1", "reviewed": True, "source_id": review["source_id"],
        "original_sha256": review["original_sha256"], "programme_code": review["programme_printed"], "cells": cells, "edges": edges,
        "geometry_pages": {"1": geometry}, "image_sha256": review["image_sha256"], "semester_groups": groups,
        "ambiguous_course_cells": [], "printed_total": review["printed_total"],
        "review_file": str(review_file.relative_to(ROOT)), "review_sha256": sha(review_file.read_bytes())}
    blocks = []
    def add(text, section, kind, identifier):
        blocks.append({"block_id": str(len(blocks)), "page": 1, "text": text, "section": section,
            "geometry_binding": {"kind": kind, "id": identifier}})
    for group in groups:
        roster = [c for c in cells if c["id"] in group["cell_ids"]]
        add(review["programme_printed"] + "\n" + roster[0]["semester_header"] + "\n" + "\n\n".join(c["text"] for c in roster) + "\n" + review["printed_total"],
            f"{review['programme_printed']} — Học kỳ {group['semester']} — các ô đã đối chiếu — PDF 1", "semester", group["id"])
    if elective_cells:
        for cell in cells:
            if re.search(r"tự\s+chọn", cell["text"], re.I) and len(cell["course_codes"]) > 1:
                add(review["programme_printed"] + "\n" + cell["semester_header"] + "\n" + cell["text"],
                    f"{review['programme_printed']} — ô nhóm tự chọn — Học kỳ {cell['semester']} — PDF 1", "cell", cell["id"])
    by_id = {c["id"]: c for c in cells}
    for edge in edges:
        origin, target = by_id[edge["from_cell"]], by_id[edge["to_cell"]]
        relation, symbol = ("Học phần tiên quyết", "→") if edge["kind"] == "PREREQUISITE" else ("Học phần song hành", "↔")
        add(review["programme_printed"] + "\n" + relation + ":\n" + origin["text"] + "\n" + symbol + "\n" + target["text"],
            f"{review['programme_printed']} — {relation} — {origin['course_codes'][0]} {symbol} {target['course_codes'][0]} — PDF 1", "edge", edge["id"])
    add(review["programme_printed"] + "\n" + review["printed_total"], review["programme_printed"] + " — tổng in sẵn — PDF 1", "total", "overall")
    at = datetime.now(UTC)
    candidate["extracted"] = {"original_sha256": review["original_sha256"], "blocks": blocks, "curriculum_geometry": witness,
        "publisher_witness": candidate["extracted"]["publisher_witness"], "review_witness": {
            "review": str(review_file.relative_to(ROOT)), "review_sha256": sha(review_file.read_bytes()), "limitations": review["notes"]}}
    candidate["pages"] = [{"block_id": b["block_id"], "page": 1, "char_start": 0, "char_end": len(b["text"]),
        "text": b["text"], "text_sha256": sha(b["text"].encode()), "section": b["section"]} for b in blocks]
    candidate["applicability"].update(reviewed_at=at.isoformat(), geometry_witness_sha256=digest(witness), limitations=review["notes"])
    validate_snapshot(candidate, candidate["extracted"], original_sha256=candidate["original_sha256"], effective_from=at)
    destination = checked(OUT / f"{label}-geometry-candidate-01.json"); save(destination, candidate)
    entry.update(candidate=str(destination.relative_to(ROOT)), candidate_sha256=sha(destination.read_bytes()), parents=len(blocks))
    if include_plan:
        extra = next(e for e in read(CORPUS / f"candidate-plan-{include_plan}.json")["sources"] if e["source_id"] == include_source)
        assert extra["source_id"] != review["source_id"] and sha(checked(ROOT / extra["candidate"]).read_bytes()) == extra["candidate_sha256"]
        plan["sources"] = [extra if e["source_id"] == include_source else e for e in plan["sources"]]
    save(CORPUS / f"candidate-plan-{number}.json", plan)
    print({"source": review["source_id"], "cells": len(cells), "edges": len(edges), "semesters": len(groups), "plan": number, "activated": False})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--review", required=True)
    parser.add_argument("--base", required=True); parser.add_argument("--plan", required=True); parser.add_argument("--label", required=True)
    parser.add_argument("--include-plan"); parser.add_argument("--include-source")
    parser.add_argument("--release-base", help="Retained predecessor release when composing several unbuilt candidate plans")
    parser.add_argument("--elective-cells", action="store_true")
    args = parser.parse_args()
    assert re.fullmatch(r"\d{2}", args.base) and re.fullmatch(r"\d{2}", args.plan) and args.base != args.plan
    assert re.fullmatch(r"[a-z][a-z0-9-]{1,50}", args.label)
    assert bool(args.include_plan) == bool(args.include_source)
    if args.include_plan:
        assert re.fullmatch(r"\d{2}", args.include_plan) and re.fullmatch(r"[0-9a-f-]{36}", args.include_source)
    if args.release_base:
        assert re.fullmatch(r"\d{2}", args.release_base)
    prepare(args.review, args.base, args.plan, args.label, args.include_plan, args.include_source, args.elective_cells, args.release_base)
