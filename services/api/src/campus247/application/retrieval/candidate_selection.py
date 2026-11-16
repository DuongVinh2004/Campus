"""Bounded hybrid preselection using the actual evidence, not cached titles."""
from collections import Counter
from math import log

from campus247.application.retrieval.excerpts import words

_STOP = frozenset("theo cua cho va la co duoc khong thi toi em minh ban muon can ai nao bao nhieu the nao huce truong dai hoc noi quy quy che quyet dinh".split())


def _selection_terms(text, *, phrases=False):
    tokens = words(text)
    if not phrases:
        return tokens
    # Keep adjacent two/three-word labels distinct from scattered occurrences
    # of their words, e.g. Nơi nhận versus nơi ... tiếp nhận hồ sơ. Never form
    # phrases by dropping intervening words; none of these tokens are evidence.
    return tokens + ["@phrase:" + " ".join(tokens[i:i+n])
        for n in (2, 3) for i in range(len(tokens)-n+1)]


def select_parent_spans(lexical, semantic, query, *, limit=3, required_version_groups=()):
    """Fuse two retrieved lists plus exact-span term coverage; never an answer.

    IDF is local to the bounded candidate union. It prevents repeated document
    titles/boilerplate from consuming every cross-encoder slot. A parent keeps
    its most query-relevant child, and every selected child still needs BGE.
    """
    scores, rows = {}, {}
    for branch in (lexical, semantic):
        for rank, row in enumerate(branch, 1):
            identifier = str(row["id"])
            rows[identifier] = row
            scores[identifier] = scores.get(identifier, 0) + 1 / (60 + rank)
    # Vietnamese syllables scattered across a long paragraph do not prove the
    # same action as adjacent source words. Keep phrase coverage for ordinary
    # questions too, without dropping intervening words or inventing synonyms.
    phrase_query = True
    terms = set(_selection_terms(query, phrases=phrase_query)) - _STOP
    prefix, separator, rest = query.partition(",")
    if separator and rest.strip() and words(prefix)[:1] == ["theo"]:
        # Keep reference/condition words in unigram coverage and the full
        # rerank question, but don't reward heading phrases over the action.
        terms = (set(words(query)) - _STOP) | {term for term in
            _selection_terms(rest, phrases=True) if term.startswith("@phrase:")}
    tokens = {}
    for identifier, row in rows.items():
        text = row["rerank_text"]
        section = row.get("section_path")
        # The locator must come from this exact parent's hashed rendition.
        # A free metadata string cannot reserve one of the three BGE slots.
        if isinstance(section, str) and section in row.get("verified_sections", set()):
            text = section + "\n" + text
        tokens[identifier] = set(_selection_terms(text, phrases=phrase_query))
    frequencies = Counter(term for value in tokens.values() for term in terms & value)
    # Phrase proximity supplements distinctive single terms (codes, acronyms,
    # names). A repeated heading must not outweigh a unique requested action.
    coverage = {identifier: sum(log(1 + len(rows) / frequencies[term]) *
                (.25 if term.startswith("@phrase:") else 1) for term in terms & value)
                for identifier, value in tokens.items()}
    maximum = max(coverage.values(), default=0)
    if maximum:
        for identifier in rows:
            scores[identifier] += coverage[identifier] / maximum / 30
    # Bound metadata helps distinguish programmes with identical compulsory
    # courses. It only selects BGE inputs; it never becomes cited evidence.
    for identifier, row in rows.items():
        title_terms = set(_selection_terms(row.get("title", ""), phrases=phrase_query)) - _STOP
        if terms and title_terms:
            scores[identifier] += len(terms & title_terms) / len(terms | title_terms) / 20
    parents = {}
    for identifier, row in rows.items():
        key = (str(row["source_id"]), str(row["document_version_id"]), row["content_checksum"])
        previous = parents.get(key)
        # A title match in one child cannot hide the action in another child
        # of this same parent. Scores only decide between distinct parents.
        if previous is None or (coverage[identifier], scores[identifier], identifier) > (
                coverage[previous], scores[previous], previous):
            parents[key] = identifier
    ordered = sorted(parents.values(), key=lambda i: (-scores[i], -coverage[i], i))
    selected = []
    if len(required_version_groups) > limit:
        raise ValueError("Explicit references exceed the bounded rerank slots")
    for group in required_version_groups:
        allowed = set(map(str, group))
        first = next((i for i in ordered if str(rows[i]["document_version_id"]) in allowed and i not in selected), None)
        if first is not None:
            selected.append(first)
    selected.extend(i for i in ordered if i not in selected)
    selected = selected[:limit]
    return [rows[i] for i in selected]
