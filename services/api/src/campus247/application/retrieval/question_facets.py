"""Rerank explicit question clauses without making one clause hide another.

Only verbatim user-query fragments are used. Every chosen candidate is scored
once; the same global deadline, typed context, model and output checks apply.
The full question remains authoritative for applicability and answer validation.
"""
import asyncio
import re
from time import monotonic

from campus247.application.conversation.followup import normalized_question
from campus247.application.retrieval.excerpts import words
from campus247.application.retrieval.rerank import StrictRerankOutputValidator
from campus247.domain.retrieval import RetrievalQuery
from campus247.ports.reranker import RerankRequest, RerankResult

_QUESTION = re.compile(r"\b(?:bao nhieu|may|ai|o dau|tai dau|khi nao|the nao|la gi|khong)\b")
_STOP = frozenset("bao nhieu la cua toi em minh ban va thi co duoc nao gi mot moi trong theo".split())


def question_facets(query):
    """Split only when both sides have explicit question cues, maximum three."""
    pieces, start = [], 0
    for match in re.finditer(r"(?i)\s+và\s+|\s+va\s+|;\s*", query):
        left, right = query[start:match.start()].strip(), query[match.end():].strip()
        if _QUESTION.search(normalized_question(left)) and _QUESTION.search(normalized_question(right)):
            pieces.append(left)
            start = match.end()
    if not pieces or len(pieces) >= 3:
        return (query,)
    pieces.append(query[start:].strip())
    return tuple(pieces)


def best_facet(text, facets):
    source = set(words(text))
    def coverage(facet):
        tokens = set(words(facet)) - _STOP
        return len(tokens & source) / len(tokens) if tokens else 0
    return max(facets, key=coverage)


async def rerank_facets(adapter, request, facets):
    if len(facets) <= 1:
        return await adapter.rerank(request)
    grouped = {}
    for candidate in request.candidates:
        grouped.setdefault(best_facet(candidate.content_text, facets), []).append(candidate)
    ranked, started = [], monotonic()
    # Splitting a question cannot reset the operation's total wall-clock budget.
    async with asyncio.timeout(request.profile.timeout_ms / 1000):
        for query, candidates in grouped.items():
            partial_request = RerankRequest(request.profile, RetrievalQuery(query), request.context, tuple(candidates))
            partial = await adapter.rerank(partial_request)
            StrictRerankOutputValidator().validate(partial_request, partial)
            ranked.extend(partial.ranked)
    combined = RerankResult(tuple(ranked), request.profile.model_id, request.profile.model_revision,
        int((monotonic()-started)*1000))
    return StrictRerankOutputValidator().validate(request, combined)
