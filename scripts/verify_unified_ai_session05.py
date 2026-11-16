"""Storage fixtures/migration/readback, exclusive evidence, no model calls."""
import asyncio
import hashlib
import json
import sqlite3
import sys
import xml.etree.ElementTree as ET

from unified_ai_runtime_probe import ROOT, checked, retain, http
from verify_unified_ai_candidate import database_digest
from audit_unified_ai_baseline import audit

STATE = checked(ROOT / "infra/local/unified-ai-20261014-05")
DATABASE = checked(ROOT / "infra/local/unified-ai-20261014-01/business-candidate01.sqlite3")
ACTOR_DATABASE = checked(STATE / "actor-state.sqlite3")
sys.path[:0] = [str(checked(ROOT / "services/api/src")),str(checked(ROOT / "packages/synthetic/src"))]


def tests():
    latest={}
    names=["backend-tests-02.xml","backend-tests-03.xml","backend-tests-04.xml","backend-tests-05.xml","backend-tests-06.xml"]
    for name in names:
        cases=list(ET.parse(checked(STATE / name)).getroot().iter("testcase"))
        assert cases and len({(c.get("classname"),c.get("name")) for c in cases})==len(cases)
        for case in cases:
            latest[(case.get("classname"),case.get("name"))]=not any(case.find(k) is not None for k in ("failure","error","skipped"))
    assert all(latest.values())
    return {"backend_unique":len(latest),"results":names,"all_passed":True,"reruns_not_added":True}


def clone(name,backup):
    destination=checked(STATE / name)
    with destination.open("xb"):
        pass
    with sqlite3.connect(checked(STATE / backup).as_uri()+"?mode=ro",uri=True) as source:
        with sqlite3.connect(destination) as target:source.backup(target)
    return destination


def preserved(before,after,expected_new):
    assert all(after.get(name)==value for name,value in before.items())
    assert set(after)-set(before)==set(expected_new)
    assert all(after[name]["rows"]==1 for name in expected_new)


def compatibility():
    from campus247.infrastructure.repositories.sqlite_conversations import SQLiteConversationRepository
    from campus247.infrastructure.repositories.sqlite_agent_runs import SQLiteAgentRunStore
    from campus247.bootstrap.unified_demo import create_unified_demo_app
    from fastapi.testclient import TestClient
    history=clone("history-compatibility01.sqlite3","history-before.sqlite3")
    runs=clone("runs-compatibility01.sqlite3","runs-before.sqlite3")
    before_history,before_runs=database_digest(history),database_digest(runs)
    conversations=SQLiteConversationRepository(history)
    agent_runs=SQLiteAgentRunStore(runs)
    with sqlite3.connect(history.as_uri()+"?mode=ro",uri=True) as connection:
        ids=[r[0] for r in connection.execute("SELECT id FROM conversation")]
    async def read_history():
        total=0
        for cid in ids:
            assert await conversations.get_conversation(cid) is not None
            total+=len(await conversations.list_messages(cid))
        return total
    message_count=asyncio.run(read_history())
    with sqlite3.connect(runs.as_uri()+"?mode=ro",uri=True) as connection:
        bindings=connection.execute("SELECT id,owner,conversation FROM agent_run").fetchall()
    for rid,owner,cid in bindings:
        assert agent_runs.get(rid,owner,cid) is not None
        assert agent_runs.get(rid,"wrong-owner",cid) is None
    preserved(before_history,database_digest(history),["conversation_schema"])
    preserved(before_runs,database_digest(runs),["agent_schema"])
    assert message_count==before_history["message"]["rows"]
    business=clone("business-compatibility01.sqlite3","business-before.sqlite3")
    before_business=database_digest(business)
    state=checked(STATE / "compatibility-state.sqlite3")
    assert not state.exists()
    app=create_unified_demo_app(business,state_database=state)
    with TestClient(app) as client:
        assert client.get("/v1/assistant/storage").status_code==401
        for actor in ("SV001","OF001","KA001"):
            session=client.post("/v1/auth/demo-login",json={"account":actor});assert session.status_code==200
            response=client.get("/v1/assistant/storage",headers={"Authorization":"Bearer "+session.json()["token"]})
            assert response.status_code==200 and response.headers["cache-control"]=="no-store"
            assert response.json()["actor_state"]=="sqlite_internal" and not response.json()["product_preferences_or_grants_enabled"]
    assert database_digest(business)==before_business
    report={"tests":tests(),"history_records_checked":len(ids),"history_messages_checked":message_count,
        "runs_checked":len(bindings),"all_original_table_rows_preserved":True,
        "only_additive_schema_versions_and_indexes":True,"business_rows_unchanged":True,
        "actor_state_store_isolated_from_business":True,"actor_state_tables":database_digest(state),
        "production_migration":False,"model_dispatches":0,
        "limitations":["Held history/run sources were not migrated or restarted; rehearsals are on exclusive clones",
            "Storage foundation does not enable settings/grants/consent product services"]}
    retain(STATE / "migration-compatibility-01.json",report)
    retain(STATE / "validation-01.json",{"compatibility_passed":True,**tests()})
    return report


def runtime():
    from handoff_unified_ai_session04 import windows_read
    from multi_agent_live_resources import paid_view,native_view
    preflight=json.loads(checked(STATE / "preflight.json").read_text(encoding="utf-8"))
    code,current=http(8006,"/v1/assistant/runtime")
    assert code==200 and current["runtime"]=="unified-local-v5"
    assert current["frontend_build_id"]==preflight["runtime"]["frontend_build_id"] and not current["owns_paid_ledger"]
    before=database_digest(checked(STATE / "business-before.sqlite3"))
    assert database_digest(DATABASE)==before
    actors=[]
    for alias in ("SV001","SV024","OF001","OF002","KA001"):
        code,session=http(8006,"/v1/auth/demo-login",body={"account":alias});assert code==200
        code,profile=http(8006,"/v1/assistant/storage",session["token"])
        assert code==200 and profile["actor_state"]=="sqlite_internal" and not profile["fallback"]
        assert not profile["product_preferences_or_grants_enabled"]
        code,capabilities=http(8006,"/v1/assistant/capabilities",session["token"])
        assert code==200 and "durable_preferences" in capabilities["unsupported"]
        actors.append({"actor":alias,"storage_read":200,"product_preferences_or_grants_enabled":False})
    code,_=http(8006,"/v1/assistant/storage");assert code==401
    assert database_digest(DATABASE)==before
    actor_tables=database_digest(ACTOR_DATABASE)
    assert all(value["rows"]==0 for name,value in actor_tables.items() if name!="unified_state_schema")
    ownership=windows_read();owners={r["LocalPort"]:r["OwningProcess"] for r in ownership["listeners"]}
    assert owners[3006]==22800 and owners[8003]==14208 and owners[18081]==owners[18082]==6132
    old_processes={p["ProcessId"]:p for p in preflight["ownership"]["processes"]}
    processes={p["ProcessId"]:p for p in ownership["processes"]}
    assert all(processes[pid]==old_processes[pid] for pid in (22800,14208,6132))
    baseline=audit(DATABASE)
    assert baseline["human_declared_session_count"]==0 and baseline["all_receipt_chains_valid"]
    paid,native=paid_view(),native_view()
    assert all(paid[k]==preflight["paid_before"][k] for k in ("hard_cap_usd","call_cap","unsettled_attempts_retained"))
    assert native["caps"]==preflight["native_before"]["caps"]
    assert paid["calls"]>=preflight["paid_before"]["calls"]
    assert all(native["counts"][k]>=preflight["native_before"]["counts"][k] for k in native["counts"])
    report={"runtime":current,"ownership":ownership,"actors":actors,"candidate_all_table_rows_unchanged":True,
        "actor_state_empty_initialized":True,"actor_state_tables":actor_tables,"baseline":baseline,
        "frontend_and_existing_model_writers_retained":True,"paid_before":preflight["paid_before"],"paid_after":paid,
        "paid_call_delta":paid["calls"]-preflight["paid_before"]["calls"],"native_after":native,
        "native_deltas":{k:native["counts"][k]-preflight["native_before"]["counts"][k] for k in native["counts"]},
        "caps_and_uncertain_reservations_retained":True,"quota_reset_or_refund":False,"model_dispatches_by_this_work":0,
        "human_measurements_started":0,"new_paid_writer":False,"production_changes":False}
    retain(STATE / "runtime-verification-01.json",report)
    return report


if __name__=="__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv)!=2 or sys.argv[1] not in {"compatibility","runtime"}:
        raise ValueError("explicit compatibility/runtime required; paths are exclusive")
    result={"compatibility":compatibility,"runtime":runtime}[sys.argv[1]]()
    print(json.dumps({"stage":sys.argv[1],"status":"passed","tests":tests(),
        "history_checked":result.get("history_records_checked"),"paid_call_delta":result.get("paid_call_delta")}))
