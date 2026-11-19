"""Real HTTP/SQLite/canonical source checks, scripted generation explicitly offline."""
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from identities import generate_identities

from campus247.bootstrap.app import create_app
from campus247.bootstrap.certificate_demo import create_certificate_demo_app
from campus247.bootstrap.settings import Settings
from campus247.application.retrieval.context import RetrievalContextFactory, ResolvedRetrievalScope
from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
from campus247.infrastructure.retrieval.public_knowledge import PublicKnowledgeStore
from campus247.infrastructure.repositories.sqlite_conversations import SQLiteConversationRepository
from campus247.infrastructure.repositories.sqlite_agent_runs import SQLiteAgentRunStore
from campus247.ports.llm import LlmResponse, LlmResponseStatus, TokenUsage
from tests.unit.agent.test_multi_agent_integrated import ScriptedModel, item, task, plan

ROOT = Path(__file__).resolve().parents[2]


class Scope:
    denied = False
    def resolve(self, identity):
        if self.denied:
            raise ValueError("scope revoked")
        return ResolvedRetrievalScope("huce-local-public", "HUCE", frozenset({"STUDENT"}), frozenset({identity.faculty_code or "PUBLIC"}), frozenset({"PUBLIC"}))


class SourceModel(ScriptedModel):
    def __init__(self, *, clarification=False):
        super().__init__(clarify=clarification)
        self.plan["items"] = [item("Q1", "Bắt đầu xin giấy xác nhận sinh viên tại đâu?")]
        self.claim = "Sinh viên/Cựu sinh viên đăng nhập vào trang motcua.huce.edu.vn."

    async def generate(self, request):
        if request.route_id in {"multi_research_report", "multi_verifier_coverage"}:
            self.calls.append(request)
            data = json.loads(request.input_items[0]["content"])["untrusted_data"]
            evidence = data["evidence"][0]
            value = {"coverage": [{"item_id": item["id"], "status": "supported", "supports": [
                {"requirement_id": "R1", "evidence_id": evidence["evidence_id"], "span_id": next(
                    span["span_id"] for span in evidence["original_spans"] if "motcua.huce.edu.vn" in span["text"])}
            ]} for item in data["items"]]}
            return LlmResponse(LlmResponseStatus.COMPLETED, "scripted", "source-control-flow",
                output_text=json.dumps(value, ensure_ascii=False), usage=TokenUsage(10, 0, 20))
        if request.route_id == "grounded_faq":
            self.calls.append(request)
            return LlmResponse(LlmResponseStatus.COMPLETED, "scripted", "source-control-flow", output_text=json.dumps(
                {"claims": [{"text": self.claim, "citation_ids": ["CIT-001"], "claim_type": "procedure"}]}, ensure_ascii=False), usage=TokenUsage(10, 0, 20))
        if request.route_id == "multi_coordinator_decision" and self.clarify:
            self.calls.append(request)
            return LlmResponse(LlmResponseStatus.COMPLETED, "scripted", "source-control-flow", output_text=json.dumps(
                {"action": "research", "tasks": [{key: value for key, value in spec.items() if key != "tools"} for spec in
                    [task("T1", "research"), task("T2", "verifier", dependencies=("T1",))]], "clarification": None}), usage=TokenUsage(10, 0, 20))
        return await super().generate(request)


def frames(text):
    values = []
    for block in text.split("\n\n"):
        rows = dict(line.split(":", 1) for line in block.splitlines() if ":" in line)
        if "data" in rows:
            values.append((rows.get("event", "").strip(), json.loads(rows["data"])))
    return values


def make(tmp_path, monkeypatch, *, model=None):
    monkeypatch.setenv("CAMPUS247_IDEMPOTENCY_DB", str(tmp_path / "idempotency.sqlite3"))
    settings = Settings(_env_file=None, ENVIRONMENT="development", DEMO_MODE=True,
        OPENAI_API_KEY=None, GEMINI_API_KEY=None, DEEPSEEK_API_KEY=None)
    corpus = PublicKnowledgeStore(ROOT / "data/huce-public-20261013", tenant_id="huce-local-public", campus_id="HUCE")
    # Original canonical parent text and hash. Test search selects one known
    # parent to isolate transport/provenance, not to measure retrieval quality.
    source = next(row for row in corpus.rows if row["page_start"] == 39)
    async def search(query, context):
        corpus._authorized(context)
        return [source]
    corpus.search = search
    model = model or SourceModel()
    scope = Scope()
    factory = RetrievalContextFactory(scope_resolver=scope, configured_tenant_id="huce-local-public", configured_campus_id="HUCE")
    app = create_app(runtime_settings=settings, synthetic_tenant_id="huce-local-public", retrieval_context_factory=factory,
        public_knowledge_store=corpus, citation_source_reader=corpus, llm_gateway=model,
        conversation_repository=SQLiteConversationRepository(tmp_path / "history.sqlite3"),
        multi_agent_store=SQLiteAgentRunStore(tmp_path / "runs.sqlite3"))
    adapter = SyntheticIdentityAdapter(settings.IDENTITY_SECRET_KEY, environment="development", tenant_id="huce-local-public")
    students = generate_identities()["records"]["student_profile"]
    headers = {"Authorization": "Bearer " + adapter.mint_token(students[0]["user_id"])}
    other = {"Authorization": "Bearer " + adapter.mint_token(students[1]["user_id"])}
    return app, headers, other, source, model, scope


def test_multi_agent_sse_citation_history_reload_and_owned_event_cursor(tmp_path, monkeypatch):
    app, headers, other, source, model, scope = make(tmp_path, monkeypatch)
    with TestClient(app) as client:
        cid = client.post("/v1/conversations", headers=headers, json={}).json()["id"]
        response = client.post(f"/v1/conversations/{cid}/messages:stream", headers=headers, json={"content": "Xin giấy xác nhận sinh viên bắt đầu từ đâu?"})
        events = frames(response.text)
        assert any(kind == "agent.status" for kind, _ in events), response.text
        final = next(data for kind, data in events if kind == "message.completed")
        assert final["response_class"] == "grounded_answer", response.text
        progress = next(data for kind, data in events if kind == "agent.status")
        run_id = progress["run_id"]
        path = f"/v1/conversations/{cid}/agent-runs/{run_id}"
        run = client.get(path, headers=headers)
        assert run.status_code == 200 and run.json()["status"] == "completed"
        assert client.get(path, headers=other).status_code == 404
        cursor = client.get(path+"/events", headers=headers).json()["cursor"]
        assert client.get(path+f"/events?after={cursor}", headers=headers).json()["events"] == []
        citation = final["citations"][0]["citation"]
        opened = client.get(f"/v1/conversations/{cid}/messages/{final['message_id']}/citations/{citation['citation_id']}/source", headers=headers)
        assert opened.status_code == 200, opened.text
        assert opened.json()["content_sha256"] == source["quote_span_hash"]
        assert hashlib.sha256(opened.json()["content_text"].encode()).hexdigest() == source["quote_span_hash"]
        assert client.post(f"/v1/conversations/{cid}/messages:stream", headers=headers, json={"content": "retry"},
            ).status_code == 200  # Separate explicit turn, never reconnect replay.
        calls = len(model.calls)
        reconnect = client.post(f"/v1/conversations/{cid}/messages:stream", headers={**headers, "Last-Event-ID": final["message_id"]}, json={"content": "retry"})
        assert reconnect.status_code == 409 and len(model.calls) == calls
        scope.denied = True
        assert client.get(path, headers=headers).status_code == 403
    # Reload whole app/repositories against the same retained test DB.
    reloaded, headers, _, _, _, _ = make(tmp_path, monkeypatch)
    with TestClient(reloaded) as client:
        history = client.get(f"/v1/conversations/{cid}/messages?limit=100", headers=headers)
        assert history.status_code == 200
        assert history.json()["items"][1]["final_result"] == final


def test_clarification_resume_cas_and_current_scope(tmp_path, monkeypatch):
    model = SourceModel(clarification=True)
    app, headers, _, _, _, scope = make(tmp_path, monkeypatch, model=model)
    with TestClient(app) as client:
        cid = client.post("/v1/conversations", headers=headers, json={}).json()["id"]
        response = client.post(f"/v1/conversations/{cid}/messages:stream", headers=headers, json={"content": "Học bổng em đủ điều kiện không?"})
        events = frames(response.text)
        final = next(data for kind, data in events if kind == "message.completed")
        assert final["response_class"] == "clarification_request"
        run_id = next(data["run_id"] for kind, data in events if kind == "agent.status")
        path = f"/v1/conversations/{cid}/agent-runs/{run_id}"
        record = client.get(path, headers=headers).json()
        scope.denied = True
        calls = len(model.calls)
        denied = client.post(path+":resume", headers=headers, json={"expected_version": record["version"], "content": "Giấy xác nhận sinh viên"})
        assert denied.status_code == 403 and len(model.calls) == calls
        scope.denied = False
        resumed = client.post(path+":resume", headers=headers, json={"expected_version": record["version"], "content": "Giấy xác nhận sinh viên"})
        assert resumed.status_code == 200, resumed.text
        assert resumed.json()["message"]["response_class"] == "grounded_answer", resumed.text
        calls = len(model.calls)
        duplicate = client.post(path+":resume", headers=headers, json={"expected_version": record["version"], "content": "Giấy xác nhận sinh viên"})
        assert duplicate.status_code == 409 and len(model.calls) == calls


def test_integrated_certificate_proxy_uses_agents_and_preserves_confirmation(tmp_path, monkeypatch):
    rag, _, _, _, _, _ = make(tmp_path, monkeypatch)
    outer = create_certificate_demo_app(tmp_path / "certificates.sqlite3", integrated_rag_app=rag)
    with TestClient(outer) as client:
        login = client.post("/v1/auth/demo-login", json={"account": "SV001"}).json()
        headers = {"Authorization": "Bearer "+login["token"]}
        cid = client.post("/v1/conversations", headers=headers, json={}).json()["id"]
        response = client.post(f"/v1/conversations/{cid}/messages:stream", headers=headers, json={"content": "Xin giấy xác nhận sinh viên bắt đầu từ đâu?"})
        assert "agent.status" in response.text and "grounded_answer" in response.text
        form = {"purpose": "Nộp thực tập", "recipient": "Phòng Nhân sự", "quantity": 1, "delivery_method": "DIGITAL", "attachments": []}
        record = client.post("/v1/document-requests/drafts", headers=headers, json={"form": form}).json()
        from campus247.application.multi_agent.service_adapter import CertificateDraftAdapter
        from campus247.domain.document_request.certificate import CertificateForm
        adapter = outer.state.certificate_draft_adapter
        actor = SyntheticIdentityAdapter(Settings().IDENTITY_SECRET_KEY, tenant_id="huce-local-public").resolve_token(login["token"])
        preview_path = f"/v1/document-requests/{record['id']}/preview"
        response = client.post(preview_path, headers=headers, json={"expected_version": record["version"]})
        assert response.status_code == 200
        prepared = response.json()
        repeated = adapter.prepare_service_draft(actor, CertificateForm.model_validate(form), document_id=record["id"], expected_version=record["version"])
        assert repeated["preview_id"] == prepared["preview_id"]
        assert client.post(preview_path, headers=headers, json={"expected_version": record["version"]}).status_code == 409
        assert client.get(preview_path, headers=headers).json()["preview_id"] == prepared["preview_id"]
        assert client.get(f"/v1/document-requests/{record['id']}", headers=headers).json()["status"] == "PENDING_CONFIRMATION"
        assert not hasattr(adapter, "confirm") and not hasattr(adapter, "submit")
        confirmed = client.post(f"/v1/document-requests/{record['id']}/confirm", headers=headers, json={"form": form,
            "preview_id": prepared["preview_id"], "confirmation_token": prepared["confirmation_token"], "idempotency_key": "multi-confirm-01"})
        assert confirmed.status_code == 201


def test_session_revoked_during_research_cannot_reach_verifier_or_answer(tmp_path, monkeypatch):
    rag, _, _, source, model, _ = make(tmp_path, monkeypatch)
    outer = create_certificate_demo_app(tmp_path / "revoked-certificates.sqlite3", integrated_rag_app=rag)
    with TestClient(outer) as client:
        login = client.post("/v1/auth/demo-login", json={"account": "SV001"}).json()
        headers = {"Authorization": "Bearer "+login["token"]}
        workflow = rag.state.multi_agent_workflow
        original_search = workflow._context_search_fn
        async def revoke_then_search(query, context):
            found = await original_search(query, context)
            rag.state.current_session_service.revoke_session(login["token"])
            return found
        workflow._context_search_fn = revoke_then_search
        cid = client.post("/v1/conversations", headers=headers, json={}).json()["id"]
        response = client.post(f"/v1/conversations/{cid}/messages:stream", headers=headers, json={"content": "Xin giấy xác nhận sinh viên bắt đầu từ đâu?"})
        final = next(data for kind, data in frames(response.text) if kind == "message.completed")
        assert final["response_class"] == "system_error"
        assert not any(call.route_id in {"multi_verifier_coverage", "grounded_faq"} for call in model.calls)
        assert client.get(f"/v1/conversations/{cid}/messages", headers=headers).status_code == 401


@pytest.mark.asyncio
async def test_corrective_worker_calls_actual_lexical_search_and_original_reader(tmp_path):
    """Actual source tools, scripted decisions/generation; no live-model quality claim."""
    import re
    from datetime import datetime, timezone
    from campus247.agent.multi_rag import MultiAgentWorkflow
    from campus247.agent.state import NormalizedTurn, Terminal
    from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy
    from campus247.domain.shared.values import generate_uuid7
    question = "Tóm tắt các bước xin giấy xác nhận sinh viên có căn cứ từ sổ tay."
    corpus = PublicKnowledgeStore(ROOT / "data/huce-public-20261013", tenant_id="huce-local-public", campus_id="HUCE", faq_directory=ROOT / "data/huce-faq-20261013")
    class Corrective(SourceModel):
        async def generate(self, request):
            route = request.route_id
            if route == "multi_coordinator_plan":
                self.plan["tasks"][0]["goal"] = question
                self.plan["items"] = [item("Q1", question)]
            if route == "multi_research_query":
                self.calls.append(request)
                data = json.loads(request.input_items[0]["content"])["untrusted_data"]
                # Evidence is capped at 15,000 bytes. The handbook now also holds a large reviewed
                # re-segmentation, so the broad first search uses a narrower wording that still
                # misses the procedure and forces the corrective second search under test.
                value = {"query": "các bước xin giấy tờ sinh viên có căn cứ" if data["task"]["id"] == "T1" else
                    "Quy trình xác nhận sinh viên đăng ký Một cửa dịch vụ mẫu xác nhận trình ký lấy dấu trả kết quả theo lịch hẹn"}
                return LlmResponse(LlmResponseStatus.COMPLETED, "scripted", "source-control-flow", output_text=json.dumps(value, ensure_ascii=False), usage=TokenUsage(10, 0, 20))
            if route in {"multi_research_report", "multi_verifier_coverage"}:
                self.calls.append(request)
                data = json.loads(request.input_items[0]["content"])["untrusted_data"]
                procedure = next((row for row in data["evidence"] if any(
                    "2. Quy trình xác nhận sinh viên" in span["text"] for span in row["original_spans"])), None)
                value = {"coverage": [{"item_id": "Q1", "status": "supported" if procedure else "missing_source", "supports": [
                    {"requirement_id": "R1", "evidence_id": procedure["evidence_id"], "span_id": next(
                        span["span_id"] for span in procedure["original_spans"] if "motcua.huce.edu.vn" in span["text"])}
                ] if procedure else []}]}
                return LlmResponse(LlmResponseStatus.COMPLETED, "scripted", "source-control-flow", output_text=json.dumps(value, ensure_ascii=False), usage=TokenUsage(10, 0, 20))
            response = await super().generate(request)
            if route == "grounded_faq":
                rendered = "\n".join(row["content"] for row in request.input_items)
                match = re.search(r"\[(CIT-\d{3})\] Nguồn:[^\n]*\(Trang 39\)", rendered)
                assert match
                value = json.loads(response.output_text)
                value["claims"][0]["citation_ids"] = [match.group(1)]
                return replace(response, output_text=json.dumps(value, ensure_ascii=False))
            return response
    model = Corrective(); model.supplement = True
    turn = NormalizedTurn(generate_uuid7(), generate_uuid7(), "source-test-student", question)
    ctx = RetrievalContext(AuthorizedScope("huce-local-public", "HUCE", turn.user_id,
        frozenset({"STUDENT"}), frozenset({"STUDENT"}), frozenset({"PUBLIC"}), frozenset({"PUBLIC"})), "vi",
        datetime.now(timezone.utc), SimulationPolicy.DENY, "1"*32)
    workflow = MultiAgentWorkflow(store=SQLiteAgentRunStore(tmp_path / "real-source-runs.sqlite3"), source_reader=corpus,
        context_search_fn=corpus.search, llm_gateway=model, require_retrieval_context=True, evidence_support_threshold=.78)
    result = await workflow.arun(turn, retrieval_context=ctx)
    assert result.terminal == Terminal.ANSWERED, result.errors
    record = workflow.store.get(turn.turn_id, turn.user_id, turn.session_id)
    searches = [event for event in record["events"] if event["tool"] == "search_knowledge"]
    assert len(searches) == 2
    procedure_id = next(row["chunk_id"] for row in corpus.rows if row["page_start"] == 39)
    assert procedure_id not in searches[0]["data"]["candidate_ids"]
    assert procedure_id in searches[1]["data"]["candidate_ids"]
    assert any(event["tool"] == "read_source" and event["data"]["chunk_id"] == procedure_id for event in record["events"])
