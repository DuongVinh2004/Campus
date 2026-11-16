"""Read back retained live history, citations and a completed certificate.

No Gateway, inference, service transition or confirmation is opened here.
Run while the evaluation client is idle to compare ledger snapshots exactly.
"""
import argparse
import hashlib
import sys
from pathlib import Path

import httpx

from multi_agent_workspace import STATE, checked, retain
from multi_agent_live_resources import paid_view, native_view

DOCUMENT = "01a1350b-8854-718f-8a37-47c544049501"
EXPECTED_RESULT_SHA = "e88565283b6cd21700449b49d5ef881c36cfc7232f0fc87b8e74407e142577f3"


def main(output, report):
    output, report = checked(output, STATE), checked(report, STATE)
    if output.exists():
        raise FileExistsError("retain earlier proof")
    import json
    evidence = json.loads(report.read_text("utf-8"))
    case = next(row for row in evidence["results"] if any(
        (turn.get("final") or {}).get("response_class") == "grounded_answer" for turn in row["turns"]))
    turn = next(turn for turn in reversed(case["turns"]) if (turn.get("final") or {}).get("response_class") == "grounded_answer")
    cid, final = case["conversation_id"], turn["final"]
    before, native_before = paid_view(), native_view()
    with httpx.Client(base_url="http://127.0.0.1:8003", trust_env=False, timeout=10) as client:
        health = client.get("/health/live"); health.raise_for_status()
        assert health.json()["mode"] == "multi_agent_integrated" and health.json()["owns_paid_ledger"] is True
        def login(account):
            response = client.post("/v1/auth/demo-login", json={"account": account}); response.raise_for_status()
            return {"Authorization": "Bearer "+response.json()["token"]}
        owner = login("SV001")
        history = client.get(f"/v1/conversations/{cid}/messages?limit=100", headers=owner); history.raise_for_status()
        assert final in [message.get("final_result") for message in history.json()["items"]]
        run = client.get(f"/v1/conversations/{cid}/agent-runs/{final['run_id']}", headers=owner); run.raise_for_status()
        sources = []
        for mapping in final["citations"]:
            ref = mapping["citation"]
            path = f"/v1/conversations/{cid}/messages/{final['message_id']}/citations/{ref['citation_id']}/source"
            response = client.get(path, headers=owner); response.raise_for_status()
            value = response.json()
            assert hashlib.sha256(value["content_text"].encode()).hexdigest() == value["content_sha256"]
            sources.append({"path": path, "content_sha256": value["content_sha256"], "locator": ref["locator"]})
        other = login("SV024")
        assert client.get(f"/v1/conversations/{cid}/agent-runs/{final['run_id']}", headers=other).status_code == 404
        for source in sources:
            assert client.get(source["path"], headers=other).status_code == 404
        document = client.get(f"/v1/document-requests/{DOCUMENT}", headers=other); document.raise_for_status()
        assert document.json()["status"] == "READY" and len(document.json()["history"]) == 5
        result = client.get(f"/v1/document-requests/{DOCUMENT}/result", headers=other); result.raise_for_status()
        checksum = hashlib.sha256(result.content).hexdigest()
        assert checksum == EXPECTED_RESULT_SHA
        assert "GIẤY XÁC NHẬN SINH VIÊN" in result.text and "DEMO" not in result.text and "MÔ PHỎNG" not in result.text
    after, native_after = paid_view(), native_view()
    assert before == after and native_before == native_after
    retain(output, {"passed": True, "mode": "actual_live_http_readback", "health": health.json(),
        "conversation_id": cid, "run_id": final["run_id"], "terminal_and_history_preserved": True,
        "sources": sources, "non_owner_run_and_citations_denied": True,
        "old_document_id": DOCUMENT, "old_document_status": "READY", "audit_count": 5,
        "old_result_sha256": checksum, "paid_before": before, "paid_after": after,
        "native_before": native_before, "native_after": native_after, "new_provider_calls": 0})
    print("live readback, ownership denial and retained READY certificate passed")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    main(args.output, args.report)
