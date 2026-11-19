import concurrent.futures
from datetime import datetime, timedelta, timezone
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from campus247.bootstrap.unified_demo import create_unified_demo_app


@pytest.fixture
def runtime(tmp_path):
    db = tmp_path / "baseline.sqlite3"
    app = create_unified_demo_app(db)
    current = [datetime(2026,10,14,tzinfo=timezone.utc)]
    app.state.baseline_measurements.clock = lambda: current[0]
    with TestClient(app) as client:
        yield app,client,db,current


def login(c, account="SV001"):
    r = c.post("/v1/auth/demo-login",json={"account":account})
    assert r.status_code == 200
    return {"Authorization":"Bearer "+r.json()["token"]}


def start(c,h,**changes):
    body = {"client_id":"baseline:"+str(uuid.uuid4()),"case_id":"UB-04","operator_kind":"automation",**changes}
    r = c.post("/v1/assistant/baseline/sessions",headers=h,json=body)
    assert r.status_code == 201,r.text
    return r.json()["session"],body


def event(c,h,s,kind,**changes):
    body = {"event_id":"event:"+str(uuid.uuid4()),"expected_version":s["version"],"kind":kind,**changes}
    r = c.post(f"/v1/assistant/baseline/sessions/{s['id']}/events",headers=h,json=body)
    return r,body


def test_clock_segments_fields_receipts_and_restart(runtime):
    app,c,db,clock = runtime
    h = login(c)
    s,_ = start(c,h)
    clock[0] += timedelta(seconds=4)
    r,body = event(c,h,s,"field_edit",field="reason")
    assert r.status_code == 200,r.text
    s = r.json()["session"]
    assert s["active_ms"] == 4000 and s["fields"] == {"reason":1}
    replay = c.post(f"/v1/assistant/baseline/sessions/{s['id']}/events",headers=h,json=body)
    assert replay.json()["is_replay"] and replay.json()["receipt"] == r.json()["receipt"]
    assert replay.json()["session"]["version"] == s["version"]
    clock[0] += timedelta(seconds=1)
    r,_ = event(c,h,s,"wait"); s = r.json()["session"]
    clock[0] += timedelta(seconds=2)
    r,_ = event(c,h,s,"resume"); s = r.json()["session"]
    clock[0] += timedelta(seconds=3)
    r,_ = event(c,h,s,"finish"); s = r.json()["session"]
    assert (s["active_ms"],s["wait_ms"],s["state"]) == (8000,2000,"finished")
    receipts = c.get(f"/v1/assistant/baseline/sessions/{s['id']}/receipts",headers=h).json()["items"]
    assert sum(r["interval_ms"] for r in receipts if r["interval_classification"] == "active") == s["active_ms"]
    assert sum(r["interval_ms"] for r in receipts if r["interval_classification"] == "waiting") == s["wait_ms"]
    assert [r["sequence"] for r in receipts] == [1,2,3,4]
    assert s["operator_kind"] == "automation" and "owner" not in s and "tenant" not in s
    with TestClient(create_unified_demo_app(db)) as restarted:
        restored = restarted.get(f"/v1/assistant/baseline/sessions/{s['id']}",headers=h)
        assert restored.status_code == 200 and restored.json() == s


@pytest.mark.parametrize("account",["SV024","OF001","OF002"])
def test_sessions_cannot_be_read_or_changed_by_another_actor(runtime,account):
    _,c,_,_ = runtime
    s,_ = start(c,login(c))
    h = login(c,account)
    assert c.get(f"/v1/assistant/baseline/sessions/{s['id']}",headers=h).status_code == 404
    assert c.get(f"/v1/assistant/baseline/sessions/{s['id']}/receipts",headers=h).status_code == 404
    r,_ = event(c,h,s,"finish")
    assert r.status_code == 404


def test_role_and_unauthenticated_boundaries(runtime):
    _,c,_,_ = runtime
    assert c.get("/v1/assistant/baseline/sessions").status_code == 401
    h = login(c,"KA001")
    assert c.get("/v1/assistant/baseline/cases",headers=h).status_code == 403
    h = login(c,"OF002")
    assert "UB-08" in {r["id"] for r in c.get("/v1/assistant/baseline/cases",headers=h).json()["items"]}
    r = c.post("/v1/assistant/baseline/sessions",headers=h,json={"client_id":"baseline:"+str(uuid.uuid4()),"case_id":"UB-01","operator_kind":"automation"})
    assert r.status_code == 403


@pytest.mark.parametrize("extra",[{"content":"private"},{"internal_notes":"private"},{"actor_id":"OF001"},{"active_ms":99999}])
def test_raw_data_and_browser_time_are_not_accepted(runtime,extra):
    _,c,_,_ = runtime
    h = login(c);s,_ = start(c,h)
    r,_ = event(c,h,s,"manual_action",**extra)
    assert r.status_code == 422


def test_stale_version_and_parallel_tabs_have_single_transition(runtime):
    _,c,_,_ = runtime
    h = login(c);s,_ = start(c,h)
    def execute(_):
        return event(c,h,s,"pause")[0].status_code
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(execute,range(2))) == [200,409]
    current = c.get(f"/v1/assistant/baseline/sessions/{s['id']}",headers=h).json()
    assert current["state"] == "paused" and current["counts"] == {"pause":1}


def test_long_gap_is_unattributed_not_claimed_human_active_time(runtime):
    _,c,_,clock = runtime
    h = login(c);s,_ = start(c,h,operator_kind="human_declared")
    clock[0] += timedelta(minutes=10)
    r,_ = event(c,h,s,"finish")
    assert r.json()["session"]["active_ms"] == 0
    assert r.json()["session"]["unattributed_ms"] == 600000
    assert "human_declared" in r.json()["session"]["limitation"]


def test_create_retry_and_event_payload_conflict_preserve_original(runtime):
    _,c,_,_ = runtime
    h = login(c);s,body = start(c,h)
    replay = c.post("/v1/assistant/baseline/sessions",headers=h,json=body)
    assert replay.json()["is_replay"] and replay.json()["session"]["id"] == s["id"]
    assert c.post("/v1/assistant/baseline/sessions",headers=h,json={**body,"case_id":"UB-05"}).status_code == 409
    r,body = event(c,h,s,"manual_action")
    conflict = c.post(f"/v1/assistant/baseline/sessions/{s['id']}/events",headers=h,json={**body,"kind":"finish"})
    assert conflict.status_code == 409 and r.json()["session"]["state"] == "active"


def test_baseline_does_not_change_business_records(runtime):
    app,c,_,_ = runtime
    def rows():
        with app.state.service_requests.repository.transaction() as tx:
            return {table:tx.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    for table in ["certificate_request","service_request","service_request_audit","certificate_replay"]}
    before = rows()
    h = login(c);s,_ = start(c,h);event(c,h,s,"finish")
    assert rows() == before


def test_finish_has_a_reserved_event_and_internal_metadata_is_not_projected(runtime):
    app,c,_,_ = runtime
    h = login(c);s,_ = start(c,h)
    with app.state.service_requests.repository.transaction() as tx:
        raw = tx.connection.execute("SELECT record FROM unified_baseline_session WHERE id=?",(s["id"],)).fetchone()[0]
        record = json.loads(raw)
        record["event_count"] = 999
        record["private_note"] = "NEVER-PROJECT-INTERNAL"
        tx.connection.execute("UPDATE unified_baseline_session SET record=? WHERE id=?",(json.dumps(record),s["id"]))
    r,_ = event(c,h,s,"manual_action")
    assert r.status_code == 429
    r,_ = event(c,h,s,"finish")
    assert r.status_code == 200 and r.json()["session"]["event_count"] == 1000
    assert "NEVER-PROJECT-INTERNAL" not in r.text


def test_contract_registry_and_openapi_have_unique_operation_ids(runtime):
    app,c,_,_ = runtime
    r = c.get("/v1/assistant/contracts",headers=login(c))
    assert r.status_code == 200 and r.json()["execution_authority"] == "none"
    assert {"IntentProposal","GrantRequest","TaskRequest","BatchPreparationRequest"} <= set(r.json()["models"])
    schema = app.openapi()
    ids = [operation["operationId"] for path in schema["paths"].values() for method,operation in path.items()
           if method in {"get","post","put","patch","delete"}]
    assert len(set(ids)) == len(ids)
