"""Prepare/build/launch one fresh unified candidate, retaining all old runtimes.

Build guard copied byte-for-byte. Business DB is SQLite backup from read-only
source into an exclusive fresh destination; no reset, deletion or paid writer.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

from unified_ai_runtime_probe import ROOT, STATE, checked, retain

FRONTEND = STATE / "frontend01/acceptance-20261012-58-frontend-repair1-local-repair2"
DATABASE = STATE / "business-candidate01.sqlite3"
SOURCE_DB = ROOT / "infra/local/certificate-stage1-20261013-01/demo.sqlite3"


def tools():
    import prepare_certificate_frontend as build_tools
    build_tools.STATE, build_tools.ATTEMPT, build_tools.FRONTEND = STATE, "01", FRONTEND
    original = build_tools.runtime_environment
    def environment():
        return {**original(), "NEXT_PUBLIC_API_URL": "http://localhost:8006",
                "NEXT_PUBLIC_SERVICE_DEMO": "true", "NEXT_PUBLIC_MULTI_AGENT": "true",
                "NEXT_PUBLIC_UNIFIED_AI": "true"}
    build_tools.runtime_environment = environment
    build_tools.retain = lambda path, value: retain(path, value)
    return build_tools


def prepare():
    checked(FRONTEND)
    if FRONTEND.exists() or DATABASE.exists():
        raise FileExistsError("candidate01 already exists; preserve it and inspect")
    source = checked(SOURCE_DB)
    if not source.is_file():
        raise ValueError("retained business source required")
    # Reserve an exact new filename before sqlite connects; existing files are
    # never truncated. Backup reads a consistent SQLite snapshot.
    with checked(DATABASE).open("xb"):
        pass
    with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as source_conn:
        with sqlite3.connect(checked(DATABASE)) as target_conn:
            source_conn.backup(target_conn)
    retain(STATE / "candidate-storage-01.json", {"source": str(source), "destination": str(DATABASE),
        "method": "read_only_sqlite_backup", "original_preserved": True, "production": False})
    tools().prepare()


def build():
    tools().build()


def start():
    import socket
    def listening(port):
        with socket.socket() as connection:
            connection.settimeout(1)
            return connection.connect_ex(("127.0.0.1", port)) == 0
    build_tools = tools()
    guard = checked(FRONTEND / "preserve-build.mjs")
    prior_guard = checked(ROOT / "infra/local/rag-fixture/m1_source_guard_20261012_58-repair1.mjs")
    if guard.read_bytes() != prior_guard.read_bytes() or not (FRONTEND / ".next/BUILD_ID").is_file():
        raise ValueError("successful build with unchanged guard required")
    if listening(8006) or listening(3006) or (STATE / "candidate-launch-01.json").exists():
        raise RuntimeError("candidate ports/receipt already owned; inspect, do not stop or overwrite")
    commands = {
        "frontend": [str(build_tools.NODE), "--import", guard.as_uri(), str(ROOT / "apps/web/node_modules/next/dist/bin/next"),
                     "start", str(FRONTEND), "-H", "127.0.0.1", "-p", "3006"],
        "api": [sys.executable, "-B", "-u", str(Path(__file__).resolve()), "api"],
    }
    processes = {}
    env = build_tools.runtime_environment()
    for name, command in commands.items():
        with checked(STATE / f"candidate-{name}-01.log").open("xb") as log:
            processes[name] = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT, creationflags=0x08000000)
    retain(STATE / "candidate-launch-01.json", {"commands": commands, "pids": {k:p.pid for k,p in processes.items()},
        "url": "http://localhost:8006/login", "database": str(DATABASE), "new_paid_writer": False,
        "build_id": (FRONTEND / ".next/BUILD_ID").read_text().strip(), "old_runtimes_preserved": True})
    for _ in range(40):
        if any(p.poll() is not None for p in processes.values()):
            raise RuntimeError("candidate exited; retained logs contain diagnostics")
        if listening(8006) and listening(3006):
            print("http://localhost:8006/login")
            return
        time.sleep(.5)
    raise RuntimeError("candidate startup incomplete; retain processes/logs for inspection")


def api():
    sys.path[:0] = [str(ROOT / "services/api/src"), str(ROOT / "packages/synthetic/src")]
    from campus247.bootstrap.unified_demo import create_unified_demo_app
    import uvicorn
    state_database = None
    configured_state = os.environ.get("C247_UNIFIED_STATE_DB")
    if configured_state is not None:
        if not configured_state.strip():
            raise ValueError("explicit actor state path required")
        state_database = checked(Path(configured_state))
        if not state_database.is_file():
            raise ValueError("retained initialized actor state database required; never replace a missing runtime store")
    if not checked(DATABASE).is_file():
        raise ValueError("retained candidate DB required")
    history_database = None
    configured_history = os.environ.get("C247_UNIFIED_HISTORY_DB")
    if configured_history is not None:
        if not configured_history.strip():raise ValueError("explicit held history path required")
        history_database = checked(Path(configured_history))
        if not history_database.is_file():raise ValueError("held history required")
    uvicorn.run(create_unified_demo_app(DATABASE, frontend_port=3006, frontend_build_id=os.environ.get("C247_UNIFIED_BUILD_ID"),
                state_database=state_database,consent_mode=os.environ.get("C247_UNIFIED_CONSENT_STORAGE","disabled"),history_database=history_database), host="127.0.0.1", port=8006,
                log_level="warning", access_log=False)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2 or sys.argv[1] not in {"prepare", "build", "start", "api"}:
        raise ValueError("explicit prepare/build/start/api command required")
    {"prepare":prepare, "build":build, "start":start, "api":api}[sys.argv[1]]()
