"""Readback proof for observed browser IDs; no model calls or other data edits."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys

import httpx
from certificate_stage1_workspace import ROOT, STATE, checked, retain
from evaluate_certificate_rag import paid_snapshot, native_snapshot

DOCUMENT = "01a1350b-8854-718f-8a37-47c544049501"
CONVERSATION = "01a1350a-ab93-75d9-8071-dbfb70e71507"
EARLIER_DOCUMENT = "01a134f1-4c47-7667-b5a6-95d7c9f9e51f"


def main():
    output = checked(STATE / "delivery-readback-01.json", STATE)
    if output.exists():
        raise FileExistsError("retain previous proof")
    before = paid_snapshot()
    with httpx.Client(base_url="http://127.0.0.1:8002", trust_env=False, timeout=10) as client:
        health = client.get("/health/live"); health.raise_for_status()
        assert health.json()["owns_paid_ledger"] is False
        response = client.post("/v1/auth/demo-login", json={"account": "SV024"}); response.raise_for_status()
        student = {"Authorization": "Bearer " + response.json()["token"]}
        owner = response.json()["user"]["user_id"]
        current = client.get(f"/v1/document-requests/{DOCUMENT}", headers=student)
        current.raise_for_status(); record = current.json()
        assert record["student_user_id"] == owner and record["status"] == "SUBMITTED"
        assert record["payload"]["purpose"] == "Nộp hồ sơ thực tập" and record["payload"]["recipient"] == "Phòng Nhân sự"
        assert [e["action"] for e in record["history"]] == ["draft.saved", "confirmation.prepared", "request.submitted"]
        response = client.post("/v1/auth/demo-login", json={"account": "OF001"}); response.raise_for_status()
        staff = {"Authorization": "Bearer " + response.json()["token"]}
        accepted = client.post(f"/v1/staff/document-requests/{DOCUMENT}/accept", headers=staff,
            json={"expected_version": record["version"], "idempotency_key": "delivery-accept-"+DOCUMENT})
        accepted.raise_for_status(); record = accepted.json()["document_request"]
        approved = client.post(f"/v1/staff/document-requests/{DOCUMENT}/approve", headers=staff,
            json={"expected_version": record["version"], "idempotency_key": "delivery-approve-"+DOCUMENT,
                  "note": "Đã kiểm tra thông tin hồ sơ"})
        approved.raise_for_status()
        final_record = client.get(f"/v1/document-requests/{DOCUMENT}", headers=student).json()
        assert final_record["status"] == "READY"
        result = client.get(f"/v1/document-requests/{DOCUMENT}/result", headers=student)
        result.raise_for_status()
        assert "GIẤY XÁC NHẬN SINH VIÊN" in result.text and "Phòng Nhân sự" in result.text
        assert "MÔ PHỎNG" not in result.text and "DEMO" not in result.text
        history = client.get(f"/v1/conversations/{CONVERSATION}/messages?limit=100", headers=student)
        history.raise_for_status()
        final = history.json()["items"][-1]["final_result"]
        assert final["response_class"] == "grounded_answer"
        sources = []
        for mapping in final["citations"]:
            citation = mapping["citation"]
            opened = client.get(f"/v1/conversations/{CONVERSATION}/messages/{final['message_id']}/citations/{citation['citation_id']}/source", headers=student)
            opened.raise_for_status(); source = opened.json()
            assert hashlib.sha256(source["content_text"].encode()).hexdigest() == source["content_sha256"]
            sources.append({"citation_id": citation["citation_id"], "locator": citation["locator"], "hash_verified": True})
        # Read only the earlier task-owned sample after two actual demo API restarts.
        response = client.post("/v1/auth/demo-login", json={"account": "SV001"}); response.raise_for_status()
        earlier_owner = {"Authorization": "Bearer " + response.json()["token"]}
        earlier = client.get(f"/v1/document-requests/{EARLIER_DOCUMENT}", headers=earlier_owner)
        earlier.raise_for_status()
        assert earlier.json()["status"] == "READY" and len(earlier.json()["history"]) == 8
    database = checked(STATE / "demo.sqlite3", STATE)
    with sqlite3.connect(database.as_uri()+"?mode=ro", uri=True) as conn:
        audit_count = conn.execute("SELECT COUNT(*) FROM certificate_audit WHERE document_id=?", (DOCUMENT,)).fetchone()[0]
        assert audit_count == len(final_record["history"]) == 5
    after = paid_snapshot()
    assert before == after  # This proof has no model generation or provider calls.
    retain(output, {"passed": True, "document_id": DOCUMENT, "conversation_id": CONVERSATION,
        "document": final_record, "audit_count": audit_count, "chat_final": final, "source_reads": sources,
        "earlier_document_persisted_after_two_actual_demo_restarts": True,
        "ui_label_change": "Human requested removal from every screen and result document; backend synthetic scope and stored historical evidence retained.",
        "paid_snapshot": after, "native_snapshot": native_snapshot(), "proof_provider_calls": 0,
        "result_html_sha256": hashlib.sha256(result.content).hexdigest()})
    print(json.dumps({"passed": True, "audit_count": audit_count, "source_reads": len(sources), "provider_calls": 0}))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
