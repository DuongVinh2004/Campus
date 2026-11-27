"""Cheap code-only check that a statement is an exact excerpt of one cited source (lever L1).

When every accepted statement of an answer is such an excerpt, and nothing about the question's scope was relaxed or
missing, the model-based support check adds little: the words are the source's own words. This module only decides
eligibility; service.py decides what to do with it (off, shadow or on).
"""
from __future__ import annotations

import os
import re
import unicodedata
from collections.abc import Mapping, Sequence

from campus247.rag_v2.generation.contacts import restore
from campus247.rag_v2.ingest.units import source_text
from campus247.rag_v2.types import Statement, Unit

MIN_CHARS = 20
_STOP = frozenset("nhung nhieu duoc khong cach nhu the nao thi nay kia cho cua voi cac mot hai ba nam khi neu sau truoc "
                  "trong ngoai tren duoi muon can phai bao nhieu gi va hay hoac thi la co".split())


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFC", text).casefold()
    text = re.sub(r"^[\s\-*•\d.)]+", "", text)           # list bullets and numbering
    return " ".join(text.split()).strip(" .;:,")


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.casefold().replace("đ", "d"))
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def mode() -> str:
    """off | shadow | on (CAMPUS247_RAG_SKIP_VERBATIM_SEMANTIC). Shadow still asks the model and records agreement."""
    from campus247.features.runtime import value as feature_value  # F0: env is the legacy source; an admin override wins
    value = str(feature_value("chat.verbatim_skip", os.environ.get("CAMPUS247_RAG_SKIP_VERBATIM_SEMANTIC", "off"))).strip().lower()
    return value if value in {"off", "shadow", "on"} else "off"


def is_verbatim(stmt: Statement, units_by_id: Mapping[str, Unit], search_query: str) -> bool:
    units = [units_by_id.get(ref) for ref in stmt.unit_ids]
    if not units or any(unit is None for unit in units):
        return False
    text = restore(stmt.text, units)
    if not text:
        return False
    wanted = _norm(text)
    if len(wanted) < MIN_CHARS:
        return False
    # One cited source must contain the whole statement: no splicing of two sources into one sentence.
    if not any(wanted in _norm(source_text(unit)) for unit in units):
        return False
    # The excerpt must mention something the question asked about (an exact quote of an unrelated row is not support).
    terms = {token for token in re.findall(r"[a-z0-9]{3,}", _fold(search_query)) if token not in _STOP}
    return not terms or any(term in _fold(text) for term in terms)


def all_verbatim(statements: Sequence[Statement], units_by_id: Mapping[str, Unit], search_query: str) -> bool:
    return bool(statements) and all(is_verbatim(stmt, units_by_id, search_query) for stmt in statements)
