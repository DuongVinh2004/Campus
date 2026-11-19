"""Administrators read the operations status; nobody else does, and /metrics never leaves the machine."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from campus247.domain.shared.values import generate_uuid7
from campus247.observability.ops_metrics import OpsMetrics, write_snapshot
from campus247.observability.ops_status import OpsConfig, ProbeCache
from campus247.ports.identity import IdentityContext, IdentityRole
from campus247.presentation.admin_ops import create_admin_ops_router, render_prometheus
from campus247.presentation.identity import IdentityMiddleware


class Adapter:
    def __init__(self):
        self.contexts = {}

    def resolve_token(self, token):
        if token in self.contexts:
            return self.contexts[token]
        raise ValueError("bad token")

    def add(self, token, role):
        now = datetime.now(UTC)
        student = role == IdentityRole.STUDENT
        self.contexts[token] = IdentityContext(
            subject_id=generate_uuid7(), external_subject="sub", issuer="test", roles=(role,), display_name="Test",
            auth_time=now, expires_at=now + timedelta(hours=1), student_code="SV123456" if student else None,
            tenant_id="t", session_id=generate_uuid7())


def model_transport():
    def handler(request):
        if request.url.port in (18081, 18082):
            return httpx.Response(200, json={})
        return httpx.Response(404)
    return httpx.MockTransport(handler)


@pytest.fixture
def env(tmp_path):
    metrics = OpsMetrics()
    for _ in range(4):
        metrics.record_turn(outcome="ok", first_token_s=0.8, total_s=3.0)
    metrics.record_rate_limited("chat")
    metrics.set_gauges(in_flight=2, waiting=0, limit=16)
    write_snapshot(tmp_path / "m", metrics.snapshot({"retrievals": 25, "failed": 0, "timeouts": 0, "vector_ms_max": 300}))
    config = OpsConfig(metrics_dir=tmp_path / "m", data_dir=tmp_path,
                       model_urls={"embedding": "http://127.0.0.1:18081/info", "reranker": "http://127.0.0.1:18082/info"})
    adapter = Adapter()
    for token, role in (("admin", IdentityRole.SYSTEM_ADMIN), ("kadmin", IdentityRole.KNOWLEDGE_ADMIN),
                        ("student", IdentityRole.STUDENT), ("officer", IdentityRole.SUPPORT_OFFICER)):
        adapter.add(token, role)
    app = FastAPI()
    app.add_middleware(IdentityMiddleware, adapter=adapter)
    app.include_router(create_admin_ops_router(config, client=httpx.AsyncClient(transport=model_transport()), cache=ProbeCache()))
    with TestClient(app, client=("127.0.0.1", 50000)) as client:  # the test client's own default peer is "testclient"
        yield client


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("token", ["admin", "kadmin"])
def test_administrators_read_the_status(env, token):
    reply = env.get("/v1/admin/operations/status", headers=bearer(token))
    assert reply.status_code == 200 and reply.headers["cache-control"] == "no-store"
    body = reply.json()
    assert body["turns"]["last_5m"]["turns"] == 4 and body["load"]["limit"] == 16 and body["models"]["embedding"] == "up"


@pytest.mark.parametrize("token", ["student", "officer"])
def test_other_roles_are_refused(env, token):
    reply = env.get("/v1/admin/operations/status", headers=bearer(token))
    assert reply.status_code == 403 and "turns" not in reply.text


def test_anonymous_requests_are_refused(env):
    assert env.get("/v1/admin/operations/status").status_code == 401


def test_status_never_contains_user_text_or_identifiers(env):
    text = json.dumps(env.get("/v1/admin/operations/status", headers=bearer("admin")).json())
    assert all(word not in text for word in ("subject", "conversation", "SV123456", "content"))


def test_metrics_answers_a_local_scraper_in_text_format(env):
    reply = env.get("/metrics")
    assert reply.status_code == 200 and reply.headers["content-type"].startswith("text/plain")
    lines = reply.text.splitlines()
    assert "campus247_turns_5m 4" in lines and "campus247_in_flight_limit 16" in lines
    assert 'campus247_model_up{model="embedding"} 1' in lines and 'campus247_rate_limited_5m{group="chat"} 1' in lines
    assert not any(line.startswith("campus247_gateway") for line in lines)  # no gateway configured: nothing is made up


@pytest.mark.parametrize("header", ["X-Forwarded-For", "Forwarded", "X-Real-IP", "X-Forwarded-Proto"])
def test_metrics_refuses_requests_that_came_through_a_proxy(env, header):
    assert env.get("/metrics", headers={header: "203.0.113.9"}).status_code == 403


def test_metrics_refuses_a_non_loopback_peer(env):
    with TestClient(env.app, client=("203.0.113.9", 5000)) as remote:
        assert remote.get("/metrics").status_code == 403


def test_prometheus_text_leaves_out_missing_values():
    status = {"workers_reporting": 0, "turns": {"last_5m": {"turns": 0, "errors": {}, "abstained": 0, "admission_rejected": 0,
              "p95_s_le": None, "loop_blocked": 0, "rate_limited": {}}, "last_60m": {"turns": 0}},
              "load": {"in_flight": 0, "waiting": 0, "limit": 0}, "retrieval": {"failed_rate": 0.0},
              "storage": {"data_free_pct": None}, "models": {}, "gateway": {"reachable": None}}
    text = render_prometheus(status)
    assert "p95" not in text and "data_free" not in text and "gateway" not in text
    assert text.endswith("\n") and "campus247_turns_5m 0" in text
