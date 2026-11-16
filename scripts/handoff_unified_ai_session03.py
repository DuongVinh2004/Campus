"""Exact local frontend/API handoff; keep writer8003, ledgers and old files.

Run only after the fresh snapshot and tests pass. Revalidate Windows process
identity and every source file before stopping the two named local listeners.
No pattern-based termination, deletion, quota changes or model calls.
"""
import hashlib
import json
import subprocess
import sys
import time

import prepare_unified_ai_session03 as prepare
from unified_ai_runtime_probe import ROOT, checked, retain, http
from verify_unified_ai_candidate import database_digest

OUTPUT = checked(ROOT / "infra/local/unified-ai-20261014-03/handoff01")
OLD_SNAPSHOT = checked(ROOT / "infra/local/unified-ai-20261014-02/frontend03/acceptance-20261012-58-frontend-repair1-local-repair2")
DATABASE = checked(ROOT / "infra/local/unified-ai-20261014-01/business-candidate01.sqlite3")


def windows_read():
    command = "$ErrorActionPreference='Stop'; $l=@(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object LocalPort -in 3006,8006,8003,18081,18082 | Select-Object LocalPort,OwningProcess); $ids=@($l | Select-Object -ExpandProperty OwningProcess); $p=@(Get-CimInstance Win32_Process | Where-Object ProcessId -in $ids | Select-Object ProcessId,ParentProcessId,CommandLine,@{Name='CreatedUtc';Expression={$_.CreationDate.ToUniversalTime().ToString('o')}}); @{listeners=$l;processes=$p} | ConvertTo-Json -Depth 5"
    result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", command], capture_output=True, text=True, check=True, timeout=15)
    return json.loads(result.stdout)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if OUTPUT.exists():
        raise FileExistsError("handoff receipt/logs already exist; inspect, never rerun")
    build = json.loads(checked(prepare.STATE / "frontend-build-01.json").read_text(encoding="utf-8"))
    tests = json.loads(checked(prepare.STATE / "frontend-tests-command-01.json").read_text(encoding="utf-8"))
    assert build["exit_code"] == tests["exit_code"] == 0
    guard = checked(prepare.FRONTEND / "preserve-build.mjs")
    assert guard.read_bytes() == checked(OLD_SNAPSHOT / "preserve-build.mjs").read_bytes()
    for name in ("src/features/assistance/AssistanceContextPanel.tsx", "src/features/assistance/WorkflowDefinitionPanel.tsx",
                 "src/features/assistance/BaselineRecorder.tsx", "src/features/documents/ServiceWorkspace.tsx"):
        assert checked(ROOT / "apps/web" / name).read_bytes() == checked(prepare.FRONTEND / name).read_bytes(), name
    observed = windows_read()
    owners = {r["LocalPort"]: r["OwningProcess"] for r in observed["listeners"]}
    assert owners == {3006:15420,8006:16688,8003:14208,18081:6132,18082:6132}, "owners changed; do not stop"
    processes = {p["ProcessId"]: p for p in observed["processes"]}
    assert str(OLD_SNAPSHOT) in processes[15420]["CommandLine"]
    assert "next" in processes[15420]["CommandLine"] and "-p 3006" in processes[15420]["CommandLine"]
    assert str(ROOT / "scripts/unified_ai_candidate.py") in processes[16688]["CommandLine"]
    code, runtime = http(8006, "/v1/assistant/runtime")
    assert code == 200 and runtime["frontend_build_id"] == checked(OLD_SNAPSHOT / ".next/BUILD_ID").read_text().strip()
    for alias in ("SV001", "SV024", "OF001", "OF002"):
        code, session = http(8006, "/v1/auth/demo-login", body={"account": alias}); assert code == 200
        code, sessions = http(8006, "/v1/assistant/baseline/sessions", session["token"]); assert code == 200
        assert not any(s["state"] != "finished" for s in sessions["items"]), "active measurement; retain old runtime"
    OUTPUT.mkdir(exist_ok=False)
    retain(OUTPUT / "preflight.json", {"observed":observed,"old_runtime":runtime,"database_tables":database_digest(DATABASE),
        "old_snapshot":str(OLD_SNAPSHOT),"new_snapshot":str(prepare.FRONTEND),"writer8003_retained":True,
        "guard_sha256":hashlib.sha256(guard.read_bytes()).hexdigest(),"exact_stopped_pids":[15420,16688]})
    # Recheck creation times in the same native shell as the exact stop. PIDs
    # cannot authorize stopping a reused or differently owned process.
    for pid in (15420,16688):
        created = processes[pid]["CreatedUtc"]
        command = ("$ErrorActionPreference='Stop'; $p=Get-CimInstance Win32_Process -Filter 'ProcessId=" + str(pid) + "'; "
                   "if ($null -eq $p -or $p.CreationDate.ToUniversalTime().ToString('o') -ne '" + created + "') { throw 'Process identity changed' }; "
                   "Stop-Process -Id " + str(pid) + " -ErrorAction Stop")
        subprocess.run(["powershell.exe","-NoProfile","-Command",command],check=True,timeout=15)
    after_stop = windows_read()
    assert not any(r["LocalPort"] in (3006,8006) for r in after_stop["listeners"]), "port acquired by another owner"
    env = prepare.environment()
    build_id = checked(prepare.FRONTEND / ".next/BUILD_ID").read_text().strip()
    env["C247_UNIFIED_BUILD_ID"] = build_id
    commands = {
        "frontend": [str(prepare.tools.NODE),"--import",guard.as_uri(),str(ROOT / "apps/web/node_modules/next/dist/bin/next"),"start",str(prepare.FRONTEND),"-H","127.0.0.1","-p","3006"],
        "api": [sys.executable,"-B","-u",str(ROOT / "scripts/unified_ai_candidate.py"),"api"],
    }
    launched = {}
    for name, command in commands.items():
        with checked(OUTPUT / (name+".log")).open("xb") as log:
            launched[name] = subprocess.Popen(command,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,
                stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000)
    retain(OUTPUT / "launch.json", {"commands":commands,"pids":{name:p.pid for name,p in launched.items()},
        "build_id":build_id,"database":str(DATABASE),"old_files_retained":True,"new_paid_writer":False})
    deadline = time.monotonic()+30
    while time.monotonic() < deadline:
        if any(p.poll() is not None for p in launched.values()):
            raise RuntimeError("candidate startup failed; retain logs, do not clean or automatically reset")
        code, current = http(8006,"/v1/assistant/runtime")
        if code == 200 and current.get("frontend_build_id") == build_id:
            retain(OUTPUT / "ready.json", {"runtime":current,"ownership":windows_read(),"writer8003_retained":True})
            print(json.dumps({"url":"http://localhost:8006/login","build_id":build_id}))
            return
        time.sleep(.5)
    raise RuntimeError("candidate not ready; retain owned processes and logs")


if __name__ == "__main__":
    main()
