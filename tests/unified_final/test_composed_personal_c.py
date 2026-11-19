"""Actual A/B composition on explicit new C stores, never registrar-only success."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from scripts.unified_completion_scope import completion_fixture

import pytest
from fastapi.testclient import TestClient

from campus247.bootstrap.unified_demo import create_unified_demo_app
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
from campus247.infrastructure.repositories.sqlite_assistant_memory import SQLiteAssistantMemory
from campus247.infrastructure.repositories.sqlite_assistant_tracking import SQLiteAssistantTracking
from tests.api.test_service_stage6 import draft, login, act, read
from tests.integration.test_unified_actor_features import consent, grant
from tests.integration.test_unified_staff12 import target

STATE = Path(__file__).resolve().parents[2] / "infra/local/unified-ai-parallel-20261015-01/stream-c"


@pytest.fixture
def composed(tmp_path):
    assert tmp_path.resolve().is_relative_to(STATE.resolve()) or completion_fixture(tmp_path)
    memory = SQLiteAssistantMemory(tmp_path / "personal-memory.sqlite3", initialize=True)
    tracking = SQLiteAssistantTracking(tmp_path / "personal-tracking.sqlite3", initialize=True)
    app = create_unified_demo_app(tmp_path / "business.sqlite3", state_database=tmp_path / "actor.sqlite3", consent_mode="sqlite",
        personal_memory_store=memory, personal_tracking_store=tracking)
    with TestClient(app) as client:
        headers = login(client)
        adapter = SyntheticIdentityAdapter("campus247-demo-secret-key-huce", environment="development", tenant_id="huce-local-public")
        actor = adapter.resolve_token(headers["Authorization"][7:])
        yield app, client, headers, actor, tmp_path


def memory_change(client, headers, body):
    response = client.post("/v1/assistant/memory/preview", headers=headers, json=body)
    assert response.status_code == 200, response.text
    value = response.json()
    confirmed = client.post("/v1/assistant/memory/confirm", headers=headers,
        json={**{key: value[key] for key in ["normalized_payload", "confirmation_token"]}, "confirmed": True})
    assert confirmed.status_code == 200, confirmed.text
    return confirmed.json()


def test_real_scoped_context_uses_actor_memory_and_forget_removes_derived_text(composed):
    app, client, headers, actor, _ = composed
    consent(app, actor)
    memory_change(client, headers, {"operation": "control", "enabled": True, "expected_version": 0, "client_id": generate_uuid7()})
    memory_change(client, headers, {"operation": "save", "expected_version": 0, "client_id": generate_uuid7(), "value": {
        "kind": "preference", "topic": "C-tone", "text": "C-personal-answer-pref", "valid_until": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}})
    record = draft(client, headers)
    grant_id, resource = grant(app, client, actor, lifetime="timed", record=record)
    request = {"resource": resource, "grant_id": grant_id, "operation_id": generate_uuid7(), "memory_terms": ["C-tone"]}
    response = client.post("/v1/assistant/context:compose", headers=headers, json=request)
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["content"]["personal_memory"]["items"][0]["text"] == "C-personal-answer-pref"
    assert value["content"]["personal_memory"]["action_authority"] == "none"
    management = client.get("/v1/assistant/memory", headers=headers).json()
    item = management["items"][0]
    memory_change(client, headers, {"operation": "forget", "key": item["key"], "expected_version": item["version"], "client_id": generate_uuid7()})
    refreshed = client.post("/v1/assistant/context:compose", headers=headers, json={**request, "operation_id": generate_uuid7()})
    assert refreshed.status_code == 200 and refreshed.json()["content"]["personal_memory"]["items"] == []
    assert "C-personal-answer-pref" not in refreshed.text
    suppressed = client.get("/v1/assistant/memory", headers=headers).json()["items"][0]
    assert suppressed["state"] == "suppressed" and suppressed["version"] == item["version"] + 1
    assert "value" not in suppressed


def test_actual_composition_missing_personal_stores_reports_unavailable(composed):
    _, _, _, _, path = composed
    app = create_unified_demo_app(path / "absent-business.sqlite3", state_database=path / "absent-actor.sqlite3")
    with TestClient(app) as client:
        headers = login(client)
        capabilities = client.get("/v1/assistant/personal-capabilities", headers=headers)
        assert capabilities.status_code == 200
        assert not capabilities.json()["memory_context"] and not capabilities.json()["tracking"]
        assert client.get("/v1/assistant/memory", headers=headers).status_code == 503
        assert client.get("/v1/assistant/tracking/notifications", headers=headers).status_code == 503


def test_actual_business_outbox_delivers_current_recipient_then_revoke_hides_inbox(composed):
    from campus247_worker.assistant_tracking.worker import AssistantTrackingWorker
    app, client, headers, actor, _ = composed
    # Retain this exact login session throughout subscriptions, source and inbox.
    from tests.api.test_service_stage6 import preview, confirm
    record = draft(client, headers)
    receipt = confirm(client, headers, preview(client, headers, record))
    assert receipt.status_code == 201
    record = read(client, headers, record["id"])
    grant_id, resource = grant(app, client, actor, lifetime="timed", record=record)
    now = datetime.now(timezone.utc)
    sid = generate_uuid7()
    subscription = client.post("/v1/assistant/tracking/preview", headers=headers, json={"operation": "subscribe", "client_id": sid,
        "subscription_id": sid, "expected_version": 0, "spec": {"resource": resource, "trigger": "feedback", "channel": "in_app",
        "expires_at": (now + timedelta(seconds=45)).isoformat(), "permission_id": grant_id, "permission_version": 1,
        "quiet_start_hour": 0, "quiet_end_hour": 0}})
    assert subscription.status_code == 200, subscription.text
    p = subscription.json()
    accepted = client.post("/v1/assistant/tracking/confirm", headers=headers,
        json={**{k: p[k] for k in ["normalized_payload", "confirmation_token"]}, "confirmed": True})
    assert accepted.status_code == 200, accepted.text
    staff = login(client, "OF002")
    claimed = act(client, staff, record, "claim")
    assert claimed.status_code == 200
    responded = act(client, staff, claimed.json()["document_request"], "respond", note="C-private-staff-note-never-notification")
    assert responded.status_code == 200
    worker = AssistantTrackingWorker(app.state.assistant_tracking)
    result = worker.tick()
    assert result["delivered"] == 1
    inbox = client.get("/v1/assistant/tracking/notifications", headers=headers)
    assert inbox.status_code == 200 and len(inbox.json()["items"]) == 1, inbox.text
    assert inbox.json()["items"][0]["recipient_id"] == actor.subject_id
    assert inbox.json()["items"][0]["resource"] == target(responded.json()["document_request"])
    assert "C-private-staff-note-never-notification" not in inbox.text
    app.state.service_requests.repository.revoke(app.state.current_session_service.hash_token(headers["Authorization"][7:]))
    denied = client.get("/v1/assistant/tracking/notifications", headers=headers)
    assert denied.status_code == 401
