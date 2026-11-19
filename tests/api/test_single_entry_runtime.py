"""Real local composition, authentication and SSE; no model/provider calls."""
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import campus_backend


def test_unified_entry_preserves_auth_history_and_closed_model_admission(tmp_path, monkeypatch):
    monkeypatch.setattr(campus_backend, "STATE", tmp_path / "runtime")
    app = campus_backend.create_runtime_app(model_mode="guarded")
    with TestClient(app) as client:
        assert client.get("/health/entry").json()["generation"] == "not_enabled"
        assert client.get("/v1/assistant/consumer-capabilities").status_code == 401
        accounts = client.get("/v1/auth/demo-accounts").json()["items"]
        account = next(row["account"] for row in accounts if row["role"] == "STUDENT")
        login = client.post("/v1/auth/demo-login", json={"account": account})
        assert login.status_code == 200
        assert "httponly" in login.headers["set-cookie"].lower()
        caps = client.get("/v1/assistant/consumer-capabilities")
        assert caps.status_code == 200
        assert caps.json()["coordination"]["read"] is True
        paths = app.openapi()["paths"]
        assert "/v1/conversations/{conversation_id}/agent-runs/{run_id}" in paths
        assert "/v1/conversations/{conversation_id}/messages/{message_id}/citations/{citation_id}/source" in paths
        created = client.post("/v1/conversations", json={})
        assert created.status_code == 201
        conversation = created.json()["id"]
        path = f"/v1/conversations/{conversation}"
        assert client.get(path + "/messages").status_code == 200
        response = client.post(path + "/messages:stream", json={"content": "Điều kiện học bổng?"})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "event: message.completed" in response.text
        assert "MODEL_BUDGET_EXHAUSTED" not in response.text
        history = client.get(path + "/messages")
        assert history.status_code == 200
        assert len(history.json()["items"]) >= 2
    # Reopening uses the same owned stores; no historical tenant reassignment.
    reopened = campus_backend.create_runtime_app(model_mode="guarded")
    assert reopened.state.native_chat_local is True
    assert (campus_backend.STATE / "history.sqlite3").is_file()
    assert (campus_backend.STATE / "conversations.sqlite3").is_file()
