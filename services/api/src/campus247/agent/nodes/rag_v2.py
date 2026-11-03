"""Map verified v2 outcomes to the existing guarded graph and SSE contract."""
from __future__ import annotations

import asyncio
import re
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from threading import Lock, Thread
from time import monotonic

from campus247.agent.guardrails.prompt_injection import PromptInjectionDetector
from campus247.agent.nodes.compose import OutputGuardNode
from campus247.agent.nodes.definitions import _validate_retrieval_context, history_block
from campus247.agent.prompts.composer import TrustDomain
from campus247.agent.state import DraftResponse, RetrievalState, Route, Terminal, ToolFlowState
from campus247.application.retrieval.evidence_gate import GroundedClaim
from campus247.rag_v2.adapters.runtime import AuthorizedIndex
from campus247.rag_v2.discipline import discipline_failure
from campus247.rag_v2.ingest.units import source_text
from campus247.rag_v2.outcome.compose import RETRY_HINT, TIMEOUT_HINT, TIMEOUT_MESSAGE, TRANSIENT_MESSAGE
from campus247.rag_v2.retrieval.hybrid import rerank_excerpt
from campus247.rag_v2.types import Outcome
from campus247.rag_v2.understanding.normalize import fold
from campus247.rag_v2.generation.rewrite import ResolvedQuestion, rewrite_question
from campus247.rag_v2.understanding.analyze import analyze


GUARD_BLOCKED_MESSAGE = ("Nội dung này liên quan đến quy định cần được xác nhận trực tiếp. "
    "Bạn vui lòng mở tài liệu chính thức được trích dẫn hoặc liên hệ Phòng Đào tạo.")


_HAYSTACKS: dict[tuple[str, int], str] = {}
# Units whose binding to an authoritative row was already proven. A row is trusted again only when its
# identifiers, title, path and evidence hash are unchanged and its text equals the proven text, so a
# changed or revoked row falls back to the full checks. Checking 9,000 units per turn blocked the loop for ~2 s.
_BOUND: dict[tuple[str, str], tuple[tuple, str]] = {}
# One entry per (unit, chunk) pair: the current index has ~48,000, so the bound leaves room for several
# index generations and still stops growth (a bound below the working set clears the cache every turn).
_CACHE_LIMIT = 250_000
_CACHE_LOCK = Lock()


def _cached(cache, key):
    with _CACHE_LOCK:
        return cache.get(key)


def _remember(cache, key, value):
    with _CACHE_LOCK:
        if len(cache) >= _CACHE_LIMIT:
            cache.clear()
        cache[key] = value


def _scope_is_grounded(unit, row):
    """Cohorts, programmes and years an index unit claims must occur in its authoritative source row.

    Folding a row costs far more than checking a claim, so the folded text is kept per row; the dash
    variants of year ranges ("2026–2027" / "2026-2027") are unified before the comparison.
    """
    claims = (*unit.scope.cohorts, *unit.scope.programs, *unit.scope.academic_years)
    if not claims:
        return True
    key = (str(row.get("chunk_id")), len(row.get("content_text") or ""))
    haystack = _cached(_HAYSTACKS, key)
    if haystack is None:
        raw = " ".join(str(part) for part in (row.get("title"), row.get("section_path"), row.get("content_text")))
        haystack = re.sub(r"\s*[\u2013\u2014-]\s*", "-", fold(raw))
        _remember(_HAYSTACKS, key, haystack)
    return all(re.sub(r"\s*[\u2013\u2014-]\s*", "-", fold(claim)) in haystack for claim in claims)


def _binding_failure(unit, rows):
    """Name of the first check an index unit fails against its authoritative rows, else None.

    The checks are those of the authorization gate: both identifiers, the original slice, the
    title, the scope the unit claims and the evidence hash of the row.
    """
    body = None
    for chunk in unit.chunk_ids:
        row = rows.get(chunk)
        if row is None:
            return "row"
        fingerprint = (row.get("evidence_sha256"), row.get("source_id"), row.get("document_version_id"),
                       row.get("title"), row.get("section_path"))
        memo = _cached(_BOUND, (unit.unit_id, chunk))
        text = row.get("content_text") or ""
        if memo is not None and memo[0] == fingerprint and (memo[1] is text or memo[1] == text):
            continue
        if row["source_id"] != unit.document_id or row["document_version_id"] != unit.version_id:
            return "ids"
        if body is None:
            body = source_text(unit)
        if not body or body not in row["content_text"]:
            return "body"
        if unit.doc_title != row.get("title"):
            return "title"
        if not _scope_is_grounded(unit, row):
            return "scope"
        if sha256(row["content_text"].encode()).hexdigest() != row["evidence_sha256"]:
            return "hash"
        _remember(_BOUND, (unit.unit_id, chunk), (fingerprint, row["content_text"]))
    return None


class RagV2Node:
    def __init__(self, *, service, index, reranker, embed, gateway, authorize_sources, revalidate=None):
        self.service, self.index, self.reranker = service, index, reranker
        self.embed, self.gateway = embed, gateway
        self.authorize_sources, self.revalidate = authorize_sources, revalidate
        self._injection: dict[str | tuple, bool] = {}
        self._injection_lock = Lock()

    def _scan(self, key, text, detector):
        with self._injection_lock:
            flagged = self._injection.get(key)
        if flagged is None:
            flagged = detector.scan(text, TrustDomain.RETRIEVED_EVIDENCE).is_injection
            with self._injection_lock:
                self._injection[key] = flagged
        return flagged

    def start_injection_warmup(self):
        def scan():
            try:
                detector = PromptInjectionDetector()
                for uid in self.index.all_ids():
                    unit = self.index.get(uid)
                    if unit is not None and unit.chunk_ids:
                        self._scan(uid, unit.text, detector)
            except Exception as exc:  # noqa: BLE001 -- optional warmup must not interrupt serving
                import logging
                logging.getLogger("campus247.rag_v2").warning(
                    "rag_v2_injection_warmup_failed kind=%s", type(exc).__name__)
        self._injection_thread = Thread(target=scan, name="rag-v2-injection", daemon=True)
        self._injection_thread.start()

    def _prepare_index(self, rows):
        detector = PromptInjectionDetector()
        units, drops = {}, {}
        for uid in self.index.all_ids():
            unit = self.index.get(uid)
            if unit is None or not unit.chunk_ids:
                continue
            # The authoritative row must match both identifiers and the
            # original slice; an index file never confers a source grant.
            failed = _binding_failure(unit, rows)
            if failed:
                drops[(unit.kind, failed)] = drops.get((unit.kind, failed), 0) + 1
                continue
            if not self._scan(uid, unit.text, detector):
                units[uid] = unit
        # Parent-row injection checks also scan the corpus, so keep them off the loop.
        return AuthorizedIndex(self.index, units, rows=rows,
            injection_check=self._chunk_injection(detector)), len(units), drops

    async def __call__(self, state, *, context=None):
        started = monotonic()
        try:
            _validate_retrieval_context(state, context)
            if context is None:
                raise ValueError("trusted retrieval context required")
            def guard():
                history_block(state)  # Preserves actor/session/consent context guard.
                if state.request.coordination_guard is not None:
                    actor = state.request.coordination_guard()
                    scope = context.authorized_scope
                    if (actor.subject_id != scope.actor_id or actor.tenant_id != scope.tenant_id
                            or {r.value for r in actor.roles} != set(scope.roles)
                            or not actor.is_active or actor.expires_at <= datetime.now(UTC)):
                        raise ValueError("current identity no longer matches trusted scope")

            # A revocation between generation and verification stops the next
            # provider dispatch, rather than merely blocking the final answer.
            owner = self
            resolved = ResolvedQuestion(state.request.query, state.request.query)

            async def revalidate(chunks):
                guard()
                live = None
                if owner.revalidate is not None:
                    live = await owner.revalidate(resolved.resolved, context, chunks)
                guard()
                return live

            class GuardedGateway:
                async def generate(self, request):
                    guard()
                    if request.request_id == "rag_v2_rewrite":
                        await revalidate(())
                    return await owner.gateway.generate(request)
            guarded_gateway = GuardedGateway()
            guard()
            history = tuple(t.content for t in state.request.history.turns if t.role == "user") if state.request.history else ()
            async with asyncio.timeout(12):
                if history:
                    # A follow-up ("nó bao nhiêu?", "à không, K67") is understood from the earlier user turns;
                    # on failure the original question and history go through the unchanged path.
                    rewritten = await rewrite_question(guarded_gateway, resolved.original, history, deadline_ms=2500)
                    if rewritten:
                        resolved = ResolvedQuestion(resolved.original, rewritten)
                        history = ()
                understanding = analyze(resolved.resolved, history)
                if understanding.clarify_prompt or understanding.out_of_scope:
                    outcome = await self.service.answer(resolved.resolved, history, gateway=guarded_gateway,
                        index=self.index, reranker=self.reranker, embed=self.embed, revalidate=revalidate)
                    return self.map_outcome(state, outcome, {})
                rows = await self.authorize_sources(resolved.resolved, context)
                t_auth = int((monotonic() - started) * 1000)
                index, unit_count, drops = await asyncio.to_thread(self._prepare_index, rows)
                t_units = int((monotonic() - started) * 1000)
                if drops:
                    import logging
                    logging.getLogger("campus247.rag_v2").warning("rag_v2_unit_drops %s", sorted(
                        ((f"{kind}:{reason}", count) for (kind, reason), count in drops.items()), key=lambda item: -item[1])[:8])
                import logging
                logging.getLogger("campus247.rag_v2").warning("rag_v2_node_stage auth_ms=%d units_ms=%d units=%d", t_auth, t_units, unit_count)
                outcome = await self.service.answer(resolved.resolved, history, gateway=guarded_gateway,
                    index=index, reranker=self.reranker, embed=self.embed,
                    deadline_s=12 - (monotonic() - started), revalidate=revalidate)
                guard()  # Recheck after all model awaits.
                cited_chunks = tuple(dict.fromkeys(chunk for c in outcome.citations for chunk in c.chunk_ids))
                live = await revalidate(cited_chunks)
                # The live read of the cited chunks carries the attestations the bulk read leaves out.
                for chunk, fresh in (live or {}).items():
                    if chunk in rows and isinstance(fresh, dict):
                        rows[chunk] = {**rows[chunk], **{key: fresh[key] for key in (
                            "_verified_publication", "_verified_curriculum", "applicability_note") if key in fresh}}
                mapped = self.map_outcome(state, outcome, rows)
                if mapped.terminal == Terminal.ANSWERED:
                    discipline = re.search(r"kỷ luật", mapped.draft.text, re.IGNORECASE)
                    refusal_code = (discipline_failure(outcome, rows) if discipline and mapped.route == Route.GROUNDED_FAQ
                                    else "route" if discipline else None)
                    verified_rule = bool(discipline) and refusal_code is None
                    if discipline and refusal_code:
                        import logging
                        logging.getLogger("campus247.rag_v2").warning("rag_v2_discipline_rule_rejected reason=%s", refusal_code)
                    guarded = OutputGuardNode().execute(mapped)
                    discipline_rejection = (
                        "Policy violation: phán quyết cá nhân hoặc quy định chưa được kiểm chứng",)
                    if (verified_rule and guarded.terminal == Terminal.SAFE_FAILURE
                            and guarded.errors[len(mapped.errors):] == discipline_rejection):
                        # Probe only the other shared rules, without duplicating their patterns.
                        # This text is never delivered; preserve the original verified answer.
                        guard_state = replace(mapped, draft=replace(mapped.draft,
                            text=re.sub(r"kỷ luật", "[verified rule]", mapped.draft.text, flags=re.IGNORECASE)))
                        guarded = OutputGuardNode().execute(guard_state)
                        if guarded.terminal != Terminal.SAFE_FAILURE:
                            mapped = replace(mapped, errors=mapped.errors + ("RAG_V2_DISCIPLINE_RULE_VERIFIED",))
                    if (discipline and not verified_rule) or guarded.terminal == Terminal.SAFE_FAILURE:
                        mapped = self.map_outcome(state, Outcome("refuse", GUARD_BLOCKED_MESSAGE, reason="unsafe"), {})
                await revalidate(cited_chunks)
                return mapped
        except Exception as exc:  # noqa: BLE001 -- never propagate denied source content or exception text
            import logging
            logging.getLogger("campus247.rag_v2").warning("rag_v2_node_failure kind=%s elapsed_ms=%d",
                type(exc).__name__, int((monotonic() - started) * 1000))
            if isinstance(exc, TimeoutError):
                return self.map_outcome(state, Outcome("transient_error", TIMEOUT_MESSAGE,
                    retry_hint=TIMEOUT_HINT), {})
            return self.map_outcome(state, Outcome("transient_error", TRANSIENT_MESSAGE,
                retry_hint=RETRY_HINT), {})

    def _chunk_injection(self, detector):
        def flagged(chunk_id, text):
            # Rows are immutable per checksum, so the verdict is cached per chunk id and length.
            key = ("chunk", chunk_id, len(text))
            return self._scan(key, text, detector)
        return flagged

    @staticmethod
    def map_outcome(state, outcome, rows):
        errors = list(state.errors)
        errors.append("RAG_V2_" + outcome.kind.upper())
        if outcome.reason:
            errors.append("RAG_V2_REFUSE_" + outcome.reason.upper())
        if outcome.kind == "clarify":
            errors.append("AI_CLARIFICATION_REQUIRED")
        if outcome.kind == "partial":
            errors.append("AI_PARTIAL_COVERAGE")
        candidates, local_ids = [], {}
        for citation in outcome.citations:
            # Each v2 citation binds one unit to an existing authorized chunk.
            row = rows[citation.chunk_ids[0]]
            quote = rerank_excerpt(citation.quote, " ".join(s.text for s in outcome.statements
                                   if citation.unit_id in s.unit_ids), limit=500)
            if not quote or quote not in row["content_text"]:
                raise ValueError("citation quote is not original evidence")
            candidates.append({**row, "unit_id": citation.unit_id, "quote": quote})
            local_ids[citation.unit_id] = f"CIT-{len(candidates):03d}"
        claims = tuple(GroundedClaim(f"v2-{i}", stmt.text,
            tuple(local_ids[ref] for ref in stmt.unit_ids), "policy")
            for i, stmt in enumerate(outcome.statements, 1))
        if outcome.kind in {"answer", "partial"}:
            # Partial note is appended once by the existing stream conversion.
            text = "\n".join(c.text + " " + " ".join(f"[{ref}]" for ref in c.citation_ids) for c in claims)
            terminal = Terminal.ANSWERED
        else:
            text = outcome.text + (" " + outcome.retry_hint if outcome.retry_hint else "")
            terminal = Terminal.ABSTAINED
        return replace(state, terminal=terminal, errors=tuple(errors),
            retrieval=RetrievalState(tuple(row["chunk_id"] for row in candidates), "rag_v2"),
            tool_flow=replace(state.tool_flow or ToolFlowState(), candidates=candidates),
            draft=DraftResponse(text, claim_count=len(claims), is_grounded=bool(claims),
                gate_decision="grounded" if claims else "abstain", grounded_claims=claims,
                partial_note=outcome.partial_note), step_count=state.step_count + 1)
