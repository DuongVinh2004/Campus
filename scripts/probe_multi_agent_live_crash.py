"""An exact task-owned API crash drill using one new synthetic conversation.

Never use during an evaluation batch. No business action is dispatched. Only
the PID and launcher from the calling chat's exact receipt may be terminated.
Provider dispatch/outcome is unknown even if its reservation is visible.
"""
import argparse
import ctypes
import json
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx

from multi_agent_workspace import ROOT, STATE, checked, retain
from multi_agent_live_resources import PAID_STATE, paid_view


def record_for(conversation):
    path = checked(STATE / "agent-runs.sqlite3", STATE)
    with sqlite3.connect(path.as_uri()+"?mode=ro", uri=True) as db:
        row = db.execute("SELECT id,version,status,lease_until,record FROM agent_run WHERE conversation=?", (conversation,)).fetchone()
    if row:
        return {"id": row[0], "version": row[1], "status": row[2], "lease_until": row[3], "record": json.loads(row[4])}


def crash(output, launch, pid):
    output, launch = checked(output, STATE), checked(launch, STATE)
    if output.exists():
        raise FileExistsError("retain earlier drill")
    receipt = json.loads(launch.read_text("utf-8"))
    launcher = receipt["owned_pids"]["api"]
    # Numeric PIDs only; no interpolated user path or shell executable text.
    command = f"Get-CimInstance Win32_Process -Filter 'ProcessId={pid}' | Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress"
    ownership = json.loads(subprocess.check_output(["powershell", "-NoProfile", "-Command", command], encoding="utf-8"))
    expected = str(ROOT / "scripts/run_multi_agent.py")
    if ownership["ParentProcessId"] != launcher or expected not in ownership["CommandLine"] or "--mode live --frontend 3003" not in ownership["CommandLine"]:
        raise ValueError("exact current chat runtime ownership required")
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_bool, ctypes.c_uint32]
    api.OpenProcess.restype = ctypes.c_void_p
    api.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    api.CloseHandle.argtypes = [ctypes.c_void_p]
    # The handle keeps this exact process identity even if a PID is reused.
    handle = api.OpenProcess(0x0001 | 0x1000 | 0x00100000, False, pid)
    if not handle:
        raise OSError("owned process handle unavailable")
    before = paid_view()
    stream_result = {}
    try:
        with httpx.Client(base_url="http://127.0.0.1:8003", trust_env=False, timeout=45) as client:
            health = client.get("/health/live"); health.raise_for_status()
            assert health.json()["owns_paid_ledger"] is True
            login = client.post("/v1/auth/demo-login", json={"account": "SV001"}); login.raise_for_status()
            headers = {"Authorization": "Bearer "+login.json()["token"]}
            created = client.post("/v1/conversations", headers=headers, json={}); created.raise_for_status()
            cid = created.json()["id"]
            def request_once():
                try:
                    response = client.post(f"/v1/conversations/{cid}/messages:stream", headers=headers,
                        json={"content": "Xin giấy xác nhận sinh viên bắt đầu thế nào và nhận ở đâu?"})
                    stream_result["http_status"] = response.status_code
                except httpx.HTTPError as failure:
                    stream_result["error_type"] = type(failure).__name__
            worker = threading.Thread(target=request_once, daemon=True)
            worker.start()
            deadline, found = time.monotonic()+20, None
            ordinal = before["calls"]+1
            reservation = checked(PAID_STATE / f"provider-{ordinal:05d}-reservation.json")
            result = checked(PAID_STATE / f"provider-{ordinal:05d}-result.json")
            while time.monotonic() < deadline:
                value = record_for(cid)
                if value and value["record"].get("pending") and reservation.exists() and not result.exists():
                    found = value
                    if not api.TerminateProcess(handle, 1):
                        raise OSError("owned API termination failed")
                    break
                if not worker.is_alive():
                    break
                time.sleep(.02)
            worker.join(timeout=5)
        if not found:
            raise RuntimeError("no crash injected; keep completed synthetic request")
        after = paid_view()
        retained = record_for(cid)
        assert ordinal in after["unsettled_attempts_retained"] and retained["record"]["pending"]
        retain(output, {"mode": "actual_process_crash_after_durable_model_and_provider_reservation",
            "ownership": ownership, "launch_receipt": str(launch), "conversation_id": cid, "run_id": found["id"],
            "run_before_crash": found, "run_after_crash": retained, "paid_before": before, "paid_after": after,
            "uncertain_ordinal": ordinal, "provider_dispatch_and_outcome": "unknown", "stream": stream_result,
            "business_actions": 0, "unknown_reservation_refunded": False})
        print(json.dumps({"crash_injected": True, "conversation_id": cid, "run_id": found["id"], "uncertain_ordinal": ordinal}))
    finally:
        api.CloseHandle(handle)


def resume(output, crash_report):
    output, crash_report = checked(output, STATE), checked(crash_report, STATE)
    if output.exists():
        raise FileExistsError("retain earlier proof")
    prior = json.loads(crash_report.read_text("utf-8"))
    before = paid_view()
    cid, rid = prior["conversation_id"], prior["run_id"]
    with httpx.Client(base_url="http://127.0.0.1:8003", trust_env=False, timeout=15) as client:
        login = client.post("/v1/auth/demo-login", json={"account": "SV001"}); login.raise_for_status()
        headers = {"Authorization": "Bearer "+login.json()["token"]}
        path = f"/v1/conversations/{cid}/agent-runs/{rid}"
        old = client.get(path, headers=headers); old.raise_for_status()
        response = client.post(path+":resume", headers=headers, json={"expected_version": old.json()["version"]})
        response.raise_for_status()
        body = response.json()
        assert "AI_AGENT_MODEL_OUTCOME_UNKNOWN" in body["run"]["error_codes"]
        assert body["message"]["run_id"] == rid and body["message"]["response_class"] == "system_error"
        history = client.get(f"/v1/conversations/{cid}/messages?limit=100", headers=headers); history.raise_for_status()
        assert history.json()["items"][-1]["final_result"] == body["message"]
        again = client.post(path+":resume", headers=headers, json={"expected_version": old.json()["version"]})
        assert again.status_code == 409
    after = paid_view()
    assert before == after and prior["uncertain_ordinal"] in after["unsettled_attempts_retained"]
    retain(output, {"passed": True, "mode": "actual_restart_and_resume_after_process_crash", "conversation_id": cid,
        "run_id": rid, "response": body, "stale_resume_http": 409, "history_readback_equal": True,
        "paid_before": before, "paid_after": after, "new_model_calls": 0, "business_actions": 0})
    print("actual crash resume preserves unknown reservation, stable terminal and CAS; no retry")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["crash", "resume"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--launch", type=Path)
    parser.add_argument("--pid", type=int)
    parser.add_argument("--crash-report", type=Path)
    args = parser.parse_args()
    if args.mode == "crash":
        if args.pid is None or args.pid <= 0 or args.launch is None:
            parser.error("exact owned launch receipt and positive PID required")
        crash(args.output, args.launch, args.pid)
    else:
        if args.crash_report is None:
            parser.error("exact retained crash report required")
        resume(args.output, args.crash_report)
