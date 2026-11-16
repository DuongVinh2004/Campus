"""Launch only fresh owned certificate processes; leave existing RAG untouched."""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone

from certificate_stage1_workspace import ROOT, STATE, checked, retain
from prepare_certificate_frontend import FRONTEND, NODE, SOURCE, runtime_environment


def listening(port):
    with socket.socket() as sock:
        sock.settimeout(.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def main():
    if any(listening(port) for port in (8002, 3002)):
        raise RuntimeError("certificate port occupied; inspect ownership without stopping processes")
    if not (FRONTEND / ".next/BUILD_ID").is_file():
        raise RuntimeError("prepare and build the isolated frontend first")
    # A missing RAG is surfaced by the proxy; the business flow remains available.
    rag_available = listening(8000)
    commands = {
        "frontend": [str(NODE), "--import", (FRONTEND / "preserve-build.mjs").as_uri(),
            str(SOURCE / "node_modules/next/dist/bin/next"), "start", str(FRONTEND), "-H", "127.0.0.1", "-p", "3002"],
        "api": [sys.executable, "-B", "-u", str(ROOT / "scripts/run_certificate_demo.py")],
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    pids = {}
    for name, command in commands.items():
        path = checked(STATE / f"{stamp}-{name}.log", STATE)
        with path.open("xb") as log:
            process = subprocess.Popen(command, cwd=ROOT, env=runtime_environment(), stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT, creationflags=0x08000000)
        pids[name] = process.pid
    retain(STATE / f"{stamp}-launch.json", {"commands": commands, "owned_pids": pids,
        "url": "http://localhost:8002/login", "database": str(STATE / "demo.sqlite3"),
        "rag_proxy": "http://127.0.0.1:8000", "rag_available_at_launch": rag_available,
        "paid_ledger_initialized": False, "data_preserved": True})
    for _ in range(20):
        if listening(8002) and listening(3002):
            print("Certificate demo: http://localhost:8002/login")
            return
        time.sleep(.5)
    raise RuntimeError("startup incomplete; inspect retained logs")


if __name__ == "__main__":
    main()
