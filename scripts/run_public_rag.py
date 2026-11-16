"""Run the actual chat application against public HUCE knowledge and a live LLM.

All state stays in an additive local namespace. Paid usage resumes the existing
ledger, including uncertain attempts. No automatic runtime expiry, data cleanup,
provider fallback to fakes, production writes or source replacement.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import ssl
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "services/api/src"), str(ROOT / "packages/synthetic/src"),
               str(ROOT / "infra/local/rag-fixture")]
STATE = ROOT / "infra/local/public-rag-20261013"
CORPUS = ROOT / "data/huce-public-20261013"
TENANT, CAMPUS = "huce-local-public", "HUCE"
# Simultaneous provider calls. One turn issues up to two calls at once (route + safety classifier), so a limit of 4
# queued every turn behind three others and the wait ate the 5 s call deadline. This is a concurrency control only:
# the per-call deadline, token caps and the spend/call caps of the budget are unchanged.
PROVIDER_CONCURRENCY_LIMIT = 16


def checked(path):
    if not path.resolve().is_relative_to(ROOT) or path.resolve() == ROOT:
        raise ValueError("outside workspace")
    for parent in (path, *path.parents):
        if parent.exists() and (parent.is_symlink() or parent.is_junction()):
            raise ValueError("reparse target")
        if parent == ROOT:
            break
    return path


def retain(name, value):
    path = checked(STATE / (name + ".json"))
    with path.open("x", encoding="utf-8") as stream:
        # One-shot compact encoding: json.dump() to a file (and any indent) runs the pure-Python encoder, which made
        # two ledger records per provider call a visible share of the API's CPU. The content of every record is
        # unchanged; readers parse it as before.
        stream.write(json.dumps({"created_at": datetime.now(timezone.utc).isoformat(), **value}, ensure_ascii=False,
                                separators=(",", ":")))


_TLS = None


def _tls_context():
    """One default TLS context for every provider call (same verification: system trust store, hostname check).

    Building it per call re-read the Windows certificate store each time (~10 ms of CPU per call)."""
    global _TLS
    if _TLS is None:
        _TLS = ssl.create_default_context()
    return _TLS


def require_provider_usage(raw):
    usage = raw.get("usage")
    if (not isinstance(usage, dict) or any(type(usage.get(key)) is not int or usage[key] < 0
            for key in ("prompt_tokens", "completion_tokens")) or usage["prompt_tokens"] == 0):
        raise ValueError("provider usage unavailable")
    choices = raw.get("choices", [])
    if choices and choices[0].get("message", {}).get("content") and usage["completion_tokens"] == 0:
        raise ValueError("provider usage unavailable")


class Gateway:
    json_mode = False
    def __init__(self):
        from scripts.public_rag_ledger import PaidLedgerWriterLease
        # Acquire ownership before credentials or ledger resume. Other public
        # and advanced processes must fail closed, before any paid HTTP call.
        lease = PaidLedgerWriterLease(checked(STATE / "paid-ledger-writer.lock"))
        try:
            self._initialize()
        except BaseException:
            lease.close()
            raise
        self._ledger_lease = lease

    def close(self):
        self._ledger_lease.close()

    def _initialize(self):
        from acceptance_live_20261006_18 import settings
        from m2_budget_20261012_74 import ConservativeBudget
        from campus247.infrastructure.llm.openai_adapter import OpenAICompatibleAdapter
        endpoint, key, _ = settings()
        self.adapter = OpenAICompatibleAdapter("deepseek", endpoint, key, "deepseek-flash",
            default_timeout_sec=5, disable_thinking=True, json_mode=self.json_mode)
        self.lock = asyncio.Lock()
        self.provider_slots = asyncio.Semaphore(PROVIDER_CONCURRENCY_LIMIT)
        old = ROOT / "infra/local/rag-fixture/manual-20261013-76/b001"
        # Prefer our append-only records on a restart; never reset reservations.
        local = sorted(STATE.glob("provider-*.json"), key=lambda p: (int(re.search(r"provider-(\d+)-", p.name).group(1)), p.name))
        # Records only ever append and `calls` grows with the ordinal, so the
        # newest few hundred hold the restart snapshot. Reading all of them
        # (150k files, ~4 GB) made every start take 15-35 minutes. Verified
        # 2026-11-14 on the live ledger: newest 400 give the same record as all.
        local = local[-2000:]
        if local:
            # At a fixed call count, settlements only remove pending attempts.
            # Completion order need not match reservation ordinal or file name.
            last = max((json.loads(p.read_text(encoding="utf-8")) for p in local), key=lambda v: (
                v["snapshot"]["calls"], -len(v["snapshot"]["unsettled_attempts_retained"]), v["stage"] == "result"))
            snapshot = last["snapshot"]
        else:
            records = [json.loads(p.read_bytes()) for p in old.glob("provider-*.json")]
            snapshot = max(records, key=lambda v: (v["snapshot"]["calls"], "exit_code" in v))["snapshot"]
        inherited = json.loads((old / "predecessor.json").read_bytes())["pending_reservation_records"]
        pending = {}
        for ordinal in snapshot["unsettled_attempts_retained"]:
            if str(ordinal) in inherited:
                pending[str(ordinal)] = inherited[str(ordinal)]
            else:
                candidate = STATE / f"provider-{ordinal:05d}-reservation.json"
                pending[str(ordinal)] = json.loads(candidate.read_bytes()) if candidate.exists() else json.loads((old / f"provider-reservation-{ordinal:03}.json").read_bytes())
        self.budget = self._restore_budget(snapshot, pending)

    def _restore_budget(self, snapshot, pending):
        from m2_budget_20261012_74 import ConservativeBudget
        # Human authorization on 2026-10-13: USD 3 total, including all prior usage.
        from public_rag_budget import resume_authorized_budget
        migration_path = checked(STATE / "authorized-cap-3.json")
        if not migration_path.exists():
            ConservativeBudget.resume_full_records(snapshot, pending, cap_usd="1.5", call_cap=8500)
            retain("authorized-cap-3", {"authorized_cap_usd": "3", "call_cap": 8500,
                "human_authorization": "3 USD tổng cộng — thêm tối đa 1,50 USD",
                "before": snapshot, "pending_reservation_records": pending})
        migration = json.loads(migration_path.read_text(encoding="utf-8"))
        return resume_authorized_budget(snapshot, pending, migration)

    async def generate(self, request):
        import httpx
        from campus247.infrastructure.llm.egress_policy import EgressPolicy
        async with self.lock:
            payload = self.adapter._build_payload(request)
            payload = EgressPolicy().validate_and_minimize({"purpose": "FAQ_ANSWERING", **payload})
            input_cap = len(json.dumps(payload, ensure_ascii=False).encode()) + 512
            if input_cap > 28_000 or request.max_output_tokens > 1000 or request.deadline_ms > 5000:
                raise ValueError("provider operation bound")
            reservation = self.budget.reserve(input_cap, request.max_output_tokens)
            retain(f"provider-{reservation.ordinal:05d}-reservation", {"stage": "reservation",
                "route": request.route_id, "input_cap": input_cap, "output_cap": request.max_output_tokens,
                "counted_before_HTTP": True, "snapshot": self.budget.snapshot(), "payload_logged": False})
        started = time.monotonic()
        try:
            # Wait for a free slot first: the 5 s deadline measures the provider call, not the queue in front of it.
            async with self.provider_slots, asyncio.timeout(request.deadline_ms / 1000):
                async with httpx.AsyncClient(
                    timeout=request.deadline_ms / 1000, trust_env=False, follow_redirects=False,
                    verify=_tls_context()) as client:
                    async with client.stream("POST", self.adapter._base_url + "/chat/completions",
                        headers={"Authorization": "Bearer " + self.adapter._api_key}, json=payload) as response:
                        response.raise_for_status()
                        body = bytearray()
                        async for part in response.aiter_bytes():
                            if len(body) + len(part) > 1_048_576:
                                raise ValueError("provider response bound")
                            body.extend(part)
            raw = json.loads(body)
            require_provider_usage(raw)
            result = self.adapter._normalize_response(raw, int((time.monotonic() - started) * 1000))
            if result.usage.reasoning_tokens or result.model_id != "deepseek-flash":
                raise ValueError("provider model mismatch")
            try:
                parsed = json.loads(result.output_text or "")
                values = parsed.get("claims") if isinstance(parsed, dict) else None
                format_flags = {"is_json": True, "exact_claims_root": isinstance(parsed, dict) and set(parsed) == {"claims"},
                    "claim_count": len(values) if isinstance(values, list) else None,
                    "claim_fields_valid": all(isinstance(v, dict) and set(v) == {"text", "citation_ids", "claim_type"}
                                              for v in values) if isinstance(values, list) else None,
                    "body_has_url": any(isinstance(v, dict) and any(u in str(v.get("text", "")) for u in ("http://", "https://"))
                                        for v in values) if isinstance(values, list) else None,
                    "body_has_citation_code": any(isinstance(v, dict) and "CIT-" in str(v.get("text", ""))
                                                 for v in values) if isinstance(values, list) else None,
                    "claim_kinds_valid": all(isinstance(v, dict) and v.get("claim_type") in {"policy", "procedure", "deadline", "fee", "contact", "personal_data"}
                                             for v in values) if isinstance(values, list) else None}
            except ValueError:
                format_flags = {"is_json": False, "starts_fence": (result.output_text or "").lstrip().startswith("```")}
            # Locked sections never await: settlement and its result stay atomic,
            # including cancellation while queued for a provider slot.
            async with self.lock:
                self.budget.settle_verified(reservation, result.usage.input_tokens, result.usage.output_tokens)
                retain(f"provider-{reservation.ordinal:05d}-result", {"stage": "result", "exit_code": 0,
                    "snapshot": self.budget.snapshot(), "latency_ms": result.latency_ms,
                    "input_tokens": result.usage.input_tokens, "output_tokens": result.usage.output_tokens,
                    # Lever L4 evidence: how much of the prompt the provider served from its prefix cache.
                    "cached_input_tokens": max(int(result.usage.cached_input_tokens or 0),
                                               int(raw["usage"].get("prompt_cache_hit_tokens") or 0)),
                    "route": request.route_id,
                    "finish_reason": str(result.finish_reason), "format_flags": format_flags,
                    "output_sha256": hashlib.sha256((result.output_text or "").encode()).hexdigest(),
                    "raw_output_logged": False})
            return result
        except BaseException as error:
            async with self.lock:
                retain(f"provider-{reservation.ordinal:05d}-result", {"stage": "result", "exit_code": 1,
                    "error_type": type(error).__name__, "snapshot": self.budget.snapshot(), "retry": False})
            raise

    def capabilities(self, provider_id, model_id):
        return self.adapter.capabilities(provider_id, model_id)


class ScopeResolver:
    def resolve(self, identity):
        from campus247.application.retrieval.context import ResolvedRetrievalScope
        return ResolvedRetrievalScope(TENANT, CAMPUS, frozenset({"STUDENT"}),
            frozenset({identity.faculty_code or "PUBLIC"}), frozenset({"PUBLIC"}))


def make_app():
    from campus247.bootstrap.app import create_app
    from campus247.bootstrap.settings import Settings
    from campus247.application.retrieval.context import RetrievalContextFactory
    from campus247.application.retrieval.semantic_support import SemanticClaimVerifier
    from campus247.infrastructure.repositories.sqlite_conversations import SQLiteConversationRepository
    from scripts.public_rag_retrieval import load_public_hybrid_store
    # Validate the existing source/model-bound index before opening state or the
    # paid gateway. Missing/drifted indexes never fall back to lexical retrieval.
    corpus = load_public_hybrid_store(CORPUS, tenant_id=TENANT, campus_id=CAMPUS,
        faq_directory=ROOT / "data/huce-faq-20261013")
    checked(STATE).mkdir(parents=True, exist_ok=True)
    os.environ["CAMPUS247_IDEMPOTENCY_DB"] = str(checked(STATE / "idempotency.sqlite3"))
    class GateDiagnostics(logging.Handler):
        def emit(self, record):
            value = getattr(record, "gate_diagnostic", None)
            if isinstance(value, dict):
                # Existing diagnostic consists of hashes, ratios and codes;
                # never persist the prompt, model draft or private reasoning.
                print(json.dumps({"gate_diagnostic": value}), flush=True)
    gate_logger = logging.getLogger("campus247.evidence_gate")
    gate_logger.setLevel(logging.INFO)
    gate_logger.addHandler(GateDiagnostics())
    factory = RetrievalContextFactory(scope_resolver=ScopeResolver(), configured_tenant_id=TENANT, configured_campus_id=CAMPUS)
    settings = Settings(_env_file=None, ENVIRONMENT="development", DEMO_MODE=True,
        OPENAI_API_KEY=None, GEMINI_API_KEY=None, DEEPSEEK_API_KEY=None)
    gateway = Gateway()
    app = create_app(runtime_settings=settings, synthetic_tenant_id=TENANT,
        allow_labeled_simulation=False, retrieval_context_factory=factory, public_knowledge_store=corpus,
        citation_source_reader=corpus, conversation_repository=SQLiteConversationRepository(checked(STATE / "conversations.sqlite3")),
        llm_gateway=gateway, claim_verifier=SemanticClaimVerifier(gateway))
    app.state.public_corpus_chunks = len(corpus.rows)
    app.state.public_faq_questions = len(corpus.faq_index.entries)
    app.state.rag_mode = "advanced_hybrid_conversational"
    from fastapi import Request, HTTPException
    from starlette.responses import Response
    globals()["Request"] = Request

    @app.get("/{page_path:path}", include_in_schema=False)
    async def frontend_page(page_path: str, request: Request):
        import httpx
        path = "/" + page_path
        if (path not in {"/", "/chat", "/login", "/privacy", "/rooms", "/schedule", "/tickets", "/staff", "/knowledge", "/admin"}
                and not path.startswith("/_next/static/") and not path.startswith("/images/")):
            raise HTTPException(404)
        if ".." in path or "\\" in path or len(request.url.query) > 1024:
            raise HTTPException(404)
        url = "http://127.0.0.1:3000" + path
        if request.url.query:
            url += "?" + request.url.query
        async with httpx.AsyncClient(timeout=5, trust_env=False, follow_redirects=False) as client:
            async with client.stream("GET", url) as response:
                data = bytearray()
                async for part in response.aiter_bytes():
                    if len(data) + len(part) > 4_194_304:
                        raise HTTPException(502)
                    data.extend(part)
                return Response(bytes(data), status_code=response.status_code,
                    headers={"Content-Type": response.headers.get("content-type", "application/octet-stream")})
    return app


if __name__ == "__main__":
    import uvicorn
    sys.stdout.reconfigure(encoding="utf-8")
    app = make_app()
    print(json.dumps({"public_runtime": {"pid": os.getpid(), "rag_mode": app.state.rag_mode,
        "source_chunks": app.state.public_corpus_chunks, "paid_ledger_exclusive": True,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}}), flush=True)
    uvicorn.run(app, host="127.0.0.1", port=8000, access_log=False, log_level="warning")
