"""UNI-005 compatibility/readback; never mutate a retained business request."""
import hashlib
import json
import sqlite3
import sys
import xml.etree.ElementTree as ET

from unified_ai_runtime_probe import ROOT, checked, retain, http
from verify_unified_ai_candidate import database_digest
from audit_unified_ai_baseline import audit
import prepare_unified_ai_session04 as prepare

STATE = prepare.STATE
DATABASE = checked(ROOT / "infra/local/unified-ai-20261014-01/business-candidate01.sqlite3")
sys.path[:0] = [str(checked(ROOT / "services/api/src")), str(checked(ROOT / "packages/synthetic/src"))]


def tests():
    latest = {}
    for name in ("backend-tests-03.xml", "backend-tests-04.xml"):
        for case in ET.parse(checked(STATE / name)).getroot().iter("testcase"):
            latest[(case.get("classname"), case.get("name"))] = not any(case.find(k) is not None for k in ("failure", "error", "skipped"))
    assert len(latest) == 203 and all(latest.values()), "a relevant backend test lacks a passing result"
    front = list(ET.parse(checked(STATE / "frontend-tests-01.xml")).getroot().iter("testcase"))
    assert len(front) == 35 and all(not any(c.find(k) is not None for k in ("failure", "error", "skipped")) for c in front)
    assert json.loads(checked(STATE / "frontend-build-01.json").read_text())["exit_code"] == 0
    assert json.loads(checked(STATE / "typescript-01.json").read_text())["exit_code"] == 0
    assert checked(prepare.FRONTEND / "preserve-build.mjs").read_bytes() == checked(ROOT / "infra/local/rag-fixture/m1_source_guard_20261012_58-repair1.mjs").read_bytes()
    return {"backend_unique": len(latest), "frontend_unique": len(front), "total_unique": len(latest)+len(front),
            "backend_results": ["backend-tests-03.xml", "backend-tests-04.xml"], "frontend_results": "frontend-tests-01.xml",
            "failed_attempts_retained": True, "guard_unchanged": True}


def packets(call):
    tokens = {}
    for alias in ("SV001", "SV024", "OF001", "OF002"):
        status, session = call("/v1/auth/demo-login", body={"account": alias})
        assert status == 200
        tokens[alias] = session["token"]  # Request-local, never exported.
    result = []
    for kind, path in (("service_request", "/v1/service-requests"), ("certificate_request", "/v1/document-requests")):
        status, records = call(path, tokens["SV001"]); assert status == 200
        for record in records["items"]:
            request = {"resource": {"kind": kind, "id": record["id"], "expected_version": record["version"]}}
            status, value = call("/v1/assistant/workflows/resolve", tokens["SV001"], request)
            assert status == 200 and value["action_authority"] == "none" and value["institutional_rules_verified"] is False
            assert not any(k in value for k in ("profile", "payload", "preview", "token", "internal_notes", "messages"))
            assert all(c["status"] == "required" and c["required"] for c in value["mandatory_reviews"])
            officer = "OF002" if record["document_type"] == "GRADE_APPEAL" else "OF001"
            if record["status"] not in {"DRAFT", "PENDING_CONFIRMATION"}:
                status, other = call("/v1/assistant/workflows/resolve", tokens[officer], request)
                assert status == 200 and other["binding"] == value["binding"] and other["supplements"] == value["supplements"]
            if kind == "certificate_request":
                assert not record.get("guidance_snapshot") and value["binding_status"] == "unresolved"
                assert value["reasons"] == ["SOURCE_SNAPSHOT_MISSING"] and value["template"] is None
            else:
                assert value["binding_status"] == "bound"
                if record["supplements"]:
                    assert value["readiness"] == "undetermined"
                    assert all(s["binding_status"] == "unresolved" and s["source"] is None for s in value["supplements"])
            denied, _ = call("/v1/assistant/workflows/resolve", tokens["SV024"], request); assert denied == 404
            stale, _ = call("/v1/assistant/workflows/resolve", tokens["SV001"], {"resource": {**request["resource"], "expected_version": record["version"]+1}})
            assert stale == 409
            injected, _ = call("/v1/assistant/workflows/resolve", tokens["SV001"], {**request, "confirmed": True})
            assert injected == 422
            result.append({"id": record["id"], "kind": kind, "version": record["version"], "status": record["status"],
                "binding_status": value["binding_status"], "readiness": value["readiness"], "reasons": value["reasons"],
                "binding_sha256": value["binding"]["sha256"] if value["binding"] else None,
                "supplements": value["supplements"], "same_role_binding": record["status"] not in {"DRAFT", "PENDING_CONFIRMATION"},
                "wrong_owner": denied, "stale": stale, "injected_confirmation": injected})
    return result


def compatibility():
    from fastapi.testclient import TestClient
    from campus247.bootstrap.unified_demo import create_unified_demo_app
    clone = checked(STATE / "workflow-compatibility01.sqlite3")
    with clone.open("xb"):
        pass
    with sqlite3.connect(checked(STATE / "business-before.sqlite3").as_uri()+"?mode=ro",uri=True) as source:
        with sqlite3.connect(clone) as destination:
            source.backup(destination)
    before = database_digest(clone)
    app = create_unified_demo_app(clone)
    with TestClient(app) as client:
        def call(path, token=None, body=None):
            headers = {"Authorization": "Bearer "+token} if token else {}
            response = client.post(path, headers=headers, json=body) if body is not None else client.get(path, headers=headers)
            if path == "/v1/assistant/workflows/resolve" and response.status_code == 200:
                assert response.headers["cache-control"] == "no-store"
            return response.status_code, response.json()
        result = packets(call)
        document = app.openapi()
        ids = [method["operationId"] for route in document["paths"].values() for method in route.values() if isinstance(method,dict) and "operationId" in method]
        assert len(ids) == len(set(ids))
    assert database_digest(clone) == before
    retain(STATE / "workflow-schemas-01.json", {"schemas": {key:value for key,value in document["components"]["schemas"].items()
        if key.startswith(("Workflow", "AppliedSource", "SupplementApplicability", "MandatoryReview", "TemplateDefinition"))}, "unique_operation_ids":len(ids)})
    retain(STATE / "workflow-compatibility-01.json", {"clone":str(clone), "packets": result,
        "all_table_rows_unchanged":True,"backfill":False,"model_dispatches":0})
    retain(STATE / "validation-01.json", {**tests(), "compatibility_passed":True,
        "frontend_build_id":checked(prepare.FRONTEND / ".next/BUILD_ID").read_text().strip()})


def runtime():
    from handoff_unified_ai_session04 import windows_read
    from multi_agent_live_resources import paid_view, native_view
    status, runtime = http(8006, "/v1/assistant/runtime")
    assert status == 200 and runtime["runtime"] == "unified-local-v4"
    build_id = checked(prepare.FRONTEND / ".next/BUILD_ID").read_text().strip()
    assert runtime["frontend_build_id"] == build_id and not runtime["owns_paid_ledger"]
    before = database_digest(checked(STATE / "business-before.sqlite3"))
    assert database_digest(DATABASE) == before
    result = packets(lambda path,token=None,body=None:http(8006,path,token,body))
    assert database_digest(DATABASE) == before
    baseline = audit(DATABASE)
    assert baseline["human_declared_session_count"] == 0 and baseline["all_receipt_chains_valid"]
    ownership = windows_read()
    owners = {r["LocalPort"]:r["OwningProcess"] for r in ownership["listeners"]}
    assert owners[8003] == 14208 and owners[18081] == owners[18082] == 6132
    retain(STATE / "runtime-verification-01.json", {"runtime":runtime,"ownership":ownership,"packets":result,
        "candidate_all_table_rows_unchanged":True,"baseline":baseline,"model_dispatches_by_this_work":0,
        "new_paid_writer":False,"human_trial_deferred":True})
    preflight=json.loads(checked(STATE / "preflight.json").read_text())
    paid,native=paid_view(),native_view()
    old_paid,old_native=preflight["paid_before"],preflight["native_before"]
    assert all(paid[k]==old_paid[k] for k in ("hard_cap_usd","call_cap","unsettled_attempts_retained"))
    assert native["caps"]==old_native["caps"]
    assert all(paid[k]>=old_paid[k] for k in ("calls","input_tokens_charged","output_tokens_charged"))
    assert all(native["counts"][k]>=old_native["counts"][k] for k in old_native["counts"])
    retain(STATE / "live-usage-observation-01.json", {"paid_before":old_paid,"paid_after":paid,"native_before":old_native,
        "native_after":native,"paid_call_delta":paid["calls"]-old_paid["calls"],
        "native_deltas":{k:native["counts"][k]-old_native["counts"][k] for k in old_native["counts"]},
        "caps_and_uncertain_reservations_retained":True,"quota_reset_or_refund":False,"model_dispatches_by_this_work":0,
        "caller_attribution":"not inferred from aggregate counters"})


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv)!=2 or sys.argv[1] not in {"compatibility", "runtime"}:
        raise ValueError("explicit compatibility/runtime required; evidence paths are exclusive")
    {"compatibility":compatibility,"runtime":runtime}[sys.argv[1]]()
    print(json.dumps({"stage":sys.argv[1],"status":"passed","tests":tests()}))
