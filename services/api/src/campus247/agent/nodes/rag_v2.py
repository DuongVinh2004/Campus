"""Map verified v2 outcomes to the existing guarded graph and SSE contract."""
from __future__ import annotations

import asyncio
import re
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
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
from campus247.rag_v2.outcome.compose import RETRY_HINT, TRANSIENT_MESSAGE
from campus247.rag_v2.retrieval.hybrid import rerank_excerpt
from campus247.rag_v2.types import Outcome
from campus247.rag_v2.understanding.normalize import fold
from campus247.rag_v2.generation.rewrite import rewrite_question
from campus247.rag_v2.understanding.analyze import analyze


GUARD_BLOCKED_MESSAGE = ("Nội dung này liên quan đến quy định cần được xác nhận trực tiếp. "
    "Bạn vui lòng mở tài liệu chính thức được trích dẫn hoặc liên hệ Phòng Đào tạo.")


_HAYSTACKS: dict[tuple[str, int], str] = {}


def _scope_is_grounded(unit, row):
    """Cohorts, programmes and years an index unit claims must occur in its authoritative source row.

    Folding a row costs far more than checking a claim, so the folded text is kept per row; the dash
    variants of year ranges ("2026–2027" / "2026-2027") are unified before the comparison.
    """
    claims = (*unit.scope.cohorts, *unit.scope.programs, *unit.scope.academic_years)
    if not claims:
        return True
    key = (str(row.get("chunk_id")), len(row.get("content_text") or ""))
    haystack = _HAYSTACKS.get(key)
    if haystack is None:
        raw = " ".join(str(part) for part in (row.get("title"), row.get("section_path"), row.get("content_text")))
        haystack = _HAYSTACKS[key] = re.sub(r"\s*[\u2013\u2014-]\s*", "-", fold(raw))
    return all(re.sub(r"\s*[\u2013\u2014-]\s*", "-", fold(claim)) in haystack for claim in claims)


def _binding_failure(unit, body, rows):
    """Name of the first check an index unit fails against its authoritative rows, else None.

    The checks are those of the authorization gate: both identifiers, the original slice, the
    title, the scope the unit claims and the evidence hash of the row.
    """
    for chunk in unit.chunk_ids:
        row = rows.get(chunk)
        if row is None:
            return "row"
        if row["source_id"] != unit.document_id or row["document_version_id"] != unit.version_id:
            return "ids"
        if not body or body not in row["content_text"]:
            return "body"
        if unit.doc_title != row.get("title"):
            return "title"
        if not _scope_is_grounded(unit, row):
            return "scope"
        if sha256(row["content_text"].encode()).hexdigest() != row["evidence_sha256"]:
            return "hash"
    return None


class RagV2Node:
    def __init__(self, *, service, index, reranker, embed, gateway, authorize_sources, revalidate=None):
        self.service, self.index, self.reranker = service, index, reranker
        self.embed, self.gateway = embed, gateway
        self.authorize_sources, self.revalidate = authorize_sources, revalidate
        self._injection: dict[str, bool] = {}

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
            class GuardedGateway:
                async def generate(self, request):
                    guard()
                    return await owner.gateway.generate(request)
            guarded_gateway = GuardedGateway()
            guard()
            history = tuple(t.content for t in state.request.history.turns if t.role == "user") if state.request.history else ()
            async with asyncio.timeout(12):
                query = state.request.query
                if history:
                    # A follow-up ("nó bao nhiêu?", "à không, K67") is understood from the earlier user turns;
                    # on failure the original question and history go through the unchanged path.
                    rewritten = await rewrite_question(guarded_gateway, query, history, deadline_ms=2500)
                    if rewritten:
                        query, history = rewritten, ()
                understanding = analyze(query, history)
                if understanding.clarify_prompt or understanding.out_of_scope:
                    outcome = await self.service.answer(query, history, gateway=guarded_gateway,
                        index=self.index, reranker=self.reranker, embed=self.embed)
                    return self.map_outcome(state, outcome, {})
                rows = await self.authorize_sources(query, context)
                t_auth = int((monotonic() - started) * 1000)
                detector = PromptInjectionDetector()
                units, drops = {}, {}
                for uid in self.index.all_ids():
                    unit = self.index.get(uid)
                    if unit is None or not unit.chunk_ids:
                        continue
                    body = source_text(unit)
                    # The authoritative row must match both identifiers and the
                    # original slice; an index file never confers a source grant.
                    failed = _binding_failure(unit, body, rows)
                    if failed:
                        drops[(unit.kind, failed)] = drops.get((unit.kind, failed), 0) + 1
                        continue
                    # The index text is immutable for this process, so scan each unit once.
                    flagged = self._injection.get(uid)
                    if flagged is None:
                        flagged = self._injection[uid] = detector.scan(unit.text, TrustDomain.RETRIEVED_EVIDENCE).is_injection
                    if flagged:
                        continue
                    units[uid] = unit
                t_units = int((monotonic() - started) * 1000)
                if drops:
                    import logging
                    logging.getLogger("campus247.rag_v2").warning("rag_v2_unit_drops %s", sorted(
                        ((f"{kind}:{reason}", count) for (kind, reason), count in drops.items()), key=lambda item: -item[1])[:8])
                import logging
                logging.getLogger("campus247.rag_v2").warning("rag_v2_node_stage auth_ms=%d units_ms=%d units=%d", t_auth, t_units, len(units))
                outcome = await self.service.answer(query, history, gateway=guarded_gateway,
                    index=AuthorizedIndex(self.index, units, rows=rows, injection_check=self._chunk_injection(detector)), reranker=self.reranker, embed=self.embed,
                    deadline_s=12 - (monotonic() - started))
                guard()  # Recheck after all model awaits.
                cited_chunks = tuple(dict.fromkeys(chunk for c in outcome.citations for chunk in c.chunk_ids))
                if self.revalidate is not None:
                    await self.revalidate(state.request.query, context, cited_chunks)
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
                return mapped
        except Exception as exc:  # noqa: BLE001 -- never propagate denied source content or exception text
            import logging
            logging.getLogger("campus247.rag_v2").warning("rag_v2_node_failure kind=%s elapsed_ms=%d",
                type(exc).__name__, int((monotonic() - started) * 1000))
            return self.map_outcome(state, Outcome("transient_error", TRANSIENT_MESSAGE,
                retry_hint=RETRY_HINT), {})

    def _chunk_injection(self, detector):
        def flagged(chunk_id, text):
            # Rows are immutable per checksum, so the verdict is cached per chunk id and length.
            key = ("chunk", chunk_id, len(text))
            verdict = self._injection.get(key)
            if verdict is None:
                verdict = self._injection[key] = detector.scan(text, TrustDomain.RETRIEVED_EVIDENCE).is_injection
            return verdict
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
