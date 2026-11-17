"""Prepare the individually inspected 71MTC page; preserve its unusual labels."""
from datetime import UTC, datetime

from knowledge_platform import ROOT
from continue_huce_completion_20261025 import CORPUS, OUT, read, save, sha
from campus247.application.conversation.followup import normalized_question
from campus247.application.knowledge.platform_models import digest
from campus247.application.knowledge.source_snapshot import validate_snapshot

ENVIRONMENT = "0ee58db3-9d84-70cb-86ee-168961dd5732"
LINKS = [
    ("PREREQUISITE", "428801", "428802", [380, 404]),
    ("PREREQUISITE", "446601", "446602", [377, 401]),
    ("PREREQUISITE", "446602", "446603", [378, 402]),
    ("PREREQUISITE", "446603", "446604", [379, 403]),
    ("PREREQUISITE", "250101", "250102", [394, 428]),
    ("PREREQUISITE", "250102", "118805", [429, 430]),
    ("PREREQUISITE", "138806", "068803", [393, 427]),
    ("PREREQUISITE", "068803", "038805", [392, 426]),
    ("PREREQUISITE", "158801", "138806", [417, 418]),
    ("PREREQUISITE", "098802", "088808", [386, 416]),
    ("PREREQUISITE", "098802", "098809", [407, 408]),
    ("PREREQUISITE", "390121", "398803", [390, 423]),
    ("PREREQUISITE", "240102", "248803", [388, 421]),
    ("PREREQUISITE", "198802", "088824", [389, 422]),
    ("PREREQUISITE", "098813", "097704", [383, 411]),
    ("COREQUISITE", "250101", "250103", [384, 412, 413]),
    ("COREQUISITE", "250102", "259904", [385, 414, 415]),
    ("COREQUISITE", "240102", "240131", [395, 431, 432]),
    ("COREQUISITE", "088808", "088809", [381, 405, 406]),
    ("COREQUISITE", "098809", "098810", [387, 419, 420]),
    ("COREQUISITE", "108818", "108819", [391, 424, 425]),
    ("COREQUISITE", "098813", "098814", [382, 409, 410]),
    ("COREQUISITE", "088824", "088825", [396, 433, 434]),
]


def main():
    source = next(s for s in read(OUT / "curriculum-cell-candidates-01.json")["sources"] if s["source_id"] == ENVIRONMENT)
    assert len(source["pages"]) == 1
    page = source["pages"][0]; geometry = read(ROOT / page["evidence"])
    assert sha((ROOT / page["image"]).read_bytes()) == page["image_sha256"]
    assert sha((ROOT / page["evidence"]).read_bytes()) == page["evidence_sha256"]
    assert not page["ambiguous_course_cells"]
    total = "Tổng: 180TC (không tính HP Giáo dục thể chất và Giáo dục quốc phòng)"
    assert total in geometry["text"] and "71MTC" in geometry["text"]
    assert "Học phần tiên quyết; Học phần song hành; Học phần tự chọn (xem thêm danh mục học phần tự chọn)." in geometry["text"]
    cells = []
    for cell in page["cells"]:
        normalized = normalized_question(cell["text"])
        physical = "the chat" in normalized
        if not cell["course_code_credit_pairs"] and not physical and "quoc phong" not in normalized:
            assert cell["text"].isdigit()
            continue
        cells.append({"id": f"p1t{cell['table']}r{cell['row']}c{cell['column']}", "page": 1,
            **{k: cell[k] for k in ("table", "row", "column", "bbox", "text", "semester", "header")},
            "text_sha256": sha(cell["text"].encode()), "semester_header": cell["header"]["text"],
            "course_codes": [code for code, _ in cell["course_code_credit_pairs"]], "unlabelled_credits": physical})
    assert len(cells) == 75
    by_code = {code: cell for cell in cells for code in cell["course_codes"]}
    shapes = {s["object_index"]: s for s in geometry["shapes"]}
    edges = [{"id": f"e{i}", "page": 1, "kind": kind, "from_cell": by_code[a]["id"], "to_cell": by_code[b]["id"],
        "arrow_objects": [shapes[n] for n in indices], "legend_verified": True} for i, (kind, a, b, indices) in enumerate(LINKS)]
    review = {"at": datetime.now(UTC), "source_id": ENVIRONMENT, "original_sha256": source["original_sha256"],
        "image": page["image"], "image_sha256": page["image_sha256"], "geometry": page["evidence"],
        "geometry_sha256": page["evidence_sha256"], "programme_printed": "71MTC", "cohort": "K71",
        "cells": cells, "edges": edges, "printed_total": total, "printed_semester_totals": [20, 17, 21, 21, 21, 21, 19, 22, 18],
        "legend_objects": [shapes[n] for n in [374, 375, 397, 398, 399, 400]],
        "elective_area_objects": [shapes[n] for n in [267, 268, 269, 271, 272, 273, 275, 276, 278]],
        "method": "Agent individually read all75 course/group cells, nine headers, 15 directed prerequisite links and8 double-ended links against the original image and printed legend; shafts/heads retained, including three bent/upward links",
        "notes": ["Retain 240102–2 Hoá học đại cương and240131–1 Thực hành Hoá học đại cương exactly as this source prints, without borrowing codes from another chart.",
            "Defence code4801xx is an unresolved printed placeholder, never a known six-digit identifier; its trailing8 is separate from the1,2,3,4 name.",
            "All three GDTC cells have no printed credit values; GD Thế chất2 retains the original spelling.",
            "Semester5 free elective prints3TC and options088812–2,118808–2,108827–3. Do not infer a required selection count or add their credits.",
            "BL1/BL2 notes, abbreviations and native spacing retained; the separate elective catalogue is referenced but not attached here.",
            "No transitive relation, absent-edge negation, prior-study equivalence or personalized eligibility inferred."],
        "reviewer": "coding agent technical transcription; no official HUCE approval claimed", "serving_scope_expanded": False}
    review_file = OUT / "environment-71-reviewed-geometry-01.json"; save(review_file, review)
    # Base strictly on the active K71KM release, excluding unverified STEM drafts.
    plan = read(CORPUS / "candidate-plan-14.json")
    entry = next(e for e in plan["sources"] if e["source_id"] == ENVIRONMENT)
    assert sha((ROOT / entry["candidate"]).read_bytes()) == entry["candidate_sha256"]
    candidate = read(ROOT / entry["candidate"])
    assert candidate["original_sha256"] == source["original_sha256"] and candidate["applicability"]["cohorts"] == ["K71"]
    previous = read(CORPUS / "candidate-release-14.json")
    candidate["previous_version_id"] = next(m["version_id"] for m in previous["members"] if m["source_id"] == ENVIRONMENT)
    groups = [{"id": f"s{n}", "semester": n, "cell_ids": [c["id"] for c in cells if c["semester"] == n]} for n in range(1, 10)]
    witness = {"schema": "reviewed-curriculum-geometry-v1", "reviewed": True, "source_id": ENVIRONMENT,
        "original_sha256": source["original_sha256"], "programme_code": "71MTC", "cells": cells, "edges": edges,
        "geometry_pages": {"1": geometry}, "image_sha256": page["image_sha256"], "semester_groups": groups,
        "ambiguous_course_cells": [], "printed_total": total, "review_file": str(review_file.relative_to(ROOT)), "review_sha256": sha(review_file.read_bytes())}
    blocks = []
    def add(text, section, kind, identifier):
        blocks.append({"block_id": str(len(blocks)), "page": 1, "text": text, "section": section,
            "geometry_binding": {"kind": kind, "id": identifier}})
    for group in groups:
        roster = [c for c in cells if c["id"] in group["cell_ids"]]
        add("71MTC\n" + roster[0]["semester_header"] + "\n" + "\n\n".join(c["text"] for c in roster) + "\n" + total,
            f"71MTC — Học kỳ {group['semester']} — toàn bộ ô đã đối chiếu — PDF 1", "semester", group["id"])
    by_id = {c["id"]: c for c in cells}
    for edge in edges:
        origin, target = by_id[edge["from_cell"]], by_id[edge["to_cell"]]
        label, symbol = ("Học phần tiên quyết", "→") if edge["kind"] == "PREREQUISITE" else ("Học phần song hành", "↔")
        add("71MTC\n" + label + ":\n" + origin["text"] + "\n" + symbol + "\n" + target["text"],
            f"71MTC — {label} — {origin['course_codes'][0]} {symbol} {target['course_codes'][0]} — PDF 1", "edge", edge["id"])
    add("71MTC\n" + total, "71MTC — dòng tổng nguyên văn — PDF 1", "total", "overall")
    at = datetime.now(UTC)
    candidate["extracted"] = {"original_sha256": source["original_sha256"], "blocks": blocks,
        "curriculum_geometry": witness, "publisher_witness": candidate["extracted"]["publisher_witness"],
        "review_witness": {"review": str(review_file.relative_to(ROOT)), "review_sha256": sha(review_file.read_bytes()), "full_original_page_read": True}}
    candidate["pages"] = [{"block_id": b["block_id"], "page": 1, "char_start": 0, "char_end": len(b["text"]),
        "text": b["text"], "text_sha256": sha(b["text"].encode()), "section": b["section"]} for b in blocks]
    candidate["applicability"].update(reviewed_at=at.isoformat(), geometry_witness_sha256=digest(witness), limitations=review["notes"])
    validate_snapshot(candidate, candidate["extracted"], original_sha256=source["original_sha256"], effective_from=at)
    destination = OUT / "environment-geometry-candidate-01.json"; save(destination, candidate)
    entry.update(candidate=str(destination.relative_to(ROOT)), candidate_sha256=sha(destination.read_bytes()), parents=len(blocks))
    save(CORPUS / "candidate-plan-17.json", plan)
    print({"cells": len(cells), "links": len(edges), "parents": len(blocks), "plan": "17", "activated": False})


if __name__ == "__main__":
    main()
