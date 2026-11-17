"""Launch verified quota transition after the previous owners release ports.

This launcher never terminates a process, deletes state or creates a second
writer. Explicit ownership inspection and handoff precede invoking it.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

from multi_agent_workspace import ROOT, STATE, checked, retain
from multi_agent_live_resources import AUTHORIZATION, CALL_EXTENSION, STAGE5_CALL_EXTENSION, NATIVE_PRIOR, NATIVE_STATE, load_authorization, paid_view
from launch_multi_agent import listening


def spawn(name, command, stamp, env):
    with checked(STATE / f"{stamp}-{name}.log", STATE).open("xb") as log:
        proc = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
            stdout=log, stderr=subprocess.STDOUT, creationflags=0x08000000)
    return proc.pid


def main(*, api_only=False, policy_graph_id=None, graph_frontend_port=None):
    authorization = load_authorization()
    paid = paid_view()  # Strict historical continuation, read-only; no Gateway.
    if api_only:
        if listening(8003) or not all(listening(port) for port in (8000, 3003, 18081, 18082)):
            raise RuntimeError("API port must be released; retain proxy/frontend/native owners")
    elif any(listening(port) for port in (8000, 8003, 18081, 18082)) or not listening(3003):
        raise RuntimeError("verified prior owners must release exact ports; retain frontend3003")
    if NATIVE_STATE.exists() and not api_only:
        raise RuntimeError("native transition namespace must be new")
    env = {key: value for key, value in os.environ.items() if not any(
        marker in key.upper() for marker in ("TOKEN", "KEY", "SECRET", "PASSWORD"))}
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    commands = {
        "native": [str(ROOT / ".venv/Scripts/python.exe"), "-B", "-u", str(ROOT / "scripts/serve_rag_models.py"),
                   "--state", str(NATIVE_STATE), "--predecessor", str(NATIVE_PRIOR), "--resource-authorization", str(AUTHORIZATION)],
        "api": [sys.executable, "-B", "-u", str(ROOT / "scripts/run_multi_agent.py"), "--mode", "live", "--frontend", "3003"],
        "public-proxy": [sys.executable, "-B", "-u", str(ROOT / "scripts/run_public_multi_proxy.py")],
    }
    if policy_graph_id is not None:
        if not api_only:
            raise ValueError("stage5 graph activation requires retained native/proxy/frontend owners")
        commands["api"].extend(["--policy-graph", policy_graph_id])
    if graph_frontend_port is not None:
        if graph_frontend_port != 3004 or policy_graph_id is None or not listening(3004):
            raise ValueError("verified graph frontend3004 required")
        commands["api"][commands["api"].index("--frontend")+1] = "3004"
    pids = {}
    if not api_only:
        pids["native"] = spawn("native", commands["native"], stamp, env)
        for _ in range(90):
            if listening(18081) and listening(18082):
                break
            time.sleep(.5)
        else:
            retain(STATE / f"{stamp}-launch-incomplete.json", {"commands": commands, "owned_pids": pids, "failure": "native_not_ready"})
            raise RuntimeError("native transition not ready; read retained logs")
    for name in (("api",) if api_only else ("api", "public-proxy")):
        pids[name] = spawn(name, commands[name], stamp, env)
    retain(STATE / f"{stamp}-live-launch.json", {"commands": commands, "owned_pids": pids,
        "mode": "live", "api_only": api_only, "url": "http://localhost:8003/login", "legacy_url": "http://localhost:8000/login",
        "authorization_sha256": hashlib.sha256(AUTHORIZATION.read_bytes()).hexdigest(),
        "paid_caps": {"usd": paid["hard_cap_usd"], "calls": paid["call_cap"]}, "native_caps": authorization["native_caps"],
        "call_extension_sha256": hashlib.sha256(CALL_EXTENSION.read_bytes()).hexdigest() if CALL_EXTENSION.exists() else None,
        "stage5_call_extension_sha256": hashlib.sha256(STAGE5_CALL_EXTENSION.read_bytes()).hexdigest() if STAGE5_CALL_EXTENSION.exists() else None,
        "policy_graph_id": policy_graph_id, "graph_frontend_port": graph_frontend_port,
        "frontend3003_preserved": True, "certificate8002_frontend3002_preserved": True,
        "business_and_history_preserved": True, "paid_writer": "api8003_only", "automatic_expiry": False})
    for _ in range(60):
        if listening(8003) and listening(8000):
            print(json.dumps({"url": "http://localhost:8003/login", "mode": "live", "owned_pids": pids}), flush=True)
            return
        time.sleep(.5)
    raise RuntimeError("startup incomplete; read retained logs")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-only", action="store_true")
    parser.add_argument("--policy-graph", default=None)
    parser.add_argument("--graph-frontend", type=int, choices=[3004], default=None)
    args = parser.parse_args()
    main(api_only=args.api_only, policy_graph_id=args.policy_graph, graph_frontend_port=args.graph_frontend)
