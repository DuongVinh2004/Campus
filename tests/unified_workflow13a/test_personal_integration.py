"""Actual A composition with B repositories, APIs, context and bounded worker."""
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from campus247.bootstrap.unified_demo import create_unified_demo_app
from campus247.infrastructure.repositories.sqlite_assistant_memory import SQLiteAssistantMemory
from campus247.infrastructure.repositories.sqlite_assistant_tracking import SQLiteAssistantTracking
from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
from campus247.domain.shared.values import generate_uuid7
from tests.api.test_service_stage6 import sent, login, act, read
from tests.integration.test_unified_actor_features import consent
from tests.unified_workflow13a.test_case_continuity import request_supplement
from tests.integration.test_unified_staff12 import target
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services/worker/src"))
from campus247_worker.assistant_tracking.worker import AssistantTrackingWorker

@pytest.fixture
def personal(tmp_path):
    memory = SQLiteAssistantMemory(tmp_path / "personal-memory.sqlite3", initialize=True)
    tracking = SQLiteAssistantTracking(tmp_path / "personal-tracking.sqlite3", initialize=True)
    app = create_unified_demo_app(tmp_path / "business.sqlite3", state_database=tmp_path / "state.sqlite3", consent_mode="sqlite",
        personal_memory_store=memory, personal_tracking_store=tracking)
    with TestClient(app) as client:
        student, record, _ = sent(client)
        adapter = SyntheticIdentityAdapter("campus247-demo-secret-key-huce", environment="development", tenant_id="huce-local-public")
        actor = adapter.resolve_token(student["Authorization"].split(" ")[1])
        yield app, client, actor, student, record, tracking

def confirmed(client, headers, prefix, change):
    p = client.post(prefix + "/preview", headers=headers, json=change)
    assert p.status_code == 200, p.text
    r = client.post(prefix + "/confirm", headers=headers, json={"normalized_payload": p.json()["normalized_payload"], "confirmation_token": p.json()["confirmation_token"], "confirmed": True})
    assert r.status_code == 200, r.text
    return r.json()

def grant(client, headers, record):
    p = client.post("/v1/assistant/grants:preview", headers=headers, json={"client_id": generate_uuid7(), "resource": target(record),
        "capability": "read_source", "lifetime": "session", "lifetime_seconds": 600})
    assert p.status_code == 200, p.text
    r = client.post("/v1/assistant/grants:confirm", headers=headers, json={"normalized_payload": p.json()["normalized_payload"], "confirmation_token": p.json()["confirmation_token"], "confirmed": True})
    assert r.status_code == 200, r.text
    return r.json()["receipt"]

def test_actual_memory_api_and_fresh_scoped_resource_context_suppression(personal):
    app, client, actor, headers, record, _ = personal
    consent(app, actor)
    prefix = "/v1/assistant/memory"
    confirmed(client, headers, prefix, {"operation": "control", "enabled": True, "expected_version": 0, "client_id": generate_uuid7()})
    saved = confirmed(client, headers, prefix, {"operation": "save", "expected_version": 0, "client_id": generate_uuid7(),
        "value": {"kind": "preference", "topic": "Cách trình bày", "text": "Tôi muốn từng bước ngắn gọn", "valid_until": (datetime.now(timezone.utc)+timedelta(days=10)).isoformat()}})
    permission = grant(client, headers, record)
    body = {"resource": target(record), "grant_id": permission["key"], "operation_id": generate_uuid7(), "memory_terms": ["ngắn gọn"]}
    response = client.post("/v1/assistant/context:compose", headers=headers, json=body)
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["content"]["personal_memory"]["items"][0]["text"] == "Tôi muốn từng bước ngắn gọn"
    assert value["content"]["personal_memory"]["action_authority"] == "none"
    key = saved["receipt"]["key"] if "receipt" in saved else saved["key"]
    confirmed(client, headers, prefix, {"operation": "forget", "key": key, "expected_version": 1, "client_id": generate_uuid7()})
    stale = client.post("/v1/assistant/context:revalidate", headers=headers, json={"request": body, "expected_sha256": value["manifest"]["sha256"]})
    assert stale.status_code == 409, stale.text
    assert client.post("/v1/assistant/context:compose", headers=headers, json={**body, "operation_id": generate_uuid7()}).json()["content"]["personal_memory"]["items"] == []
    caps = client.get("/v1/assistant/personal-capabilities", headers=headers).json()
    assert caps["memory_management"] and caps["memory_context"] and caps["tracking"]

def test_actual_outbox_worker_inbox_open_and_session_revoke(personal):
    app, client, actor, student, record, tracking = personal
    permission = grant(client, student, record)
    confirmed(client, student, "/v1/assistant/tracking", {"operation": "subscribe", "client_id": generate_uuid7(),
        "subscription_id": generate_uuid7(), "expected_version": 0, "spec": {"resource": target(record), "trigger": "supplement",
            "expires_at": (datetime.now(timezone.utc)+timedelta(seconds=300)).isoformat(), "permission_id": permission["key"], "permission_version": permission["version"],
            "quiet_start_hour": 0, "quiet_end_hour": 0}})
    staff = login(client, "OF002")
    claimed = act(client, staff, record, "claim"); assert claimed.status_code == 200
    record = claimed.json()["document_request"]
    request_supplement(client, staff, record)
    worker = AssistantTrackingWorker(app.state.assistant_tracking)
    first = worker.tick()
    assert first["delivered"] == 1, first
    assert worker.tick()["delivered"] == 0
    inbox = client.get("/v1/assistant/tracking/notifications", headers=student)
    assert inbox.status_code == 200, inbox.text
    value = inbox.json()
    assert len(value["items"]) == 1 and "PRIVATE SENTINEL" not in str(value)
    with tracking.transaction() as connection:
        event_id = connection.execute("SELECT event_id FROM tracking_inbox").fetchone()[0]
    opened = client.post("/v1/assistant/cases/notification:open", headers=student, json={"event_id": event_id})
    assert opened.status_code == 200, opened.text
    assert opened.json()["open_path"] == "/services?request=" + record["id"]
    other = login(client, "SV024")
    assert client.post("/v1/assistant/cases/notification:open", headers=other, json={"event_id": event_id}).status_code == 404
    app.state.service_requests.repository.revoke(app.state.current_session_service.hash_token(student["Authorization"].split(" ")[1]))
    with pytest.raises(Exception):
        app.state.assistant_recipient_registry.resolve(actor.tenant_id, actor.subject_id, actor.session_id)
    assert client.get("/v1/assistant/tracking/notifications", headers=student).status_code == 401

def test_private_preparation_never_creates_tracking_event(personal):
    app, client, _, student, record, _ = personal
    from tests.api.test_service_stage6 import draft, preview
    initial = app.state.assistant_tracking_source.read_batch(limit=20)
    created = draft(client, student)
    preview(client, student, created)
    assert app.state.assistant_tracking_source.read_batch(limit=20) == initial

def test_source_permission_drift_blocks_notification_even_with_bound_workflow(personal):
    app, client, actor, student, record, tracking = personal
    permission = grant(client, student, record)
    confirmed(client, student, "/v1/assistant/tracking", {"operation": "subscribe", "client_id": generate_uuid7(),
        "subscription_id": generate_uuid7(), "expected_version": 0, "spec": {"resource": target(record), "trigger": "supplement",
            "expires_at": (datetime.now(timezone.utc)+timedelta(seconds=300)).isoformat(), "permission_id": permission["key"], "permission_version": permission["version"],
            "quiet_start_hour": 0, "quiet_end_hour": 0}})
    staff = login(client, "OF002"); claimed = act(client, staff, record, "claim").json()["document_request"]
    request_supplement(client, staff, claimed)
    original = app.state.assistance_context.resolve
    def changed(actor, request):
        observation = original(actor, request)
        return observation.model_copy(update={"evidence": [observation.evidence[0].model_copy(update={"sha256": "0"*64})]})
    app.state.assistance_context.resolve = changed
    result = AssistantTrackingWorker(app.state.assistant_tracking).tick()
    assert result["delivered"] == 0 and result["suppressed"] >= 1
    assert client.get("/v1/assistant/tracking/notifications", headers=student).json()["items"] == []

def test_no_implicit_personal_store_or_legacy_mode(tmp_path):
    app = create_unified_demo_app(tmp_path / "business.sqlite3", state_database=tmp_path / "state.sqlite3")
    with TestClient(app) as client:
        headers = login(client)
        caps = client.get("/v1/assistant/personal-capabilities", headers=headers).json()
        assert not caps["memory_management"] and not caps["tracking"] and not caps["memory_context"]
        assert client.get("/v1/assistant/memory", headers=headers).status_code == 503
        assert client.get("/v1/assistant/tracking/notifications", headers=headers).status_code == 503
