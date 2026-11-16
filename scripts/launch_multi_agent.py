"""Launch additive guarded local API/frontend without replacing old runtimes."""
import hashlib
import argparse
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone

from multi_agent_workspace import ROOT, STATE, checked, retain

NODE = ROOT.parent / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe"
SOURCE = ROOT / "apps/web"
FRONTEND = checked(STATE / "frontend02/acceptance-20261012-58-frontend-repair1-local-repair2", STATE)


def listening(port):
    with socket.socket() as sock:
        sock.settimeout(.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def main(*, frontend_only=False):
    if any(listening(port) for port in ((3003,) if frontend_only else (8003, 3003))):
        raise RuntimeError("integrated port occupied; inspect receipt/ancestry before changes")
    if not (FRONTEND / ".next/BUILD_ID").is_file():
        raise RuntimeError("fresh integrated frontend build required")
    env = {key: value for key, value in os.environ.items() if not any(
        marker in key.upper() for marker in ("TOKEN", "KEY", "SECRET", "PASSWORD"))}
    env.update(NODE_PATH=str(SOURCE / "node_modules"), C247_M1_FRONTEND=str(FRONTEND),
        NEXT_PUBLIC_API_URL="http://localhost:8003", NEXT_PUBLIC_CERTIFICATE_DEMO="true", NEXT_PUBLIC_MULTI_AGENT="true",
        NEXT_TELEMETRY_DISABLED="1", NODE_ENV="production", PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8",
        TEMP=str(FRONTEND / "temp"), TMP=str(FRONTEND / "temp"), USERPROFILE=str(FRONTEND),
        APPDATA=str(FRONTEND / "appdata"), LOCALAPPDATA=str(FRONTEND / "localappdata"))
    commands = {
        "frontend": [str(NODE), "--import", (FRONTEND / "preserve-build.mjs").as_uri(),
            str(SOURCE / "node_modules/next/dist/bin/next"), "start", str(FRONTEND), "-H", "127.0.0.1", "-p", "3003"],
        "api": [sys.executable, "-B", "-u", str(ROOT / "scripts/run_multi_agent.py"), "--mode", "guarded", "--frontend", "3003"],
    }
    if frontend_only:
        commands = {"frontend": commands["frontend"]}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    owned = {}
    for name, command in commands.items():
        with checked(STATE / f"{stamp}-{name}.log", STATE).open("xb") as log:
            proc = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=log,
                stderr=subprocess.STDOUT, creationflags=0x08000000)
        owned[name] = proc.pid
    retain(STATE / f"{stamp}-launch.json", {"commands": commands, "owned_pids": owned,
        "url": "http://localhost:8003/login", "mode": "frontend_only" if frontend_only else "guarded", "paid_ledger_initialized": False,
        "guard_sha256": hashlib.sha256((FRONTEND / "preserve-build.mjs").read_bytes()).hexdigest(),
        "previous_runtime_preserved": {"public_api": 8000, "certificate_api": 8002, "certificate_frontend": 3002},
        "business_database": str(ROOT / "infra/local/certificate-stage1-20261013-01/demo.sqlite3"),
        "history_database": str(ROOT / "infra/local/public-rag-20261013/conversations.sqlite3")})
    for _ in range(30):
        if listening(3003) and (frontend_only or listening(8003)):
            print("Frontend3003 ready" if frontend_only else "Integrated local: http://localhost:8003/login (guarded admission)")
            return
        time.sleep(.5)
    raise RuntimeError("startup incomplete; read retained logs")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--frontend-only", action="store_true")
    main(frontend_only=parser.parse_args().frontend_only)
