"""Actual factory/proxy/auth wiring over retained sources; no inference/generation."""
import asyncio
from pathlib import Path
import sys

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def test_graph_factory_proxy_real_sources_and_existing_synthetic_admin_roles(tmp_path, monkeypatch):
    from build_policy_graph import corpus, review_context
    from campus247.application.policy_graph.source_mapping import authored_public_proposal
    from campus247.application.policy_graph.service import PolicyGraphService
    from campus247.application.retrieval.context import RetrievalContextFactory, ResolvedRetrievalScope
    from campus247.bootstrap.app import create_app
    from campus247.bootstrap.certificate_demo import create_certificate_demo_app
    from campus247.bootstrap.settings import Settings
    from campus247.domain.policy_graph import fingerprint, source_fingerprint
    from campus247.infrastructure.repositories.sqlite_policy_graph import SQLitePolicyGraphRepository
    from campus247.infrastructure.repositories.sqlite_agent_runs import SQLiteAgentRunStore
    from campus247.infrastructure.repositories.sqlite_conversations import SQLiteConversationRepository
    monkeypatch.setenv("CAMPUS247_IDEMPOTENCY_DB", str(tmp_path / "idempotency.sqlite3"))
    source = corpus()
    proposal = authored_public_proposal(source, graph_id="bootstrap-real-source", index_fingerprint=source.fingerprint)
    repo = SQLitePolicyGraphRepository(tmp_path / "graph.sqlite3", workspace=tmp_path)
    repo.add(proposal, raw=proposal.model_dump_json())
    service = PolicyGraphService(repo, source, graph_id=proposal.id, index_fingerprint=source.fingerprint,
        source_fingerprint=source_fingerprint(source.rows))
    async def publish():
        ctx = review_context()
        revision = 0
        for row in (*proposal.nodes, *proposal.edges):
            revision = await service.review(proposal.id, ctx, target=row.id, verdict="approved",
                note="Explicit development source fixture review", expected_revision=revision)
        preview = service.publication_preview(proposal.id, ctx, expected_revision=revision)
        await service.publish(proposal.id, ctx, expected_revision=revision, confirmation=fingerprint(preview))
    asyncio.run(publish())
    class Scope:
        def resolve(self, identity):
            return ResolvedRetrievalScope("huce-local-public", "HUCE", frozenset({"STUDENT"}),
                frozenset({"PUBLIC", identity.faculty_code or "PUBLIC"}), frozenset({"PUBLIC"}))
    class Gateway:
        calls = 0
        async def generate(self, request):
            self.calls += 1
            raise AssertionError("No generation without admission")
    gateway = Gateway()
    settings = Settings(_env_file=None, ENVIRONMENT="development", DEMO_MODE=True,
        OPENAI_API_KEY=None, GEMINI_API_KEY=None, DEEPSEEK_API_KEY=None)
    rag = create_app(runtime_settings=settings, synthetic_tenant_id="huce-local-public", llm_gateway=gateway,
        retrieval_context_factory=RetrievalContextFactory(scope_resolver=Scope(), configured_tenant_id="huce-local-public", configured_campus_id="HUCE"),
        public_knowledge_store=source, citation_source_reader=source, policy_graph=service,
        conversation_repository=SQLiteConversationRepository(tmp_path / "history.sqlite3"),
        multi_agent_store=SQLiteAgentRunStore(tmp_path / "runs.sqlite3"), multi_agent_admission=lambda _: False)
    outer = create_certificate_demo_app(tmp_path / "business.sqlite3", settings=settings, integrated_rag_app=rag)
    assert rag.state.multi_agent_workflow.snapshot["policy_graph"] == service.snapshot
    client = TestClient(outer)
    assert {"KA001", "KA002"} <= {row["account"] for row in client.get("/v1/auth/demo-accounts").json()["items"]}
    login = client.post("/v1/auth/demo-login", json={"account": "KA001"})
    assert login.status_code == 200 and "KNOWLEDGE_ADMIN" in login.json()["user"]["roles"]
    admin = {"Authorization": "Bearer "+login.json()["token"]}
    base = "/v1/policy-graph/versions/"+proposal.id
    assert client.get(base, headers=admin).status_code == 200
    assert client.get("/v1/document-requests", headers=admin).status_code == 403
    assert client.post(base+":extract-candidate", headers=admin, json={"target_ids": ["certificate-form"]}).status_code == 409
    login = client.post("/v1/auth/demo-login", json={"account": "SV001"})
    student = {"Authorization": "Bearer "+login.json()["token"]}
    assert client.get(base, headers=student).status_code == 403
    result = client.post("/v1/policy-graph/relations:search", headers=student, json={"query": "quy trình xác nhận"})
    assert result.status_code == 200, result.text
    assert result.json()["edges"] and result.json()["sources"]
    assert gateway.calls == 0
