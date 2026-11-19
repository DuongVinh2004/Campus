"""Public factory/SSE regressions with offline models; no live quality claim."""
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
from campus247.infrastructure.retrieval.public_hybrid import PublicHybridKnowledgeStore
from campus247.ports.llm import LlmResponse, LlmResponseStatus, TokenUsage

from scripts import public_rag_retrieval as wiring
from scripts import run_public_rag as public

SOURCE = "Phòng tự học thư viện ở tầng 2."


@pytest.fixture
def corpus(tmp_path):
    directory = tmp_path / "corpus"
    directory.mkdir()
    manifest = {"public_only": True, "acquired_at": "2026-10-13T01:00:00+07:00", "chunks": [
        {"url": "https://thuvien.huce.edu.vn/test", "title": "Hướng dẫn thư viện",
         "section": "Phòng tự học", "page": 1, "text": SOURCE},
    ]}
    (directory / "corpus.json").write_text(json.dumps(manifest), encoding="utf-8")
    value = wiring.create_public_hybrid_store(directory, tenant_id=public.TENANT, campus_id=public.CAMPUS)
    vector = [1.0] + [0.0] * 1023
    index = {"fingerprint": value.fingerprint, "model_id": value.embedding_profile.model_id,
             "model_revision": value.embedding_profile.model_revision,
             "child_ids": [child["id"] for child in value.children],
             "vectors": [vector for _ in value.children], "source_text_unchanged": True}
    value.load_vectors(index)
    value.faq_index = SimpleNamespace(entries=(), source_matches=lambda _: [])
    return value, directory, index


def test_common_factory_keeps_exact_models_and_runtime_envelope(corpus):
    value, _, _ = corpus
    assert isinstance(value, PublicHybridKnowledgeStore)
    assert (value.embedding_profile.model_id, value.embedding_profile.model_revision) == (
        "BAAI/bge-m3", "5617a9f61b028005a4858fdac845db406aefb181")
    assert (value.reranker.profile.model_id, value.reranker.profile.model_revision) == (
        "BAAI/bge-reranker-v2-m3", "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e")
    assert (value.embedding_profile.dimension, value.embedding_profile.batch_limit,
            value.embedding_profile.timeout_ms, value.reranker.profile.timeout_ms) == (1024, 1, 5000, 10000)
    assert (value.policy.fusion_k, value.policy.query_limit, value.policy.parent_k,
            value.policy.context_bytes, value.policy.deadline_seconds) == (6, 3, 4, 15000, 12)


def test_retained_huce_index_loads_without_model_or_paid_calls(monkeypatch):
    def no_http(*args, **kwargs):
        pytest.fail("Index validation must not call a model")
    monkeypatch.setattr(wiring.httpx, "AsyncClient", no_http)
    value = wiring.load_public_hybrid_store(public.CORPUS, tenant_id=public.TENANT,
        campus_id=public.CAMPUS, faq_directory=ROOT / "data/huce-faq-20261013")
    assert value.vectors and len(value.vectors) == len(value.children)
    # Validate the retained curriculum release independently of additive service releases.
    retained = wiring.create_public_hybrid_store(public.CORPUS, tenant_id=public.TENANT,
        campus_id=public.CAMPUS, faq_directory=ROOT / "data/huce-faq-20261013", include_reviewed_services=False)
    assert retained.fingerprint == "dc625eaaa3ccccfe5b703ca8a540cb66ee4dd1e2400e10b34002335a6f93bf93"
    retained.load_vectors(json.loads(wiring.public_hybrid_index_path(retained).read_text(encoding="utf-8")))
    # Visually corrected excerpts replace automated QLDA, handbook flow-chart,
    # and title-only curricula; their historical readbacks are covered separately.
    # Later reviewed releases replaced every title-and-total-credits stub with the full curriculum
    # (each stub is under 400 characters) and re-segmented handbook page 31 without losing its text.
    title_only = ("— tiêu đề (tổng tín chỉ chưa xác định)", "— tiêu đề, ngành và dòng tổng tín chỉ",
                  "— tiêu đề và dòng tổng tín chỉ, trang 1")

    def replaced(parent):
        row = retained.rows[parent]
        return (row["title"] == "K71 — Quản lý dự án" or row["section_path"] in {"Trang 27", "Trang 31"}
                or (row["section_path"].endswith(title_only) and len(row["content_text"]) < 400))
    untouched = {c["id"] for c in retained.children if not replaced(c["parent"])}
    assert untouched < {c["id"] for c in value.children}


@pytest.mark.parametrize("change", [
    {"fingerprint": "drifted"}, {"model_revision": "other"},
    {"source_text_unchanged": False}, {"vectors": [[1.0, 0.0]]},
])
def test_loader_rejects_index_drift_without_fallback(corpus, tmp_path, monkeypatch, change):
    _, directory, manifest = corpus
    index = tmp_path / "index.json"
    index.write_text(json.dumps(dict(manifest, **change)), encoding="utf-8")
    monkeypatch.setattr(wiring, "public_hybrid_index_path", lambda _: index)
    with pytest.raises(ValueError):
        wiring.load_public_hybrid_store(directory, tenant_id=public.TENANT, campus_id=public.CAMPUS)


def test_index_path_rejects_workspace_escape(corpus):
    value, _, _ = corpus
    with pytest.raises(ValueError, match="outside workspace"):
        wiring.public_hybrid_index_path(value, ROOT.parent)


def test_missing_index_fails_before_gateway_or_local_state(monkeypatch, tmp_path):
    monkeypatch.setattr(public, "STATE", tmp_path / "unopened-state")
    def unavailable(*args, **kwargs):
        raise FileNotFoundError("test missing index")
    def no_gateway():
        pytest.fail("Missing index must not open the paid gateway")
    monkeypatch.setattr(wiring, "load_public_hybrid_store", unavailable)
    monkeypatch.setattr(public, "Gateway", no_gateway)
    with pytest.raises(FileNotFoundError):
        public.make_app()
    assert not public.STATE.exists()


class OfflineGateway:
    def __init__(self):
        self.requests = []
        self.supported = True

    async def generate(self, request):
        self.requests.append(request)
        assert 0 < request.deadline_ms <= 5000 and 0 < request.max_output_tokens <= 1000
        assert not request.allowed_tools
        if request.route_id == "sensitive_classifier":
            result = {"severity": "normal", "is_crisis": False, "confidence": 1.0}
        elif request.route_id == "route_intent":
            result = {"route": "grounded_faq"}
        elif request.route_id == "grounded_faq":
            result = {"claims": [{"text": SOURCE, "citation_ids": ["CIT-001"], "claim_type": "policy"}]}
        elif request.route_id == "grounded_semantic_verification":
            result = {"answers_question": True, "verdicts": [{"claim_id": "CLM-001",
                "status": "SUPPORTED" if self.supported else "CONTRADICTED"}]}
        else:
            pytest.fail("Unexpected provider route")
        return LlmResponse(LlmResponseStatus.COMPLETED, "offline-test", "offline-test",
            output_text=json.dumps(result), usage=TokenUsage(input_tokens=5, output_tokens=20))


@pytest.fixture
def stack(corpus, tmp_path, monkeypatch):
    value, _, _ = corpus
    gateway, model_requests, load_requests = OfflineGateway(), [], []
    fault = {"mode": None}
    original_client = httpx.AsyncClient

    def model(request):
        kind = "embedding" if request.url.port == 18081 else "reranker"
        model_requests.append((kind, request.method, request.url.path))
        profile = value.embedding_profile if kind == "embedding" else value.reranker.profile
        if fault["mode"] == kind + "_unavailable":
            return httpx.Response(503, json={"error": "MODEL_RUNTIME_UNAVAILABLE"})
        if request.url.path == "/info":
            model_id = "wrong-model" if fault["mode"] == kind + "_wrong_model" else profile.model_id
            return httpx.Response(200, json={"model_id": model_id, "model_sha": profile.model_revision,
                "model_type": {kind: {}}, "auto_truncate": False})
        payload = json.loads(request.content)
        assert payload["truncate"] is False
        if kind == "embedding":
            assert len(payload["inputs"]) == 1 and payload["normalize"] is True
            return httpx.Response(200, json=[[1.0] + [0.0] * 1023])
        assert 1 <= len(payload["texts"]) <= 6
        assert payload["raw_scores"] is True and payload["return_text"] is False
        rows = [{"index": i, "score": 1.0} for i in range(len(payload["texts"]))]
        return httpx.Response(200, json=[] if fault["mode"] == "reranker_incomplete" else rows)

    monkeypatch.setattr(wiring.httpx, "AsyncClient", lambda **kwargs: original_client(
        **kwargs, transport=httpx.MockTransport(model)))
    def load(*args, **kwargs):
        load_requests.append((args, kwargs))
        return value
    monkeypatch.setattr(wiring, "load_public_hybrid_store", load)
    monkeypatch.setattr(public, "Gateway", lambda: gateway)
    monkeypatch.setattr(public, "STATE", tmp_path / "public-state")
    monkeypatch.setenv("CAMPUS247_IDEMPOTENCY_DB", str(tmp_path / "unused.sqlite3"))
    app = public.make_app()
    client = TestClient(app)
    auth = client.get("/v1/auth/demo-session")
    assert auth.status_code == 200
    headers = {"Authorization": "Bearer " + auth.json()["token"]}
    created = client.post("/v1/conversations", headers=headers, json={})
    assert created.status_code == 201
    yield SimpleNamespace(app=app, client=client, gateway=gateway, corpus=value, headers=headers,
        cid=created.json()["id"], model_requests=model_requests, load_requests=load_requests, fault=fault)
    client.close()


def stream(stack, question="Phòng tự học thư viện ở đâu?"):
    response = stack.client.post(f"/v1/conversations/{stack.cid}/messages:stream",
        headers=stack.headers, json={"content": question})
    assert response.status_code == 200
    frames = []
    for block in response.text.replace("\r\n", "\n").split("\n\n"):
        fields = dict(line.split(":", 1) for line in block.splitlines() if ":" in line)
        if "data" in fields:
            frames.append((fields["event"].strip(), json.loads(fields["data"])))
    return frames


def test_public_chat_runs_hybrid_verifier_sse_source_and_persisted_history(stack):
    assert stack.app.state.rag_mode == "advanced_hybrid_conversational"
    assert stack.load_requests == [((public.CORPUS,), {"tenant_id": public.TENANT,
        "campus_id": public.CAMPUS, "faq_directory": ROOT / "data/huce-faq-20261013"})]
    final = next(data for event, data in stream(stack) if event == "message.completed")
    assert final["response_class"] == "grounded_answer" and SOURCE in final["content"]
    assert stack.model_requests == [("embedding", "GET", "/info"), ("embedding", "POST", "/embed"),
        ("reranker", "GET", "/info"), ("reranker", "POST", "/rerank")]
    assert [r.route_id for r in stack.gateway.requests][-2:] == ["grounded_faq", "grounded_semantic_verification"]
    assert stack.gateway.requests[-1].max_output_tokens <= 1000 - 20
    citation = final["citations"][0]["citation"]
    url = f"/v1/conversations/{stack.cid}/messages/{final['message_id']}/citations/{citation['citation_id']}/source"
    source = stack.client.get(url, headers=stack.headers)
    assert source.status_code == 200
    excerpt = source.json()
    assert excerpt["content_text"] == SOURCE
    assert excerpt["content_sha256"] == hashlib.sha256(SOURCE.encode()).hexdigest()
    unauthenticated = TestClient(stack.app)
    try:
        assert unauthenticated.get(url).status_code == 401
    finally:
        unauthenticated.close()
    adapter = SyntheticIdentityAdapter(secret_key=stack.app.state.runtime_settings.IDENTITY_SECRET_KEY,
        environment="development", tenant_id=public.TENANT)
    other = {"Authorization": "Bearer " + adapter.mint_token("97c5ab40-6399-7ad3-9838-eab50f267b2d")}
    assert stack.client.get(url, headers=other).status_code == 404
    reloaded = TestClient(public.make_app())
    try:
        history = reloaded.get(f"/v1/conversations/{stack.cid}/messages", headers=stack.headers)
        assert history.status_code == 200
        assert any(item.get("final_result") == final for item in history.json()["items"])
    finally:
        reloaded.close()


@pytest.mark.parametrize("fault", ["embedding_unavailable", "reranker_unavailable",
    "reranker_wrong_model", "reranker_incomplete"])
def test_model_failure_is_dependency_failure_without_grounded_fallback(stack, fault):
    stack.fault["mode"] = fault
    frames = stream(stack)
    assert next(data for event, data in frames if event == "message.failed")["code"] == "DEPENDENCY_UNAVAILABLE"
    assert not any(event == "message.completed" for event, _ in frames)
    assert all(r.route_id not in {"grounded_faq", "grounded_semantic_verification"} for r in stack.gateway.requests)


def test_semantic_rejection_does_not_publish_claim_or_citations(stack):
    stack.gateway.supported = False
    final = next(data for event, data in stream(stack) if event == "message.completed")
    assert final["response_class"] == "safe_refusal" and not final["citations"]
    assert SOURCE not in final["content"]


def test_missing_calendar_source_does_not_invoke_models_or_generation(stack):
    final = next(data for event, data in stream(stack, "Lịch nghỉ Tết năm 2030 bắt đầu ngày nào?")
        if event == "message.completed")
    assert final["response_class"] == "safe_refusal" and not final["citations"]
    assert not stack.model_requests
    assert all(r.route_id not in {"grounded_faq", "grounded_semantic_verification"} for r in stack.gateway.requests)


@pytest.mark.parametrize("failure", ["missing-models", "missing-index", "advanced-api"])
def test_public_launcher_checks_prerequisites_before_spawning(monkeypatch, tmp_path, failure):
    # The frontend preparation module reads CLI arguments on import. Supply the
    # launcher's actual invocation rather than pytest's unrelated arguments.
    monkeypatch.setattr(sys, "argv", ["launch_public_rag.py"])
    from scripts import launch_public_rag as launch
    frontend = tmp_path / "frontend11/.next"
    frontend.mkdir(parents=True)
    (frontend / "BUILD_ID").write_text("test-only", encoding="utf-8")
    monkeypatch.setattr(launch, "STATE", tmp_path)
    monkeypatch.setattr(launch, "listening", lambda port: failure == "advanced-api" and port == 8001)
    def index(*args, **kwargs):
        if failure == "missing-index":
            raise FileNotFoundError("test index missing")
    monkeypatch.setattr(launch, "load_public_hybrid_store", index)
    def no_spawn(*args, **kwargs):
        pytest.fail("Failed prerequisites must not spawn a service")
    monkeypatch.setattr(launch.subprocess, "Popen", no_spawn)
    with pytest.raises((RuntimeError, FileNotFoundError)):
        launch.main()
