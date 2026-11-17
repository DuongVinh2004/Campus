"""Build/run Advanced + Conversational public RAG using real local BGE models."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts"), str(ROOT / "services/api/src"), str(ROOT / "packages/synthetic/src")]
from run_public_rag import CAMPUS, CORPUS, TENANT, Gateway, ScopeResolver, checked
from scripts.public_rag_retrieval import create_public_hybrid_store, public_hybrid_index_path

STATE = checked(ROOT / "infra/local/rag-advanced-20261013")


def store():
    return create_public_hybrid_store(CORPUS, tenant_id=TENANT, campus_id=CAMPUS,
        faq_directory=ROOT / "data/huce-faq-20261013")


def index_path(corpus):
    return public_hybrid_index_path(corpus, STATE)


async def build():
    STATE.mkdir(parents=True, exist_ok=True)
    corpus = store()
    target = index_path(corpus)
    if target.exists():
        corpus.load_vectors(json.loads(target.read_text(encoding="utf-8")))
        print(json.dumps({"index": str(target), "validated_existing": True, "children": len(corpus.children)}))
        return
    print(json.dumps({"building": True, "parents": len(corpus.rows), "children": len(corpus.children)}), flush=True)
    manifest = await corpus.build_vectors()
    with target.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False)
    print(json.dumps({"built": True, "index": str(target), "children": len(corpus.children)}), flush=True)


def make_app():
    from campus247.application.retrieval.context import RetrievalContextFactory
    from campus247.application.retrieval.semantic_support import SemanticClaimVerifier
    from campus247.bootstrap.app import create_app
    from campus247.bootstrap.settings import Settings
    from campus247.infrastructure.repositories.sqlite_conversations import (
        SQLiteConversationRepository,
    )
    STATE.mkdir(parents=True, exist_ok=True)
    corpus = store()
    corpus.load_vectors(json.loads(index_path(corpus).read_text(encoding="utf-8")))
    # Generation uses the existing append-only paid ledger and USD 3 cap,
    # including all historical and uncertain charges. No new cap or provider.
    gateway = Gateway()
    settings = Settings(_env_file=None, ENVIRONMENT="development", DEMO_MODE=True,
                        OPENAI_API_KEY=None, GEMINI_API_KEY=None, DEEPSEEK_API_KEY=None)
    factory = RetrievalContextFactory(scope_resolver=ScopeResolver(), configured_tenant_id=TENANT,
                                     configured_campus_id=CAMPUS)
    os.environ["CAMPUS247_IDEMPOTENCY_DB"] = str(checked(STATE / "idempotency.sqlite3"))
    app = create_app(runtime_settings=settings, synthetic_tenant_id=TENANT, allow_labeled_simulation=False,
        retrieval_context_factory=factory, public_knowledge_store=corpus, citation_source_reader=corpus,
        conversation_repository=SQLiteConversationRepository(checked(STATE / "conversations.sqlite3")),
        llm_gateway=gateway, claim_verifier=SemanticClaimVerifier(gateway))
    app.state.public_corpus_chunks = len(corpus.rows)
    app.state.rag_mode = "advanced_hybrid_conversational"
    from fastapi import HTTPException, Request
    from starlette.responses import Response
    globals()["Request"] = Request

    @app.get("/{page_path:path}", include_in_schema=False)
    async def frontend_page(page_path: str, request: Request):
        import httpx
        path = "/" + page_path
        if ((path not in {"/", "/chat", "/login", "/privacy", "/rooms", "/schedule", "/tickets", "/staff", "/knowledge", "/admin"}
             and not path.startswith("/_next/static/") and not path.startswith("/images/"))
                or ".." in path or "\\" in path or len(request.url.query) > 1024):
            raise HTTPException(404)
        url = "http://127.0.0.1:3001" + path + ("?" + request.url.query if request.url.query else "")
        async with httpx.AsyncClient(timeout=5, trust_env=False, follow_redirects=False) as client, client.stream("GET", url) as response:
            body = bytearray()
            async for chunk in response.aiter_bytes():
                if len(body) + len(chunk) > 4_194_304:
                    raise HTTPException(502)
                body.extend(chunk)
            return Response(bytes(body), status_code=response.status_code,
                headers={"Content-Type": response.headers.get("content-type", "application/octet-stream")})
    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-index", action="store_true")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.build_index:
        asyncio.run(build())
    else:
        import uvicorn
        uvicorn.run(make_app(), host="127.0.0.1", port=args.port, access_log=False, log_level="warning")
