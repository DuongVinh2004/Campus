"""Launch new owned local processes only; no handoff/stop of prior runtimes."""
import hashlib
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

from service_stage6_workspace import ROOT, STATE, BUSINESS, destination, retain, checked
from launch_certificate_demo import listening


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-ordinal", choices=["01", "02", "03"], required=True)
    args = parser.parse_args()
    sys.argv = [sys.argv[0], "start", args.build_ordinal]
    import prepare_service_stage6_frontend as prepare
    frontend, node = prepare.build_tools.FRONTEND, prepare.build_tools.NODE
    guard = checked(frontend / "preserve-build.mjs")
    old_guard = checked(ROOT / "infra/local/rag-fixture/m1_source_guard_20261012_58-repair1.mjs")
    if guard.read_bytes() != old_guard.read_bytes() or not (frontend / ".next/BUILD_ID").is_file():
        raise ValueError("verified new build and unchanged preservation guard required")
    if listening(8004) or listening(3005):
        raise RuntimeError("new port occupied; do not stop the existing owner")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    commands = {
        "frontend": [str(node), "--import", guard.as_uri(), str(ROOT / "apps/web/node_modules/next/dist/bin/next"),
                     "start", str(frontend), "-H", "127.0.0.1", "-p", "3005"],
        "api": [sys.executable, "-B", "-u", str(ROOT / "scripts/run_service_stage6.py"), "--frontend", "3005"],
    }
    processes = {}
    environment = prepare.environment()
    for name, command in commands.items():
        with destination(f"{stamp}-{name}.log").open("xb") as log:
            processes[name] = subprocess.Popen(command, cwd=ROOT, env=environment, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT, creationflags=0x08000000)
    receipt = {"commands": commands, "pids": {k: p.pid for k, p in processes.items()}, "ports": [8004, 3005],
        "url": "http://localhost:8004/login", "database": str(BUSINESS), "owns_paid_ledger": False,
        "existing_writer": "http://127.0.0.1:8003", "prior_runtimes_preserved": True,
        "guard_sha256": hashlib.sha256(guard.read_bytes()).hexdigest(), "build_id": (frontend / ".next/BUILD_ID").read_text()}
    retain(f"{stamp}-launch.json", receipt)
    for _ in range(40):
        if any(p.poll() is not None for p in processes.values()):
            raise RuntimeError("new runtime exited; inspect retained logs/receipt")
        if listening(8004) and listening(3005):
            print(json.dumps(receipt)); return
        time.sleep(.5)
    raise RuntimeError("startup incomplete; retain all logs and inspect")


if __name__ == "__main__":
    main()
