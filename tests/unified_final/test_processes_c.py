"""C processes exercise allowed C fixtures without changing legacy probe guards."""
import json
from pathlib import Path
import subprocess
import sys
import time

import pytest

from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
from tests.api.test_service_stage6 import read, sent
from tests.unified_final.test_security_c import runtime as runtime_fixture
from tests.unified_final.test_composed_personal_c import composed as composed_fixture
from tests.unified_workflow13a.test_case_workflow import draft_body, prepare, preview, confirmation

runtime = runtime_fixture
composed = composed_fixture
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("mode", ["case_confirm", "draft", "claim"])
def test_C_two_processes_preserve_receipt_or_cas_semantics(runtime, mode):
    _, client, student, staff, record, path = runtime
    payload = {}
    if mode == "case_confirm":
        body = draft_body(client, staff, record)
        prepare(client, staff, body)
        payload["confirmation"] = confirmation(preview(client, staff, body))
    elif mode == "claim":
        _, record, _ = sent(client)
    actor = SyntheticIdentityAdapter("campus247-demo-secret-key-huce", environment="development", tenant_id="huce-local-public").resolve_token(staff["Authorization"][7:])
    processes = []
    for index in range(2):
        command = [sys.executable, "-B", str(ROOT / "scripts/unified_parallel_c_process.py"), mode, str(path), str(index)]
        with (path / ("c-child-log-" + str(index) + ".log")).open("xb") as log:
            process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT, creationflags=0x08000000)
        process.stdin.write((json.dumps({**payload, "owner": actor.subject_id, "session": actor.session_id,
            "resource": {"kind": "service_request", "id": record["id"], "expected_version": record["version"]}, "client_id": generate_uuid7()}) + "\n").encode())
        process.stdin.flush()
        process.stdin.close()
        processes.append(process)
    deadline = time.monotonic() + 20
    while not all((path / ("c-ready-" + str(index) + ".json")).exists() for index in range(2)):
        assert all(process.poll() is None for process in processes), "C child exited before readiness; retained child log"
        assert time.monotonic() < deadline
        time.sleep(.02)
    with (path / "c-process-gate.json").open("x", encoding="utf-8") as output:
        json.dump({"go": True}, output)
    for process in processes:
        assert process.wait(timeout=20) == 0
    results = [json.loads((path / ("c-process-result-" + str(index) + ".json")).read_text(encoding="utf-8")) for index in range(2)]
    if mode == "case_confirm":
        assert len({value["receipt_id"] for value in results}) == 1
        assert sorted(value["is_replay"] for value in results) == [False, True]
    else:
        assert sorted(value["state"] for value in results) == ["committed", "conflict"]
    public = read(client, student, record["id"])
    assert public["version"] == record["version"] + (0 if mode == "draft" else 1)


def test_C_actual_worker_process_restart_never_redelivers(composed):
    from tests.unified_personal13b.test_wired_consumers import subscribe
    from tests.api.test_service_stage6 import draft, preview as student_preview, confirm, login, act
    _, client, student, _, path = composed
    record = draft(client, student)
    assert confirm(client, student, student_preview(client, student, record)).status_code == 201
    record = read(client, student, record["id"])
    subscribe(client, student, record)
    staff = login(client, "OF002")
    claimed = act(client, staff, record, "claim").json()["document_request"]
    assert act(client, staff, claimed, "respond").status_code == 200
    for index in range(2):
        with (path / ("c-worker-log-" + str(index) + ".log")).open("xb") as output:
            result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/unified_parallel_c_process.py"), "worker", str(path), str(index)],
                cwd=ROOT, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT, timeout=30, creationflags=0x08000000)
        assert result.returncode == 0
    results = [json.loads((path / ("c-worker-result-" + str(index) + ".json")).read_text(encoding="utf-8")) for index in range(2)]
    assert [value["delivered"] for value in results] == [1, 0]
    inbox = client.get("/v1/assistant/tracking/notifications", headers=student)
    assert inbox.status_code == 200 and len(inbox.json()["items"]) == 1
