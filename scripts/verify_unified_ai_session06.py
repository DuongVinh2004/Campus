"""Retained deterministic tests, clone rehearsal and read-only runtime evidence."""
import asyncio
import json
import os
import sqlite3
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from unified_ai_runtime_probe import ROOT, checked, retain, http
from handoff_unified_ai_session04 import windows_read
from verify_unified_ai_candidate import database_digest
from audit_unified_ai_baseline import audit
from multi_agent_live_resources import paid_view, native_view

STATE = checked(ROOT / "infra/local/unified-ai-20261014-06")
sys.path[:0] = [str(checked(ROOT / "services/api/src")),str(checked(ROOT / "packages/synthetic/src"))]
TEST_FILES = [
    "tests/integration/test_unified_durable_services.py",
    "tests/api/test_certificate_stage1.py", "tests/api/test_chat_sse.py", "tests/api/test_multi_agent_api.py",
    "tests/api/test_privacy_notice_consent.py", "tests/api/test_privacy_authorization.py",
    "tests/api/test_service_stage6.py", "tests/api/test_unified_assistance.py", "tests/api/test_unified_baseline.py",
    "tests/api/test_unified_proxy_compatibility.py", "tests/api/test_unified_storage_profile.py",
    "tests/api/test_unified_workflow.py", "tests/api/test_unified_workflow_continuation.py",
    "tests/integration/conversation/test_messages.py", "tests/integration/test_durable_consent_storage.py",
    "tests/integration/test_repository_composition.py", "tests/integration/test_unified_history_baseline.py",
    "tests/integration/test_unified_storage_transactions.py", "tests/unit/agent/test_multi_agent_admission.py",
    "tests/unit/agent/test_multi_agent_integrated.py", "tests/unit/assistance/test_actor_state_storage.py",
    "tests/unit/assistance/test_baseline_evidence.py", "tests/unit/assistance/test_unified_contracts.py",
    "tests/unit/conversation/test_sqlite_local_history.py", "tests/unit/conversation/test_stream_result.py",
    "tests/unit/test_settings.py", "tests/security/test_action_confirmation.py",
]


def test_results():
    latest = {}
    files = ["backend-tests-01.xml", "backend-tests-02.xml", "backend-tests-03.xml"]
    for name in files:
        for case in ET.parse(checked(STATE / name)).getroot().iter("testcase"):
            latest[(case.get("classname"),case.get("name"))] = not any(case.find(k) is not None for k in ("failure","error","skipped"))
    assert latest and all(latest.values())
    return {"unique":len(latest), "all_passed":True, "reruns_not_added":True, "files":files}


def tests(final=False):
    number = "03" if final else "02"
    destinations = [checked(STATE / name) for name in (
        "backend-tests-"+number, "backend-tests-"+number+".xml", "backend-tests-"+number+".log", "test-command-"+number+".json", "idempotency-tests"+number+".sqlite3")]
    assert not any(p.exists() for p in destinations)
    assert all(checked(ROOT / path).is_file() for path in TEST_FILES)
    env = {**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD":"1", "PYTHONDONTWRITEBYTECODE":"1",
           "CAMPUS247_IDEMPOTENCY_DB":str(destinations[4])}
    selected = [p for p in TEST_FILES if p in {
        "tests/integration/test_unified_durable_services.py", "tests/integration/test_durable_consent_storage.py",
        "tests/unit/assistance/test_actor_state_storage.py", "tests/api/test_unified_storage_profile.py",
        "tests/api/test_privacy_notice_consent.py", "tests/unit/test_settings.py", "tests/security/test_action_confirmation.py",
        "tests/api/test_unified_workflow.py"}] if final else TEST_FILES
    command = [sys.executable,"-B","-m","pytest",*selected,"-q","-p","no:cacheprovider","-p","pytest_asyncio.plugin",
               "--basetemp="+str(destinations[0]),"--junitxml="+str(destinations[1])]
    with destinations[2].open("xb") as log:
        result = subprocess.run(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
    retain(destinations[3],{"command":command,"exit_code":result.returncode,"log":destinations[2].name,
        "fixtures_retained":True,"model_dispatches":0})
    if result.returncode:
        print(destinations[2].read_text(encoding="utf-8",errors="replace")[-12000:])
        raise RuntimeError("retain failed test evidence; use a fresh namespace for any rerun")
    print(json.dumps(test_results()))


def clone(name, backup):
    target = checked(STATE / name)
    with target.open("xb"):
        pass
    with sqlite3.connect(checked(STATE / backup).as_uri()+"?mode=ro",uri=True) as source:
        with sqlite3.connect(target) as destination: source.backup(destination)
    return target


def compatibility():
    from campus247.infrastructure.repositories.sqlite_conversations import SQLiteConversationRepository
    from campus247.infrastructure.repositories.sqlite_agent_runs import SQLiteAgentRunStore
    from campus247.bootstrap.unified_demo import create_unified_demo_app
    from fastapi.testclient import TestClient
    history = clone("history-compatibility01.sqlite3","history-before.sqlite3")
    runs = clone("runs-compatibility01.sqlite3","runs-before.sqlite3")
    business = clone("business-compatibility01.sqlite3","business-before.sqlite3")
    actor = clone("actor-compatibility01.sqlite3","actor-before.sqlite3")
    before = {k:database_digest(p) for k,p in {"history":history,"runs":runs,"business":business,"actor":actor}.items()}
    conversations, agents = SQLiteConversationRepository(history), SQLiteAgentRunStore(runs)
    with sqlite3.connect(history.as_uri()+"?mode=ro",uri=True) as connection:
        ids = [r[0] for r in connection.execute("SELECT id FROM conversation")]
    async def read():
        messages = 0
        for cid in ids:
            assert await conversations.get_conversation(cid) is not None
            messages += len(await conversations.list_messages(cid))
        return messages
    messages = asyncio.run(read())
    with sqlite3.connect(runs.as_uri()+"?mode=ro",uri=True) as connection:
        bindings = connection.execute("SELECT id,owner,conversation FROM agent_run").fetchall()
    for rid,owner,cid in bindings:
        assert agents.get(rid,owner,cid) is not None and agents.get(rid,"wrong-owner",cid) is None
    app = create_unified_demo_app(business,state_database=actor,consent_mode="sqlite")
    assert app.state.assistant_settings and app.state.assistant_grant_requests and app.state.assistant_proposals
    with TestClient(app) as client:
        assert client.get("/v1/privacy/consents").status_code == 401
        version = client.get("/v1/privacy/notice").json()["version"]
        for account in ("SV001","SV024","OF001","OF002","KA001"):
            login = client.post("/v1/auth/demo-login",json={"account":account}); assert login.status_code == 200
            headers = {"Authorization":"Bearer "+login.json()["token"]}
            consents = client.get("/v1/privacy/consents",headers=headers)
            assert consents.status_code == 200 and consents.json()["items"] == []
            assert client.get("/v1/assistant/storage",headers=headers).json()["consent"] == "sqlite"
        assert version == "unified-local-consent.v1"
    preservation = []
    for key,path in {"history":history,"runs":runs,"business":business,"actor":actor}.items():
        after = database_digest(path)
        assert all(after.get(table) == value for table,value in before[key].items())
        assert set(after)-set(before[key]) <= {"conversation_schema","agent_schema"}
        preservation.append({"database":key,"all_original_table_rows_preserved":True,
                             "added_tables":sorted(set(after)-set(before[key]))})
    assert messages == before["history"]["message"]["rows"]
    report = {"tests":test_results(),"history_conversations":len(ids),"history_messages":messages,"agent_runs":len(bindings),
        "preservation":preservation,"durable_consent_composition":"sqlite","internal_services_wired":True,
        "consent_writes_on_retained_data":0,"product_settings_or_grants_enabled":False,
        "production_migration":False,"originals_not_opened_for_write":True,"model_dispatches":0}
    retain(STATE / "migration-compatibility-01.json",report)
    print(json.dumps(report))


def runtime():
    preflight = json.loads(checked(STATE / "preflight.json").read_text(encoding="utf-8"))
    ownership = windows_read()
    assert ownership == preflight["ownership"]
    code,current = http(8006,"/v1/assistant/runtime")
    assert code == 200 and current == preflight["runtime"] and current["runtime"] == "unified-local-v5"
    held = []
    for snapshot in preflight["snapshots"]:
        after = database_digest(checked(ROOT / snapshot["source"]))
        assert after == snapshot["tables"]
        held.append({"path":snapshot["source"],"all_table_rows_unchanged":True})
    baseline = audit(checked(ROOT / "infra/local/unified-ai-20261014-01/business-candidate01.sqlite3"))
    assert baseline["human_declared_session_count"] == 0 and baseline["all_receipt_chains_valid"]
    paid,native = paid_view(),native_view()
    assert paid == preflight["paid_before"] and native == preflight["native_before"]
    report = {"captured_at":datetime.now(timezone.utc).isoformat(),"runtime":current,"ownership":ownership,
        "held_sources":held,"baseline":baseline,"source_candidate_version":"unified-local-v6",
        "runtime_handoff":False,"handoff_reason":"Internal services have no UI consumer yet; stateless candidate sessions do not provide reliable proof that no user is active. Retain v5.",
        "source_v6_verified_on_fixtures_and_clones":True,"live_consent_adapter_enabled":False,
        "frontend_unchanged":True,"existing_model_writers_unchanged":True,
        "paid_call_delta":0,"native_deltas":{"http":0,"inference":0,"tokens":0},
        "caps_and_uncertain_reservations_retained":True,"human_measurements_started":0,
        "model_dispatches":0,"production_changes":False}
    retain(STATE / "runtime-verification-01.json",report)
    print(json.dumps({"runtime":current["runtime"],"all_held_sources_unchanged":True,"runtime_handoff":False,"paid_call_delta":0}))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv)!=2 or sys.argv[1] not in {"tests","final-tests","compatibility","runtime"}:
        raise ValueError("explicit stage required; each output is exclusive-create")
    {"tests":tests,"final-tests":lambda:tests(final=True),"compatibility":compatibility,"runtime":runtime}[sys.argv[1]]()
