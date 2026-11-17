"""Exclusive source preimages and read-only snapshots before UNI-007–010."""
import prepare_unified_ai_session06 as previous
import subprocess
import hashlib
import sqlite3
from unified_ai_runtime_probe import retain, http
from verify_unified_ai_candidate import database_digest
from unified_ai_runtime_probe import ROOT, checked

previous.STATE = checked(ROOT / "infra/local/unified-ai-20261014-08")
previous.SOURCES = list(dict.fromkeys([*previous.SOURCES,
    "services/api/src/campus247/application/assistance/durable_services.py",
    "services/api/src/campus247/application/assistance/unified_contracts.py",
    "services/api/src/campus247/application/privacy/consent.py",
    "services/api/src/campus247/presentation/chat.py",
    "services/api/src/campus247/presentation/agent_runs.py",
    "services/api/src/campus247/agent/state.py",
    "services/api/src/campus247/agent/nodes/definitions.py",
]))


def listener_inventory():
    # WMI is unavailable in this sandbox. Capture OS listeners without changing
    # a process; do not infer permission to restart from a PID observation.
    result = subprocess.run(["netstat.exe", "-ano", "-p", "tcp"], capture_output=True, text=True, check=True)
    ports = {"3006", "8006", "8003", "18081", "18082"}
    lines = [line.strip() for line in result.stdout.splitlines()
             if len(line.split()) >= 4 and line.split()[1].rsplit(":", 1)[-1] in ports]
    return {"listeners": lines, "process_metadata": "WMI unavailable; no process mutation"}


def main():
    state = previous.STATE
    if state.exists():
        raise FileExistsError("preserve existing evidence")
    sources = [checked(ROOT / name) for name in previous.SOURCES]
    databases = {name: checked(ROOT / path) for name, path in previous.DATABASES.items()}
    assert all(path.is_file() for path in [*sources, *databases.values()])
    status = subprocess.run(["git", "status", "--porcelain=v1"], cwd=ROOT, capture_output=True, text=True, check=True)
    ownership = listener_inventory()
    runtime = {str(port): http(port, "/v1/assistant/runtime" if port == 8006 else "/health/live") for port in (8006, 8003)}
    state.mkdir(exist_ok=False)
    preimages, snapshots = [], []
    for index, source in enumerate(sources):
        data = source.read_bytes()
        target = checked(state / f"source-before-{index:02d}.snapshot")
        with target.open("xb") as stream:
            stream.write(data)
        preimages.append({"path": source.relative_to(ROOT).as_posix(), "backup": target.name,
                          "sha256": hashlib.sha256(data).hexdigest()})
    for name, source in databases.items():
        target = checked(state / f"{name}-before.sqlite3")
        with target.open("xb"):
            pass
        with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as src, sqlite3.connect(target) as dst:
            src.backup(dst)
        snapshots.append({"source": source.relative_to(ROOT).as_posix(), "snapshot": target.name,
                          "tables": database_digest(target)})
    retain(state / "preflight.json", {"sources": preimages, "snapshots": snapshots,
        "git_status": status.stdout, "git_warnings": status.stderr, "ownership": ownership, "runtime": runtime,
        "paid_before": previous.paid_view(), "native_before": previous.native_view(),
        "model_dispatches": 0, "human_measurements_started": 0})
    print({"preimages": len(preimages), "snapshots": len(snapshots), "runtime": runtime})

if __name__ == "__main__":
    main()
