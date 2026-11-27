"""Balanced RRF, applicability filtering, diverse reranking and bounded fallback."""
from __future__ import annotations

import asyncio
import math
import os
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass, replace
from weakref import WeakKeyDictionary

from campus247.rag_v2.observability.vector_stats import VECTOR_STATS
from campus247.rag_v2.ports import Reranker, UnitIndex
from campus247.rag_v2.scope_ranges import covers
from campus247.rag_v2.types import Candidate, Understanding, Unit
from campus247.rag_v2.understanding.analyze import _PROGRAMS, contains, program_key
from campus247.rag_v2.understanding.normalize import fold, normalize_query


RRF_K = 60
# Without a reranker, lexical hits at this rank or better stay inside the packed rows (0 disables).
LEXICAL_PIN = 4
PACK_WINDOW = 6


def label_only_page(unit: Unit) -> bool:
    """A page whose text only repeats its own heading: the label of a small table ("71CS / Học phần tiên quyết:" under
    "71CS — Học phần tiên quyết — 608825 → 608807"), whose rows are indexed on their own."""
    from campus247.rag_v2.ingest.units import source_text
    if unit.kind != "page":
        return False
    words = re.findall(r"\w+", source_text(unit).casefold())
    heading = set(re.findall(r"\w+", (unit.path or "").casefold()))
    return 0 < len(words) <= 12 and all(word in heading for word in words)


_ROW_DOCUMENTS: WeakKeyDictionary = WeakKeyDictionary()


def _row_documents(index: UnitIndex) -> frozenset[str]:
    """Documents that have reviewed curriculum rows indexed on their own, computed once per loaded index."""
    try:
        return _ROW_DOCUMENTS[index]
    except (KeyError, TypeError):
        pass
    documents = frozenset(unit.document_id for uid in index.all_ids()
                          if (unit := index.get(uid)) is not None and unit.kind == "curriculum_row")
    try:
        _ROW_DOCUMENTS[index] = documents
    except TypeError:
        pass
    return documents


def _label_pages_last(ranked: list[Candidate], index: UnitIndex) -> tuple[list[Candidate], frozenset[str]]:
    """Move behind the rest the label pages of a document after its first one.

    A curriculum prints one small table per semester and per prerequisite pair; each is a page whose text is only a label
    ("71CS / Học phần tiên quyết:", "71CS / Học kỳ 6") while its rows, indexed on their own with the same headings, carry the
    course names. The labels tie on every score: 12 of them took all the slots from the row "Học máy" (rank 13). Only a short
    page of a document with rows of its own moves; nothing is dropped, and the first label of a document keeps its place.
    Returns the order and the ids that were moved (they are not pinned back by their lexical rank either).
    """
    rows = _row_documents(index)
    kept, later, labelled = [], [], set()
    for candidate in ranked:
        unit = index.get(candidate.unit_id)
        if unit is not None and unit.document_id in rows and label_only_page(unit):
            if unit.document_id in labelled:
                later.append(candidate)
                continue
            labelled.add(unit.document_id)
        kept.append(candidate)
    return kept + later, frozenset(c.unit_id for c in later)


@dataclass(frozen=True)
class RetrievalResult:
    candidates: tuple[Candidate, ...]
    fallback_used: bool
    trace: Mapping[str, object]


def scope_allows(u: Understanding, unit: Unit) -> bool:
    scope = unit.scope
    if (u.cohort and scope.cohorts and fold(u.cohort) not in {fold(c) for c in scope.cohorts}
            and not covers(unit.text, u.cohort)):  # "K70 trở về trước" contains K69
        return False
    if u.academic_year and scope.academic_years and u.academic_year not in scope.academic_years:
        return False
    if u.program and scope.programs:
        wanted = {program_key(u.program)}
        offered = {program_key(p) for p in scope.programs}
        dimensions = ({"chinh quy", "lien thong", "vua lam vua hoc"}, {"dai tra", "chat luong cao", "tien tien"})
        query = fold(u.search_query)
        source = fold(normalize_query(" ; ".join(scope.programs)))
        tracks = set.union(*dimensions)
        wanted.update(track for track in tracks if contains(query, track))
        offered.update(track for track in tracks if contains(source, track))
        # The shared field can contain both a major and a fee track. Compare
        # each explicit dimension, retaining units that leave it unspecified.
        for dimension in (*dimensions, (wanted | offered) - tracks):
            expected, actual = wanted & dimension, offered & dimension
            if expected and actual and not expected.intersection(actual):
                return False
    return True


_STOP_WORDS = "em toi minh cho hoi la gi co duoc khong va cua ve bao nhieu nam hoc ky nao the"
_STOP = set(_STOP_WORDS.split())


def rerank_excerpt(text: str, query: str, limit: int = 320) -> str:
    """Exact best-match window, trimmed to whole tokens (including numbers/codes).

    CPU measurements in rerank-bench.json: 300 chars ~2.9 pairs/s versus
    600 chars ~1.4 pairs/s. Ten <=320-char pairs fit the 4.5 s fallback budget.
    """
    if len(text) <= limit:
        return text
    terms = {w for w in re.findall(r"\w+", fold(query)) if w not in _STOP}
    hits = [(m.start(), m.end(), fold(m[0])) for m in re.finditer(r"\w+", text)
            if fold(m[0]) in terms]
    starts = {max(0, min(len(text) - limit, start - limit // 4)) for start, _, _ in hits}
    def quality(start):
        matched = {term for a, b, term in hits if a >= start and b <= start + limit}
        return (sum(len(term) for term in matched), len(matched), -start)
    start = max(starts, key=quality) if starts else 0
    end = min(len(text), start + limit)
    # Whitespace boundaries cannot bisect 580.500, 924/QĐ-ĐHXDHN or K64-K65.
    while start < end and start and not text[start - 1].isspace():
        start += 1
    while end > start and end < len(text) and not text[end].isspace():
        end -= 1
    return text[start:end]


def _article(unit: Unit) -> str:
    match = re.search(r"\bdieu\s+\d+\w?", fold(unit.path))
    return match[0] if match else unit.path.split(">")[0].strip()


def _diverse(ranked: list[Candidate], index: UnitIndex, count: int) -> list[Candidate]:
    chosen, seen, docs, articles = [], set(), set(), set()
    # First give every document a chance, then every article within a document,
    # then fill spare capacity. Preserve RRF order for the fallback itself.
    for mode in ("document", "article", "fill"):
        for candidate in ranked:
            if candidate.unit_id in seen:
                continue
            unit = index.get(candidate.unit_id)
            doc = unit.document_id
            article = (doc, _article(unit))
            if (mode == "document" and doc in docs) or (mode == "article" and article in articles):
                continue
            chosen.append(candidate)
            seen.add(candidate.unit_id)
            docs.add(doc)
            articles.add(article)
            if len(chosen) == count:
                return chosen
    return chosen


_FOLDED_TITLES: dict[str, str] = {}


def _programme_titled(u: Understanding, index: UnitIndex, allowed: set[str], limit: int) -> list:
    """A fourth ranked list: the best lexical hits among documents whose title names the programme asked about.

    "Kinh tế xây dựng K70" shares most words with every civil-engineering plan, and the plan of another programme
    can outrank the right one. A document named after the programme is the strongest evidence of which plan is
    meant, so it gets its own list in the fusion. Nothing is dropped; questions that name no programme add nothing.
    """
    if not u.program:
        return []
    names = next((names for code, names in _PROGRAMS if code == u.program), ())
    if not names:
        return []
    titled = set()
    for uid in allowed:
        unit = index.get(uid)
        title = _FOLDED_TITLES.get(unit.doc_title)
        if title is None:
            title = _FOLDED_TITLES[unit.doc_title] = fold(unit.doc_title)
        if any(contains(title, name) for name in names):
            titled.add(uid)
    if not titled or len(titled) == len(allowed):
        return []
    return index.lexical(u.search_query, limit, allowed=titled)


# How long the vector branch may take before retrieval goes on with lexical results only. A real-provider load test with
# 100 users measured 20 % of retrievals losing the branch at 1.0 s (the embedding server shares the machine's CPU with the
# API); a longer wait costs a slower turn instead of worse retrieval, and the turn budget is 22 s.
VECTOR_TIMEOUT_S = float(os.environ.get("CAMPUS247_VECTOR_TIMEOUT_S", "2.5"))


async def retrieve(u: Understanding, index: UnitIndex, reranker: Reranker, *,
                   lexical_k: int = 40, vector_k: int = 40, preselect: int = 10,
                   rerank_deadline_s: float = 4.5, min_rerank_logit: float = -1.0,
                   final_limit: int = 8) -> RetrievalResult:
    if any(type(n) is not int or n < 1 for n in (lexical_k, vector_k, preselect)):
        raise ValueError("positive integer retrieval limits required")
    if not math.isfinite(rerank_deadline_s) or rerank_deadline_s < 0 or not math.isfinite(min_rerank_logit):
        raise ValueError("finite deadline and threshold required")
    if u.out_of_scope or u.clarify_prompt:
        return RetrievalResult((), False, {"status": "SKIPPED", "preselected": 0, "returned": 0})
    allowed = {uid for uid in index.all_ids() if (unit := index.get(uid)) is not None and scope_allows(u, unit)}
    if not allowed:
        return RetrievalResult((), False, {"status": "EMPTY", "eligible": 0, "preselected": 0, "returned": 0})
    lexical = index.lexical(u.search_query, lexical_k, allowed=allowed)
    vector_failed, vector_timeout, vector_started = False, False, time.perf_counter()
    try:
        async with asyncio.timeout(VECTOR_TIMEOUT_S):
            vector = await index.vector(u.search_query, vector_k, allowed=allowed)
    except Exception as error:  # noqa: BLE001 -- a vector adapter outage must preserve lexical retrieval
        vector, vector_failed, vector_timeout = [], True, isinstance(error, TimeoutError)
    VECTOR_STATS.record(failed=vector_failed, timeout=vector_timeout, seconds=time.perf_counter() - vector_started)
    ranks = {}
    anchored = index.anchored(u.search_query, lexical_k, allowed=allowed) if hasattr(index, "anchored") else []
    titled = _programme_titled(u, index, allowed, lexical_k)
    for branch, rows in enumerate((lexical, vector, anchored, titled)):
        seen = set()
        for rank, (uid, _) in enumerate(rows, 1):
            if uid not in allowed or uid in seen:
                continue
            seen.add(uid)
            ranks.setdefault(uid, [None, None, None, None])[branch] = rank
    k = RRF_K
    ranked = [Candidate(uid, pair[0], pair[1], sum(1 / (k + rank) for rank in pair if rank is not None))
              for uid, pair in ranks.items()]
    ranked.sort(key=lambda c: (-c.fused_score, c.unit_id))
    ranked, labels = _label_pages_last(ranked, index)
    # Diversity is a shortlist for the reranker, not a relevance filter. When
    # reranking is disabled, keep the fused top-k directly: otherwise sibling
    # clauses lose their slots to lower-ranked documents before context packing.
    chosen = ranked[:final_limit] if rerank_deadline_s == 0 else _diverse(ranked, index, max(10, preselect))
    trace = {"status": "EMPTY", "eligible": len(allowed), "lexical": len(lexical), "vector": len(vector),
             "vector_failed": vector_failed, "fused": len(ranked), "preselected": len(chosen),
             "documents": len({index.get(c.unit_id).document_id for c in chosen}),
             "articles": len({(index.get(c.unit_id).document_id, _article(index.get(c.unit_id))) for c in chosen})}
    fallback = False
    if chosen:
        try:
            if rerank_deadline_s == 0:
                raise TimeoutError
            async with asyncio.timeout(rerank_deadline_s):
                scores = await reranker.rerank(u.search_query,
                    [rerank_excerpt(index.get(c.unit_id).text, u.search_query) for c in chosen],
                    deadline_s=rerank_deadline_s)
            if len(scores) != len(chosen) or any(type(s) not in (int, float) or not math.isfinite(s) for s in scores):
                raise ValueError("invalid rerank scores")
            chosen = [replace(c, rerank_score=float(score)) for c, score in zip(chosen, scores)
                      if score > min_rerank_logit]
            chosen.sort(key=lambda c: (-c.rerank_score, -c.fused_score, c.unit_id))
            trace["status"] = "RERANKED"
        except Exception as error:  # noqa: BLE001 -- every reranker failure must fall back to RRF
            fallback = True
            chosen.sort(key=lambda c: (-c.fused_score, c.unit_id))
            # A zero deadline means reranking is switched off on purpose (measured: the CPU reranker lowered
            # gold survival, see rag_v2/service.py), so it must not be reported as a timeout.
            trace["status"] = ("RRF_ONLY" if rerank_deadline_s == 0
                               else "RRF_TIMEOUT" if isinstance(error, TimeoutError) else "RRF_ERROR")
    if LEXICAL_PIN and chosen and rerank_deadline_s == 0:
        # Context packing reads only the first PACK_WINDOW rows, so the strongest lexical hits
        # (exact codes and names that vectors miss) must sit inside that window.
        pinned = sorted((c for c in ranked if c.lexical_rank is not None and c.lexical_rank <= LEXICAL_PIN
                         and c.unit_id not in labels),
                        key=lambda c: c.lexical_rank)
        head = chosen[:PACK_WINDOW]
        missing = [c for c in pinned if all(c.unit_id != h.unit_id for h in head)]
        if missing:
            head = head[:max(0, PACK_WINDOW - len(missing))] + missing
            kept = {c.unit_id for c in head}
            chosen = head + [c for c in chosen if c.unit_id not in kept]
    final = tuple(replace(c, final_rank=i) for i, c in enumerate(chosen[:final_limit], 1))
    trace["returned"] = len(final)
    return RetrievalResult(final, fallback, trace)
