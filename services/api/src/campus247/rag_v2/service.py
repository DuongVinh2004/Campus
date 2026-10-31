"""Port-only orchestration with one repair, one semantic call and a total deadline."""
from __future__ import annotations

import asyncio
import json
import logging
import math
import re
from dataclasses import replace
from time import monotonic

from campus247.ports.llm import LlmResponseStatus
from campus247.rag_v2.generation.generate import clarification_question, generate_draft
from campus247.rag_v2.ingest.units import context_text, source_text
from campus247.rag_v2.observability.trace import TurnTrace, emit
from campus247.rag_v2.outcome.compose import build_outcome
from campus247.rag_v2.retrieval.hybrid import retrieve, scope_allows
from campus247.rag_v2.types import Fact, Outcome, Statement
from campus247.rag_v2.understanding.analyze import analyze, contains, program_key
from campus247.rag_v2.understanding.normalize import fold, normalize_query
from campus247.rag_v2.verification.deterministic import REASON_CODES, check_statement
from campus247.rag_v2.verification.semantic import verify_semantic

REPAIRABLE = REASON_CODES - {"SEMANTIC_UNSUPPORTED"}


class _GenerationGateway:
    def __init__(self, gateway, reasons=()):
        self.gateway, self.reasons = gateway, reasons

    async def generate(self, request):
        request = replace(request, max_output_tokens=min(request.max_output_tokens, 1000))
        if self.reasons:
            request = replace(request, system_instructions=request.system_instructions +
                "\nLần sửa duy nhất. Mã lỗi xác định: " + ", ".join(self.reasons) +
                ". Đối chiếu lại nguồn, giữ đủ điều kiện và chỉ dẫn đúng nhãn nguồn.")
        response = await self.gateway.generate(request)
        if response.status != LlmResponseStatus.COMPLETED:
            raise RuntimeError("GENERATION_UNAVAILABLE")
        return response


def _fact_kind(u):
    if u.question_type in {"deadline", "contact"}:
        return u.question_type
    if contains(fold(u.search_query), "tien quyet"):
        return "prerequisite"
    if "hoc_phi" in u.topics and u.question_type in {"number", "lookup"}:
        return "fee"
    return None


_CONDITION = re.compile(
    r"\b(?:chi|ap dung|danh cho|doi voi|tru|ngoai tru|rieng|neu|khi|truong hop|khong|chua|"
    r"toi thieu|toi da|dieu kien|tu khoa|nam hoc|k\d{2,3}|20\d{2})\b", re.IGNORECASE)


def _self_contained(fact, unit, parent=None):
    """Inspect the complete available structure, never a window after the quoted row.

    Sliced/table units need a readable parent. Context and headings are evidence
    of scope too, including column headings; uncertainty leaves the fast path.
    """
    quote = fold(fact.quote)
    if not quote or (parent is None and (unit.kind in {"table_row", "curriculum_row"} or unit.parent_unit_id)):
        return False
    for structure in (unit, parent) if parent is not None else (unit,):
        whole = fold(source_text(structure))
        if quote not in whole:
            return False
        outside = "\n".join((structure.doc_title, structure.path, context_text(structure),
                              whole.replace(quote, " ", 1)))
        if _CONDITION.search(fold(outside)) is not None:
            return False
    return True


def _matches(fact, u, unit, parent=None):
    if not _self_contained(fact, unit, parent):
        return False
    if not scope_allows(u, unit) or not scope_allows(u, replace(unit, scope=fact.scope)):
        return False
    query = fold(u.search_query)
    subject = fold(normalize_query(fact.subject)).strip()
    # A shared topic alone cannot identify a department, a deadline event or a
    # course. Require the complete normalized subject (or equivalent program).
    if not subject or not (contains(query, subject) or
            u.program and program_key(subject) == program_key(u.program)):
        return False
    scope = fact.scope
    for value, values in ((u.cohort, scope.cohorts), (u.academic_year, scope.academic_years)):
        if value and not values and not contains(fold(fact.quote), fold(value)):
            return False
        if values and not value:
            return False  # Do not choose an arbitrary dated/cohort-specific fact.
    if scope.programs and not u.program:
        return False
    if u.program and not scope.programs and not (
            contains(fold(fact.quote), fold(u.program)) or program_key(subject) == program_key(u.program)):
        return False
    # Semester and requested contact channel also change the answer.
    semesters = re.findall(r"\bhoc ky\s*[123]\b", query)
    if any(not contains(fold(normalize_query(fact.quote)), semester) for semester in semesters):
        return False
    if fact.kind == "contact":
        channel = fact.attributes.get("contact_type")
        if contains(query, "email") and channel != "email":
            return False
        if contains(query, "dien thoai") and channel != "phone":
            return False
    return fact.value in fact.quote and fact.quote in source_text(unit)


CONTEXT_CHUNKS = 6
CONTEXT_BYTES = 19_000


class RagV2Service:
    """Facts are injected separately because UnitIndex intentionally has no fact API.

    ``embed`` is the query-embedding dependency already bound into UnitIndex.vector;
    the service never embeds the same query a second time. All deadlines share one
    monotonic end time. The retained generation gateway permits at most 5 s/call.
    """

    def __init__(self, facts: tuple[Fact, ...] = ()):
        self.facts = tuple(facts)

    def _declined(self, u, draft) -> Outcome:
        """The model decided the sources cannot answer: ask back, or refuse with a typed reason."""
        if draft.decision == "clarify":
            question = clarification_question(draft.missing_slots)
            return build_outcome(replace(u, missing_slots=draft.missing_slots,
                clarify_prompt="Câu hỏi chưa đủ rõ để tra đúng nguồn. " + question))
        return build_outcome(u, refuse_reason=draft.decision)

    async def answer(self, question, history_turns, *, gateway, index, reranker,
                     embed, deadline_s=12.0, revalidate=None) -> Outcome:
        started = monotonic()
        trace = TurnTrace()
        u = analyze(question, history_turns)
        trace.latency_ms["understanding"] = (monotonic() - started) * 1000

        async def validate(units):
            if revalidate is not None:
                await revalidate(tuple(dict.fromkeys(chunk for unit in units.values() for chunk in unit.chunk_ids)))

        async def finish(outcome, units=None, *, original_quotes=True):
            if outcome.kind != "transient_error":
                await validate(units or {})
            # Context headers are useful for generation, but only the original
            # source body is quotable. Never expose the synthetic context marker.
            if units and original_quotes:
                outcome = replace(outcome, citations=tuple(replace(c,
                    quote=source_text(units[c.unit_id])) for c in outcome.citations))
            trace.outcome_kind = outcome.kind
            trace.latency_ms["total"] = (monotonic() - started) * 1000
            emit(trace)
            return replace(outcome, trace=trace.payload())

        if u.clarify_prompt or u.out_of_scope:
            return await finish(build_outcome(u))
        if not math.isfinite(deadline_s) or deadline_s <= 0:
            return await finish(build_outcome(u, infra_error=True))
        end = started + deadline_s

        def budget(cap, reserve=0):
            value = min(cap, end - monotonic() - reserve)
            if value <= 0:
                raise TimeoutError
            return value

        try:
            async with asyncio.timeout(budget(deadline_s)):
                phase = monotonic()
                kind = _fact_kind(u)
                chunk_unit = getattr(index, "chunk_unit", None)
                matched = [(fact, unit) for fact in self.facts if fact.kind == kind
                           and (unit := index.get(fact.unit_id)) is not None
                           and (all((parent := chunk_unit(chunk)) is not None and _matches(fact, u, unit, parent)
                                    for chunk in unit.chunk_ids) if chunk_unit else _matches(fact, u, unit))]
                # A compound question needs the normal generation/coverage path.
                compound = bool(re.search(r"[;,\n]|\b(?:va|dong thoi|ngoai ra)\b", fold(question)))
                if matched and not compound and len({f.unit_id for f, _ in matched}) <= 8:
                    units = {unit.unit_id: unit for _, unit in matched}
                    statements = tuple(dict.fromkeys(Statement(f.quote, (f.unit_id,)) for f, _ in matched))
                    verdicts = [check_statement(stmt, units) for stmt in statements]
                    trace.candidate_count = len(units)
                    trace.latency_ms["facts"] = (monotonic() - phase) * 1000
                    for i, verdict in enumerate(verdicts):
                        if not verdict.passed:
                            trace.statement_rejections[i] = verdict.reasons
                    result = build_outcome(u, verdicts, units, semantic_required=False)
                    # Fact citations use the exact fact quote, including its value.
                    quotes = {}
                    for uid, unit in units.items():
                        body = source_text(unit)
                        spans = [(body.index(f.quote), body.index(f.quote) + len(f.quote))
                                 for f, _ in matched if f.unit_id == uid]
                        quotes[uid] = body[min(a for a, _ in spans):max(b for _, b in spans)]
                    result = replace(result, citations=tuple(replace(c, quote=quotes[c.unit_id])
                                                             for c in result.citations))
                    # Keep the fact-specific citation quote while checking its actual source grant.
                    return await finish(result, units, original_quotes=False)
                trace.latency_ms["facts"] = (monotonic() - phase) * 1000
                phase = monotonic()
                # Measured on the dev set (445 answerable cases): fused RRF keeps the gold unit in the
                # top 12 for 92%, while the CPU reranker (~4 s, 320-char windows) lowered survival
                # to 83% at top 8 and 60% above a -1 logit floor. The generator reads 12 units, so
                # reranking is left out of the request path.
                retrieval = await retrieve(u, index, reranker, rerank_deadline_s=0, final_limit=12)
                trace.latency_ms["retrieval"] = (monotonic() - phase) * 1000
                trace.candidate_count = len(retrieval.candidates)
                trace.rerank_scores = [c.rerank_score for c in retrieval.candidates if c.rerank_score is not None]
                units = {c.unit_id: unit for c in retrieval.candidates if (unit := index.get(c.unit_id)) is not None}
                chunk_unit = getattr(index, "chunk_unit", None)
                if chunk_unit is not None and units:
                    # Read the whole parent rows of the best units (answers often sit in sibling
                    # rows or footnotes the fine unit lacks): 83% -> measured in REPORT-v2.
                    parents, used = {}, 0
                    for unit in units.values():
                        for chunk_id in unit.chunk_ids[:1]:
                            if len(parents) < CONTEXT_CHUNKS and chunk_id not in parents:
                                parent = chunk_unit(chunk_id)
                                # The provider gateway rejects a request above 28,000 bytes of JSON, so
                                # pack whole rows in rank order until the evidence budget is spent.
                                size = len(json.dumps(parent.text, ensure_ascii=False).encode()) if parent else 0
                                if parent is not None and used + size <= CONTEXT_BYTES:
                                    parents[chunk_id] = parent
                                    used += size
                    if parents:
                        units = {parent.unit_id: parent for parent in parents.values()}
                if not units:
                    return await finish(build_outcome(u, candidate_count=0))
                phase = monotonic()
                generation_end = monotonic() + budget(8, reserve=min(3, deadline_s / 4))
                reasons = ()
                slow = False
                verdicts = []
                for attempt in range(2):
                    verdicts = []  # An unavailable attempt cannot reuse an earlier rejection.
                    trace.statement_rejections.clear()
                    milliseconds = int(min(5, generation_end - monotonic()) * 1000)
                    if milliseconds < 1:
                        raise TimeoutError
                    await validate(units)
                    try:
                        draft = await generate_draft(_GenerationGateway(gateway, reasons),
                            u.search_query, u, list(units.values()), deadline_ms=milliseconds,
                            max_output_tokens=900)
                        statements = list(draft.statements)
                    except TimeoutError:
                        logging.getLogger("campus247.rag_v2").warning(
                            "rag_v2_generation_attempt attempt=%d status=timeout", attempt + 1)
                        # A slow provider answers the second request in time more often than not;
                        # one retry is made only while a full attempt still fits in the budget.
                        if attempt or slow or generation_end - monotonic() < 2.5:
                            raise
                        slow = True
                        logging.getLogger("campus247.rag_v2").warning("rag_v2_generation_retry")
                        continue
                    if draft.decision != "answer":
                        trace.latency_ms["generation"] = (monotonic() - phase) * 1000
                        return await finish(self._declined(u, draft), units)
                    verdicts = [check_statement(stmt, units) for stmt in statements]
                    for i, verdict in enumerate(verdicts):
                        if not verdict.passed:
                            trace.statement_rejections[i] = verdict.reasons
                    reasons = tuple(sorted({code for verdict in verdicts for code in verdict.reasons}))
                    logging.getLogger("campus247.rag_v2").info(
                        "rag_v2_generation_attempt attempt=%d status=%s", attempt + 1,
                        "rejected" if reasons else "checked")
                    if (attempt or not verdicts or any(v.passed for v in verdicts)
                            or not reasons or not set(reasons) <= REPAIRABLE):
                        break
                trace.latency_ms["generation"] = (monotonic() - phase) * 1000
                passed = [v.statement for v in verdicts if v.passed]
                if not passed:
                    return await finish(build_outcome(u, verdicts, units), units)
                phase = monotonic()
                semantic = None
                for attempt in range(2):
                    # One retry: a malformed or late verdict is usually transient and the deterministic
                    # checks above have already passed, so a second look is cheaper than an error.
                    await validate(units)
                    try:
                        semantic = await verify_semantic(_GenerationGateway(gateway), passed, units, u.search_query,
                            deadline_ms=max(1, int(budget(3.5, reserve=0.5 if attempt == 0 else 0) * 1000)))
                    except TimeoutError:
                        semantic = None
                    if semantic is not None:
                        break
                    logging.getLogger("campus247.rag_v2").warning("rag_v2_semantic_unavailable attempt=%d", attempt + 1)
                trace.latency_ms["semantic"] = (monotonic() - phase) * 1000
                if semantic is None:
                    return await finish(build_outcome(u, infra_error=True))
                iterator = iter(semantic)
                aligned = [next(iterator) if verdict.passed else False for verdict in verdicts]
                for i, (verdict, supported) in enumerate(zip(verdicts, aligned)):
                    if verdict.passed and not supported:
                        trace.statement_rejections[i] = ("SEMANTIC_UNSUPPORTED",)
                return await finish(build_outcome(u, verdicts, units, semantic_results=aligned), units)
        except Exception as exc:  # noqa: BLE001 -- port failures must become content-free typed outcomes
            logging.getLogger("campus247.rag_v2").warning("rag_v2_failure kind=%s where=%s detail=%s", type(exc).__name__,
                exc.__traceback__.tb_next.tb_frame.f_code.co_name if exc.__traceback__ and exc.__traceback__.tb_next else "?",
                str(getattr(getattr(exc, "response", None), "status_code", "")))
            return await finish(build_outcome(u, infra_error=True))
