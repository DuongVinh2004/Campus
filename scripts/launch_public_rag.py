"""Start the local HUCE chat stack in hidden background processes, preserving all state."""
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.prepare_public_rag_frontend import NODE, SOURCE
from scripts.public_rag_retrieval import load_public_hybrid_store
from scripts.run_public_rag import CAMPUS, CORPUS, ROOT, STATE, TENANT, checked


def listening(port):
    with socket.socket() as client:
        client.settimeout(1)
        return client.connect_ex(("127.0.0.1", port)) == 0


def main():
    frontend = checked(STATE / "frontend11")
    if not (frontend / ".next/BUILD_ID").is_file():
        raise RuntimeError("build frontend11 before launch")
    if any(listening(port) for port in (8000, 3000, 8001)):
        raise RuntimeError("a public/advanced runtime is already listening; preserve it and inspect paid-ledger ownership")
    # Validate prerequisites before spawning either child. Runtime identities
    # are checked again by the adapters before any embedding or rerank POST.
    load_public_hybrid_store(CORPUS, tenant_id=TENANT, campus_id=CAMPUS,
        faq_directory=ROOT / "data/huce-faq-20261013")
    if not all(listening(port) for port in (18081, 18082)):
        raise RuntimeError("start the bounded BGE model services on 127.0.0.1:18081/18082 with the retained native ledger")
    checked(STATE).mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    env = {k: v for k, v in os.environ.items() if not any(part in k.upper() for part in ("TOKEN", "SECRET", "PASSWORD", "API_KEY"))}
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1",
        NODE_PATH=str(SOURCE / "node_modules"), C247_M1_FRONTEND=str(frontend), NEXT_TELEMETRY_DISABLED="1",
        NODE_ENV="production", USERPROFILE=str(frontend), APPDATA=str(frontend / "appdata"),
        LOCALAPPDATA=str(frontend / "localappdata"), TEMP=str(frontend / "temp"), TMP=str(frontend / "temp"))
    commands = {
        "frontend": [str(NODE), "--import", (frontend / "preserve-build.mjs").as_uri(),
            str(SOURCE / "node_modules/next/dist/bin/next"), "start", str(frontend), "-H", "127.0.0.1", "-p", "3000"],
        "api": [sys.executable, "-B", "-u", str(ROOT / "scripts/run_public_rag.py")],
    }
    pids = {}
    for name, command in commands.items():
        with checked(STATE / f"{stamp}-{name}.log").open("xb") as log:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT, creationflags=0x08000000)
        pids[name] = process.pid
    with checked(STATE / f"{stamp}-launch.json").open("x", encoding="utf-8") as stream:
        json.dump({"commands": commands, "owned_pids": pids, "url": "http://localhost:8000/chat",
            "data_preserved": True, "automatic_expiry": False}, stream, indent=2)
    for _ in range(20):
        if listening(8000) and listening(3000):
            print("HUCE chat: http://localhost:8000/chat")
            return
        time.sleep(.5)
    raise RuntimeError("startup incomplete; inspect the retained launch logs")


if __name__ == "__main__":
    main()
