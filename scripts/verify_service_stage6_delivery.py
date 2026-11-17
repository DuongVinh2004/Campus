"""Readback and row preservation evidence; never confirm an existing request."""
import base64
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts"), str(ROOT / "services/api/src"), str(ROOT / "packages/synthetic/src")]
from service_stage6_workspace import BUSINESS, destination, retain
from multi_agent_live_resources import paid_view, native_view

READY = "01a1350b-8854-718f-8a37-47c544049501"
EXPECTED_HTML = "e88565283b6cd21700449b49d5ef881c36cfc7232f0fc87b8e74407e142577f3"
APPEAL = "01a1380c-cd67-7544-800d-7e7413d817c2"
SUPPORT = "01a13812-0104-7008-a9e1-2b11a0c32d38"
CHAT = "01a13816-ec9d-7726-9f2d-d7af45b594d0"


def encoded(row):
    return json.dumps(row, ensure_ascii=False, default=lambda v: v.hex())


def main():
    import httpx
    before_paid, before_native = paid_view(), native_view()
    tables = []
    with sqlite3.connect(destination("business-before.sqlite3").as_uri()+"?mode=ro", uri=True) as old, sqlite3.connect(BUSINESS.as_uri()+"?mode=ro", uri=True) as current:
        names = [r[0] for r in old.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for name in names:
            identifier = '"'+name.replace('"','""')+'"'
            previous = [encoded(r) for r in old.execute(f"SELECT * FROM {identifier}")]
            present = [encoded(r) for r in current.execute(f"SELECT * FROM {identifier}")]
            preserved = all(row in present for row in previous)
            tables.append({"table": name, "prior_rows": len(previous), "current_rows": len(present), "all_prior_rows_preserved": preserved})
            if not preserved: raise ValueError("pre-existing business row changed")
        schema = [r[0] for r in current.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    endpoints = []
    def login(client, account):
        response = client.post("/v1/auth/demo-login", json={"account": account}); response.raise_for_status()
        return {"Authorization": "Bearer "+response.json()["token"]}
    with httpx.Client(base_url="http://127.0.0.1:8004", timeout=15, trust_env=False) as client:
        student, other = login(client, "SV001"), login(client, "SV024")
        records = []
        for identifier in (APPEAL, SUPPORT):
            response = client.get(f"/v1/service-requests/{identifier}", headers=student); response.raise_for_status(); value = response.json()
            assert value["status"] == "READY"
            result = client.get(f"/v1/service-requests/{identifier}/result", headers=student); result.raise_for_status()
            checksum = hashlib.sha256(result.content).hexdigest()
            assert checksum == value["result"]["checksum"] == result.headers["x-content-sha256"]
            assert "MÔ PHỎNG" in result.text and "KHÔNG CÓ GIÁ TRỊ PHÁP LÝ" in result.text
            assert client.get(f"/v1/service-requests/{identifier}", headers=other).status_code == 404
            assert client.get(f"/v1/service-requests/{identifier}/result", headers=other).status_code == 404
            assert client.get(f"/v1/document-requests/{identifier}", headers=student).status_code == 404
            records.append({"id": identifier, "type": value["document_type"], "status": value["status"], "version": value["version"],
                "queue": value["queue"], "audit_events": len(value["history"]), "template": value["result"]["template_version"], "checksum": checksum,
                "owner_download": True, "nonowner_denied": True, "certificate_route_denied": True})
        history = client.get(f"/v1/conversations/{CHAT}/messages?limit=100", headers=student); history.raise_for_status()
        history = history.json()
        final = history["items"][-1]["final_result"]
        assert final["response_class"] != "system_error"
        citations = []
        for mapping in final["citations"]:
            ref = mapping["citation"]
            response = client.get(f"/v1/conversations/{CHAT}/messages/{final['message_id']}/citations/{ref['citation_id']}/source", headers=student)
            response.raise_for_status(); source = response.json()
            assert hashlib.sha256(source["content_text"].encode()).hexdigest() == source["content_sha256"]
            citations.append({"id": ref["citation_id"], "checksum": source["content_sha256"], "hash_matches": True})
        assert client.get(f"/v1/conversations/{CHAT}/messages?limit=100", headers=other).status_code == 404
        admin = login(client, "KA002")
        knowledge = client.get("/v1/knowledge-operations", headers=admin); knowledge.raise_for_status(); knowledge = knowledge.json()
        sources = []
        for source in knowledge["sources"]:
            assert hashlib.sha256(base64.b64decode(source["original_base64"])).hexdigest() == source["original_sha256"]
            sources.append({"id": source["id"], "hash_matches": True, "locator": source["locator"]})
        search = client.post("/v1/service-knowledge/search", headers=student, json={"message": "phúc khảo"}); search.raise_for_status()
        assert all(v["version_id"] != "01a1380b-88a0-77d7-b1f0-6724c9efca99" for v in search.json()["items"])
        knowledge_view = {"sources": sources, "versions": [{"id": v["id"], "state": v["state"], "revision": v["revision"]} for v in knowledge["versions"]],
            "active": knowledge["active"], "superseded_excluded_from_current_search": True}
    for port in (8003, 8004):
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=15, trust_env=False) as client:
            # Retained READY request belongs to SV024, as verified from its row.
            owner, other = login(client, "SV024"), login(client, "SV001")
            response = client.get(f"/v1/document-requests/{READY}", headers=owner); response.raise_for_status(); value = response.json()
            assert value["status"] == "READY" and len(value["history"]) == 5
            html = client.get(f"/v1/document-requests/{READY}/result", headers=owner); html.raise_for_status()
            assert hashlib.sha256(html.content).hexdigest() == EXPECTED_HTML
            assert client.get(f"/v1/document-requests/{READY}", headers=other).status_code == 404
            certificate_ids = [r["id"] for r in client.get("/v1/document-requests?limit=100", headers=owner).json()["items"]]
            assert APPEAL not in certificate_ids and SUPPORT not in certificate_ids
            assert client.get(f"/v1/document-requests/{APPEAL}", headers=owner).status_code == 404
            endpoints.append({"port": port, "certificate_ready": True, "audit_events": 5, "html_sha256": EXPECTED_HTML,
                "nonowner_denied": True, "stage6_ids_absent_from_certificate_list": True})
    after_paid, after_native = paid_view(), native_view()
    assert before_paid == after_paid and before_native == after_native
    retain("data-retention-readback-01.json", {"passed": True, "prior_tables": tables, "additive_tables": [t for t in schema if t not in names],
        "old_certificate": endpoints, "service_outcomes": records, "knowledge": knowledge_view,
        "browser_chat": {"conversation": CHAT, "response_class": final["response_class"], "citations": citations, "nonowner_denied": True},
        "paid_before": before_paid, "paid_after": after_paid, "native_before": before_native, "native_after": after_native,
        "provider_and_native_delta": 0, "existing_requests_confirmed_again": False})
    retain("business-after.sqlite3.json", {"database": str(BUSINESS), "old_rows_preserved": True, "new_outcomes": records})


if __name__ == "__main__":
    main()
