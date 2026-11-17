"""Bind the reviewed K71 multimedia cells and graph to typed serving capabilities."""
import argparse
from datetime import UTC, datetime

from knowledge_platform import ROOT
from continue_huce_completion_20261025 import CORPUS, OUT, read, save, sha
from review_huce_curriculum_geometry import MULTIMEDIA
from campus247.application.knowledge.platform_models import digest
from campus247.application.knowledge.source_snapshot import validate_snapshot


def main():
    review_path = OUT / "multimedia-71-reviewed-geometry-01.json"
    review = read(review_path); geometry = read(ROOT / review["geometry"])
    assert sha((ROOT/review["geometry"]).read_bytes()) == review["geometry_sha256"]
    assert sha((ROOT/review["image"]).read_bytes()) == review["image_sha256"]
    plan = read(CORPUS / "candidate-plan-10.json")
    entry = next(e for e in plan["sources"] if e["source_id"] == MULTIMEDIA)
    candidate = read(ROOT / entry["candidate"])
    assert sha((ROOT/entry["candidate"]).read_bytes()) == entry["candidate_sha256"]
    assert review["original_sha256"] == candidate["original_sha256"]
    old = read(CORPUS / "candidate-release-10.json")
    candidate["previous_version_id"] = next(e["version_id"] for e in old["members"] if e["source_id"] == MULTIMEDIA)
    cells = []
    for cell in review["cells"]:
        # Exclude plain numeric footer cells. They have no independent printed
        # unit; the printed overall total is retained separately, never summed.
        if not cell["course_code_credit_pairs"] and not any(s in cell["text"] for s in ("GD thể chất", "Giáo dục quốc phòng")):
            continue
        cells.append({"id": f"p1t{cell['table']}r{cell['row']}c{cell['column']}", "page": 1,
            **{k: cell[k] for k in ("table", "row", "column", "bbox", "text", "text_sha256", "semester", "header")},
            "semester_header": cell["header"]["text"],
            "course_codes": [code for code, _ in cell["course_code_credit_pairs"]],
            "unlabelled_credits": not bool(cell["course_code_credit_pairs"])})
    by_code = {code: c for c in cells for code in c["course_codes"]}
    edges = [{"id": f"e{i}", "page": e["page"], "kind": e["kind"],
        "from_cell": by_code[e["from_course"]]["id"], "to_cell": by_code[e["to_course"]]["id"],
        "arrow_objects": e["arrowhead_objects"], "legend_verified": True}
        for i, e in enumerate(review["edges"])]
    witness = {"schema": "reviewed-curriculum-geometry-v1", "reviewed": True,
        "source_id": MULTIMEDIA, "original_sha256": review["original_sha256"], "programme_code": "71CNDPT",
        "review_file": str(review_path.relative_to(ROOT)), "review_sha256": sha(review_path.read_bytes()),
        "geometry_pages": {"1": geometry}, "image_sha256": review["image_sha256"],
        "cells": cells, "edges": edges, "ambiguous_course_cells": [], "printed_total": review["printed_total"]}
    blocks = []
    def add(text, section, kind, identifier):
        blocks.append({"block_id": str(len(blocks)), "page": 1, "text": text, "section": section,
            "geometry_binding": {"kind": kind, "id": identifier}})
    for cell in cells:
        add("71CNDPT\n"+cell["semester_header"]+"\n"+cell["text"],
            f"71CNDPT — {cell['semester_header']} — ô hàng {cell['row']} cột {cell['column']} — PDF 1", "cell", cell["id"])
    by_id = {c["id"]: c for c in cells}
    for edge in edges:
        origin, target = by_id[edge["from_cell"]], by_id[edge["to_cell"]]
        label, symbol = ("Học phần tiên quyết", "→") if edge["kind"] == "PREREQUISITE" else ("Học phần song hành", "↔")
        add("71CNDPT\n"+label+":\n"+origin["text"]+"\n"+symbol+"\n"+target["text"],
            f"71CNDPT — {label} — {origin['course_codes'][0]} {symbol} {target['course_codes'][0]} — PDF 1", "edge", edge["id"])
    add("71CNDPT\n"+review["printed_total"], "71CNDPT — dòng tổng nguyên văn — PDF 1", "total", "overall")
    at = datetime.now(UTC)
    candidate["extracted"] = {"original_sha256": candidate["original_sha256"], "blocks": blocks,
        "curriculum_geometry": witness, "review_witness": {"review": str(review_path.relative_to(ROOT)),
            "review_sha256": sha(review_path.read_bytes()), "full_original_page_read": True},
        "publisher_witness": candidate["extracted"]["publisher_witness"]}
    candidate["applicability"].update(reviewed_at=at.isoformat(), geometry_witness_sha256=digest(witness),
        limitations=["Only this retained K71 / 71CNDPT page and its reviewed cells and 13 links; no unprinted elective selection count or missing separate elective catalogue inferred",
            "Numbers in the names of unlabelled PE/defence cells are not credit assertions; no derived overall sum"])
    candidate["pages"] = [{"block_id": b["block_id"], "page": 1, "char_start": 0, "char_end": len(b["text"]),
        "text": b["text"], "text_sha256": sha(b["text"].encode()), "section": b["section"]} for b in blocks]
    validate_snapshot(candidate, candidate["extracted"], original_sha256=candidate["original_sha256"], effective_from=at)
    target = OUT / "multimedia-geometry-candidate-01.json"; save(target, candidate)
    entry.update(candidate=str(target.relative_to(ROOT)), candidate_sha256=sha(target.read_bytes()), parents=len(blocks))
    save(CORPUS / "candidate-plan-11.json", plan)
    print({"cells": len(cells), "edges": len(edges), "parents": len(blocks), "activated": False})


def with_unit_context():
    plan = read(CORPUS / "candidate-plan-11.json")
    entry = next(e for e in plan["sources"] if e["source_id"] == MULTIMEDIA)
    candidate = read(ROOT / entry["candidate"])
    witness = candidate["extracted"]["curriculum_geometry"]
    witness["include_printed_unit_context"] = True
    for block in candidate["extracted"]["blocks"]:
        if block["geometry_binding"]["kind"] == "cell":
            block["text"] += "\n" + witness["printed_total"]
    candidate["applicability"]["geometry_witness_sha256"] = digest(witness)
    candidate["pages"] = [{**p, "char_end": len(b["text"]), "text": b["text"], "text_sha256": sha(b["text"].encode())}
        for p, b in zip(candidate["pages"], candidate["extracted"]["blocks"], strict=True)]
    validate_snapshot(candidate, candidate["extracted"], original_sha256=candidate["original_sha256"],
        effective_from=datetime.fromisoformat(candidate["applicability"]["reviewed_at"]))
    target = OUT / "multimedia-geometry-candidate-02.json"; save(target, candidate)
    entry.update(candidate=str(target.relative_to(ROOT)), candidate_sha256=sha(target.read_bytes()))
    save(CORPUS / "candidate-plan-12.json", plan)
    print({"plan": "12", "printed_total_context_retained_without_derived_sum": True})


def semester_parents():
    plan = read(CORPUS / "candidate-plan-12.json")
    entry = next(e for e in plan["sources"] if e["source_id"] == MULTIMEDIA)
    candidate = read(ROOT / entry["candidate"])
    release = read(CORPUS / "candidate-release-12.json")
    candidate["previous_version_id"] = next(r["version_id"] for r in release["members"] if r["source_id"] == MULTIMEDIA)
    witness = candidate["extracted"]["curriculum_geometry"]
    groups = [{"id": f"s{semester}", "semester": semester,
        "cell_ids": [c["id"] for c in witness["cells"] if c["semester"] == semester]} for semester in range(1, 8)]
    witness["semester_groups"] = groups
    blocks = []
    for group in groups:
        cells = [c for c in witness["cells"] if c["id"] in group["cell_ids"]]
        blocks.append({"block_id": str(len(blocks)), "page": 1, "section": f"71CNDPT — Học kỳ {group['semester']} — toàn bộ ô đã đối chiếu — PDF 1",
            "text": "71CNDPT\n"+cells[0]["semester_header"]+"\n"+"\n\n".join(c["text"] for c in cells)+"\n"+witness["printed_total"],
            "geometry_binding": {"kind": "semester", "id": group["id"]}})
    for block in candidate["extracted"]["blocks"]:
        if block["geometry_binding"]["kind"] != "cell":
            blocks.append({**block, "block_id": str(len(blocks))})
    at = datetime.now(UTC)
    candidate["extracted"]["blocks"] = blocks
    candidate["applicability"].update(reviewed_at=at.isoformat(), geometry_witness_sha256=digest(witness))
    candidate["pages"] = [{"block_id": b["block_id"], "page": 1, "char_start": 0, "char_end": len(b["text"]),
        "text": b["text"], "text_sha256": sha(b["text"].encode()), "section": b["section"]} for b in blocks]
    validate_snapshot(candidate, candidate["extracted"], original_sha256=candidate["original_sha256"], effective_from=at)
    target = OUT / "multimedia-geometry-candidate-03.json"; save(target, candidate)
    entry.update(candidate=str(target.relative_to(ROOT)), candidate_sha256=sha(target.read_bytes()), parents=len(blocks))
    save(CORPUS / "candidate-plan-13.json", plan)
    print({"semester_parents": 7, "relation_parents": 13, "printed_total_parent": 1, "plan": "13"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--unit-context", action="store_true")
    parser.add_argument("--semester-parents", action="store_true")
    args = parser.parse_args()
    semester_parents() if args.semester_parents else with_unit_context() if args.unit_context else main()
