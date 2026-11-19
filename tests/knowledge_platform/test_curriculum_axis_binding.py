import json
from pathlib import Path

import pytest

from campus247.application.knowledge.curriculum_geometry import assert_axis_line_binding, geometry_scopes
from campus247.application.knowledge.platform_models import PlatformError

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "infra/local/huce-completion-20261025-02"


def test_prior_neighbor_assignment_is_rejected_and_the_new_version_withholds_that_edge():
    plan = json.loads((ROOT / "infra/local/huce-corpus-completion-20261024-01/candidate-plan-22.json").read_text(encoding="utf-8"))
    entry = next(e for e in plan["sources"] if e["source_id"] == "0ee58db3-9d84-70cb-86ee-168961dd5732")
    old = json.loads((ROOT / entry["candidate"]).read_text(encoding="utf-8"))
    with pytest.raises(PlatformError, match="CURRICULUM_EDGE_AXIS"):
        geometry_scopes(old, old["extracted"])
    new = json.loads((OUT / "environment-71-boundary-correction-geometry-candidate-01.json").read_text(encoding="utf-8"))
    caps, _ = geometry_scopes(new, new["extracted"])
    assert caps["relation_types"] == ["COREQUISITE", "PREREQUISITE"]
    witness = new["extracted"]["curriculum_geometry"]
    by_id = {c["id"]: c["course_codes"] for c in witness["cells"]}
    assert len(witness["edges"]) == 22
    assert not any(by_id[e["from_cell"]] == ["098813"] and by_id[e["to_cell"]] in [["097704"], ["097712"]]
        for e in witness["edges"])


def shapes():
    return [{"x0": 8, "top": 4, "x1": 9, "bottom": 16, "pts": [[8, 4], [9, 4], [9, 16], [8, 16]]},
        {"x0": 5.5, "top": 15, "x1": 11.5, "bottom": 20, "pts": [[5.5, 15], [11.5, 15], [8.5, 20], [5.5, 15]]}]


def test_plain_arrow_requires_axis_and_direction_without_reinterpreting_the_legend():
    top, below = {"bbox": [0, 0, 12, 10]}, {"bbox": [0, 10, 12, 25]}
    edge = {"kind": "PREREQUISITE", "arrow_objects": shapes()}
    assert_axis_line_binding(edge, top, below)
    with pytest.raises(PlatformError, match="CURRICULUM_EDGE_AXIS"):
        assert_axis_line_binding(edge, top, {"bbox": [15, 10, 27, 25]})
    with pytest.raises(PlatformError, match="CURRICULUM_EDGE_DIRECTION"):
        assert_axis_line_binding(edge, below, top)
    with pytest.raises(PlatformError, match="CURRICULUM_EDGE_KIND"):
        assert_axis_line_binding({**edge, "kind": "COREQUISITE"}, top, below)
