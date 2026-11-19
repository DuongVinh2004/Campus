"""Optional durable consent service wiring on fresh SQLite only."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import sqlite3

from fastapi.testclient import TestClient
import pytest

from campus247.application.privacy.consent import PrivacyConsentService, PrivacyNoticeConfig, ServiceUnavailableError
from campus247.bootstrap.app import create_app
from campus247.bootstrap.settings import Settings
from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
from campus247.infrastructure.llm.fake import DeterministicFakeProvider
from campus247.infrastructure.repositories.sqlite_actor_state import SQLiteActorStateStore
from campus247.infrastructure.repositories.sqlite_consents import SQLiteConsentRepository
from campus247.ports.identity import AccountState

TENANT="huce-local-public"
OWNER="4b419a1b-6d41-7dfb-8943-2edd9f071385"
OTHER="97c5ab40-6399-7ad3-9838-eab50f267b2d"


def notice():
    return PrivacyNoticeConfig("fixture-notice","fixture-v1",datetime.now(timezone.utc),"ACTIVE",{},[],[],[])


def actor(owner=OWNER):
    adapter=SyntheticIdentityAdapter("fixture-identity",environment="development",tenant_id=TENANT)
    return adapter.resolve_token(adapter.mint_token(owner))


def make(path):
    repository=SQLiteConsentRepository(SQLiteActorStateStore(path),tenant=TENANT)
    return PrivacyConsentService(active_notice=notice(),repository=repository),repository


def test_durable_grant_withdrawal_retains_history_through_restart_and_owner_tenant_scope(tmp_path):
    path=tmp_path / "state.sqlite3";service,repository=make(path)
    grant=service.record_consent(actor(),"OPTIONAL_PERSONALIZATION","GRANTED","fixture-v1")
    assert service.has_active_consent(OWNER,"OPTIONAL_PERSONALIZATION")
    withdrawal=service.record_consent(actor(),"OPTIONAL_PERSONALIZATION","WITHDRAWN","fixture-v1")
    restarted,_=make(path)
    assert restarted.list_user_consents(OWNER)==[grant,withdrawal]
    assert not restarted.has_active_consent(OWNER,"OPTIONAL_PERSONALIZATION")
    assert restarted.list_user_consents(OTHER)==[] and not restarted.has_active_consent(OTHER,"OPTIONAL_PERSONALIZATION")
    other_tenant=PrivacyConsentService(active_notice=notice(),repository=SQLiteConsentRepository(repository.store,tenant="other-tenant"))
    assert other_tenant.list_user_consents(OWNER)==[]
    with pytest.raises(ValueError,match="server-bound"):
        other_tenant.record_consent(actor(),"OPTIONAL_PERSONALIZATION","GRANTED","fixture-v1")


def test_expired_inactive_or_wrong_tenant_identity_cannot_write_consent(tmp_path):
    service,repository=make(tmp_path / "state.sqlite3")
    identity=actor()
    for invalid in [replace(identity,auth_time=datetime.now(timezone.utc)-timedelta(hours=2),expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)),
            replace(identity,tenant_id="other-tenant"),replace(identity,session_id=""),replace(identity,is_synthetic=False),
            replace(identity,account_state=AccountState.SUSPENDED)]:
        with pytest.raises(ValueError):service.record_consent(invalid,"QUALITY_FEEDBACK","GRANTED","fixture-v1")
    assert service.list_user_consents(OWNER)==[]


def test_concurrent_distinct_consent_declarations_are_atomic_and_ordered(tmp_path):
    path=tmp_path / "state.sqlite3";make(path)
    def record(decision):
        service,_=make(path)
        return service.record_consent(actor(),"QUALITY_FEEDBACK",decision,"fixture-v1")
    with ThreadPoolExecutor(max_workers=2) as pool:records=list(pool.map(record,["GRANTED","WITHDRAWN"]))
    service,_=make(path);stored=service.list_user_consents(OWNER)
    assert {r.id for r in stored}=={r.id for r in records} and len(stored)==2
    assert service.has_active_consent(OWNER,"QUALITY_FEEDBACK")== (stored[-1].decision=="GRANTED")


def test_consent_receipt_failure_rolls_back_decision_and_history(tmp_path):
    path=tmp_path / "state.sqlite3";service,_=make(path)
    granted=service.record_consent(actor(),"QUALITY_FEEDBACK","GRANTED","fixture-v1")
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TRIGGER fixture_fail BEFORE INSERT ON unified_state_receipt BEGIN SELECT RAISE(ABORT,'fixture failure'); END")
    with pytest.raises(ServiceUnavailableError):service.record_consent(actor(),"QUALITY_FEEDBACK","WITHDRAWN","fixture-v1")
    assert service.has_active_consent(OWNER,"QUALITY_FEEDBACK") and service.list_user_consents(OWNER)==[granted]


def test_main_factory_http_consent_restore_and_dependency_503(tmp_path,monkeypatch):
    monkeypatch.setenv("CAMPUS247_IDEMPOTENCY_DB",str(tmp_path / "idempotency.sqlite3"))
    path=tmp_path / "state.sqlite3";_,repository=make(path)
    settings=Settings(_env_file=None,ENVIRONMENT="development",DEMO_MODE=True,OPENAI_API_KEY=None,GEMINI_API_KEY=None,DEEPSEEK_API_KEY=None)
    adapter=SyntheticIdentityAdapter(settings.IDENTITY_SECRET_KEY,environment="development",tenant_id=TENANT)
    headers={"Authorization":"Bearer "+adapter.mint_token(OWNER)}
    def app(repo):return create_app(runtime_settings=settings,synthetic_tenant_id=TENANT,consent_repository=repo,llm_gateway=DeterministicFakeProvider.default())
    first=TestClient(app(repository))
    assert first.app.state.consent_storage=={"mode":"sqlite","fallback":False,"grants_authority":False}
    first_record=first.post("/v1/privacy/consents",headers=headers,json={"purpose":"QUALITY_FEEDBACK","decision":"GRANTED","notice_version":"1.0.0"})
    assert first_record.status_code==201,first_record.text
    _,restarted_repository=make(path);second=TestClient(app(restarted_repository))
    items=second.get("/v1/privacy/consents",headers=headers).json()["items"]
    assert items==[first_record.json()]
    withdrawn=second.post("/v1/privacy/consents",headers=headers,json={"purpose":"QUALITY_FEEDBACK","decision":"WITHDRAWN","notice_version":"1.0.0"})
    assert withdrawn.status_code==201 and not restarted_repository.has_active_consent(OWNER,"QUALITY_FEEDBACK")
    other_headers={"Authorization":"Bearer "+adapter.mint_token(OTHER)}
    assert second.get("/v1/privacy/consents",headers=other_headers).json()["items"]==[]
    assert second.get("/v1/privacy/consents").status_code==401
    missing=tmp_path / "missing.sqlite3";restarted_repository.store.path=missing
    failed=second.get("/v1/privacy/consents",headers=headers)
    assert failed.status_code==503 and failed.json()["code"]=="DEPENDENCY_UNAVAILABLE" and "items" not in failed.json()
    assert not missing.exists()
    first.close();second.close()


def test_factory_requires_correct_typed_tenant_binding_before_use(tmp_path):
    _,repository=make(tmp_path / "state.sqlite3")
    settings=Settings(_env_file=None,ENVIRONMENT="development",DEMO_MODE=True,OPENAI_API_KEY=None,GEMINI_API_KEY=None,DEEPSEEK_API_KEY=None)
    with pytest.raises(ValueError,match="tenant must match"):
        create_app(runtime_settings=settings,synthetic_tenant_id="other-tenant",consent_repository=repository,llm_gateway=DeterministicFakeProvider.default())
    with pytest.raises(ValueError,match="typed durable"):
        create_app(runtime_settings=settings,synthetic_tenant_id=TENANT,consent_repository=object(),llm_gateway=DeterministicFakeProvider.default())
