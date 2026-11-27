"""F3.3/F3.4: snapshots, analysis report with dependencies, HTTP access control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "announcements"))
from ann_helpers import person, sid  # noqa: E402

from campus247.application.policy_impact.service import ImpactService, SnapshotStore  # noqa: E402
from campus247.ports.identity import IdentityRole  # noqa: E402
from campus247.presentation.campus_ops import register_ops_errors  # noqa: E402
from campus247.presentation.policy_impact import create_policy_impact_router  # noqa: E402


def row(uid, text, path="Điều 1 > Khoản 1", family="quy_che", version="v1"):
    return {"unit_id": uid, "document_id": "d1", "version_id": version, "doc_family": family, "doc_title": "Quy chế", "path": path, "text": text,
            "scope": {}, "effective_from": None, "effective_until": None}


def make(tmp_path):
    state = {"release": "r1", "rows": [row("a", "Sinh viên nghỉ quá 20% bị điểm F."), row("b", "Học phí nộp trước ngày 15/12/2026.", "Điều 2 > Khoản 1", "hoc_phi")]}
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    (eval_dir / "set.jsonl").write_text(json.dumps({"id": "case-1", "gold_unit_ids": ["a"]}) + "\n" + json.dumps({"id": "case-2", "gold_unit_ids": ["zzz"]}) + "\n", encoding="utf-8")
    svc = ImpactService(SnapshotStore(tmp_path / "snap"), lambda: iter(state["rows"]), lambda: state["release"], report_dir=tmp_path / "rep",
        rules_citing=lambda ids: [{"rule_id": "attendance-requirement", "version": 1, "status": "PUBLISHED", "units": sorted(ids & {"a"})}] if ids & {"a"} else [],
        eval_dir=eval_dir, facts=lambda: [])
    return svc, state


def test_first_release_is_baseline_then_second_lists_changes_and_dependants(tmp_path):
    svc, state = make(tmp_path)
    first = svc.on_new_release()
    assert first["status"] == "BASELINE_ONLY" and svc.snapshots.has("r1")
    assert svc.on_new_release()["status"] == "BASELINE_ONLY"  # same release again: nothing new to compare, no crash
    state["release"] = "r2"
    state["rows"] = [row("a2", "Sinh viên nghỉ quá 30% bị điểm F."), state["rows"][1]]
    result = svc.on_new_release()
    assert result["status"] == "ANALYZED" and result["summary"]["by_status"]["MODIFIED"] == 1
    rep = svc.report("r2")
    [item] = rep["items"]
    assert item["severity"] == "HIGH" and "NUMERIC" in item["labels"] and item["numeric"] == [{"old": "20", "new": "30"}]
    assert rep["dependencies"]["rules"] == [{"rule_id": "attendance-requirement", "version": 1, "status": "PUBLISHED", "units": ["a"]}]
    assert [c["case_id"] for c in rep["dependencies"]["eval_cases"]] == ["case-1"]
    # the report holds counts and unit ids only
    assert "inputs" not in json.dumps(rep) and "subject" not in json.dumps(rep)


def test_snapshot_is_atomic_and_pruned_but_protected_ones_stay(tmp_path):
    store = SnapshotStore(tmp_path / "s")
    for i in range(5):
        store.save(f"r{i}", [row(f"u{i}", "x" * 30)])
    assert not list((tmp_path / "s").glob("*.tmp"))
    assert store.prune(keep=2, protected={"r0"}) == ["r1", "r2"]
    assert set(store.releases()) == {"r0", "r3", "r4"}
    assert store.load("r3")[0].unit_id == "u3"


def client(svc, who):
    app = FastAPI()
    register_ops_errors(app)
    app.include_router(create_policy_impact_router(svc))

    @app.middleware("http")
    async def ident(request, call_next):
        request.state.identity = who
        return await call_next(request)
    return TestClient(app)


def test_http_is_admin_only(tmp_path):
    svc, _ = make(tmp_path)
    assert client(svc, person(sid(1), IdentityRole.STUDENT)).get("/v1/policy-impact/releases").status_code == 403
    assert client(svc, person(sid(1), IdentityRole.STUDENT)).get("/v1/policy-conflicts").status_code == 403
    admin = client(svc, person(sid(2000), IdentityRole.KNOWLEDGE_ADMIN))
    assert admin.post("/v1/policy-impact/snapshot").json()["status"] == "BASELINE_ONLY"
    assert admin.get("/v1/policy-impact/releases").json()["releases"] == ["r1"]
    assert admin.get("/v1/policy-impact/report").json()["status"] == "BASELINE_ONLY"
    assert admin.get("/v1/policy-impact/report?release=nope").status_code == 404
    assert admin.get("/v1/policy-conflicts").json()["count"] == 0
