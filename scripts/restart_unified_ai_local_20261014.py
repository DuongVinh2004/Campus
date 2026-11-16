"""Restart the retained local candidate and its existing RAG runtime.

No process termination, rebuild, quota change or data reset. All receipts and
logs use a new exact directory; old namespaces remain untouched.
"""
import hashlib
import json
import os
import socket
import subprocess
import sys
import time

from unified_ai_runtime_probe import ROOT, checked, retain
import prepare_unified_ai_session02 as prepare

OUTPUT = checked(ROOT / "infra/local/unified-ai-restart-20261014-01")
SNAPSHOT = checked(ROOT / "infra/local/unified-ai-20261014-02/frontend03/acceptance-20261012-58-frontend-repair1-local-repair2")
NATIVE = checked(ROOT / "infra/local/rag-advanced-models-20261013-11")
PRIOR_NATIVE = checked(ROOT / "infra/local/rag-advanced-models-20261013-10")


def listening(port):
    with socket.socket() as connection:
        connection.settimeout(1)
        return connection.connect_ex(("127.0.0.1",port)) == 0


def spawn(name, command, env):
    with checked(OUTPUT / (name+".log")).open("xb") as log:
        return subprocess.Popen(command,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,
            stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000)


def ready(processes, ports, seconds):
    deadline = time.monotonic()+seconds
    while time.monotonic() < deadline:
        if any(p.poll() is not None for p in processes):
            raise RuntimeError("process exited; inspect retained logs, no automatic cleanup")
        if all(listening(port) for port in ports):
            return
        time.sleep(.5)
    raise RuntimeError("startup timeout; processes/logs retained for inspection")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if OUTPUT.exists() or NATIVE.exists():
        raise FileExistsError("restart namespaces already exist; inspect before another attempt")
    ports = (3006,8006,8003,8000,18081,18082)
    if any(listening(port) for port in ports):
        raise RuntimeError("an existing listener owns a required port; no duplicate launch")
    build = json.loads(checked(ROOT / "infra/local/unified-ai-20261014-02/frontend-build-03.json").read_text(encoding="utf-8"))
    guard = checked(SNAPSHOT / "preserve-build.mjs")
    assert build["exit_code"] == 0
    assert guard.read_bytes() == checked(ROOT / "infra/local/rag-fixture/m1_source_guard_20261012_58-repair1.mjs").read_bytes()
    for file in ["src/features/documents/ServiceWorkspace.tsx","src/features/assistance/BaselineRecorder.tsx",
                 "src/features/assistance/AssistanceContextPanel.tsx","src/lib/api/client.ts","src/lib/unified-ai-contracts.ts"]:
        assert checked(ROOT / "apps/web" / file).read_bytes() == checked(SNAPSHOT / file).read_bytes(), "source differs from verified snapshot: " + file
    database = checked(ROOT / "infra/local/unified-ai-20261014-01/business-candidate01.sqlite3")
    assert database.is_file() and PRIOR_NATIVE.is_dir()
    from multi_agent_live_resources import AUTHORIZATION, paid_view, native_view
    from run_multi_agent import headroom
    from campus247.application.multi_agent.contracts import MultiAgentPolicy
    paid_before, native_before = paid_view(), native_view()
    if not headroom(MultiAgentPolicy()):
        raise RuntimeError("existing quota cannot admit live runtime; no quota changes")
    OUTPUT.mkdir(exist_ok=False)
    git = subprocess.run(["git","status","--porcelain=v1"],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace")
    assert git.returncode == 0
    retain(OUTPUT / "preflight.json",{"git_status":git.stdout,"paid_before":paid_before,"native_before":native_before,
        "database":str(database),"snapshot":str(SNAPSHOT),"ports_empty":list(ports),"native_predecessor":str(PRIOR_NATIVE),
        "native_new_namespace":str(NATIVE),"guard_sha256":hashlib.sha256(guard.read_bytes()).hexdigest()})
    prepare.build_tools.FRONTEND = SNAPSHOT
    env = prepare.environment()
    build_id = checked(SNAPSHOT / ".next/BUILD_ID").read_text().strip()
    env["C247_UNIFIED_BUILD_ID"] = build_id
    commands = {
        "frontend":[str(prepare.build_tools.NODE),"--import",guard.as_uri(),str(ROOT / "apps/web/node_modules/next/dist/bin/next"),"start",str(SNAPSHOT),"-H","127.0.0.1","-p","3006"],
        "api":[sys.executable,"-B","-u",str(ROOT / "scripts/unified_ai_candidate.py"),"api"],
        "native":[sys.executable,"-B","-u",str(ROOT / "scripts/serve_rag_models.py"),"--state",str(NATIVE),"--predecessor",str(PRIOR_NATIVE),"--resource-authorization",str(checked(AUTHORIZATION))],
        "rag-api":[str(ROOT / "infra/local/rag-fixture/.venv/Scripts/python.exe"),"-B","-u",str(ROOT / "scripts/run_multi_agent.py"),"--mode","live","--frontend","3004","--policy-graph","huce-policy-development-v1"],
    }
    processes = {name:spawn(name,commands[name],env) for name in ["frontend","api"]}
    retain(OUTPUT / "candidate-launch.json",{"commands":{name:commands[name] for name in processes},
        "wrapper_pids":{name:p.pid for name,p in processes.items()},"build_id":build_id,"url":"http://localhost:8006/login"})
    ready(list(processes.values()),(3006,8006),25)
    print("Candidate ready at http://localhost:8006/login",flush=True)
    runtime_env = {key:value for key,value in os.environ.items() if not any(part in key.upper() for part in ("TOKEN","KEY","SECRET","PASSWORD"))}
    runtime_env.update(PYTHONDONTWRITEBYTECODE="1",PYTHONIOENCODING="utf-8",PYTHONUNBUFFERED="1")
    processes["native"] = spawn("native",commands["native"],runtime_env)
    retain(OUTPUT / "native-launch.json",{"command":commands["native"],"wrapper_pid":processes["native"].pid,"quota_reset":False})
    ready([processes["native"]],(18081,18082),55)
    processes["rag-api"] = spawn("rag-api",commands["rag-api"],runtime_env)
    retain(OUTPUT / "rag-launch.json",{"command":commands["rag-api"],"wrapper_pid":processes["rag-api"].pid,"paid_writer":"api8003_only","quota_change":False})
    ready(list(processes.values()),(8003,8006,3006,18081,18082),35)
    print("Local candidate and retained RAG runtime ready; no model dispatch",flush=True)


if __name__ == "__main__":
    main()
