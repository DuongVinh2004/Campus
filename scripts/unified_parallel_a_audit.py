"""Read-only preservation, scoped byte diffs, current source hashes and counts."""
import difflib
import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from unified_parallel_a_workspace import ROOT, STATE, checked, retain, write, database_digests
from unified_parallel_a_handoff import SOURCES, NEW_SOURCE

def sha(path):
    return hashlib.sha256(checked(path).read_bytes()).hexdigest()

if __name__ == "__main__":
    number = sys.argv[1]
    if len(number) != 2 or not number.isdigit(): raise ValueError("exact new audit attempt required")
    before = json.loads((STATE / "preflight-01.json").read_text(encoding="utf-8"))
    current = database_digests()
    rows = list(before["preimages"])
    for name in ["extra-preimages-01.json", "extra-preimages-02.json"]:
        rows.extend(json.loads((STATE / name).read_text(encoding="utf-8")))
    diffs = []
    for row in rows:
        original = checked(STATE / "preimages" / row["path"])
        assert sha(original) == row["sha256"], row["path"]
        target = checked(ROOT / row["path"])
        diffs.extend(difflib.unified_diff(original.read_text(encoding="utf-8").splitlines(True), target.read_text(encoding="utf-8").splitlines(True), fromfile="preimage/"+row["path"], tofile=row["path"]))
    write(STATE / ("scope-diff-"+number+".patch"), "".join(diffs).encode())
    paths = sorted(set([*SOURCES, *NEW_SOURCE, "services/api/src/campus247/presentation/assistant_state.py"]))
    paths += [str(p.relative_to(ROOT)).replace("\\", "/") for folder, pattern in [(ROOT / "tests/unified_workflow13a", "*.py"), (ROOT / "scripts", "unified_parallel_a_*.py"), (ROOT / "contracts/json-schema/assistance/cases-v13-02", "*.json")] for p in folder.glob(pattern)]
    hashes = {p: sha(ROOT / p) for p in paths}
    lint = subprocess.run([str(ROOT/".venv/Scripts/ruff.exe"), "check", *[str(ROOT/p) for p in paths if p.startswith("services/") and p.endswith(".py")], "--select", "E9,F"], cwd=ROOT, capture_output=True, text=True)
    baseline = json.loads((STATE.parent / "coordination-manifest.json").read_text(encoding="utf-8"))
    changed = [v["path"] for v in baseline["files"] if not (ROOT/v["path"]).is_file() or sha(ROOT/v["path"]) != v["sha256"]]
    protected = [v for v in baseline["files"] if v["path"] in {"AGENTS.md", "apps/web/AGENTS.md", "pnpm-lock.yaml", "uv.lock", "pyproject.toml", "services/api/src/campus247/application/single_agent/resources.py", "infra/local/rag-fixture/m1_source_guard_20261012_58-repair1.mjs"}]
    protected_checks = {v["path"]: sha(ROOT/v["path"]) == v["sha256"] for v in protected}
    latest = {}
    for path in sorted((STATE / "checks").glob("backend-*.xml")):
        for case in ET.parse(path).getroot().iter("testcase"):
            latest[(case.get("classname"), case.get("name"))] = {"status": "failed" if any(case.find(t) is not None for t in ("failure", "error")) else "skipped" if case.find("skipped") is not None else "passed", "evidence": str(path.relative_to(ROOT))}
    diagnostics = {k:v for k,v in latest.items() if k[0] == "tests.unified_final.test_workflow_c" or k[1].startswith("test_actual_two_process_staff_cas[")}
    runnable = {k:v for k,v in latest.items() if k not in diagnostics}
    guard = ROOT / "infra/local/rag-fixture/m1_source_guard_20261012_58-repair1.mjs"
    frontend = {}
    for attempt in ["01", "02"]:
        snapshot = STATE / ("frontend"+attempt) / "acceptance-20261012-58-frontend-repair1-local-repair2"
        frontend[attempt] = {"guard_sha256": sha(snapshot / "preserve-build.mjs"), "guard_equal": sha(guard) == sha(snapshot / "preserve-build.mjs"),
            "build_id": (snapshot / ".next/BUILD_ID").read_text().strip(),
            "typescript_exit": json.loads((STATE / ("frontend-typescript-"+attempt+".json")).read_text())["exit_code"],
            "build_exit": json.loads((STATE / ("frontend-build-"+attempt+".json")).read_text())["exit_code"]}
    git = subprocess.run(["git", "status", "--porcelain=v1"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    diff_names = subprocess.run(["git", "diff", "--name-only"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    preservation = {"retained_db_unchanged": current == before["retained_databases"], "retained_databases": current,
        "preimage_records_verified": len(rows), "protected_unchanged": protected_checks,
        "source_hashes": hashes, "changed_baseline_files_all_streams": changed,
        "lint": {"exit_code": lint.returncode, "stdout": lint.stdout, "stderr": lint.stderr},
        "git_status": git.stdout, "git_warnings": git.stderr, "git_diff_names": diff_names.stdout,
        "latest_unique_cases": len(latest), "passed": sum(v["status"] == "passed" for v in latest.values()),
        "runnable_unique_cases": len(runnable), "runnable_passed": sum(v["status"] == "passed" for v in runnable.values()),
        "namespace_harness_diagnostics": len(diagnostics), "frontend": frontend,
        "unresolved_cases": [{"class": k[0], "name": k[1], **v} for k,v in latest.items() if v["status"] != "passed"],
        "limits": ["old two-process probes reject A namespace; original tests unchanged; new two-process A confirmation evidence", "attempt06 C test namespace assertions failed before business; C independent retest passed in C namespace", "UI/component/DOM/browser/E2E not run", "no provider/serving-runtime transition/production mutations"]}
    retain(STATE / ("audit-"+number+".json"), preservation)
    assert preservation["retained_db_unchanged"] and all(protected_checks.values()) and lint.returncode == 0
    print(json.dumps({k: preservation[k] for k in ["retained_db_unchanged", "preimage_records_verified", "latest_unique_cases", "passed", "unresolved_cases"]}, ensure_ascii=False, indent=2))
