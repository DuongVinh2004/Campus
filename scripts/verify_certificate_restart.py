"""Actual process restart with owned handles; preserve every database/log."""
import json
import os
import socket
import subprocess
import sys
import time
import httpx
from certificate_stage1_workspace import ROOT, STATE, checked, retain


def listening():
    with socket.socket() as sock:
        sock.settimeout(.3)
        return sock.connect_ex(("127.0.0.1", 8003)) == 0


def main():
    output = checked(STATE / "process-restart-01.json", STATE)
    database = checked(STATE / "process-restart.sqlite3", STATE)
    if output.exists() or database.exists() or listening():
        raise RuntimeError("fresh test database/evidence and free port required")
    processes = []
    def start(ordinal):
        path = checked(STATE / f"process-restart-{ordinal}.log", STATE)
        env = {k:v for k,v in os.environ.items() if not any(p in k.upper() for p in ("SECRET", "TOKEN", "KEY", "PASSWORD"))}
        env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
        with path.open("xb") as stream:
            process = subprocess.Popen([sys.executable, "-B", str(ROOT / "scripts/run_certificate_restart_worker.py")],
                cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, creationflags=0x08000000)
        processes.append(process.pid)
        for _ in range(30):
            if process.poll() is not None:
                raise RuntimeError("owned restart worker exited; inspect retained log")
            try:
                response = httpx.get("http://127.0.0.1:8003/health/live", timeout=.5, trust_env=False)
                if response.status_code == 200 and response.json().get("owns_paid_ledger") is False:
                    return process
            except httpx.HTTPError:
                pass
            time.sleep(.2)
        raise RuntimeError("owned restart worker did not become ready")

    def stop(process):
        # Only this exact Popen process, launched in this function, is stopped.
        process.terminate()
        process.wait(timeout=15)
        for _ in range(20):
            if not listening():
                return
            time.sleep(.2)
        raise RuntimeError("worker child still listening; do not start a second writer")

    first = start(1)
    with httpx.Client(base_url="http://127.0.0.1:8003", trust_env=False) as client:
        response = client.post("/v1/auth/demo-login", json={"account": "SV001"}); response.raise_for_status()
        student = {"Authorization": "Bearer " + response.json()["token"]}
        form = {"purpose": "Process restart demo", "recipient": "Synthetic receiver"}
        response = client.post("/v1/document-requests/drafts", headers=student, json={"form": form}); response.raise_for_status()
        record = response.json(); did = record["id"]
        response = client.post(f"/v1/document-requests/{did}/preview", headers=student, json={"expected_version": record["version"]}); response.raise_for_status()
        p = response.json()
    stop(first)
    second = start(2)
    with httpx.Client(base_url="http://127.0.0.1:8003", trust_env=False) as client:
        resumed = client.get(f"/v1/document-requests/{did}/preview", headers=student)
        assert resumed.status_code == 200 and resumed.json()["preview_id"] == p["preview_id"]
        confirm = {"preview_id": p["preview_id"], "confirmation_token": p["confirmation_token"], "idempotency_key": "actual-process-restart-001", "form": form}
        sent = client.post(f"/v1/document-requests/{did}/confirm", headers=student, json=confirm)
        assert sent.status_code == 201
    stop(second)
    third = start(3)
    with httpx.Client(base_url="http://127.0.0.1:8003", trust_env=False) as client:
        replay = client.post(f"/v1/document-requests/{did}/confirm", headers=student, json=confirm)
        assert replay.status_code == 201 and replay.json()["is_replay"]
        record = client.get(f"/v1/document-requests/{did}", headers=student).json()
        assert record["status"] == "SUBMITTED" and len(record["history"]) == 3
        assert len(client.get("/v1/document-requests", headers=student).json()["items"]) == 1
        retain(output, {"passed": True, "owned_worker_pids": processes, "document_id": did,
            "pending_confirmation_survived_process_restart": True, "same_signed_session_remained_valid": True,
            "replay_survived_second_process_restart": True, "request_count": 1, "history": record["history"],
            "paid_gateway_initialized": False, "database_retained": str(database)})
    stop(third)
    print("Actual process restart, pending confirmation, replay and history: passed")


if __name__ == "__main__":
    main()
