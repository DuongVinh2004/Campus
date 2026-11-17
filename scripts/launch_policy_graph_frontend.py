"""Start only the new graph UI on loopback3004; retain frontend3003 and all builds."""
import hashlib
import json
import os
import subprocess
import sys
import time

from build_policy_graph import ROOT, destination
from certificate_stage1_workspace import checked
from launch_multi_agent import listening


def main():
    from prepare_policy_graph_frontend import build_tools, environment
    frontend = checked(build_tools.FRONTEND)
    guard = checked(frontend/"preserve-build.mjs")
    original = checked(ROOT/"infra/local/rag-fixture/m1_source_guard_20261012_58-repair1.mjs")
    if guard.read_bytes() != original.read_bytes() or not (frontend/".next/BUILD_ID").is_file() or listening(3004):
        raise ValueError("fresh verified graph frontend/guard and free port3004 required")
    command = [str(build_tools.NODE), "--import", guard.as_uri(),
        str(ROOT/"apps/web/node_modules/next/dist/bin/next"), "start", str(frontend), "-H", "127.0.0.1", "-p", "3004"]
    with destination("frontend-runtime-01.log").open("xb") as log:
        process = subprocess.Popen(command, cwd=frontend, env=environment(), stdin=subprocess.DEVNULL,
            stdout=log, stderr=subprocess.STDOUT, creationflags=0x08000000)
    receipt = {"pid": process.pid, "command": command, "port": 3004, "guard_sha256": hashlib.sha256(guard.read_bytes()).hexdigest(),
        "build_id": (frontend/".next/BUILD_ID").read_text(), "old_frontend3003_preserved": True, "cwd": str(frontend)}
    with destination("frontend-launch-01.json").open("x", encoding="utf-8") as out:
        json.dump(receipt, out, indent=2)
    for _ in range(30):
        if listening(3004):
            print(json.dumps(receipt)); return
        if process.poll() is not None:
            raise RuntimeError("graph frontend exited; inspect retained log")
        time.sleep(.5)
    raise RuntimeError("graph frontend not ready; inspect retained receipt/log")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8"); main()
