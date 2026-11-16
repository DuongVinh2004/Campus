"""Real process restart on fresh fixture8005 with scoped graceful shutdown."""
import hashlib
import json
import os
import secrets
import subprocess
import sys
import time

import httpx

from service_stage6_workspace import ROOT, destination, retain
from launch_certificate_demo import listening


def main():
    if destination("process-restart.sqlite3").exists() or destination("process-restart-01.json").exists() or listening(8005):
        raise ValueError("new fixture and free test port required")
    nonce = secrets.token_urlsafe(32)
    headers = {"X-Test-Lifecycle": nonce}
    environment = {k: v for k, v in os.environ.items() if not any(s in k.upper() for s in ("SECRET", "TOKEN", "KEY", "PASSWORD"))}
    environment.update(CAMPUS247_STAGE6_LIFECYCLE_NONCE=nonce, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    command = [sys.executable, "-B", str(ROOT / "scripts/run_service_stage6_restart_worker.py")]
    pids = []
    def start(number):
        if listening(8005): raise RuntimeError("test port still owned; no second worker")
        with destination(f"process-restart-{number}.log").open("xb") as log:
            process = subprocess.Popen(command, cwd=ROOT, env=environment, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT, creationflags=0x08000000)
        for _ in range(50):
            if process.poll() is not None: raise RuntimeError("owned worker exited; inspect retained log")
            try:
                response = httpx.get("http://127.0.0.1:8005/internal/owned-test/status", headers=headers, timeout=.5, trust_env=False)
                if response.status_code == 200:
                    value = response.json()
                    if value["fixture_database"] != str(destination("process-restart.sqlite3")) or value["owns_paid_ledger"]:
                        raise RuntimeError("lifecycle ownership mismatch")
                    pids.append({"launcher": process.pid, "worker": value["pid"]})
                    return process
            except httpx.HTTPError: pass
            time.sleep(.2)
        raise RuntimeError("new test worker not ready")
    def stop(process):
        response = httpx.post("http://127.0.0.1:8005/internal/owned-test/exit", headers=headers, timeout=5, trust_env=False)
        response.raise_for_status()
        process.wait(timeout=15)
        if listening(8005): raise RuntimeError("owned worker listener retained; no restart")
    client = httpx.Client(base_url="http://127.0.0.1:8005", timeout=10, trust_env=False)
    def get(path, auth):
        response = client.get(path, headers=auth); response.raise_for_status(); return response.json()
    def post(path, body, auth=None):
        response = client.post(path, headers=auth, json=body); response.raise_for_status(); return response.json()
    first = start(1)
    student = {"Authorization": "Bearer " + post("/v1/auth/demo-login", {"account": "SV001"})["token"]}
    forms = [{"kind": "GRADE_APPEAL", "course_record_id": "demo-student1-CS101", "reason": "Actual restart demo"},
             {"kind": "GENERAL_SUPPORT", "reason": "Actual support restart demo"}]
    previews = []
    for form in forms:
        row = post("/v1/service-requests/drafts", {"form": form}, student)
        p = post(f"/v1/service-requests/{row['id']}/preview", {"expected_version": row["version"]}, student)
        previews.append(p)
    stop(first)
    second = start(2)
    confirmations = []
    for p in previews:
        identifier = p["document_request"]["id"]
        assert get(f"/v1/service-requests/{identifier}/preview", student)["preview_id"] == p["preview_id"]
        body = {"preview_id": p["preview_id"], "confirmation_token": p["confirmation_token"], "idempotency_key": "restart:"+p["preview_id"], "form": p["form"]}
        assert post(f"/v1/service-requests/{identifier}/confirm", body, student)["status"] == "SUBMITTED"
        confirmations.append(body)
    stop(second)
    third = start(3)
    results = []
    for p, body, name in zip(previews, confirmations, ("OF002", "OF001"), strict=True):
        identifier = p["document_request"]["id"]
        assert post(f"/v1/service-requests/{identifier}/confirm", body, student)["is_replay"]
        staff = {"Authorization": "Bearer " + post("/v1/auth/demo-login", {"account": name})["token"]}
        r = get(f"/v1/staff/service-requests/{identifier}", staff)
        r = post(f"/v1/staff/service-requests/{identifier}/claim", {"expected_version": r["version"], "idempotency_key": "restart-claim:"+identifier, "note": "Scoped demo intake"}, staff)["document_request"]
        r = post(f"/v1/staff/service-requests/{identifier}/resolve", {"expected_version": r["version"], "idempotency_key": "restart-resolve:"+identifier, "note": "Scoped demo outcome", "outcome": "UNCHANGED" if name == "OF002" else None}, staff)["document_request"]
        response = client.get(f"/v1/service-requests/{identifier}/result", headers=student); response.raise_for_status()
        results.append({"id": identifier, "record": r, "result_sha256": hashlib.sha256(response.content).hexdigest()})
    stop(third)
    fourth = start(4)
    for r in results:
        assert get(f"/v1/service-requests/{r['id']}", student) == r["record"]
        assert hashlib.sha256(client.get(f"/v1/service-requests/{r['id']}/result", headers=student).content).hexdigest() == r["result_sha256"]
    assert len(get("/v1/service-requests", student)["items"]) == 2
    stop(fourth)
    retain("process-restart-01.json", {"passed": True, "owned_processes": pids, "command": command,
        "port": 8005, "pending_preview_and_original_session_survived": True, "confirm_replay_no_duplicate": True,
        "outcomes_survived": [{"id": r["id"], "result_sha256": r["result_sha256"]} for r in results],
        "paid_dispatch": 0, "existing_runtimes_touched": False, "shutdown": "unique in-memory lifecycle nonce; graceful exit of newly launched test workers only"})
    client.close()


if __name__ == "__main__":
    main()
