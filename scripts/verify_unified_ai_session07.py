"""Scoped completion tests and preserved clone rehearsal; no model dispatch."""
import asyncio
import json
import os
import sqlite3
import subprocess
import sys
import xml.etree.ElementTree as ET

from unified_ai_runtime_probe import ROOT, checked, retain
from verify_unified_ai_candidate import database_digest

STATE = checked(ROOT / "infra/local/unified-ai-20261014-07")
sys.path[:0] = [str(checked(ROOT / "services/api/src")),str(checked(ROOT / "packages/synthetic/src"))]


def test_results():
    latest = {}
    files = sorted(p for p in STATE.glob("backend-tests-*.xml") if p.is_file())
    for path in files:
        for case in ET.parse(checked(path)).getroot().iter("testcase"):
            latest[(case.get("classname"),case.get("name"))] = not any(case.find(k) is not None for k in ("failure","error","skipped"))
    assert latest and all(latest.values())
    front = json.loads(checked(STATE / "frontend-tests-01.json").read_text(encoding="utf-8"))
    assert front["numFailedTests"] == front["numPendingTests"] == 0
    return {"backend_unique":len(latest),"frontend_unique":front["numPassedTests"],"all_passed":True,
            "backend_files":[p.name for p in files],"frontend_file":"frontend-tests-01.json","reruns_not_added":True}


def tests(final=False,number=None):
    from verify_unified_ai_session06 import TEST_FILES
    selected = list(dict.fromkeys([*TEST_FILES,"tests/integration/test_unified_storage_completion.py",
        "tests/api/test_privacy_requests.py","tests/api/test_answer_feedback.py","tests/api/test_session_revocation.py",
        "tests/api/test_identity_middleware.py","tests/api/test_identity_boundary.py"]))
    number = number if number is not None else "03" if final else "02"
    paths = [checked(STATE / name) for name in ("backend-tests-"+number,"backend-tests-"+number+".xml","backend-tests-"+number+".log",
                                               "idempotency-tests"+number+".sqlite3","test-command-"+number+".json")]
    if final:
        selected = [p for p in selected if p in {"tests/integration/test_unified_storage_completion.py",
            "tests/integration/test_unified_durable_services.py","tests/api/test_unified_storage_profile.py",
            "tests/api/test_privacy_requests.py","tests/api/test_answer_feedback.py","tests/api/test_session_revocation.py",
            "tests/api/test_identity_middleware.py","tests/api/test_identity_boundary.py",
            "tests/integration/test_unified_storage_transactions.py","tests/unit/assistance/test_actor_state_storage.py"}]
    assert not any(path.exists() for path in paths)
    command = [sys.executable,"-B","-m","pytest",*selected,"-q","-p","no:cacheprovider","-p","pytest_asyncio.plugin",
        "--basetemp="+str(paths[0]),"--junitxml="+str(paths[1])]
    env = {**os.environ,"PYTEST_DISABLE_PLUGIN_AUTOLOAD":"1","PYTHONDONTWRITEBYTECODE":"1","CAMPUS247_IDEMPOTENCY_DB":str(paths[3])}
    with paths[2].open("xb") as log: result = subprocess.run(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,check=False)
    retain(paths[4],{"command":command,"exit_code":result.returncode,"log":paths[2].name,
        "environment":{"PYTEST_DISABLE_PLUGIN_AUTOLOAD":"1","PYTHONDONTWRITEBYTECODE":"1","CAMPUS247_IDEMPOTENCY_DB":str(paths[3])},
        "new_fixtures_retained":True,"model_dispatches":0})
    if result.returncode:
        print(paths[2].read_text(encoding="utf-8",errors="replace")[-16000:]);raise RuntimeError("retain failing evidence; never rerun into existing paths")
    print(json.dumps(test_results()))


def clone(name,backup):
    destination = checked(STATE / name)
    with destination.open("xb"):pass
    with sqlite3.connect(checked(STATE / backup).as_uri()+"?mode=ro",uri=True) as source, sqlite3.connect(destination) as target:
        source.backup(target)
    return destination


def compatibility(number="01"):
    from campus247.application.conversation.messages import ConversationMessageService
    from campus247.bootstrap.unified_demo import create_unified_demo_app
    from campus247.infrastructure.repositories.held_history import HeldHistoryRepository
    from campus247.infrastructure.repositories.sqlite_agent_runs import (
        SQLiteAgentRunStore,
    )
    from campus247.infrastructure.repositories.sqlite_conversations import (
        SQLiteConversationRepository,
    )
    from fastapi.testclient import TestClient
    paths = {name:clone(name+"-compatibility"+number+".sqlite3",name+"-before.sqlite3") for name in ("business","actor","history","runs")}
    before = {name:database_digest(path) for name,path in paths.items()}
    held = HeldHistoryRepository(paths["history"],tenant="huce-local-public")
    with sqlite3.connect(paths["history"].as_uri()+"?mode=ro",uri=True) as connection:
        ids = [row[0] for row in connection.execute("SELECT id FROM conversation")]
    async def read_all():
        count = 0
        for identifier in ids:
            assert await held.get_conversation(identifier) is not None
            count += len(await held.list_messages(identifier))
        return count
    messages = asyncio.run(read_all())
    assert database_digest(paths["history"]) == before["history"]
    app = create_unified_demo_app(paths["business"],state_database=paths["actor"],consent_mode="sqlite",history_database=paths["history"])
    with TestClient(app) as client:
        assert client.get("/v1/conversations/019a0000-0000-7000-8000-000000000001/messages").status_code == 401
        for account in ("SV001","SV024","OF001","OF002","KA001"):
            login = client.post("/v1/auth/demo-login",json={"account":account});assert login.status_code == 200
            headers = {"Authorization":"Bearer "+login.json()["token"]}
            assert client.get("/v1/assistant/storage",headers=headers).json()["conversation_reads"] == "validated_held_read_only"
            assert client.get("/v1/privacy/consents",headers=headers).json()["items"] == []
    # Migration rehearsal stays on clones; do not bind unknown legacy owners
    # to a tenant, and never initialize the held sources.
    migrated_history = SQLiteConversationRepository(paths["history"])
    runs = SQLiteAgentRunStore(paths["runs"])
    with sqlite3.connect(paths["runs"].as_uri()+"?mode=ro",uri=True) as connection:
        rows = connection.execute("SELECT id,owner,conversation FROM agent_run").fetchall()
    for run,owner,conversation in rows:
        assert runs.get(run,owner,conversation) is not None and runs.get(run,"wrong-owner",conversation) is None
    assert asyncio.run(ConversationMessageService(migrated_history).get_conversation(ids[0])) is not None
    preservation = []
    for name,path in paths.items():
        after = database_digest(path)
        assert all(after.get(table) == value for table,value in before[name].items())
        assert set(after)-set(before[name]) <= {"conversation_schema","agent_schema"}
        preservation.append({"database":name,"all_original_rows_preserved":True,"added_tables":sorted(set(after)-set(before[name]))})
    assert messages == before["history"]["message"]["rows"]
    result = {"tests":test_results(),"history_conversations":len(ids),"history_messages":messages,"agent_runs":len(rows),
        "preservation":preservation,"held_history_reads_have_no_schema_writes":True,"originals_not_migrated":True,
        "human_measurements_started":0,"model_dispatches":0}
    retain(STATE / ("migration-compatibility-"+number+".json"),result);print(json.dumps(result))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2 or sys.argv[1] not in {"tests","final-tests","batch-tests","post-lint-tests","compatibility","compatibility-retry"}:raise ValueError("explicit exclusive stage required")
    {"tests":tests,"final-tests":lambda:tests(final=True),"batch-tests":lambda:tests(number="04"),
        "post-lint-tests":lambda:tests(final=True,number="05"),"compatibility":compatibility,
        "compatibility-retry":lambda:compatibility(number="02")}[sys.argv[1]]()
