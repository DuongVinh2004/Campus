"""Bind the individually inspected K71KM page, without inferring extra rules."""
from datetime import UTC, datetime

from knowledge_platform import ROOT
from continue_huce_completion_20261025 import CORPUS, OUT, read, save, sha
from campus247.application.knowledge.platform_models import digest
from campus247.application.knowledge.source_snapshot import validate_snapshot

MECHANICAL = "1442730c-ae63-7121-821a-7a7037cbaa96"

# Read against the full original page and its printed legend. Include both
# shaft and arrowhead objects; objects 492, 507-510 are legend, not courses.
LINKS = [
    ("PREREQUISITE", "010213", "010212", [494, 512]),
    ("PREREQUISITE", "260402", "268809", [493, 511]),
    ("PREREQUISITE", "428801", "428802", [497, 518]),
    ("PREREQUISITE", "268803", "268806", [495, 516]),
    ("PREREQUISITE", "268806", "281207", [496, 517]),
    ("PREREQUISITE", "268870", "281306", [498, 528]),
    ("PREREQUISITE", "250101", "250102", [499, 529]),
    ("PREREQUISITE", "300103", "261206", [500, 533]),
    ("PREREQUISITE", "390121", "396602", [501, 534]),
    ("PREREQUISITE", "396602", "400101", [502, 535]),
    ("PREREQUISITE", "446601", "446602", [505, 541]),
    ("PREREQUISITE", "446602", "446603", [503, 536]),
    ("PREREQUISITE", "446603", "446604", [504, 537]),
    ("PREREQUISITE", "060223", "060222", [506, 542]),
    ("COREQUISITE", "268806", "268870", [513, 514, 515]),
    ("COREQUISITE", "281207", "281306", [525, 526, 527]),
    ("COREQUISITE", "281209", "281307", [519, 520, 521]),
    ("COREQUISITE", "281210", "281308", [522, 523, 524]),
    ("COREQUISITE", "250102", "250103", [530, 531, 532]),
    ("COREQUISITE", "240131", "240102", [538, 539, 540]),
]


def main():
    source = next(s for s in read(OUT / "curriculum-cell-candidates-01.json")["sources"]
        if s["source_id"] == MECHANICAL)
    assert len(source["pages"]) == 1
    page = source["pages"][0]
    geometry = read(ROOT / page["evidence"])
    assert sha((ROOT / page["evidence"]).read_bytes()) == page["evidence_sha256"]
    assert sha((ROOT / page["image"]).read_bytes()) == page["image_sha256"]
    assert not page["ambiguous_course_cells"]
    total = "Tổng: 180TC (Không tính HP Giáo dục thể chất và Giáo dục quốc phòng)"
    assert total in geometry["text"] and "(K71KM)" in geometry["text"]
    assert "Học phần tiên quyết Học phần; Học phần song hành." in geometry["text"]
    cells = []
    for cell in page["cells"]:
        # Only plain footer totals are excluded. All course cells were read
        # on the image, including the three explicit 1TC physical-ed cells.
        if not cell["course_code_credit_pairs"] and "thể chất" not in cell["text"]:
            assert cell["text"].isdigit()
            continue
        cells.append({"id": f"p1t{cell['table']}r{cell['row']}c{cell['column']}", "page": 1,
            **{k: cell[k] for k in ("table", "row", "column", "bbox", "text", "semester", "header")},
            "text_sha256": sha(cell["text"].encode()), "semester_header": cell["header"]["text"],
            "course_codes": [code for code, _ in cell["course_code_credit_pairs"]],
            "unlabelled_credits": False})
    by_code = {code: cell for cell in cells for code in cell["course_codes"]}
    shapes = {s["object_index"]: s for s in geometry["shapes"]}
    edges = [{"id": f"e{i}", "page": 1, "kind": kind, "from_cell": by_code[a]["id"],
        "to_cell": by_code[b]["id"], "arrow_objects": [shapes[n] for n in indices], "legend_verified": True}
        for i, (kind, a, b, indices) in enumerate(LINKS)]
    review = {"at": datetime.now(UTC), "source_id": MECHANICAL, "original_sha256": source["original_sha256"],
        "image": page["image"], "image_sha256": page["image_sha256"], "geometry": page["evidence"],
        "geometry_sha256": page["evidence_sha256"], "programme_printed": "K71KM", "cohort": "K71",
        "cells": cells, "edges": edges, "printed_total": total,
        "printed_semester_totals": [19, 19, 19, 22, 22, 21, 21, 20, 18],
        "legend_objects": [shapes[n] for n in [492, 507, 508, 509, 510]],
        "method": "Agent individually compared all course cells, headers, continuous shafts, arrowheads and the printed legend on the full original image; native objects retained",
        "notes": ["Preserve the original 'Thực hành ký thuật cơ khí' and 'Đổi mơi' spellings, abbreviations and BL2 annotation.",
            "PE1/2/3 explicitly print 1TC each. Defence code480101 explicitly prints8; no credit inferred from its1,2,3,4 name.",
            "Keep the printed total and exclusions; do not recompute a required total or interpret BL2.",
            "No invisible prerequisite, transitive path, prior-study rule or personal eligibility asserted."],
        "reviewer": "coding agent technical transcription; no official HUCE approval claimed", "serving_scope_expanded": False}
    review_file = OUT / "mechanical-71-reviewed-geometry-01.json"
    save(review_file, review)
    plan = read(CORPUS / "candidate-plan-13.json")
    entry = next(s for s in plan["sources"] if s["source_id"] == MECHANICAL)
    assert sha((ROOT / entry["candidate"]).read_bytes()) == entry["candidate_sha256"]
    candidate = read(ROOT / entry["candidate"])
    assert candidate["original_sha256"] == source["original_sha256"]
    assert candidate["applicability"]["cohorts"] == ["K71"]
    old = read(CORPUS / "candidate-release-13.json")
    candidate["previous_version_id"] = next(m["version_id"] for m in old["members"] if m["source_id"] == MECHANICAL)
    groups = [{"id": f"s{n}", "semester": n, "cell_ids": [c["id"] for c in cells if c["semester"] == n]}
        for n in range(1, 10)]
    witness = {"schema": "reviewed-curriculum-geometry-v1", "reviewed": True, "source_id": MECHANICAL,
        "original_sha256": source["original_sha256"], "programme_code": "K71KM", "cells": cells, "edges": edges,
        "geometry_pages": {"1": geometry}, "image_sha256": page["image_sha256"], "semester_groups": groups,
        "ambiguous_course_cells": [], "printed_total": total,
        "review_file": str(review_file.relative_to(ROOT)), "review_sha256": sha(review_file.read_bytes())}
    blocks = []
    def add(text, section, kind, identifier):
        blocks.append({"block_id": str(len(blocks)), "page": 1, "text": text, "section": section,
            "geometry_binding": {"kind": kind, "id": identifier}})
    for group in groups:
        roster = [c for c in cells if c["id"] in group["cell_ids"]]
        add("K71KM\n" + roster[0]["semester_header"] + "\n" + "\n\n".join(c["text"] for c in roster) + "\n" + total,
            f"K71KM — Học kỳ {group['semester']} — toàn bộ ô đã đối chiếu — PDF 1", "semester", group["id"])
    by_id = {c["id"]: c for c in cells}
    for edge in edges:
        origin, target = by_id[edge["from_cell"]], by_id[edge["to_cell"]]
        label, symbol = ("Học phần tiên quyết", "→") if edge["kind"] == "PREREQUISITE" else ("Học phần song hành", "↔")
        add("K71KM\n" + label + ":\n" + origin["text"] + "\n" + symbol + "\n" + target["text"],
            f"K71KM — {label} — {origin['course_codes'][0]} {symbol} {target['course_codes'][0]} — PDF 1", "edge", edge["id"])
    add("K71KM\n" + total, "K71KM — dòng tổng nguyên văn — PDF 1", "total", "overall")
    at = datetime.now(UTC)
    candidate["extracted"] = {"original_sha256": source["original_sha256"], "blocks": blocks,
        "curriculum_geometry": witness, "publisher_witness": candidate["extracted"]["publisher_witness"],
        "review_witness": {"review": str(review_file.relative_to(ROOT)), "review_sha256": sha(review_file.read_bytes()),
            "full_original_page_read": True}}
    candidate["pages"] = [{"block_id": b["block_id"], "page": 1, "char_start": 0, "char_end": len(b["text"]),
        "text": b["text"], "text_sha256": sha(b["text"].encode()), "section": b["section"]} for b in blocks]
    candidate["applicability"].update(reviewed_at=at.isoformat(), geometry_witness_sha256=digest(witness),
        limitations=["Only the retained K71KM page, its complete semester cells and20 individually inspected links; no transitive, missing or prior-study rule inferred",
            "Printed credit values and original spellings preserved; BL2 is uninterpreted; no recomputed total or personalized eligibility"])
    validate_snapshot(candidate, candidate["extracted"], original_sha256=source["original_sha256"], effective_from=at)
    destination = OUT / "mechanical-geometry-candidate-01.json"
    save(destination, candidate)
    entry.update(candidate=str(destination.relative_to(ROOT)), candidate_sha256=sha(destination.read_bytes()), parents=len(blocks))
    save(CORPUS / "candidate-plan-14.json", plan)
    print({"cells": len(cells), "links": len(edges), "parents": len(blocks), "plan": "14", "activated": False})


if __name__ == "__main__":
    main()
