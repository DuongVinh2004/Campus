import json
import subprocess
import sys
import time
from pathlib import Path
import pytest
from tests.integration.test_unified_staff12 import runtime
from tests.api.test_service_stage6 import read
from tests.unified_workflow13a.test_case_workflow import draft_body, prepare, preview, confirmation, post

ROOT = Path(__file__).resolve().parents[2]

def test_two_fresh_processes_confirm_one_transaction_and_same_receipt(runtime):
    app, client, student, staff, record, path = runtime
    body = draft_body(client, staff, record); prepare(client, staff, body); p = preview(client, staff, body)
    from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
    actor = SyntheticIdentityAdapter("campus247-demo-secret-key-huce", environment="development", tenant_id="huce-local-public").resolve_token(staff["Authorization"].split(" ")[1])
    with (path / "process-input.json").open("x", encoding="utf-8") as f:
        json.dump({"owner": actor.subject_id, "session": actor.session_id, "confirmation": confirmation(p)}, f)
    processes = []
    for index in range(2):
        with (path / f"process-log-{index}.log").open("xb") as log:
            processes.append(subprocess.Popen([sys.executable, "-B", str(ROOT / "scripts/unified_parallel_a_process.py"), str(path), str(index)], cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, creationflags=0x08000000))
    deadline = time.monotonic() + 20
    while not all((path / f"process-ready-{i}.json").exists() for i in range(2)):
        assert time.monotonic() < deadline, [p.poll() for p in processes]
        time.sleep(.02)
    with (path / "process-gate.json").open("x") as f: f.write('{}')
    for worker in processes: assert worker.wait(timeout=20) == 0
    values = [json.loads((path / f"process-result-{i}.json").read_text()) for i in range(2)]
    assert values[0]["receipt_id"] == values[1]["receipt_id"]
    assert sorted(v["is_replay"] for v in values) == [False, True]
    assert read(client, student, record["id"])["version"] == record["version"] + 1

def test_receipt_failure_rolls_back_business_audit_event_outbox_and_preserves_draft(runtime, monkeypatch):
    app, client, student, staff, record, _ = runtime
    body = draft_body(client, staff, record); prepare(client, staff, body); p = preview(client, staff, body)
    repo = app.state.case_workflow.repository
    with app.state.service_requests.repository.transaction() as tx:
        before = {k: repo.records(tx, k) for k in ["event", "tracking_event", "receipt", "draft"]}
    original = repo.insert
    def broken(tx, kind, value):
        if kind == "receipt": raise OSError("fixture receipt failure")
        return original(tx, kind, value)
    monkeypatch.setattr(repo, "insert", broken)
    with pytest.raises(OSError): post(client, staff, ":confirm", confirmation(p))
    with app.state.service_requests.repository.transaction() as tx:
        assert {k: repo.records(tx, k) for k in before} == before
    assert read(client, student, record["id"])["version"] == record["version"]
    monkeypatch.setattr(repo, "insert", original)
    assert post(client, staff, ":confirm", confirmation(p)).status_code == 200
