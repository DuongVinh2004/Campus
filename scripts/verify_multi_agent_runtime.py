"""Readback guarded integrated runtime and retained stage-1 records; no inference."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import httpx

from multi_agent_workspace import STATE, checked, retain
from evaluate_certificate_rag import paid_snapshot, native_snapshot

CONVERSATION = "01a13568-ab62-765e-a72c-fe553a0074b6"
DOCUMENT = "01a1350b-8854-718f-8a37-47c544049501"


def main(output):
    output = checked(output, STATE)
    if output.exists():
        raise FileExistsError("retain earlier proof")
    before, native_before = paid_snapshot(), native_snapshot()
    with httpx.Client(base_url="http://127.0.0.1:8003", trust_env=False, timeout=10) as client:
        health = client.get("/health/live"); health.raise_for_status()
        assert health.json()["mode"] == "multi_agent_integrated" and health.json()["owns_paid_ledger"] is False
        login = client.post("/v1/auth/demo-login", json={"account": "SV001"}); login.raise_for_status()
        headers = {"Authorization": "Bearer "+login.json()["token"]}
        history = client.get(f"/v1/conversations/{CONVERSATION}/messages?limit=100", headers=headers)
        history.raise_for_status()
        final = history.json()["items"][-1]["final_result"]
        assert final["response_class"] == "system_error"
        assert final["status"] == "abstained" and "giới hạn" in final["content"]
        # One new explicit local request demonstrates the final runtime version
        # saves stable run bindings, without provider or native reservations.
        created = client.post("/v1/conversations", headers=headers, json={}); created.raise_for_status()
        cid = created.json()["id"]
        stream = client.post(f"/v1/conversations/{cid}/messages:stream", headers=headers,
                            json={"content": "Phí xin giấy xác nhận sinh viên là bao nhiêu?"})
        stream.raise_for_status()
        from evaluate_certificate_rag import frames
        events = frames(stream.text)
        terminal = next(data for kind, data in events if kind == "message.completed")
        assert terminal["response_class"] == "system_error" and terminal["run_id"]
        run = client.get(f"/v1/conversations/{cid}/agent-runs/{terminal['run_id']}", headers=headers)
        run.raise_for_status(); run_record = run.json()
        assert run_record["usage"]["model_calls"] == run_record["usage"]["searches"] == 0
        reloaded = client.get(f"/v1/conversations/{cid}/messages?limit=100", headers=headers)
        reloaded.raise_for_status()
        assert reloaded.json()["items"][-1]["final_result"] == terminal
        # Existing completed document is read under its actual synthetic owner.
        login = client.post("/v1/auth/demo-login", json={"account": "SV024"}); login.raise_for_status()
        owner = {"Authorization": "Bearer "+login.json()["token"]}
        document = client.get(f"/v1/document-requests/{DOCUMENT}", headers=owner); document.raise_for_status()
        assert document.json()["status"] == "READY" and len(document.json()["history"]) == 5
        result = client.get(f"/v1/document-requests/{DOCUMENT}/result", headers=owner); result.raise_for_status()
        assert "GIẤY XÁC NHẬN SINH VIÊN" in result.text and "Phòng Nhân sự" in result.text
        assert "MÔ PHỎNG" not in result.text and "DEMO" not in result.text
    after, native_after = paid_snapshot(), native_snapshot()
    assert before == after and native_before == native_after
    retain(output, {"passed": True, "mode": "guarded_runtime_actual_http", "live_generation_verified": False,
        "previous_browser_conversation_preserved": CONVERSATION, "new_conversation_id": cid,
        "terminal": terminal, "run": run_record, "history_readback_equal": True,
        "old_document_id": DOCUMENT, "old_document_status": document.json()["status"],
        "old_document_audit_count": len(document.json()["history"]),
        "old_result_sha256": hashlib.sha256(result.content).hexdigest(),
        "paid_before": before, "paid_after": after, "native_before": native_before, "native_after": native_after,
        "provider_calls": 0, "native_inference": 0, "health": health.json()})
    print(json.dumps({"passed": True, "history_preserved": True, "old_document": "READY", "provider_calls": 0}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.output)
