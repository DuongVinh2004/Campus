"""Conservative native-arrow proposals for review; never source admission."""
from datetime import UTC, datetime
import argparse

from continue_huce_completion_20261025 import OUT, ROOT, checked, read, save, sha


def blue(shape):
    color = shape.get("non_stroking_color")
    return isinstance(color, list) and len(color) == 3 and color[2] > color[0] + .15


def head(shape):
    points = list(dict.fromkeys(tuple(round(v, 3) for v in p) for p in shape.get("pts", [])))
    if len(points) != 3:
        return None
    for i, a in enumerate(points):
        b, c = [p for j, p in enumerate(points) if j != i]
        if abs(b[0]-c[0]) <= .5 and abs(b[1]-c[1]) >= 3 and abs(a[0]-(b[0]+c[0])/2) >= 3:
            return {"shape": shape, "tip": a, "base": ((b[0]+c[0])/2, (b[1]+c[1])/2),
                "direction": "right" if a[0] > (b[0]+c[0])/2 else "left"}
        if abs(b[1]-c[1]) <= .5 and abs(b[0]-c[0]) >= 3 and abs(a[1]-(b[1]+c[1])/2) >= 3:
            return {"shape": shape, "tip": a, "base": ((b[0]+c[0])/2, (b[1]+c[1])/2),
                "direction": "down" if a[1] > (b[1]+c[1])/2 else "up"}
    return None


def inside(point, bbox, tolerance=0):
    x, y = point; x0, top, x1, bottom = bbox
    return x0-tolerance <= x <= x1+tolerance and top-tolerance <= y <= bottom+tolerance


def proposals(geometry, cells):
    coded = [c for c in cells if len(c["course_code_credit_pairs"]) == 1 and "\n" in c["text"]]
    shapes = [s for s in geometry["shapes"] if blue(s)]
    heads, shafts = [], []
    for shape in shapes:
        value = head(shape)
        if value:
            heads.append(value); continue
        width, height = shape["x1"]-shape["x0"], shape["bottom"]-shape["top"]
        if min(width, height) <= 2.2 and max(width, height) >= 5 and max(width, height) >= 4*min(width, height):
            shafts.append(shape)
    attached = {s["object_index"]: [] for s in shafts}
    unassigned = []
    for arrow in heads:
        matches = [s for s in shafts if inside(arrow["base"], [s[k] for k in ("x0", "top", "x1", "bottom")], 1.4)]
        if len(matches) == 1:
            attached[matches[0]["object_index"]].append(arrow)
        else:
            unassigned.append(arrow["shape"]["object_index"])
    edges, unresolved = [], []
    bottom = max((c["bbox"][3] for c in cells), default=geometry["height"])
    def cell_for(point):
        matches = [c for c in coded if inside(point, c["bbox"])]
        return matches[0] if len(matches) == 1 else None
    for shaft in shafts:
        arrows = attached[shaft["object_index"]]
        if shaft["top"] > bottom:
            continue  # Below the printed grid: a legend candidate, not a course edge.
        axis = "horizontal" if shaft["x1"]-shaft["x0"] > shaft["bottom"]-shaft["top"] else "vertical"
        points, kind = [], None
        if len(arrows) == 1:
            arrow = arrows[0]; direction = arrow["direction"]
            if axis == "horizontal" and direction in {"left", "right"}:
                tail = (shaft["x0"] if direction == "right" else shaft["x1"], (shaft["top"]+shaft["bottom"])/2)
                points, kind = [tail, arrow["tip"]], "PREREQUISITE"
            elif axis == "vertical" and direction in {"up", "down"}:
                tail = ((shaft["x0"]+shaft["x1"])/2, shaft["top"] if direction == "down" else shaft["bottom"])
                points, kind = [tail, arrow["tip"]], "PREREQUISITE"
        elif len(arrows) == 2 and {a["direction"] for a in arrows} in ({"left", "right"}, {"up", "down"}):
            points, kind = [a["tip"] for a in arrows], "COREQUISITE"
        endpoints = [cell_for(point) for point in points]
        if len(endpoints) != 2 or any(c is None for c in endpoints) or endpoints[0] is endpoints[1]:
            unresolved.append({"shaft": shaft["object_index"], "heads": [a["shape"]["object_index"] for a in arrows],
                "reason": "No unique complete coded cell at both endpoints"}); continue
        a, b = endpoints
        edges.append({"kind": kind, "from_code": a["course_code_credit_pairs"][0][0],
            "to_code": b["course_code_credit_pairs"][0][0], "from_native_cell": [a["table"], a["row"], a["column"]],
            "to_native_cell": [b["table"], b["row"], b["column"]], "endpoint_points": points,
            "arrow_objects": [shaft] + [a["shape"] for a in arrows], "legend_semantics_verified": False,
            "admitted": False})
    used = {s["object_index"] for edge in edges for s in edge["arrow_objects"]}
    remaining = [s["object_index"] for s in shapes if s["top"] <= bottom and s["object_index"] not in used
        and not (s["object_type"] == "rect" and s["x1"]-s["x0"] > 3 and s["bottom"]-s["top"] > 3)]
    return {"proposed_edges": edges, "unresolved_shafts": unresolved, "unassigned_heads": unassigned,
        "remaining_in_grid_blue_objects": remaining, "admission_claimed": False}


def key(kind, a, b):
    return (kind, *sorted([a, b])) if kind == "COREQUISITE" else (kind, a, b)


def main(summarize_only=False):
    folder = checked(OUT / "native-arrow-candidates-01")
    if summarize_only:
        assert folder.is_dir()
    else:
        assert not folder.exists()
        folder.mkdir()
    results = []
    for source in read(OUT / "curriculum-cell-candidates-01.json")["sources"]:
        path = folder / (source["source_id"] + ".json")
        pages = []
        if summarize_only:
            existing = read(path)
            assert existing["source_id"] == source["source_id"] and existing["original_sha256"] == source["original_sha256"]
            pages = existing["pages"]
            assert [p["page"] for p in pages] == [p["page"] for p in source["pages"]]
        else:
            for page in source["pages"]:
                geometry_file = checked(ROOT / page["evidence"])
                assert sha(geometry_file.read_bytes()) == page["evidence_sha256"]
                geometry = read(geometry_file)
                assert sha(checked(ROOT / page["image"]).read_bytes()) == page["image_sha256"]
                pages.append({"page": page["page"], **proposals(geometry, page["cells"])})
            save(path, {"source_id": source["source_id"], "original_sha256": source["original_sha256"], "pages": pages,
                "method": "Native blue triangle/shaft topology and unique complete code-cell endpoint containment. Bent/ambiguous/unmatched objects remain for review. No source admitted; no visual review claimed."})
        results.append({"source_id": source["source_id"], "file": str(path.relative_to(ROOT)), "sha256": sha(path.read_bytes()),
            "proposed": sum(len(p["proposed_edges"]) for p in pages),
            "remaining_objects": sum(len(p["remaining_in_grid_blue_objects"]) for p in pages)})
    checks = []
    for name in ["multimedia-71", "mechanical-71", "environment-71", "network-71", "data-science-71", "building-services-71"]:
        number = "02" if name == "network-71" else "01"
        review = read(OUT / f"{name}-reviewed-geometry-{number}.json")
        by_id = {c["id"]: c for c in review["cells"] if "id" in c}
        expected = {key(e["kind"], e["from_course"], e["to_course"]) if "from_course" in e else
            key(e["kind"], by_id[e["from_cell"]]["course_codes"][0], by_id[e["to_cell"]]["course_codes"][0]) for e in review["edges"]}
        proposal = read(folder / (review["source_id"] + ".json"))
        actual = {key(e["kind"], e["from_code"], e["to_code"]) for p in proposal["pages"] for e in p["proposed_edges"]}
        checks.append({"source_id": review["source_id"], "expected": len(expected), "proposed": len(actual),
            "matched": len(expected & actual), "false_proposals": sorted(actual-expected), "unresolved_expected": sorted(expected-actual)})
    save(OUT / "native-arrow-candidate-summary-01.json", {"at": datetime.now(UTC), "sources": results,
        "gold_review_checks": checks, "proposed_edges": sum(r["proposed"] for r in results),
        "admitted_sources": 0, "all_content_complete": False})
    print({"sources": len(results), "proposals": sum(r["proposed"] for r in results),
        "gold_matches": sum(r["matched"] for r in checks), "gold_false_proposals": sum(len(r["false_proposals"]) for r in checks)})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--summarize-only", action="store_true")
    main(parser.parse_args().summarize_only)
