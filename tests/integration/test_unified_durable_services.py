"""Fresh retained fixtures: confirmed storage is never business authority."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import hashlib
import sqlite3

from fastapi.testclient import TestClient
import pytest

from campus247.application.assistance.durable_services import ConfirmedPreview
from campus247.application.assistance.state_storage import StorageConflict, StorageUnavailable, StorageCorrupt
from campus247.application.document_request.certificates import CertificateError
from campus247.bootstrap.app import create_app
from campus247.bootstrap.settings import Settings
from campus247.bootstrap.unified_demo import create_unified_demo_app
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
from campus247.infrastructure.llm.fake import DeterministicFakeProvider
from campus247.infrastructure.repositories.sqlite_actor_state import SQLiteActorStateStore
from campus247.ports.identity import AccountState
from tests.api.test_certificate_stage1 import login
from tests.api.test_service_stage6 import draft


def actor(account="SV001"):
    from identities import generate_identities
    rows = generate_identities()["records"]
    uid = rows["student_profile"][0 if account == "SV001" else 1]["user_id"]
    adapter = SyntheticIdentityAdapter("campus247-demo-secret-key-huce", environment="development", tenant_id="huce-local-public")
    return adapter.resolve_token(adapter.mint_token(uid))


@pytest.fixture
def runtime(tmp_path):
    business, state = tmp_path / "business.sqlite3", tmp_path / "state.sqlite3"
    app = create_unified_demo_app(business, state_database=state, consent_mode="sqlite")
    with TestClient(app) as client:
        yield app, client, business, state


def counts(path):
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as connection:
        return [connection.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] for table in
                ("unified_actor_state", "unified_state_revision", "unified_state_receipt")]


def tables(path):
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as connection:
        return {name: connection.execute('SELECT * FROM "' + name.replace('"','""') + '" ORDER BY rowid').fetchall()
                for name, in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def new_resource(client):
    return draft(client, login(client))


def grant(record, **changes):
    return {"client_id": generate_uuid7(), "purpose": "source_assistance", "capability": "read_own_resource",
        "resource": {"kind": "service_request", "id": record["id"], "expected_version": record["version"]},
        "requested_lifetime_seconds": 120, **changes}


def proposal(app, identity, record):
    from campus247.application.assistance.workflow import WorkflowResolveRequest
    resource = {"kind":"service_request", "id":record["id"], "expected_version":record["version"]}
    evidence = app.state.workflow_packages.resolve(identity, WorkflowResolveRequest.model_validate({"resource":resource}))
    binding = evidence.binding
    assert binding is not None
    source = binding.source
    return {"client_id":generate_uuid7(), "target":resource, "audience":"student", "operation":"revise_draft",
        "workflow_binding":{"workflow":evidence.resource.workflow, "version":binding.workflow_version,
            "source":{"source_id":source.source_id, "version_id":source.version_id, "locator":source.locator,
                      "sha256":source.rendition_sha256, "classification":source.classification},
            "effective_from":source.effective_from, "effective_until":source.effective_until},
        "changes":[{"field":"reason", "before":record["payload"]["reason"], "candidate":"A candidate reason", "origin":"user_statement"}]}


def test_settings_confirmed_restart_replay_and_defaults_are_not_saved(runtime):
    app, _, business, state = runtime
    service = app.state.assistant_settings; identity = actor()
    assert service.read(identity)["version"] == 0 and not service.read(identity)["saved"]
    before = tables(business)
    prepared = service.prepare(identity, {"locale":"en", "custom_instructions":"A private style instruction"}, 0, generate_uuid7())
    receipt = service.confirm(identity, prepared, confirmed=True)
    restarted = create_unified_demo_app(business, state_database=state)
    restored = restarted.state.assistant_settings
    assert restored.read(identity)["preferences"]["locale"] == "en"
    assert not restored.read(identity)["consumer_enabled"]
    replay = restored.confirm(identity, prepared, confirmed=True)
    assert replay.is_replay and replay.receipt_id == receipt.receipt_id and counts(state) == [1,1,1]
    assert "private" not in receipt.model_dump_json() and tables(business) == before
    assert restored.read(actor("SV024"))["version"] == 0


@pytest.mark.parametrize("alteration", ["payload", "token", "session", "tenant", "other_owner", "unconfirmed", "expired_identity", "inactive"])
def test_confirmation_rejects_changed_content_or_identity_without_writing(runtime, alteration):
    app, _, _, state = runtime; service = app.state.assistant_settings; identity = actor()
    prepared = service.prepare(identity, {"locale":"en"}, 0, generate_uuid7()); confirm = True
    if alteration == "payload":
        body = json.loads(prepared.preview.normalized_payload); body["payload"]["locale"] = "vi"
        prepared = ConfirmedPreview(replace(prepared.preview, normalized_payload=json.dumps(body),
            payload_hash="sha256:" + hashlib.sha256(json.dumps(body).encode()).hexdigest()), prepared.confirmation_token)
    elif alteration == "token": prepared = ConfirmedPreview(prepared.preview, "invalid.token")
    elif alteration == "session": identity = replace(identity, session_id=generate_uuid7())
    elif alteration == "tenant": identity = replace(identity, tenant_id="other-tenant")
    elif alteration == "other_owner": identity = actor("SV024")
    elif alteration == "unconfirmed": confirm = False
    elif alteration == "inactive": identity = replace(identity, account_state=AccountState.SUSPENDED)
    else: identity = replace(identity, auth_time=datetime.now(timezone.utc)-timedelta(hours=2), expires_at=datetime.now(timezone.utc)-timedelta(seconds=1))
    with pytest.raises(CertificateError): service.confirm(identity, prepared, confirmed=confirm)
    assert counts(state) == [0,0,0]


def test_concurrent_settings_same_preview_replays_and_distinct_cas_rejects(runtime):
    app, _, _, state = runtime; service = app.state.assistant_settings; identity = actor()
    prepared = service.prepare(identity, {"locale":"en"}, 0, generate_uuid7())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _:service.confirm(identity, prepared, confirmed=True), range(2)))
    assert sorted(r.is_replay for r in results) == [False, True] and results[0].receipt_id == results[1].receipt_id
    previews = [service.prepare(identity, {"locale":locale}, 1, generate_uuid7()) for locale in ("vi","en")]
    def commit(prepared):
        try: return service.confirm(identity, prepared, confirmed=True)
        except StorageConflict as exc: return str(exc)
    with ThreadPoolExecutor(max_workers=2) as pool: outcomes = list(pool.map(commit, previews))
    assert sum(isinstance(r,str) and r == "STATE_STALE_VERSION" for r in outcomes) == 1
    assert counts(state) == [1,2,2]


def test_grant_request_restart_reprepare_revoke_replay_never_active(runtime):
    app, client, business, state = runtime; identity = actor(); record = new_resource(client)
    service = app.state.assistant_grant_requests; request = grant(record); before = tables(business)
    prepared = service.prepare(identity, request); first = service.confirm(identity, prepared, confirmed=True)
    restored = create_unified_demo_app(business, state_database=state).state.assistant_grant_requests
    replay = restored.confirm(identity, restored.prepare(identity, request), confirmed=True)
    assert replay.is_replay and replay.receipt_id == first.receipt_id
    read = restored.read(identity, request["client_id"])
    assert read["state"] == "requested" and not read["active"] and read["action_authority"] == "none"
    revoke = restored.prepare_revoke(identity, request["client_id"], 1, generate_uuid7())
    withdrawal = restored.confirm(identity, revoke, confirmed=True)
    assert restored.confirm(identity, revoke, confirmed=True).receipt_id == withdrawal.receipt_id
    assert restored.read(identity, request["client_id"])["state"] == "revoked"
    assert counts(state) == [1,2,2] and tables(business) == before
    with pytest.raises(CertificateError): restored.read(actor("SV024"), request["client_id"])
    with pytest.raises(CertificateError): restored.prepare(identity, {**request, "capability":"prepare_draft"})


def test_expired_grant_requests_do_not_activate_or_get_renewed(runtime, monkeypatch):
    import campus247.application.assistance.durable_services as module
    app, client, _, _ = runtime; identity = actor(); service = app.state.assistant_grant_requests
    request = grant(new_resource(client), requested_lifetime_seconds=1)
    service.confirm(identity, service.prepare(identity, request), confirmed=True)
    class Future(datetime):
        @classmethod
        def now(cls, tz=None): return datetime.now(tz)+timedelta(seconds=2)
    monkeypatch.setattr(module, "datetime", Future)
    assert service.read(identity, request["client_id"])["state"] == "expired"
    with pytest.raises(CertificateError, match="hết hạn"):
        service.confirm(identity, service.prepare(identity, request), confirmed=True)
    revoke = service.prepare_revoke(identity, request["client_id"], 1, generate_uuid7())
    service.confirm(identity, revoke, confirmed=True)
    assert service.read(identity, request["client_id"])["state"] == "revoked"


@pytest.mark.parametrize("mode", ["wrong_owner", "stale", "unsupported", "false_authority"])
def test_grant_service_rechecks_resource_and_rejects_unsupported_consumers(runtime, mode):
    app, client, _, state = runtime; identity = actor(); service = app.state.assistant_grant_requests
    record = new_resource(client); request = grant(record)
    if mode == "wrong_owner": identity = actor("SV024")
    elif mode == "stale": request["resource"]["expected_version"] += 1
    elif mode == "unsupported": request.update(purpose="notifications", capability="notify_resource")
    else: request["state"] = "active"
    with pytest.raises((CertificateError, ValueError)): service.prepare(identity, request)
    assert counts(state) == [0,0,0]


def test_proposal_and_evidence_are_atomic_and_resource_version_is_rechecked(runtime):
    app, client, business, state = runtime; identity = actor(); record = new_resource(client)
    service = app.state.assistant_proposals; value = proposal(app, identity, record); before = tables(business)
    prepared = service.prepare(identity, value, 0)
    receipt = service.confirm(identity, prepared, confirmed=True)
    restored = create_unified_demo_app(business, state_database=state).state.assistant_proposals
    saved = restored.read(identity, value["client_id"])
    assert saved.payload["proposal"]["target"]["expected_version"] == record["version"]
    assert saved.payload["evidence"]["resource"]["version"] == record["version"]
    assert restored.confirm(identity, prepared, confirmed=True).receipt_id == receipt.receipt_id
    assert counts(state) == [1,1,1] and tables(business) == before
    with pytest.raises(CertificateError): restored.read(actor("SV024"), value["client_id"])
    # Legitimate fixture business update, preserving its history and receipts.
    preview = app.state.service_requests.preview(identity, record["id"], record["version"])
    assert preview
    with pytest.raises(CertificateError): restored.read(identity, value["client_id"])
    assert counts(state) == [1,1,1]


@pytest.mark.parametrize("mismatch", ["source", "dates", "workflow", "audience"])
def test_proposal_cannot_invent_source_dates_or_bind_other_workflow(runtime, mismatch):
    app, client, _, state = runtime; identity = actor(); value = proposal(app, identity, new_resource(client))
    if mismatch == "source": value["workflow_binding"]["source"]["sha256"] = "0"*64
    elif mismatch == "dates": value["workflow_binding"]["effective_from"] = "2026-10-01T00:00:00+00:00"
    elif mismatch == "workflow": value["workflow_binding"]["version"] = "invented-version"
    else: value["audience"] = "staff_internal"
    with pytest.raises((ValueError,CertificateError)): app.state.assistant_proposals.prepare(identity, value, 0)
    assert counts(state) == [0,0,0]


@pytest.mark.parametrize("service_name", ["assistant_settings", "assistant_grant_requests", "assistant_proposals"])
@pytest.mark.parametrize("table", ["unified_state_revision", "unified_state_receipt"])
def test_atomic_commit_failure_returns_no_success_or_partial_state(runtime, service_name, table):
    app, client, _, state = runtime; identity = actor(); service = getattr(app.state, service_name)
    if service_name == "assistant_settings": prepared = service.prepare(identity, {"locale":"en"}, 0, generate_uuid7())
    elif service_name == "assistant_grant_requests": prepared = service.prepare(identity, grant(new_resource(client)))
    else: prepared = service.prepare(identity, proposal(app, identity, new_resource(client)), 0)
    with sqlite3.connect(state) as connection:
        connection.execute("CREATE TRIGGER fixture_abort BEFORE INSERT ON " + table + " BEGIN SELECT RAISE(ABORT,'fixture failure'); END")
    with pytest.raises(StorageUnavailable): service.confirm(identity, prepared, confirmed=True)
    assert counts(state) == [0,0,0]


def test_existing_store_unknown_schema_is_rejected_on_every_open_without_repair(tmp_path):
    path = tmp_path / "future.sqlite3"
    # Construct the unknown schema before the repository ever owns this file.
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE unified_state_schema(version INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO unified_state_schema VALUES(99)")
    before = path.read_bytes()
    with pytest.raises(StorageCorrupt): SQLiteActorStateStore(path)
    assert path.read_bytes() == before


def test_configured_main_consent_restores_and_fails_without_ephemeral_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("CAMPUS247_IDEMPOTENCY_DB", str(tmp_path / "idempotency.sqlite3"))
    state = tmp_path / "state.sqlite3"; SQLiteActorStateStore(state)
    settings = Settings(_env_file=None,OPENAI_API_KEY=None,GEMINI_API_KEY=None,DEEPSEEK_API_KEY=None,
        CONSENT_STORAGE_MODE="sqlite",CONSENT_SQLITE_PATH=state)
    def app(): return create_app(runtime_settings=settings,synthetic_tenant_id="huce-local-public", llm_gateway=DeterministicFakeProvider.default())
    identity = actor(); adapter = SyntheticIdentityAdapter(settings.IDENTITY_SECRET_KEY,environment="development",tenant_id="huce-local-public")
    headers = {"Authorization":"Bearer " + adapter.mint_token(identity.subject_id)}
    first = TestClient(app())
    result = first.post("/v1/privacy/consents",headers=headers,json={"purpose":"QUALITY_FEEDBACK","decision":"GRANTED","notice_version":"1.0.0"})
    assert result.status_code == 201
    second = TestClient(app())
    assert second.get("/v1/privacy/consents",headers=headers).json()["items"] == [result.json()]
    first.close();second.close()


def test_candidate_consent_restart_withdrawal_owner_scope_and_revoked_session(runtime):
    app, client, business, state = runtime; headers = login(client)
    notice = client.get("/v1/privacy/notice").json(); version = notice["version"]
    first = client.post("/v1/privacy/consents",headers=headers,json={"purpose":"QUALITY_FEEDBACK", "decision":"GRANTED", "notice_version":version})
    assert first.status_code == 201
    restarted = create_unified_demo_app(business,state_database=state,consent_mode="sqlite")
    with TestClient(restarted) as second:
        assert second.get("/v1/privacy/consents",headers=headers).json()["items"] == [first.json()]
        assert second.get("/v1/privacy/consents",headers=login(second,"SV024")).json()["items"] == []
        withdrawal = second.post("/v1/privacy/consents",headers=headers,json={"purpose":"QUALITY_FEEDBACK", "decision":"WITHDRAWN", "notice_version":version})
        assert withdrawal.status_code == 201 and not restarted.state.consent_service.has_active_consent(actor().subject_id,"QUALITY_FEEDBACK")
        assert len(second.get("/v1/privacy/consents",headers=headers).json()["items"]) == 2
        assert second.post("/v1/auth/logout",headers=headers).status_code == 200
        assert second.get("/v1/privacy/consents",headers=headers).status_code == 401
    with TestClient(create_unified_demo_app(business,state_database=state,consent_mode="sqlite")) as third:
        assert third.get("/v1/privacy/consents",headers=headers).status_code == 401
    assert counts(state) == [1,2,2]


def test_candidate_missing_database_fails_503_and_injected_authority_is_rejected(runtime,tmp_path):
    app, client, _, _ = runtime; headers = login(client); version = client.get("/v1/privacy/notice").json()["version"]
    invalid = client.post("/v1/privacy/consents",headers=headers,json={"purpose":"QUALITY_FEEDBACK", "decision":"GRANTED", "notice_version":version, "owner":actor().subject_id})
    assert invalid.status_code == 422
    missing = tmp_path / "missing.sqlite3"; app.state.actor_state_store.path = missing
    for method in ("GET","POST"):
        response = client.request(method,"/v1/privacy/consents",headers=headers,
            json={"purpose":"QUALITY_FEEDBACK", "decision":"GRANTED", "notice_version":version} if method == "POST" else None)
        assert response.status_code == 503 and "items" not in response.json() and "id" not in response.json()
    assert not missing.exists()


def test_invalid_or_incomplete_composition_is_rejected_before_use(tmp_path):
    with pytest.raises(ValueError): create_unified_demo_app(tmp_path / "business.sqlite3",consent_mode="sqlite")
    settings = Settings(_env_file=None,CONSENT_STORAGE_MODE="sqlite")
    with pytest.raises(ValueError): create_app(runtime_settings=settings,synthetic_tenant_id="huce-local-public",llm_gateway=DeterministicFakeProvider.default())
    assert not (tmp_path / "business.sqlite3").exists()


def test_settings_confirmation_expiry_cannot_write(runtime):
    app, _, _, state = runtime; service = app.state.assistant_settings; identity = actor()
    prepared = service.prepare(identity, {"locale":"en"}, 0, generate_uuid7())
    old = datetime.now(timezone.utc)-timedelta(hours=1)
    preview = replace(prepared.preview, created_at=old-timedelta(minutes=1),expires_at=old)
    expired = ConfirmedPreview(preview,service.tokens.mint_token(preview))
    with pytest.raises(CertificateError): service.confirm(identity,expired,confirmed=True)
    assert counts(state) == [0,0,0]


def test_resource_changes_between_grant_prepare_and_confirm_and_revoke_after_access_loss(runtime):
    app, client, _, state = runtime; identity = actor(); record = new_resource(client)
    service = app.state.assistant_grant_requests; request = grant(record)
    prepared = service.prepare(identity,request)
    receipt = service.confirm(identity,prepared,confirmed=True)
    pending = service.prepare(identity,grant(record))
    app.state.service_requests.preview(identity,record["id"],record["version"])
    with pytest.raises(CertificateError): service.confirm(identity,pending,confirmed=True)
    with pytest.raises(CertificateError): service.read(identity,request["client_id"])
    revoke = service.prepare_revoke(identity,request["client_id"],1,generate_uuid7())
    service.confirm(identity,revoke,confirmed=True)
    assert counts(state) == [1,2,2] and receipt.state == "committed"


def test_proposal_source_change_between_prepare_and_commit_returns_no_receipt(runtime):
    from tests.api.test_service_stage6 import candidate, kp, kc
    app, client, _, state = runtime; identity = actor(); record = new_resource(client)
    service = app.state.assistant_proposals; value = proposal(app,identity,record)
    prepared = service.prepare(identity,value,0)
    editor,reviewer = login(client,"KA001"),login(client,"KA002")
    _,version = candidate(client,editor,reviewer)
    assert kc(client,reviewer,version,kp(client,reviewer,version)).status_code == 200
    with pytest.raises(CertificateError): service.confirm(identity,prepared,confirmed=True)
    assert counts(state) == [0,0,0]


@pytest.mark.parametrize("operation", ["get", "history", "commit"])
def test_missing_initial_commit_receipt_blocks_read_and_further_mutation(tmp_path,operation):
    from campus247.application.assistance.state_storage import StateScope
    identity = actor();scope = StateScope("huce-local-public",identity.subject_id)
    valid = tmp_path / "valid.sqlite3"; source = SQLiteActorStateStore(valid)
    source.commit(scope,"preferences","account",0,{"locale":"en"},generate_uuid7())
    broken = tmp_path / "initially-incomplete.sqlite3"; store = SQLiteActorStateStore(broken)
    # Populate an initially incomplete fixture; never erase a committed receipt.
    rows = tables(valid)
    with sqlite3.connect(broken) as connection:
        for table in ("unified_actor_state","unified_state_revision"):
            for row in rows[table]:
                connection.execute("INSERT INTO " + table + " VALUES(" + ",".join("?" for _ in row) + ")",row)
    before = tables(broken)
    with pytest.raises(StorageCorrupt):
        if operation == "get": store.get(scope,"preferences","account")
        elif operation == "history": store.history(scope,"preferences","account")
        else: store.commit(scope,"preferences","account",1,{"locale":"vi"},generate_uuid7())
    assert tables(broken) == before


def test_configured_consent_missing_file_is_not_silently_initialized(tmp_path):
    path = tmp_path / "missing.sqlite3"
    settings = Settings(_env_file=None,CONSENT_STORAGE_MODE="sqlite",CONSENT_SQLITE_PATH=path)
    with pytest.raises(StorageUnavailable):
        create_app(runtime_settings=settings,synthetic_tenant_id="huce-local-public",llm_gateway=DeterministicFakeProvider.default())
    assert not path.exists()


def test_unknown_schema_checked_by_existing_repository_without_mutation(tmp_path):
    from campus247.application.assistance.state_storage import StateScope
    store = SQLiteActorStateStore(tmp_path / "valid.sqlite3")
    unknown = tmp_path / "unknown.sqlite3"
    with sqlite3.connect(unknown) as connection:
        connection.execute("CREATE TABLE unified_state_schema(version INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO unified_state_schema VALUES(99)")
    store.path = unknown;scope = StateScope("huce-local-public",actor().subject_id);before = unknown.read_bytes()
    with pytest.raises(StorageCorrupt):store.get(scope,"preferences","account")
    with pytest.raises(StorageCorrupt):store.commit(scope,"preferences","account",0,{"locale":"en"},generate_uuid7())
    assert unknown.read_bytes() == before


def test_proposal_before_value_must_be_observed_and_snapshot_cannot_overwrite_another(runtime):
    app, client, _, state = runtime; identity = actor(); value = proposal(app,identity,new_resource(client))
    value["changes"][0]["before"] = "invented previous reason"
    with pytest.raises(CertificateError):app.state.assistant_proposals.prepare(identity,value,0)
    with pytest.raises(ValueError):app.state.assistant_proposals.prepare(identity,value,1)
    assert counts(state) == [0,0,0]
