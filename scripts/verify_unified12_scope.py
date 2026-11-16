"""Exact scoped preimage/new-file diffs, inherited lint and guard preservation."""
import difflib
import hashlib
import json
import sys
from unified_ai_runtime_probe import ROOT, checked, retain
from verify_unified10_scope import command

STATE = checked(ROOT / "infra/local/unified-ai-20261015-12")
NEW = [
    "services/api/src/campus247/application/assistance/staff_contracts.py",
    "services/api/src/campus247/application/assistance/staff_workspace.py",
    "services/api/src/campus247/infrastructure/repositories/staff_workspace.py",
    "services/api/src/campus247/presentation/staff_workspace.py",
    "apps/web/src/features/assistance/StaffWorkspacePanel.tsx",
    "tests/integration/test_unified_staff12.py",
    "scripts/prepare_unified_ai_session12.py", "scripts/preserve_unified12_extra.py",
    "scripts/prepare_unified_ai_frontend12.py", "scripts/prepare_unified12_contracts.py",
    "scripts/verify_unified_ai_session12.py", "scripts/probe_unified_staff_process12.py", "scripts/verify_unified12_scope.py",
    "contracts/json-schema/assistance/staff-v1-01/StaffRead.json",
    "contracts/json-schema/assistance/staff-v1-01/StaffReview.json",
    "contracts/json-schema/assistance/staff-v1-01/StaffSourceRead.json",
    "contracts/json-schema/assistance/staff-v1-01/StaffDossier.json",
    "docs/UNIFIED_AI_SESSION12_20261015.md",
]

if __name__ == "__main__":
    number = sys.argv[1]
    if number not in {"01", "02", "03", "04", "05"}: raise ValueError("fresh scope attempt required")
    before = json.loads((STATE / "preflight.json").read_text(encoding="utf-8"))
    entries = [*before["sources"], *json.loads((STATE / "extra-preimages.json").read_text(encoding="utf-8"))]
    changed, differences = [], []
    for entry in entries:
        original = checked(STATE / entry["backup"]).read_bytes()
        assert hashlib.sha256(original).hexdigest() == entry["sha256"]
        current = checked(ROOT / entry["path"]).read_bytes()
        if hashlib.sha256(current).hexdigest() != entry["sha256"]:
            changed.append(entry["path"])
            differences.extend(difflib.unified_diff(original.decode("utf-8").splitlines(True), current.decode("utf-8").splitlines(True),
                fromfile=entry["path"] + " (preimage)", tofile=entry["path"]))
    for name in NEW:
        source = checked(ROOT / name).read_text(encoding="utf-8")
        differences.extend(difflib.unified_diff([], source.splitlines(True), fromfile="(new)", tofile=name))
    with checked(STATE / ("complete-source-changes-" + number + ".patch")).open("x", encoding="utf-8") as output:
        output.write("".join(differences))
    commands = [command(["git", "status", "--porcelain=v1"]), command(["git", "diff", "--name-only"]),
        command(["git", "diff", "--check", "--", *changed])]
    missing = sorted(set(before["git_status"].splitlines()) - set(commands[0]["stdout"].splitlines()))
    findings = []
    for name in [*changed, *NEW]:
        if not name.endswith(".py"): continue
        args = [sys.executable, "-B", "-m", "ruff", "check", "--select", "E9,F", "--no-cache", "--output-format=json", "--stdin-filename", name, "-"]
        source = checked(ROOT / name).read_text(encoding="utf-8")
        entry = next((e for e in entries if e["path"] == name), None)
        old = checked(STATE / entry["backup"]).read_text(encoding="utf-8") if entry else ""
        current_result, old_result = command(args, input_text=source), command(args, input_text=old)
        def signature(row, text): return row["code"], row["message"], text.splitlines()[row["location"]["row"] - 1].strip()
        inherited = {signature(row, old) for row in json.loads(old_result["stdout"])}
        findings.extend({"file": name, "finding": row} for row in json.loads(current_result["stdout"]) if signature(row, source) not in inherited)
    guard = checked(ROOT / "infra/local/rag-fixture/m1_source_guard_20261012_58-repair1.mjs").read_bytes()
    builds = []
    for attempt in ("01", "02", "03", "04", "05"):
        folder = checked(STATE / ("frontend" + attempt) / "acceptance-20261012-58-frontend-repair1-local-repair2")
        if folder.exists():
            builds.append({"attempt": attempt, "guard_unchanged": (folder / "preserve-build.mjs").read_bytes() == guard,
                "build_id": (folder / ".next/BUILD_ID").read_text() if (folder / ".next/BUILD_ID").exists() else None})
    result = {"commands": commands, "preimages_verified": len(entries), "changed_files": changed, "new_files": NEW,
        "new_file_sha256": {name: hashlib.sha256(checked(ROOT / name).read_bytes()).hexdigest() for name in NEW},
        "preexisting_git_entries_missing": missing, "new_lint_findings": findings, "builds": builds,
        "guard_sha256": hashlib.sha256(guard).hexdigest()}
    retain(STATE / ("scope-verification-" + number + ".json"), result)
    print(json.dumps({k: result[k] for k in ("new_lint_findings", "preexisting_git_entries_missing", "builds", "guard_sha256")}))
    assert not missing and not findings and all(row["exit_code"] == 0 for row in commands)
    assert result["guard_sha256"] == "8f0886295da2214205cf257dd9e1d9476993ed1a7fb0ac67434909fa4af2eae6"
    assert all(row["guard_unchanged"] for row in builds)
