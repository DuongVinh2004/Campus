"""Every fixture is new and retained; no real grants or model dispatch."""
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
from datetime import datetime, timezone

import pytest

from campus247.application.assistance.state_storage import (StateScope, StoredState, StateReceipt, StorageConflict, StorageCorrupt,
    StorageUnavailable, digest, payload_for)
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.repositories.sqlite_actor_state import SQLiteActorStateStore


@pytest.fixture
def store(tmp_path):
    path=tmp_path / "actor-state.sqlite3"
    return SQLiteActorStateStore(path),StateScope("huce-test",generate_uuid7()),path


def counts(path):
    with sqlite3.connect(path.as_uri()+"?mode=ro",uri=True) as connection:
        return [connection.execute("SELECT COUNT(*) FROM "+table).fetchone()[0] for table in
            ["unified_actor_state","unified_state_revision","unified_state_receipt"]]


def test_commit_replay_revision_and_preferences_survive_restart(store):
    repository,scope,path=store
    payload={"locale":"en","reply_style":"steps"}
    receipt=repository.commit(scope,"preferences","account",0,payload,"client-preferences-001")
    first=repository.get(scope,"preferences","account")
    assert first.payload["locale"]=="en" and first.version==1 and counts(path)==[1,1,1]
    second=SQLiteActorStateStore(path)
    replay=second.commit(scope,"preferences","account",0,payload,"client-preferences-001")
    assert replay.is_replay and replay.receipt_id==receipt.receipt_id and replay.committed_at==receipt.committed_at
    assert second.get(scope,"preferences","account")==first and counts(path)==[1,1,1]
    second.commit(scope,"preferences","account",1,{"locale":"vi"},"client-preferences-002")
    assert [row.version for row in second.history(scope,"preferences","account")]==[1,2]
    assert second.history(scope,"preferences","account",after_version=1,limit=1)[0].payload["locale"]=="vi"
    old=second.commit(scope,"preferences","account",0,payload,"client-preferences-001")
    assert old.version==1 and old.is_replay and counts(path)==[1,2,2]


def test_actor_and_tenant_isolation_and_opaque_receipt(store):
    repository,scope,path=store
    receipt=repository.commit(scope,"preferences","account",0,{"custom_instructions":"PRIVATE-FIXTURE"},"same-client-001")
    for other in [StateScope(scope.tenant,generate_uuid7()),StateScope("other-tenant",scope.owner)]:
        assert repository.get(other,"preferences","account") is None
        assert repository.history(other,"preferences","account")==[]
        saved=repository.commit(other,"preferences","account",0,{"locale":"en"},"same-client-001")
        assert not saved.is_replay and saved.receipt_id!=receipt.receipt_id
    assert "PRIVATE-FIXTURE" not in receipt.model_dump_json() and counts(path)==[3,3,3]


def test_stale_version_idempotency_conflict_and_payload_injection_preserve_state(store):
    repository,scope,path=store
    repository.commit(scope,"preferences","account",0,{"locale":"vi"},"client-original-001")
    before=counts(path)
    for version,client,payload in [(0,"client-new-002",{"locale":"en"}),
            (1,"client-original-001",{"locale":"en"})]:
        with pytest.raises(StorageConflict):repository.commit(scope,"preferences","account",version,payload,client)
    for payload in [{"locale":"vi","memory_enabled":True},{"consent":True},{"custom_instructions":"bad\x00"},{"reply_style":"execute"}]:
        with pytest.raises(ValueError):repository.commit(scope,"preferences","account",1,payload,"client-invalid-001")
    with pytest.raises(ValueError):repository.commit(scope,"preferences","account",True,{"locale":"en"},"client-invalid-001")
    assert counts(path)==before and repository.get(scope,"preferences","account").version==1


@pytest.mark.parametrize("target",["unified_state_revision","unified_state_receipt"])
def test_audit_or_receipt_failure_rolls_back_state_update(store,target):
    repository,scope,path=store
    repository.commit(scope,"preferences","account",0,{"locale":"vi"},"client-before-001")
    before=counts(path)
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TRIGGER fixture_abort BEFORE INSERT ON "+target+" BEGIN SELECT RAISE(ABORT,'fixture failure'); END")
    with pytest.raises(StorageUnavailable,match="STATE_STORAGE_UNAVAILABLE"):
        repository.commit(scope,"preferences","account",1,{"locale":"en"},"client-failed-002")
    assert repository.get(scope,"preferences","account").payload["locale"]=="vi" and counts(path)==before


@pytest.mark.parametrize("same_client",[True,False])
def test_concurrent_creation_commits_once(store,same_client):
    _,scope,path=store
    def write(index):
        try:
            return SQLiteActorStateStore(path).commit(scope,"preferences","account",0,{"locale":"vi"},
                "client-race-001" if same_client else "client-race-00"+str(index))
        except StorageConflict as error:return str(error)
    with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(write,[1,2]))
    if same_client:
        assert sorted(r.is_replay for r in outcomes)==[False,True]
        assert outcomes[0].receipt_id==outcomes[1].receipt_id
    else:
        assert sum(isinstance(r,str) and r=="STATE_STALE_VERSION" for r in outcomes)==1
    assert counts(path)==[1,1,1]


def test_consent_withdrawal_is_append_only_and_does_not_erase_preferences(store):
    repository,scope,path=store
    repository.commit(scope,"preferences","account",0,{"locale":"en"},"client-prefs-001")
    for version,decision in enumerate(["GRANTED","WITHDRAWN"]):
        repository.commit(scope,"consent","personalization",version,
            {"purpose":"OPTIONAL_PERSONALIZATION","decision":decision,"notice_version":"fixture-v1"},"client-consent-00"+str(version))
    restarted=SQLiteActorStateStore(path)
    assert [r.payload["decision"] for r in restarted.history(scope,"consent","personalization")]==["GRANTED","WITHDRAWN"]
    assert restarted.get(scope,"preferences","account").payload["locale"]=="en"


def test_grants_remain_requests_and_never_activate_authority(store):
    repository,scope,path=store
    payload={"client_id":generate_uuid7(),"purpose":"source_assistance","capability":"read_own_resource",
        "resource":{"kind":"service_request","id":generate_uuid7(),"expected_version":1},"requested_lifetime_seconds":120}
    receipt=repository.commit(scope,"grant_request","request-001",0,payload,"client-grant-001")
    assert repository.get(scope,"grant_request","request-001").payload["state"]=="requested"
    for extra in [{"state":"active"},{"roles":["SYSTEM_ADMIN"]},{"capability":"approve"}]:
        with pytest.raises(ValueError):repository.commit(scope,"grant_request","request-002",0,{**payload,**extra},"client-grant-002")
    assert receipt.state=="committed" and counts(path)==[1,1,1]


@pytest.mark.parametrize("table",["unified_actor_state","unified_state_revision","unified_state_receipt"])
def test_initially_malformed_owner_binding_is_rejected_without_repair(store,table):
    repository,scope,path=store
    payload={"locale":"en"};client="client-corrupt-001"
    value=payload_for("preferences",payload);sha=digest(value);at=datetime.now(timezone.utc).isoformat()
    record=StoredState(tenant=scope.tenant,owner=scope.owner,namespace="preferences",key="account",version=1,
        payload=value,sha256=sha,committed_at=at).model_dump(mode="json")
    fingerprint=digest({"tenant":scope.tenant,"owner":scope.owner,"namespace":"preferences","key":"account",
        "expected_version":0,"payload_sha256":sha})
    receipt=StateReceipt(receipt_id=generate_uuid7(),tenant=scope.tenant,owner=scope.owner,client_id=client,
        namespace="preferences",key="account",version=1,payload_sha256=sha,fingerprint=fingerprint,committed_at=at).model_dump(mode="json")
    # Construct malformed fixture rows initially; no committed audit is overwritten.
    state_record,revision_record,receipt_record=dict(record),dict(record),dict(receipt)
    {"unified_actor_state":state_record,"unified_state_revision":revision_record,"unified_state_receipt":receipt_record}[table]["owner"]=generate_uuid7()
    with sqlite3.connect(path) as connection:
        connection.execute("INSERT INTO unified_actor_state VALUES(?,?,?,?,?,?)",(scope.tenant,scope.owner,"preferences","account",1,json.dumps(state_record)))
        connection.execute("INSERT INTO unified_state_revision VALUES(?,?,?,?,?,?,?)",(scope.tenant,scope.owner,"preferences","account",1,receipt["receipt_id"],json.dumps(revision_record)))
        connection.execute("INSERT INTO unified_state_receipt VALUES(?,?,?,?,?)",(scope.tenant,scope.owner,client,fingerprint,json.dumps(receipt_record)))
    with pytest.raises(StorageCorrupt):
        if table=="unified_actor_state":repository.get(scope,"preferences","account")
        else:repository.commit(scope,"preferences","account",0,payload,client)
    assert counts(path)==[1,1,1]


def test_missing_database_fails_without_creating_an_empty_replacement(store,tmp_path):
    repository,scope,path=store
    missing=tmp_path / "missing.sqlite3"
    repository.path=missing  # Preserve the created database; simulate configured storage disappearing.
    with pytest.raises(StorageUnavailable):repository.get(scope,"preferences","account")
    assert not missing.exists() and counts(path)==[0,0,0]


def test_unknown_schema_is_preserved_and_denied(tmp_path):
    path=tmp_path / "future.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE unified_state_schema(version INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO unified_state_schema VALUES(999)")
    with pytest.raises(StorageCorrupt,match="STATE_SCHEMA_UNSUPPORTED"):SQLiteActorStateStore(path)
    with sqlite3.connect(path.as_uri()+"?mode=ro",uri=True) as connection:
        assert connection.execute("SELECT version FROM unified_state_schema").fetchall()==[(999,)]
        assert connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()==[("unified_state_schema",)]


def test_initial_state_missing_revision_cannot_be_read_or_hidden_by_next_commit(store):
    repository,scope,path=store
    payload=payload_for("preferences",{"locale":"en"})
    record=StoredState(tenant=scope.tenant,owner=scope.owner,namespace="preferences",key="account",version=1,
        payload=payload,sha256=digest(payload),committed_at=datetime.now(timezone.utc).isoformat())
    with sqlite3.connect(path) as connection:
        connection.execute("INSERT INTO unified_actor_state VALUES(?,?,?,?,?,?)",(scope.tenant,scope.owner,"preferences","account",1,record.model_dump_json()))
    with pytest.raises(StorageCorrupt,match="STATE_CURRENT_REVISION_MISMATCH"):
        repository.get(scope,"preferences","account")
    with pytest.raises(StorageCorrupt,match="STATE_CURRENT_REVISION_MISMATCH"):
        repository.commit(scope,"preferences","account",1,{"locale":"vi"},"client-no-repair-001")
    assert counts(path)==[1,0,0]
