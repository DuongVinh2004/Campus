"""C-only, append-only preservation and source evidence. No runtime transitions."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "infra/local/unified-ai-parallel-20261015-01"
STATE = BATCH / "stream-c"
DATABASES = [
    "infra/local/unified-ai-20261014-01/business-candidate01.sqlite3",
    "infra/local/unified-ai-20261014-05/actor-state.sqlite3",
    "infra/local/public-rag-20261013/conversations.sqlite3",
    "infra/local/multi-agent-integrated-20261013-01/agent-runs.sqlite3",
]
GUARD = "infra/local/rag-fixture/m1_source_guard_20261012_58-repair1.mjs"


def checked(path: Path) -> Path:
    if any(part in {"..", "*", "?"} for part in path.parts):
        raise ValueError("literal exact descendant required")
    absolute = path.resolve()
    if absolute == ROOT or not absolute.is_relative_to(ROOT):
        raise ValueError("workspace descendant required")
    for parent in [path, *path.parents]:
        if parent == ROOT.parent:
            break
        if parent.is_symlink() or parent.is_junction() or (parent.exists() and getattr(parent.stat(), "st_file_attributes", 0) & 0x400):
            raise ValueError("reparse mutation/read target rejected: " + str(parent))
    return absolute


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def retain(path: Path, value):
    target = checked(path)
    if not target.is_relative_to(checked(STATE)):
        raise ValueError("C evidence only")
    with target.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def git_status():
    result = subprocess.run(["git", "status", "--porcelain=v1"], cwd=ROOT, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", check=True)
    return {"entries": result.stdout.splitlines(), "warnings": result.stderr}


def database_digest(path: Path):
    source = checked(path)
    if not source.is_file():
        raise FileNotFoundError(str(source))
    result = {}
    with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as connection:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        definitions = connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name").fetchall()
        result["schema_sha256"] = sha(json.dumps(definitions, ensure_ascii=False).encode())
        result["tables"] = {}
        for (table,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
            quoted = '"' + table.replace('"', '""') + '"'
            rows = connection.execute(f"SELECT * FROM {quoted}").fetchall()
            encoded = sorted(json.dumps(row, ensure_ascii=False, default=lambda b: {"bytes": b.hex()}) for row in rows)
            result["tables"][table] = {"rows": len(rows), "sha256": sha("\n".join(encoded).encode())}
        connection.rollback()
    return result


def resource_metadata():
    # Read-only accessors: never construct/resume a budget or dispatch a provider.
    from multi_agent_live_resources import paid_view, native_view
    return {"paid": paid_view(), "native": native_view()}


def source_files():
    result = subprocess.run(["rg", "--files", "services/api/src", "services/worker/src", "packages/synthetic/src",
                             "apps/web/src", "apps/web/public", "contracts", "scripts", "tests"],
                            cwd=ROOT, capture_output=True, text=True, check=True)
    extras = ["AGENTS.md", "apps/web/AGENTS.md", "pyproject.toml", "uv.lock", "pnpm-lock.yaml", "package.json",
              "apps/web/package.json", "apps/web/tsconfig.json", "apps/web/postcss.config.mjs", GUARD,
              "infra/local/rag-fixture/manual-20261013-76/frontend/tsconfig.json",
              "infra/local/rag-fixture/manual-20261013-76/frontend/next.config.js",
              "infra/local/rag-fixture/manual-20261013-76/frontend/font-responses.cjs",
              "docs/UNIFIED_AI_IMPLEMENTATION_BACKLOG_20261014.json"]
    return sorted(set(result.stdout.splitlines() + extras))


def manifest():
    return {name.replace("\\", "/"): sha(checked(ROOT / name).read_bytes()) for name in source_files()}


def init():
    status = git_status()
    target = checked(STATE)
    target.mkdir(exist_ok=False)
    for name in ["preimages", "findings", "checks", "snapshots", "fixtures", "handoffs"]:
        checked(target / name).mkdir(exist_ok=False)
    backlog = checked(ROOT / "docs/UNIFIED_AI_IMPLEMENTATION_BACKLOG_20261014.json")
    data = backlog.read_bytes()
    with checked(target / "preimages/backlog-before-01.json").open("xb") as output:
        output.write(data)
    current = manifest()
    retain(target / "preflight-01.json", {
        "captured_at": datetime.now(timezone.utc).isoformat(), "workspace": str(ROOT), "git": status,
        "source_hashes": current, "backlog_preimage_sha256": sha(data),
        "retained_databases": {name: database_digest(ROOT / name) for name in DATABASES},
        "resource_metadata": resource_metadata(), "guard_sha256": current[GUARD],
        "ui_tests_run": False, "paid_calls": 0, "runtime_transitions": 0,
        "namespace_exclusive_create": True,
    })
    print(json.dumps({"namespace": str(target), "source_hashes": len(current), "retained_db_read_only": len(DATABASES)}))


def snapshot(number):
    status = git_status()
    target = checked(STATE / "snapshots" / ("source-" + number))
    target.mkdir(exist_ok=False)
    before = manifest()
    for name, checksum in before.items():
        data = checked(ROOT / name).read_bytes()
        if sha(data) != checksum:
            raise RuntimeError("source changed during snapshot: " + name)
        destination = checked(target / name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as output:
            output.write(data)
    after = manifest()
    retain(STATE / "snapshots" / ("manifest-" + number + ".json"), {
        "source_root": str(ROOT), "snapshot": str(target), "hashes": before,
        "stable_during_capture": before == after, "git": status,
        "source_only_not_a_complete_runtime": True,
    })
    if before != after:
        raise RuntimeError("snapshot retained but source changed; use a fresh attempt")
    print(json.dumps({"snapshot": str(target), "files": len(before), "stable": True}))


def audit(number):
    before = json.loads(checked(STATE / "preflight-01.json").read_text(encoding="utf-8"))
    current_git = git_status()
    databases = {name: database_digest(ROOT / name) for name in DATABASES}
    resources = resource_metadata()
    missing = sorted(set(before["git"]["entries"]) - set(current_git["entries"]))
    result = {"retained_databases": databases,
              "all_table_row_digests_unchanged": databases == before["retained_databases"],
              "resource_metadata_unchanged": resources == before["resource_metadata"],
              "preexisting_git_entries_missing": missing, "git": current_git,
              "guard_unchanged": sha(checked(ROOT / GUARD).read_bytes()) == before["guard_sha256"],
              "backlog_preimage_unchanged": sha(checked(STATE / "preimages/backlog-before-01.json").read_bytes()) == before["backlog_preimage_sha256"],
              "ui_tests_run": False, "provider_calls": 0, "runtime_transition": False}
    retain(STATE / ("preservation-" + number + ".json"), result)
    print(json.dumps({k: v for k, v in result.items() if k not in {"retained_databases", "git"}}))
    if not all(result[k] for k in ["all_table_row_digests_unchanged", "resource_metadata_unchanged", "guard_unchanged", "backlog_preimage_unchanged"]) or missing:
        raise RuntimeError("preservation difference retained for inspection")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["init", "snapshot", "audit"])
    parser.add_argument("number", nargs="?", default="01")
    args = parser.parse_args()
    if re.fullmatch(r"[0-9]{2}", args.number) is None:
        raise ValueError("exact two-digit attempt required")
    {"init": lambda _: init(), "snapshot": snapshot, "audit": audit}[args.stage](args.number)
