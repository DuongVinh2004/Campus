"""Exact API-only local handoff. Frontend, writer, native and all data retained."""
import json
import sqlite3
import subprocess
import sys
import time

from unified_ai_runtime_probe import ROOT, checked, retain, http
from handoff_unified_ai_session04 import windows_read
from verify_unified_ai_candidate import database_digest
import prepare_unified_ai_session04 as prepare

STATE=checked(ROOT / "infra/local/unified-ai-20261014-05")
OUTPUT=checked(STATE / "handoff01")
DATABASE=checked(ROOT / "infra/local/unified-ai-20261014-01/business-candidate01.sqlite3")
ACTOR_DATABASE=checked(STATE / "actor-state.sqlite3")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if OUTPUT.exists() or ACTOR_DATABASE.exists():
        raise FileExistsError("retain prior receipt/store; do not rerun or overwrite")
    from verify_unified_ai_session05 import tests
    validation=json.loads(checked(STATE / "validation-01.json").read_text(encoding="utf-8"))
    assert validation["compatibility_passed"] and tests()["all_passed"]
    preflight=json.loads(checked(STATE / "preflight.json").read_text(encoding="utf-8"))
    observed=windows_read();owners={r["LocalPort"]:r["OwningProcess"] for r in observed["listeners"]}
    assert owners=={3006:22800,8006:18264,8003:14208,18081:6132,18082:6132},"ownership changed; do not stop"
    old_processes={p["ProcessId"]:p for p in preflight["ownership"]["processes"]}
    processes={p["ProcessId"]:p for p in observed["processes"]}
    assert processes==old_processes,"process identity changed; retain existing runtime"
    assert str(ROOT / "scripts/unified_ai_candidate.py") in processes[18264]["CommandLine"]
    code,current=http(8006,"/v1/assistant/runtime")
    assert code==200 and current==preflight["runtime"]
    assert database_digest(DATABASE)==database_digest(checked(STATE / "business-before.sqlite3")),"business rows changed; inspect"
    with sqlite3.connect(DATABASE.as_uri()+"?mode=ro",uri=True) as connection:
        assert all(json.loads(row[0])["state"]=="finished" for row in connection.execute("SELECT record FROM unified_baseline_session")),"active measurement; retain runtime"
    guard=checked(prepare.FRONTEND / "preserve-build.mjs")
    assert guard.read_bytes()==checked(ROOT / "infra/local/rag-fixture/m1_source_guard_20261012_58-repair1.mjs").read_bytes()
    for name in ("src/features/assistance/WorkflowDefinitionPanel.tsx","src/features/assistance/AssistanceContextPanel.tsx",
                 "src/features/documents/CertificateWorkspace.tsx","src/features/documents/ServiceWorkspace.tsx"):
        assert checked(ROOT / "apps/web" / name).read_bytes()==checked(prepare.FRONTEND / name).read_bytes()
    OUTPUT.mkdir(exist_ok=False)
    retain(OUTPUT / "preflight.json",{"observed":observed,"old_runtime":current,"exact_stopped_pids":[18264],
        "frontend_retained_pid":22800,"writer_retained_pid":14208,"native_retained_pid":6132,
        "state_database":str(ACTOR_DATABASE),"business_database":str(DATABASE)})
    created=processes[18264]["CreatedUtc"]
    command=("$ErrorActionPreference='Stop'; $p=Get-CimInstance Win32_Process -Filter 'ProcessId=18264'; "
        "if ($null -eq $p -or $p.CreationDate.ToUniversalTime().ToString('o') -ne '"+created+"') { throw 'Process identity changed' }; Stop-Process -Id 18264 -ErrorAction Stop")
    subprocess.run(["powershell.exe","-NoProfile","-Command",command],check=True,timeout=15)
    assert not any(r["LocalPort"]==8006 for r in windows_read()["listeners"]),"port acquired by another process"
    env=prepare.environment()
    env["C247_UNIFIED_BUILD_ID"]=current["frontend_build_id"]
    env["C247_UNIFIED_STATE_DB"]=str(ACTOR_DATABASE)
    args=[sys.executable,"-B","-u",str(ROOT / "scripts/unified_ai_candidate.py"),"api"]
    with checked(OUTPUT / "api.log").open("xb") as log:
        process=subprocess.Popen(args,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000)
    retain(OUTPUT / "launch.json",{"command":args,"launcher_pid":process.pid,"state_database":str(ACTOR_DATABASE),
        "frontend_build_id":current["frontend_build_id"],"new_paid_writer":False,"frontend_restarted":False})
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        if process.poll() is not None:
            raise RuntimeError("startup failed; retain files/logs, do not automatically reset")
        code,runtime=http(8006,"/v1/assistant/runtime")
        if code==200 and runtime.get("runtime")=="unified-local-v5" and runtime.get("storage_profile",{}).get("actor_state")=="sqlite_internal":
            retain(OUTPUT / "ready.json",{"runtime":runtime,"ownership":windows_read(),"old_files_retained":True})
            print(json.dumps({"url":"http://localhost:8006/login","runtime":runtime}))
            return
        time.sleep(.5)
    raise RuntimeError("runtime not ready; retain processes and evidence")


if __name__=="__main__":
    main()
