"""Append-only C reconciliation; never changes master backlog or owner source."""
import argparse
import ast
import difflib
import json
import re
import subprocess

from unified_parallel_c_preserve import BATCH, ROOT, STATE, checked, git_status, retain, sha
from unified_parallel_c_verify import outcomes


def main(number):
    target = checked(STATE / "checks" / ("checkpoint-" + number))
    target.mkdir(exist_ok=False)
    old_raw = checked(STATE / "preimages/backlog-before-patch-02.json").read_bytes()
    new_raw = checked(ROOT / "docs/UNIFIED_AI_IMPLEMENTATION_BACKLOG_20261014.json").read_bytes()
    old, new = json.loads(old_raw), json.loads(new_raw)
    marker = ('  "session11_record"').encode()
    preserved = {
        "tasks001_042_unchanged": old["tasks"][:42] == new["tasks"][:42],
        "session11_object_unchanged": old["session11_record"] == new["session11_record"],
        "session12_object_unchanged": old["last_session"] == new["last_session"],
        "session11_12_raw_suffix_unchanged": old_raw[old_raw.index(marker):] in new_raw,
        "unrelated_top_level_records_unchanged": all(new.get(k) == v for k, v in old.items() if k != "tasks"),
        "task_definitions_unchanged": all({k: v for k, v in before.items() if k not in {"status", "evidence"}}
            == {k: v for k, v in after.items() if k in before and k not in {"status", "evidence"}}
            for before, after in zip(old["tasks"][42:], new["tasks"][42:])),
    }
    patch = "".join(difflib.unified_diff(old_raw.decode().splitlines(True), new_raw.decode().splitlines(True),
                        fromfile="backlog preimage", tofile="docs/UNIFIED_AI_IMPLEMENTATION_BACKLOG_20261014.json"))
    with checked(target / "backlog.patch").open("x", encoding="utf-8") as output:
        output.write(patch)
    records, xmls = [], []
    directories = [p for p in checked(STATE / "checks").iterdir() if (p / "command.json").is_file()]
    # Stage names do not establish temporal order. Completed command record
    # creation time orders old attempts; retain exact ordering in this report.
    for directory in sorted(directories, key=lambda p: (p / "command.json").stat().st_mtime_ns):
        command = directory / "command.json"
        if command.is_file() and (directory / "backend.xml").is_file():
            item = json.loads(command.read_text(encoding="utf-8"))
            records.append({"command_file": str(command.relative_to(ROOT)), "exit_code": item["exit_code"],
                            "source_stable": item["stable_during_checks"], "completed_record_mtime_ns": command.stat().st_mtime_ns,
                            "command_record_sha256": sha(command.read_bytes())})
            xmls.append(directory / "backend.xml")
    latest = outcomes(xmls)
    owner_artifacts = {}
    for stream in ["stream-a", "stream-b"]:
        owner_artifacts[stream] = {}
        for subdirectory in ["handoffs", "integration-requests", "integration-acks"]:
            directory = checked(BATCH / stream / subdirectory)
            owner_artifacts[stream][subdirectory] = [{"path": str(p.relative_to(ROOT)), "sha256": sha(p.read_bytes())}
                for p in sorted(directory.glob("*.json"))] if directory.is_dir() else []
    sources = sorted([*ROOT.joinpath("scripts").glob("unified_parallel_c_*.py"), *ROOT.joinpath("tests/unified_final").glob("*.py")])
    syntax = []
    for path in sources:
        path = checked(path)
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        syntax.append({"path": str(path.relative_to(ROOT)), "sha256": sha(path.read_bytes())})
    command = [str(ROOT / ".venv/Scripts/ruff.exe"), "check", "--no-cache", "--select", "E9,F", *[row["path"] for row in syntax]]
    lint = subprocess.run(command, cwd=ROOT, text=True, encoding="utf-8", capture_output=True)
    coverage = {
        "requirements": [{"id": requirement["id"], "tasks": [{"id": task["id"], "source_status": task["status"],
            "evidence": task["evidence"], "full_acceptance": task.get("full_acceptance", "not_inferred_from_source_status")}
            for task in new["tasks"] if requirement["id"] in task["requirements"]]} for requirement in new["requirements"]],
        "acceptance": [{"id": group["id"], "expected": group["expected"],
            "tasks": [task["id"] for task in new["tasks"] if group["id"] in task["acceptance"]],
            "verified_by_C": False, "source_evidence_map": "docs/UNIFIED_AI_ACCEPTANCE_C_20261015_01.md"}
            for group in new["acceptance_groups"]],
    }
    retain(target / "coverage.json", coverage)
    retain(target / "report.json", {"backlog_preservation": preserved, "backlog_before_sha256": sha(old_raw),
        "backlog_after_sha256": sha(new_raw), "C_latest_unique": latest, "completed_commands": records,
        "owner_artifacts_readiness": owner_artifacts, "source_syntax": syntax,
        "lint": {"command": command, "exit_code": lint.returncode, "stdout": lint.stdout, "stderr": lint.stderr},
        "git": git_status(), "final_integrated_acceptance": False, "baseline50ms_failure_still_unresolved": True,
        "ui_pilot_human_usefulness_production": "pending", "snapshot_build": "pending immutable final handoffs"})
    print(json.dumps({"preserved": preserved, "C_latest_unique": latest, "syntax_files": len(syntax), "lint_exit": lint.returncode}))
    if not all(preserved.values()) or lint.returncode:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("number")
    args = parser.parse_args()
    if re.fullmatch(r"[0-9]{2}", args.number) is None:
        raise ValueError("fresh exact attempt required")
    main(args.number)
