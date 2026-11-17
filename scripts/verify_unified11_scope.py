"""Exact scoped diffs, retained status and byte-identical build guard checks."""
import hashlib
import json
import sys
from unified_ai_runtime_probe import ROOT, checked, retain
from verify_unified10_scope import command

STATE = checked(ROOT / "infra/local/unified-ai-20261015-11")
NEW = ["services/api/src/campus247/application/document_request/student_preparation.py",
    "tests/integration/test_unified_student11.py", "scripts/prepare_unified_ai_session11.py",
    "scripts/preserve_unified11_extra.py", "scripts/prepare_unified_ai_frontend11.py",
    "scripts/verify_unified_ai_session11.py", "scripts/prepare_unified11_contracts.py", "scripts/verify_unified11_scope.py",
    "apps/web/src/lib/student-preparation.ts", "apps/web/src/features/assistance/StudentPreparationPanel.tsx",
    "apps/web/src/features/assistance/StudentActionCoverage.tsx", "apps/web/src/features/assistance/UnavailableStudentSurface.tsx",
    "apps/web/src/features/documents/StudentFieldHelp.tsx",
    "contracts/json-schema/assistance/student-v1-01/StudentGoal.json",
    "contracts/json-schema/assistance/student-v1-01/SavePreparedDraft.json",
    "docs/UNIFIED_AI_SESSION11_20261015.md"]

if __name__ == "__main__":
    number = sys.argv[1]
    if number not in {"01", "02", "03", "04", "05"}: raise ValueError("fresh scope attempt required")
    before = json.loads((STATE / "preflight.json").read_text(encoding="utf-8"))
    entries = [*before["sources"], *json.loads((STATE / "extra-preimages.json").read_text(encoding="utf-8"))]
    changed = []
    for entry in entries:
        assert hashlib.sha256(checked(STATE / entry["backup"]).read_bytes()).hexdigest() == entry["sha256"]
        if hashlib.sha256(checked(ROOT / entry["path"]).read_bytes()).hexdigest() != entry["sha256"]:
            changed.append(entry["path"])
    commands = [command(["git", "status", "--porcelain=v1"]), command(["git", "diff", "--name-only"]),
                command(["git", "diff", "--check", "--", *changed])]
    missing = sorted(set(before["git_status"].splitlines()) - set(commands[0]["stdout"].splitlines()))
    lint, findings = [], []
    for name in [*changed, *NEW]:
        if not name.endswith(".py"): continue
        args = [sys.executable, "-B", "-m", "ruff", "check", "--select", "E9,F", "--no-cache", "--output-format=json", "--stdin-filename", name, "-"]
        current_text = checked(ROOT / name).read_text(encoding="utf-8")
        original = next((e for e in entries if e["path"] == name), None)
        old_text = checked(STATE / original["backup"]).read_text(encoding="utf-8") if original else ""
        current, old = command(args, input_text=current_text), command(args, input_text=old_text)
        def signature(row, text):
            return row["code"], row["message"], text.splitlines()[row["location"]["row"]-1].strip()
        inherited = {signature(row, old_text) for row in json.loads(old["stdout"])}
        added = [row for row in json.loads(current["stdout"]) if signature(row, current_text) not in inherited]
        findings.extend({"file": name, "finding": row} for row in added)
        lint.append({"file": name, "current": current, "baseline": old, "new_findings": added})
    guard = checked(ROOT / "infra/local/rag-fixture/m1_source_guard_20261012_58-repair1.mjs").read_bytes()
    builds = []
    for attempt in ("01", "02", "03", "04", "05"):
        folder = checked(STATE / ("frontend" + attempt) / "acceptance-20261012-58-frontend-repair1-local-repair2")
        if folder.exists():
            builds.append({"attempt": attempt, "guard_unchanged": (folder / "preserve-build.mjs").read_bytes() == guard,
                "build_id": (folder / ".next/BUILD_ID").read_text() if (folder / ".next/BUILD_ID").exists() else None})
    result = {"commands": commands, "preimages_verified": len(entries), "changed_files": changed, "new_files": NEW,
        "new_file_sha256": {name: hashlib.sha256(checked(ROOT / name).read_bytes()).hexdigest() for name in NEW},
        "preexisting_git_entries_missing": missing, "lint": lint, "new_lint_findings": findings, "builds": builds,
        "guard_sha256": hashlib.sha256(guard).hexdigest()}
    retain(STATE / ("scope-verification-" + number + ".json"), result)
    print(json.dumps({k: result[k] for k in ("new_lint_findings", "preexisting_git_entries_missing", "builds", "guard_sha256")}))
    assert not missing and not findings and all(row["exit_code"] == 0 for row in commands)
    assert result["guard_sha256"] == "8f0886295da2214205cf257dd9e1d9476993ed1a7fb0ac67434909fa4af2eae6"
    assert all(row["guard_unchanged"] for row in builds)
