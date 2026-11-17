"""Extract table-cell candidates; record separately the exact visually reviewed graph."""
import argparse
import re
from datetime import UTC, datetime

from continue_huce_completion_20261025 import OUT, ROOT, read, save, sha

MULTIMEDIA = "02f95519-1cc3-72d6-84fa-acd95957b626"


def table_cells(page):
    result, unresolved = [], []
    for table in page["tables"]:
        headers = [(cell, re.search(r"Học kỳ\s*(\d+)", cell["text"] or "", re.I))
            for row in table["rows"] for cell in row]
        headers = [(cell, int(match[1])) for cell, match in headers if match]
        for row in table["rows"]:
            for cell in row:
                text = cell["text"] or ""
                if not text.strip() or re.search(r"Học kỳ", text, re.I):
                    continue
                # Containment in a unique printed header column is required.
                x0, top, x1, bottom = cell["bbox"]
                matches = [(header, semester) for header, semester in headers
                    if header["bbox"][0] <= x0+1 and x1 <= header["bbox"][2]+1
                    and header["bbox"][3] <= top+1]
                codes = re.findall(r"(?m)^(\d{6})\s*[-–—]\s*(\d{1,2})(?=\s|$)", text)
                entry = {"table": table["index"], **cell, "course_code_credit_pairs": codes,
                    "native_unit_assumed": False, "visually_reviewed": False}
                if len(matches) == 1:
                    header, semester = matches[0]
                    entry.update(semester=semester, header=header)
                    result.append(entry)
                elif codes:
                    unresolved.append({**entry, "reason": "No unique whole-cell containment in a printed semester column"})
    return result, unresolved


def candidates():
    material = read(OUT / "original-geometry-manifest-01.json")
    sources = []
    for source in material["sources"]:
        if source.get("kind") != "COHORT_SNAPSHOT" or source["source_id"] == "c2454951-46ce-7a56-8421-ca4927bf3339":
            continue
        pages = []
        for info in source["pages"]:
            file = ROOT / info["evidence"]; assert sha(file.read_bytes()) == info["sha256"]
            page = read(file); cells, unresolved = table_cells(page)
            pages.append({"page": info["page"], "evidence": info["evidence"], "evidence_sha256": info["sha256"],
                "image": info["image"], "image_sha256": info["image_sha256"], "cells": cells,
                "ambiguous_course_cells": unresolved,
                "course_entries": sum(len(c["course_code_credit_pairs"]) for c in cells),
                "relations_verified": False,
                "needs_visual_review": True})
        sources.append({"source_id": source["source_id"], "title": source["title"],
            "original_sha256": source["original_sha256"], "pages": pages,
            "serving_scope_expanded": False, "category_unchanged": source["category"]})
    save(OUT / "curriculum-cell-candidates-01.json", {"at": datetime.now(UTC), "sources": sources,
        "source_count": len(sources), "course_entries": sum(p["course_entries"] for s in sources for p in s["pages"]),
        "qualification": "Source geometry candidates only. Every cell, unit, elective boundary and arrow still needs its review witness; no admission by automation"})
    print({"curriculum_sources": len(sources), "pages": sum(len(s["pages"]) for s in sources),
        "course_entries": sum(p["course_entries"] for s in sources for p in s["pages"])})


def reviewed_multimedia():
    candidates_file = OUT / "curriculum-cell-candidates-01.json"
    source = next(s for s in read(candidates_file)["sources"] if s["source_id"] == MULTIMEDIA)
    assert len(source["pages"]) == 1
    page = source["pages"][0]; geometry = read(ROOT/page["evidence"])
    assert sha((ROOT/page["image"]).read_bytes()) == page["image_sha256"]
    # All original cells and all 13 in-chart links were individually read on
    # the full original image. Object indexes are retained from pdfplumber.
    links = [
        ("PREREQUISITE", "428801", "428802", [232]),
        ("PREREQUISITE", "446601", "446602", [233]),
        ("PREREQUISITE", "446602", "446603", [234]),
        ("PREREQUISITE", "446603", "446604", [235]),
        ("PREREQUISITE", "531816", "451802", [241]),
        ("PREREQUISITE", "291803", "291804", [242]),
        ("PREREQUISITE", "390121", "396602", [243]),
        ("COREQUISITE", "531819", "531820", [236, 237, 238]),
        ("COREQUISITE", "531826", "531827", [239, 240]),
        ("COREQUISITE", "531831", "531832", [244, 245]),
        ("COREQUISITE", "531829", "531830", [246, 247]),
        ("COREQUISITE", "291804", "291805", [248, 249]),
        ("COREQUISITE", "531812", "531813", [250, 251]),
    ]
    cells = page["cells"]
    courses = {code: cell for cell in cells for code, _ in cell["course_code_credit_pairs"]}
    edges = []
    for kind, origin, target, indices in links:
        assert origin in courses and target in courses
        objects = [s for s in geometry["shapes"] if s["object_index"] in indices]
        assert len(objects) == len(indices)
        edges.append({"kind": kind, "from_course": origin, "to_course": target,
            "direction": "left_to_right" if kind == "PREREQUISITE" else "bidirectional",
            "from_cell": courses[origin], "to_cell": courses[target], "arrowhead_objects": objects,
            "geometry_sha256": page["evidence_sha256"], "page": 1,
            "review_method": "Endpoint cells, visible continuous shaft, arrowhead direction and printed legend read together"})
    for cell in cells:
        cell["visually_reviewed"] = True
    save(OUT / "multimedia-71-reviewed-geometry-01.json", {"at": datetime.now(UTC),
        "source_id": MULTIMEDIA, "original_sha256": source["original_sha256"],
        "page": 1, "image": page["image"], "image_sha256": page["image_sha256"],
        "geometry": page["evidence"], "geometry_sha256": page["evidence_sha256"],
        "programme_printed": "71CNDPT", "cohort": "K71", "semesters": list(range(1, 8)),
        "cells": cells, "ambiguous_course_cells": page["ambiguous_course_cells"], "edges": edges,
        "elective_groups": [{"group": 1, "printed_label": "TỰ CHỌN 1 (2TC)", "semester": 5,
            "courses": ["531833", "531834"], "selection_count_not_inferred": True},
            {"group": 2, "printed_label": "TỰ CHỌN 2 (2TC)", "semester": 6,
            "courses": ["531835", "531836"], "selection_count_not_inferred": True}],
        "printed_semester_totals": [18, 19, 21, 22, 20, 20, 10],
        "printed_total": "Tổng: 130TC (Không tính HP giáo dục thể chất, Giáo dục quốc phòng)",
        "unlabelled_credit_cells": "GD thể chất 1/2/3 and Giáo dục quốc phòng 1,2,3,4 have no credit values printed in these cells; numbers are not credit assertions",
        "retained_abbreviations": True, "original_legend_semantics_verified": True,
        "reviewer": "coding agent, technical visual transcription; no HUCE official approval claimed",
        "serving_scope_expanded": False})
    print({"source": MULTIMEDIA, "reviewed_cells": len(cells), "reviewed_edges": len(edges), "activated": False})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("mode", choices=["candidates", "multimedia-review"])
    mode = parser.parse_args().mode
    candidates() if mode == "candidates" else reviewed_multimedia()
