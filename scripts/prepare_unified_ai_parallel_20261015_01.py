"""Exclusive source-only dispatch snapshot; no retained DB/runtime mutations."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "infra/local/unified-ai-parallel-20261015-01"


def checked(path):
    absolute = path.resolve()
    if absolute == ROOT or not absolute.is_relative_to(ROOT):
        raise ValueError("exact workspace descendant required")
    for parent in [path, *path.parents]:
        if parent == ROOT.parent:
            break
        if parent.is_symlink() or parent.is_junction() or (parent.exists() and getattr(parent.stat(), "st_file_attributes", 0) & 0x400):
            raise ValueError("reparse paths outside dispatch scope")
    return absolute


def retain(path, value):
    destination = checked(path)
    with destination.open("x", encoding="utf-8") as output:
        json.dump(value, output, ensure_ascii=False, indent=2)


def main():
    state = checked(STATE)
    if state.exists():
        raise FileExistsError("preserve existing batch; choose a new namespace")
    status = subprocess.run(["git", "status", "--porcelain=v1"], cwd=ROOT, capture_output=True, text=True, check=True)
    roots = ["services/api/src", "services/worker/src", "packages/synthetic/src", "apps/web/src", "apps/web/public", "contracts", "scripts", "tests"]
    inventory = subprocess.run(["rg", "--files", *roots], cwd=ROOT, capture_output=True, text=True, check=True)
    files = inventory.stdout.splitlines() + ["AGENTS.md", "apps/web/AGENTS.md", "package.json", "apps/web/package.json", "pyproject.toml", "pnpm-lock.yaml", "uv.lock",
        "docs/UNIFIED_AI_SESSION11_20261015.md", "docs/UNIFIED_AI_SESSION12_20261015.md",
        "docs/UNIFIED_AI_IMPLEMENTATION_PLAN_20261014.md", "docs/UNIFIED_AI_IMPLEMENTATION_BACKLOG_20261014.json",
        "docs/UNIFIED_AI_PARALLEL_20261015_01.md", "docs/UNIFIED_AI_CHAT_A_20261015_01.md", "docs/UNIFIED_AI_CHAT_B_20261015_01.md", "docs/UNIFIED_AI_CHAT_C_20261015_01.md",
        "infra/local/rag-fixture/m1_source_guard_20261012_58-repair1.mjs",
        "infra/local/unified-ai-20261015-12/test-outcomes-02.json", "infra/local/unified-ai-20261015-12/final-readback-01.json"]
    sources = sorted({checked(ROOT / name) for name in files})
    for source in sources:
        if not source.is_file() or source.suffix.lower() in {".sqlite3", ".db", ".pyc"}:
            raise ValueError("source-only snapshot expected: " + str(source.relative_to(ROOT)))
    state.mkdir(exist_ok=False)
    baseline = checked(state / "baseline")
    baseline.mkdir(exist_ok=False)
    records = []
    for source in sources:
        relative = source.relative_to(ROOT)
        destination = checked(baseline / relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        data = source.read_bytes()
        with destination.open("xb") as output:
            output.write(data)
        records.append({"path": relative.as_posix(), "snapshot": destination.relative_to(state).as_posix(), "sha256": hashlib.sha256(data).hexdigest()})
    retain(state / "coordination-manifest.json", {"workspace": str(ROOT), "project_id": "a51e0376-40a1-4c8d-9436-75d76a6c614c",
        "source_only_baseline": True, "git_status_before_dispatch": status.stdout, "git_warnings": status.stderr, "files": records,
        "streams": {"a": {"tasks": [f"UNI-{n:03d}" for n in range(31, 39)], "shared_source_writer": True},
                    "b": {"tasks": [f"UNI-{n:03d}" for n in range(39, 43)], "shared_source_writer": False},
                    "c": {"tasks": [f"UNI-{n:03d}" for n in range(43, 51)], "backlog_writer": True}},
        "ui_tests_authorized": False, "paid_dispatches_authorized": False, "production_mutations_authorized": False,
        "serving_runtime_transition_authorized": False, "destructive_actions_authorized": False})
    after = subprocess.run(["git", "status", "--porcelain=v1"], cwd=ROOT, capture_output=True, text=True, check=True)
    missing = sorted(set(status.stdout.splitlines()) - set(after.stdout.splitlines()))
    retain(state / "dispatch-preservation.json", {"preexisting_git_entries_missing": missing, "git_status_after_snapshot": after.stdout,
        "snapshot_file_count": len(records), "retained_databases_opened_for_write": 0, "source_mutations": 0})
    assert not missing
    print(json.dumps({"state": str(state), "source_preimages": len(records), "preexisting_git_entries_missing": missing}))


if __name__ == "__main__":
    main()
