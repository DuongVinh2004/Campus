"""Integrated policy agents plus the existing certificate UI/service.

Guarded mode opens no paid writer. Live mode uses the unchanged exclusive
Gateway and existing cumulative ceilings, and refuses insufficient headroom.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "services/api/src"), str(ROOT / "packages/synthetic/src"), str(ROOT / "scripts")]
from multi_agent_workspace import STATE, checked, stage_path


class GuardedGateway:
    async def generate(self, request):
        from campus247.application.single_agent.resources import AgentStop
        raise AgentStop("MODEL_BUDGET_EXHAUSTED")


def headroom(policy):
    from decimal import Decimal
    from multi_agent_live_resources import AUTHORIZATION, paid_view, native_view, authorized_paid_caps, NATIVE_CAPS
    paid, native = paid_view(), native_view()
    caps = authorized_paid_caps()
    expected_paid = (caps["usd"], caps["calls"])
    expected_native = NATIVE_CAPS if AUTHORIZATION.exists() else {"http": 6000, "inference": 2000, "tokens": 750000}
    if (paid["hard_cap_usd"], paid["call_cap"]) != expected_paid or native["caps"] != expected_native:
        raise ValueError("retained ledger ceilings changed")
    # Conservative full-run admission. No new provider/native reservations,
    # reset, refunds or model calls occur while checking existing headroom.
    # Native worker reserves per sequence: up to six rerank pairs plus three
    # query embeddings per search. Each sequence retains the 900-token envelope.
    native_sequences = policy.max_searches * 9
    conservative_cost = Decimal(policy.max_reserved_tokens) * Decimal("1.2") / 1000000
    allowed = ((paid["call_cap"] is None or paid["call_cap"]-paid["calls"] >= policy.max_model_calls) and
               (paid["hard_cap_usd"] is None or Decimal(paid["remaining_usd"]) >= conservative_cost) and
               native["caps"]["inference"]-native["counts"]["inference"] >= native_sequences and
               native["caps"]["tokens"]-native["counts"]["tokens"] >= native_sequences * 900 and
               native["caps"]["http"]-native["counts"]["http"] >= policy.max_searches * 18)
    return allowed


def make_app(*, mode="guarded", frontend_port=None, policy_graph_id=None):
    import httpx
    from campus247.bootstrap.app import create_app
    from campus247.bootstrap.certificate_demo import create_certificate_demo_app
    from campus247.bootstrap.settings import Settings
    from campus247.application.retrieval.context import RetrievalContextFactory
    from campus247.application.multi_agent.contracts import MultiAgentPolicy
    from campus247.infrastructure.repositories.sqlite_agent_runs import SQLiteAgentRunStore
    from campus247.infrastructure.repositories.sqlite_conversations import SQLiteConversationRepository
    from scripts.public_rag_retrieval import load_public_hybrid_store
    from scripts.run_public_rag import ScopeResolver, TENANT, CAMPUS, Gateway
    from campus247.infrastructure.retrieval.public_hybrid import PublicRetrievalPolicy
    corpus = load_public_hybrid_store(ROOT / "data/huce-public-20261013", tenant_id=TENANT, campus_id=CAMPUS,
        faq_directory=ROOT / "data/huce-faq-20261013", policy=PublicRetrievalPolicy(fusion_k=4, query_limit=1))
    policy = MultiAgentPolicy()
    scope_resolver = ScopeResolver()
    policy_graph = None
    if policy_graph_id is not None:
        from scripts.build_policy_graph import destination
        from campus247.domain.policy_graph import source_fingerprint
        from campus247.application.policy_graph.service import PolicyGraphService
        from campus247.infrastructure.repositories.sqlite_policy_graph import SQLitePolicyGraphRepository
        path = destination("policy-graph.sqlite3")
        if not path.is_file():
            raise ValueError("retained stage5 graph required")
        repo = SQLitePolicyGraphRepository(path, workspace=ROOT)
        if not repo.publication(policy_graph_id):
            raise ValueError("published graph version required")
        policy_graph = PolicyGraphService(repo, corpus, graph_id=policy_graph_id,
            index_fingerprint=corpus.fingerprint, source_fingerprint=source_fingerprint(corpus.rows))
        class PublicGraphScopeResolver(ScopeResolver):
            def resolve(self, identity):
                from dataclasses import replace
                current = super().resolve(identity)
                # The independently configured corpus is entirely public.
                # Retain faculty grants and explicitly include its PUBLIC
                # classification; never give a grant to another private faculty.
                return replace(current, faculty_codes=current.faculty_codes | {"PUBLIC"})
        scope_resolver = PublicGraphScopeResolver()
    if mode not in {"guarded", "live"}:
        raise ValueError("explicit runtime mode required")
    if mode == "live" and not headroom(policy):
        raise RuntimeError("insufficient shared ledger headroom; no Gateway opened")
    if mode == "live":
        from multi_agent_live_resources import AUTHORIZATION, restore_paid
        class IntegratedGateway(Gateway):
            json_mode = True
            def _restore_budget(self, snapshot, pending):
                return restore_paid(snapshot, pending) if AUTHORIZATION.exists() else super()._restore_budget(snapshot, pending)
        gateway = IntegratedGateway()
    else:
        gateway = GuardedGateway()
    settings = Settings(_env_file=None, ENVIRONMENT="development", DEMO_MODE=True,
        OPENAI_API_KEY=None, GEMINI_API_KEY=None, DEEPSEEK_API_KEY=None)
    # Retain the established history and certificate DB; new run/task state has
    # its own additive database. SQLite append operations keep ownership/CAS.
    database = checked(ROOT / "infra/local/certificate-stage1-20261013-01/demo.sqlite3")
    conversations = checked(ROOT / "infra/local/public-rag-20261013/conversations.sqlite3")
    if not database.is_file() or not conversations.is_file():
        raise ValueError("retained business/history databases required")
    os.environ["CAMPUS247_IDEMPOTENCY_DB"] = str(stage_path("idempotency.sqlite3"))
    rag = create_app(runtime_settings=settings, synthetic_tenant_id=TENANT,
        retrieval_context_factory=RetrievalContextFactory(scope_resolver=scope_resolver, configured_tenant_id=TENANT, configured_campus_id=CAMPUS),
        public_knowledge_store=corpus, citation_source_reader=corpus,
        conversation_repository=SQLiteConversationRepository(conversations), llm_gateway=gateway,
        multi_agent_store=SQLiteAgentRunStore(stage_path("agent-runs.sqlite3")), multi_agent_policy=policy,
        multi_agent_admission=headroom if mode == "live" else lambda _: False, policy_graph=policy_graph)
    app = create_certificate_demo_app(database, settings=settings, integrated_rag_app=rag, frontend_port=frontend_port)
    app.state.integrated_rag_app = rag
    app.state.rag_mode = "multi_agent_"+mode
    app.state.owns_paid_ledger = mode == "live"
    from multi_agent_live_resources import paid_view, native_view
    paid, native = paid_view(), native_view()
    from dataclasses import asdict
    app.state.configuration = {"mode": mode, "index_fingerprint": corpus.fingerprint, "retrieval_policy": asdict(corpus.policy),
        "policy_version": policy.version, "policy": asdict(policy),
        "generation": {"provider": "deepseek", "model": "deepseek-flash", "json_object_mode": mode == "live", "thinking": "disabled"},
        "policy_fingerprint": policy.fingerprint, "shared_paid_cap_calls": paid["call_cap"], "shared_paid_cap_usd": paid["hard_cap_usd"],
        "shared_native_inference_cap": native["caps"]["inference"], "source_chunks": len(corpus.rows),
        "live_generation_verified": False, "policy_graph": policy_graph.snapshot if policy_graph else None}
    return app


if __name__ == "__main__":
    import uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["guarded", "live"], default="guarded")
    parser.add_argument("--frontend", type=int, choices=[3003, 3004])
    parser.add_argument("--policy-graph", default=None, help="Explicit immutable stage5 graph version")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    app = make_app(mode=args.mode, frontend_port=args.frontend, policy_graph_id=args.policy_graph)
    print(json.dumps({"runtime": app.state.configuration, "pid": os.getpid(),
                      "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}), flush=True)
    uvicorn.run(app, host="127.0.0.1", port=8003, access_log=False, log_level="warning")
