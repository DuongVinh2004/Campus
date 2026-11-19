"""HTTP authorization, review CAS, publication confirmation and source denial."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from campus247.presentation.policy_graph import create_policy_graph_router
from campus247.ports.identity import IdentityContext, IdentityRole
from campus247.domain.shared.values import generate_uuid7
from tests.unit.policy_graph.test_policy_graph import service, context


def app_client(tmp_path, *, gateway=None, admission=None):
    from datetime import datetime, timedelta, timezone
    s, p = service(tmp_path)
    now = datetime.now(timezone.utc)
    actor_id = generate_uuid7()
    app = FastAPI()
    @app.middleware("http")
    async def identity(request, call_next):
        role = request.headers.get("x-test-role")
        request.state.identity = None if role is None else IdentityContext(actor_id, "synthetic-test",
            "test", (IdentityRole(role),), "Synthetic test", now, now+timedelta(hours=1),
            student_code="SYN001" if role == "STUDENT" else None)
        return await call_next(request)
    def factory(turn, actor, **kwargs):
        return context(actor=actor.subject_id, roles=tuple(r.value for r in actor.roles))
    app.include_router(create_policy_graph_router(s, context_factory=factory, gateway=gateway, admission=admission))
    return TestClient(app), s, p


def test_no_session_and_student_cannot_review_or_see_admin_versions(tmp_path):
    client, s, p = app_client(tmp_path)
    assert client.get("/v1/policy-graph/versions").status_code == 401
    for path in ("/versions", f"/versions/{p.id}"):
        assert client.get("/v1/policy-graph" + path, headers={"x-test-role": "STUDENT"}).status_code == 403
    assert s.reader.calls == []


def test_http_review_preview_confirm_and_no_false_success(tmp_path):
    client, s, p = app_client(tmp_path)
    headers = {"x-test-role": "KNOWLEDGE_ADMIN"}
    base = "/v1/policy-graph/versions/" + p.id
    view = client.get(base, headers=headers)
    assert view.status_code == 200 and view.headers["cache-control"] == "no-store"
    assert view.json()["raw_proposal"] == p.model_dump_json()
    revision = 0
    for record in (*p.nodes, *p.edges):
        body = {"target": record.id, "verdict": "approved", "note": "Synthetic source review", "expected_revision": revision}
        response = client.post(base+"/reviews", headers=headers, json=body)
        assert response.status_code == 200, response.text
        revision = response.json()["revision"]
    preview = client.post(base+":publish-preview", headers=headers, json={"expected_revision": revision}).json()
    bad = {"expected_revision": revision, "confirmation": preview["confirmation"], "confirmed": False}
    assert client.post(base+":publish", headers=headers, json=bad).status_code == 422
    assert s.repository.publication(p.id) is None
    bad["confirmed"] = True
    published = client.post(base+":publish", headers=headers, json=bad)
    assert published.status_code == 200, published.text
    result = client.post("/v1/policy-graph/relations:search", headers={"x-test-role": "STUDENT"}, json={"query": "thử nghiệm"})
    assert result.status_code == 200 and len(result.json()["edges"]) == 3
    assert client.post(base+":publish", headers=headers, json=bad).status_code == 409


def test_denied_original_sources_hide_review_versions_and_diagnostics(tmp_path):
    client, s, p = app_client(tmp_path)
    s.reader.denied = True
    headers = {"x-test-role": "KNOWLEDGE_ADMIN"}
    assert client.get("/v1/policy-graph/versions", headers=headers).json() == {"items": []}
    response = client.get("/v1/policy-graph/versions/"+p.id, headers=headers)
    assert response.status_code == 404 and "source" not in response.text.lower()


def test_extraction_requires_admin_and_shared_admission_before_dispatch(tmp_path):
    class Gateway:
        calls = 0
        async def generate(self, request):
            self.calls += 1
            raise AssertionError("must not dispatch without quota")
    gateway = Gateway()
    client, _, p = app_client(tmp_path, gateway=gateway, admission=lambda _: False)
    path = f"/v1/policy-graph/versions/{p.id}:extract-candidate"
    assert client.post(path, headers={"x-test-role": "STUDENT"}, json={"target_ids": ["procedure"]}).status_code == 403
    response = client.post(path, headers={"x-test-role": "KNOWLEDGE_ADMIN"}, json={"target_ids": ["procedure"]})
    assert response.status_code == 409 and gateway.calls == 0


def test_extraction_http_uses_same_gateway_and_creates_candidate_without_review(tmp_path):
    import json
    from campus247.ports.llm import LlmResponse, LlmResponseStatus, TokenUsage
    class Gateway:
        calls = 0
        async def generate(self, request):
            self.calls += 1
            assert request.max_output_tokens == 900 and request.deadline_ms <= 5000
            value = {"nodes": [{"id": "p", "kind": "Procedure", "label": "Candidate procedure", "source_span_id": "S1"},
                {"id": "clause", "kind": "Clause", "label": "Original clause", "source_span_id": "S1"}],
                "edges": [{"id": "e", "from_id": "p", "to_id": "clause", "relation": "defined_by", "source_span_id": "S1"}]}
            return LlmResponse(LlmResponseStatus.COMPLETED, "scripted", "test", output_text=json.dumps(value), usage=TokenUsage(10, 0, 20))
    gateway = Gateway()
    client, s, p = app_client(tmp_path, gateway=gateway, admission=lambda _: True)
    response = client.post(f"/v1/policy-graph/versions/{p.id}:extract-candidate", headers={"x-test-role": "KNOWLEDGE_ADMIN"}, json={"target_ids": ["procedure"]})
    assert response.status_code == 200, response.text
    candidate_id = response.json()["candidate_id"]
    assert response.json()["usage"]["model_calls"] == gateway.calls == 1
    assert s.repository.publication(candidate_id) is None and s.repository.reviews(candidate_id) == []


@pytest.mark.parametrize("payload", [{"query": "thử nghiệm", "depth": 5}, {"query": "x", "nodes": 0},
    {"query": "x", "tenant_id": "spoofed"}, {"query": "x", "nodes": True}])
def test_client_cannot_spoof_scope_or_exceed_bounds(tmp_path, payload):
    client, _, _ = app_client(tmp_path)
    assert client.post("/v1/policy-graph/relations:search", headers={"x-test-role": "STUDENT"}, json=payload).status_code == 422
