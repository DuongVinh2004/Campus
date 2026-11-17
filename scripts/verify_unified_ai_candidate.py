"""Read-only candidate verification with exclusive evidence output."""
from __future__ import annotations

import difflib
import hashlib
import json
import sqlite3
import subprocess
import xml.etree.ElementTree as ET

from unified_ai_runtime_probe import ROOT, STATE, checked, http, retain


def database_digest(path):
    result = {}
    with sqlite3.connect(checked(path).as_uri() + "?mode=ro", uri=True) as conn:
        for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
            name = '"' + table.replace('"', '""') + '"'
            rows = conn.execute(f"SELECT * FROM {name}").fetchall()
            data = sorted(json.dumps(r, ensure_ascii=False, default=lambda b:b.hex()) for r in rows)
            result[table] = {"rows": len(rows), "sha256": hashlib.sha256("\n".join(data).encode()).hexdigest()}
    return result


def status():
    result = subprocess.run(["git", "status", "--porcelain=v1"], cwd=ROOT, capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError("git status failed")
    return result.stdout


def verify():
    build = json.loads((STATE / "frontend-build-01.json").read_text(encoding="utf-8"))
    if build["exit_code"] != 0:
        raise RuntimeError("frontend compiler did not succeed")
    probe = json.loads((STATE / "candidate-runtime-probe-02.json").read_text(encoding="utf-8"))
    snapshot = checked(STATE / "frontend01/acceptance-20261012-58-frontend-repair1-local-repair2")
    build_id = (snapshot / ".next/BUILD_ID").read_text().strip()
    assert build_id == probe["frontend"]["build_id"]
    guard = ROOT / "infra/local/rag-fixture/m1_source_guard_20261012_58-repair1.mjs"
    assert guard.read_bytes() == (snapshot / "preserve-build.mjs").read_bytes()
    source_component = ROOT / "apps/web/src/features/documents/ServiceWorkspace.tsx"
    assert source_component.read_bytes() == (snapshot / "src/features/documents/ServiceWorkspace.tsx").read_bytes()
    assert (ROOT / "apps/web/src/features/assistance/AssistanceContextPanel.tsx").read_bytes() == (snapshot / "src/features/assistance/AssistanceContextPanel.tsx").read_bytes()
    test_reports = []
    for name in ["baseline-tests-01.xml", "context-tests-03.xml", "frontend-tests-02.xml"]:
        document = ET.parse(STATE / name)
        suites = list(document.getroot().iter("testsuite"))
        summary = {key:sum(int(s.get(key, "0")) for s in suites) for key in ["tests", "failures", "errors", "skipped"]}
        assert summary["failures"] == summary["errors"] == summary["skipped"] == 0
        test_reports.append({"path": name, **summary})
    tokens = {}
    for alias in ["SV001", "SV024", "OF001", "OF002"]:
        code, session = http(8006, "/v1/auth/demo-login", body={"account":alias})
        assert code == 200
        tokens[alias] = session["token"]
    code, records = http(8006, "/v1/service-requests", tokens["SV001"])
    assert code == 200
    record = next(r for r in records["items"] if r["document_type"] == "GRADE_APPEAL")
    request = {"surface":"service", "resource":{"kind":"service_request", "id":record["id"], "expected_version":record["version"]}}
    projections = {}
    for alias in ["SV001", "OF002"]:
        code, context = http(8006, "/v1/assistant/context", tokens[alias], request)
        assert code == 200 and context["action_authority"] == "none"
        assert not any(key in context for key in ["preview", "token", "profile", "internal_notes"])
        projections[alias] = context
    assert projections["SV001"]["resource"]["view"] == "student"
    assert projections["OF002"]["resource"]["view"] == "staff"
    assert projections["SV001"]["evidence"] == projections["OF002"]["evidence"]
    assert projections["SV001"]["resource"]["status"] == projections["OF002"]["resource"]["status"]
    denials = {}
    for alias in ["SV024", "OF001"]:
        code, _ = http(8006, "/v1/assistant/context", tokens[alias], request)
        assert code == 404
        denials[alias] = code
    stale = {**request, "resource": {**request["resource"], "expected_version": record["version"]+1}}
    code, _ = http(8006, "/v1/assistant/context", tokens["SV001"], stale)
    assert code == 409
    browser = json.loads((STATE / "browser-verification-01.json").read_text(encoding="utf-8"))
    assert browser["build_id"] == build_id
    assert browser["resource_version"] == record["version"]
    assert projections["SV001"]["status"] == "source_changed"
    assert browser["source_hash_observed"] == projections["SV001"]["evidence"][0]["sha256"]
    original = database_digest(ROOT / "infra/local/certificate-stage1-20261013-01/demo.sqlite3")
    candidate = database_digest(STATE / "business-candidate01.sqlite3")
    assert original == candidate, "business rows diverged; inspect, never reset"
    prior_snapshot = ROOT / "infra/local/service-stage6-20261014-01/frontend02/acceptance-20261012-58-frontend-repair1-local-repair2"
    before = (prior_snapshot / "src/features/documents/ServiceWorkspace.tsx").read_text(encoding="utf-8")
    after = source_component.read_text(encoding="utf-8")
    source_diff = "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile="preserved_snapshot", tofile="source"))
    before_git = json.loads((STATE / "runtime-probe-01.json").read_text(encoding="utf-8"))["git"]["status"]
    current_git = status()
    old_entries = set(before_git.splitlines())
    missing = sorted(old_entries - set(current_git.splitlines()))
    assert not missing, "pre-existing version-control state changed; inspect"
    return {"scope":"local_synthetic_context_slice", "url":"http://localhost:8006/login", "build_id":build_id,
        "test_reports":test_reports, "shared_context": {"resource_id":record["id"], "version":record["version"],
            "status":record["status"], "source_status":projections["SV001"]["status"], "denials":denials,
            "stale_version_status":409}, "business_tables":original, "candidate_matches_original_business_rows":True,
        "preexisting_git_entries_preserved":True, "source_patch":source_diff,
        "git_status":current_git, "guard_unchanged":True, "new_paid_writer":False, "model_calls_in_verification":0,
        "limitations":["No user pilot or active human-time measurements", "UNI-004 remains a partial contract slice",
            "Existing proxy OpenAPI duplicate operation-ID warnings", "Other routes/preferences/grants/memory need remaining backlog",
            "Candidate DB is a preserved snapshot, not automatic synchronization with old app8004"]}


if __name__ == "__main__":
    output = checked(STATE / "candidate-verification-01.json")
    if output.exists():
        raise FileExistsError("verification01 is retained; inspect it before selecting another exact output")
    retain(output, verify())
    print(str(output))
