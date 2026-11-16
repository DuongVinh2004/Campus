"""Exclusive preimages and consistent snapshots for UNI-006 continuation."""
import hashlib
import json
import sqlite3
import subprocess
from datetime import datetime, timezone

from unified_ai_runtime_probe import ROOT, checked, retain, http
from handoff_unified_ai_session04 import windows_read
from verify_unified_ai_candidate import database_digest
from multi_agent_live_resources import paid_view, native_view

STATE = checked(ROOT / "infra/local/unified-ai-20261014-06")
SOURCES = [
    "services/api/src/campus247/application/assistance/state_storage.py",
    "services/api/src/campus247/infrastructure/repositories/sqlite_actor_state.py",
    "services/api/src/campus247/bootstrap/settings.py",
    "services/api/src/campus247/bootstrap/app.py",
    "services/api/src/campus247/bootstrap/unified_demo.py",
    "services/api/src/campus247/presentation/privacy_notice.py",
    "scripts/unified_ai_candidate.py",
    "docs/UNIFIED_AI_IMPLEMENTATION_BACKLOG_20261014.json",
    "docs/UNIFIED_AI_IMPLEMENTATION_PLAN_20261014.md",
    "docs/UNIFIED_AI_RUNTIME_INVENTORY_20261014.md",
]
DATABASES = {
    "business": "infra/local/unified-ai-20261014-01/business-candidate01.sqlite3",
    "actor": "infra/local/unified-ai-20261014-05/actor-state.sqlite3",
    "history": "infra/local/public-rag-20261013/conversations.sqlite3",
    "runs": "infra/local/multi-agent-integrated-20261013-01/agent-runs.sqlite3",
}


def main():
    if STATE.exists():
        raise FileExistsError("retain existing session; select a fresh exact namespace")
    sources = [checked(ROOT / name) for name in SOURCES]
    databases = {name: checked(ROOT / path) for name, path in DATABASES.items()}
    assert all(path.is_file() for path in [*sources, *databases.values()])
    status = subprocess.run(["git", "status", "--porcelain=v1"], cwd=ROOT, capture_output=True, text=True, check=True)
    ownership = windows_read()
    code, runtime = http(8006, "/v1/assistant/runtime")
    assert code == 200 and runtime["runtime"] == "unified-local-v5"
    STATE.mkdir(exist_ok=False)
    preimages = []
    for index, source in enumerate(sources):
        data = source.read_bytes()
        target = checked(STATE / f"source-before-{index:02d}.snapshot")
        with target.open("xb") as stream:
            stream.write(data)
        preimages.append({"path": str(source.relative_to(ROOT)), "backup": target.name,
                          "sha256": hashlib.sha256(data).hexdigest()})
    snapshots = []
    for name, source in databases.items():
        target = checked(STATE / f"{name}-before.sqlite3")
        with target.open("xb"):
            pass
        with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as src:
            with sqlite3.connect(target) as dst:
                src.backup(dst)
        snapshots.append({"source": str(source.relative_to(ROOT)), "snapshot": target.name,
                          "tables": database_digest(target)})
    retain(STATE / "preflight.json", {"captured_at": datetime.now(timezone.utc).isoformat(),
        "git_status": status.stdout, "git_warnings": status.stderr, "sources": preimages,
        "snapshots": snapshots, "ownership": ownership, "runtime": runtime,
        "paid_before": paid_view(), "native_before": native_view(),
        "model_dispatches": 0, "human_measurements_started": 0})
    print(json.dumps({"state": str(STATE), "preimages": len(preimages), "snapshots": len(snapshots)}))


if __name__ == "__main__":
    main()
