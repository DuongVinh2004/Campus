"""Launch the verified session02 snapshot on the established candidate ports.

Existing owners must be explicitly inspected/handed off before running this;
this script never stops a process or overwrites any previous receipt/log.
"""
import hashlib
import json
import socket
import subprocess
import sys
import time

from unified_ai_runtime_probe import ROOT, checked, retain
from unified_ai_session02_preflight import STATE
import prepare_unified_ai_session02 as prepare

FINAL_BUILD = len(sys.argv) == 2 and sys.argv[1] == "start03"
if len(sys.argv) > 1 and not FINAL_BUILD:
    raise ValueError("only the explicit start03 handoff is supported")
BUILD_NUMBER = "03" if FINAL_BUILD else "02"
LAUNCH_NUMBER = "02" if FINAL_BUILD else "01"
FRONTEND = checked(STATE / ("frontend" + BUILD_NUMBER + "/acceptance-20261012-58-frontend-repair1-local-repair2"))


def listening(port):
    with socket.socket() as connection:
        connection.settimeout(1)
        return connection.connect_ex(("127.0.0.1",port)) == 0


if __name__ == "__main__":
    output = checked(STATE / ("runtime-launch-" + LAUNCH_NUMBER + ".json"))
    logs = [checked(STATE / ("api-" + LAUNCH_NUMBER + ".log")),checked(STATE / ("frontend-" + LAUNCH_NUMBER + ".log"))]
    if output.exists() or any(p.exists() for p in logs) or listening(8006) or listening(3006):
        raise RuntimeError("retained output or occupied candidate port; inspect, never replace")
    build = json.loads(checked(STATE / ("frontend-build-" + BUILD_NUMBER + ".json")).read_text(encoding="utf-8"))
    guard = checked(FRONTEND / "preserve-build.mjs")
    original = checked(ROOT / "infra/local/rag-fixture/m1_source_guard_20261012_58-repair1.mjs")
    if build["exit_code"] != 0 or guard.read_bytes() != original.read_bytes():
        raise ValueError("successful build and unchanged guard required")
    prepare.build_tools.FRONTEND = FRONTEND
    env = prepare.environment()
    build_id = (FRONTEND / ".next/BUILD_ID").read_text().strip()
    env["C247_UNIFIED_BUILD_ID"] = build_id
    commands = {
        "frontend":[str(prepare.build_tools.NODE),"--import",guard.as_uri(),str(ROOT / "apps/web/node_modules/next/dist/bin/next"),"start",str(FRONTEND),"-H","127.0.0.1","-p","3006"],
        "api":[sys.executable,"-B","-u",str(ROOT / "scripts/unified_ai_candidate.py"),"api"],
    }
    processes = {}
    for name,command in commands.items():
        with checked(STATE / (name+"-" + LAUNCH_NUMBER + ".log")).open("xb") as log:
            processes[name] = subprocess.Popen(command,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,
                stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000)
    retain(output,{"url":"http://localhost:8006/login","commands":commands,"wrapper_pids":{name:p.pid for name,p in processes.items()},
        "build_id":build_id,"frontend":str(FRONTEND),"guard_sha256":hashlib.sha256(guard.read_bytes()).hexdigest(),
        "database":"infra/local/unified-ai-20261014-01/business-candidate01.sqlite3","database_backup":"business-before-01.sqlite3",
        "paid_writer":"existing8003_only","new_paid_writer":False,"prior_snapshots_preserved":True})
    for _ in range(40):
        if any(p.poll() is not None for p in processes.values()):
            raise RuntimeError("new process exited; retain and inspect logs")
        if listening(8006) and listening(3006):
            print(build_id); break
        time.sleep(.5)
    else:
        raise RuntimeError("startup not verified; no cleanup/stop performed")
