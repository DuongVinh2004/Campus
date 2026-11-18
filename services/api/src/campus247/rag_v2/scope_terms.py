"""Check that the scope a question names is a scope the sources actually carry.

Sources are tables and rules written along some dimensions (training programme and cohort, a fee per year, an exam per cohort). A question may
name a scope on a dimension the sources do not use: "học phí ngành Trí tuệ nhân tạo" against a fee table that is per programme and cohort.
No row mentions the major, so no sentence of the answer can be tied to it, and the answer used to be refused as unverified. The honest
answer is what the sources say in their own terms, with a plain statement that they do not split by that name.

This works on what was retrieved, not on a list of known names: a name the question uses that no retrieved source mentions is set aside
(removed from the query the generator and the checker see) and reported to the person.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from campus247.rag_v2.ingest.units import source_text
from campus247.rag_v2.understanding.normalize import fold
from campus247.rag_v2.vocabulary import Vocabulary, initialism


def _folded_with_offsets(text: str) -> tuple[str, list[int]]:
    plain, offsets = [], []
    for i, char in enumerate(text):
        for c in fold(char):
            plain.append(c)
            offsets.append(i)
    return "".join(plain), offsets


def _pattern(term: str, aliases: Iterable[str]) -> re.Pattern[str]:
    names = [re.escape(term), *(re.escape(a) for a in aliases)]
    return re.compile(rf"(?:(?:chuyen\s+nganh|nganh)\s+)?(?<!\w)(?:{'|'.join(names)})(?!\w)")


def missing_terms(terms: Iterable[str], units: Iterable, vocabulary: Vocabulary) -> list[str]:
    """Terms of the question that no retrieved source mentions (by name, or by its initialism)."""
    evidence = fold("\n".join(source_text(unit) + "\n" + unit.doc_title for unit in units))
    absent = []
    for term in terms:
        alias = initialism(term) if len(term.split()) >= 3 else ""
        names = [term] + ([alias] if alias else [])
        if not any(re.search(rf"(?<!\w){re.escape(name)}(?!\w)", evidence) for name in names):
            absent.append(term)
    return absent


def without_terms(query: str, terms: Iterable[str]) -> tuple[str, list[str]]:
    """The query with the given scope names (and a leading "ngành") cut out, and the words the person actually used for them."""
    plain, offsets = _folded_with_offsets(query)
    spans, shown = [], []
    for term in terms:
        alias = initialism(term) if len(term.split()) >= 3 else ""
        for match in _pattern(term, [alias] if alias else []).finditer(plain):
            start, end = offsets[match.start()], offsets[match.end() - 1] + 1
            spans.append((start, end))
            shown.append(query[start:end].strip())
    for start, end in sorted(spans, reverse=True):
        query = query[:start] + " " + query[end:]
    return " ".join(query.split()), list(dict.fromkeys(re.sub(r"^(?:chuyên\s+ngành|chuyen\s+nganh|ngành|nganh)\s+", "", s, flags=re.IGNORECASE) for s in shown))
