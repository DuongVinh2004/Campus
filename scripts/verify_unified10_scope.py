"""Exact preimage diff, inherited/new lint distinction, guard/status checks."""
import hashlib
import json
import subprocess
import sys
from unified_ai_runtime_probe import ROOT, checked, retain

STATE = checked(ROOT / "infra/local/unified-ai-20261015-10")
NEW = ["services/api/src/campus247/application/multi_agent/coordination.py",
       "tests/integration/test_unified_coordination10.py", "scripts/prepare_unified_ai_session10.py",
       "scripts/preserve_unified10_extra.py", "scripts/prepare_unified_ai_frontend10.py",
       "scripts/verify_unified_ai_session10.py", "scripts/prepare_unified10_contracts.py", "scripts/verify_unified10_scope.py", "scripts/preserve_unified10_schema.py", "scripts/preserve_unified10_composition.py"]


def command(args, *, input_text=None):
    result = subprocess.run(args, cwd=ROOT, input=input_text, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return {"command": args, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


if __name__ == "__main__":
    number = sys.argv[1]
    if number not in {"01", "02", "03"}: raise ValueError("fresh exact scope attempt required")
    before = json.loads((STATE / "preflight.json").read_text(encoding="utf-8"))
    preimages = [*before["sources"], *json.loads((STATE / "extra-preimages.json").read_text(encoding="utf-8")),
                *json.loads((STATE / "schema-preimages.json").read_text(encoding="utf-8")),
                *json.loads((STATE / "composition-preimages.json").read_text(encoding="utf-8"))]
    changed = []
    for entry in preimages:
        snapshot = checked(STATE / entry["backup"])
        assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == entry["sha256"]
        if hashlib.sha256(checked(ROOT / entry["path"]).read_bytes()).hexdigest() != entry["sha256"]:
            changed.append(entry["path"])
    commands = [command(["git", "status", "--porcelain=v1"]), command(["git", "diff", "--name-only"]),
                command(["git", "diff", "--check", "--", *changed])]
    lint, new_findings = [], []
    for name in [*changed, *NEW]:
        if not name.endswith(".py"): continue
        args = [sys.executable, "-B", "-m", "ruff", "check", "--select", "E9,F", "--no-cache", "--output-format=json", "--stdin-filename", name, "-"]
        current_text = checked(ROOT / name).read_text(encoding="utf-8")
        current = command(args, input_text=current_text)
        original = next((entry for entry in preimages if entry["path"] == name), None)
        baseline_text = checked(STATE / original["backup"]).read_text(encoding="utf-8") if original else ""
        baseline = command(args, input_text=baseline_text)
        def signature(row, source):
            return (row["code"], row["message"], source.splitlines()[row["location"]["row"]-1].strip())
        inherited = {signature(row, baseline_text) for row in json.loads(baseline["stdout"])}
        added = [row for row in json.loads(current["stdout"]) if signature(row, current_text) not in inherited]
        new_findings.extend({"file": name, "finding": row} for row in added)
        lint.append({"file": name, "baseline": baseline, "current": current, "new_findings": added})
    missing = sorted(set(before["git_status"].splitlines()) - set(commands[0]["stdout"].splitlines()))
    guard_path = checked(ROOT / "infra/local/rag-fixture/m1_source_guard_20261012_58-repair1.mjs")
    guard = guard_path.read_bytes()
    builds = []
    for attempt in ("01", "02", "03", "04", "05"):
        folder = checked(STATE / ("frontend" + attempt) / "acceptance-20261012-58-frontend-repair1-local-repair2")
        if folder.exists():
            builds.append({"attempt": attempt, "build_id": (folder / ".next/BUILD_ID").read_text() if (folder / ".next/BUILD_ID").exists() else None,
                           "guard_unchanged": (folder / "preserve-build.mjs").read_bytes() == guard})
    prior_scope = json.loads(checked(ROOT / "infra/local/unified-ai-20261014-09/scope-verification-02.json").read_text(encoding="utf-8"))
    result = {"commands": commands, "lint": lint, "new_lint_findings": new_findings,
        "preexisting_git_entries_missing": missing, "preimages_verified": len(preimages),
        "changed_files": changed, "new_files": NEW, "builds": builds,
        "guard_sha256": hashlib.sha256(guard).hexdigest(), "guard_matches_session09": hashlib.sha256(guard).hexdigest() == prior_scope["guard_sha256"]}
    retain(STATE / ("scope-verification-" + number + ".json"), result)
    print(json.dumps({k: result[k] for k in ("new_lint_findings", "preexisting_git_entries_missing", "builds", "guard_matches_session09")}))
    assert not missing and not new_findings and all(row["exit_code"] == 0 for row in commands)
    assert result["guard_matches_session09"] and all(row["guard_unchanged"] for row in builds)
