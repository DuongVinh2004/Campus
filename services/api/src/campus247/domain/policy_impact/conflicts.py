"""Deterministic fact-value conflicts (F3.5): same kind + subject, different value, overlapping scope and validity."""
from __future__ import annotations

import re
import unicodedata
from itertools import combinations


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFD", str(text).casefold()).replace("đ", "d")
    return " ".join("".join(c for c in text if unicodedata.category(c) != "Mn").split())


def _value(text: str) -> str:
    return re.sub(r"[\s.,;:]+", "", _fold(text))


def _overlap(a: list, b: list) -> bool:
    """An empty axis means 'all', so it overlaps everything."""
    return not a or not b or bool(set(a) & set(b))


def scopes_overlap(a: dict, b: dict) -> bool:
    return all(_overlap(a.get(k) or [], b.get(k) or []) for k in ("cohorts", "programs", "academic_years"))


def _interval_overlap(a: dict, b: dict) -> bool:
    af, au, bf, bu = a.get("from"), a.get("until"), b.get("from"), b.get("until")
    return (au is None or bf is None or bf < au) and (bu is None or af is None or af < bu)


def find_fact_conflicts(facts: list[dict], validity: dict | None = None) -> list[dict]:
    """facts: {fact_id, kind, subject, value, unit_id, quote, scope}. validity: unit_id -> {from, until}."""
    validity = validity or {}
    groups: dict[tuple, list[dict]] = {}
    for f in facts:
        groups.setdefault((f["kind"], _fold(f["subject"])), []).append(f)
    out = []
    for (kind, subject), members in sorted(groups.items()):
        for a, b in combinations(members, 2):
            if a["unit_id"] == b["unit_id"] or _value(a["value"]) == _value(b["value"]):
                continue
            if not scopes_overlap(a.get("scope") or {}, b.get("scope") or {}):
                continue
            if not _interval_overlap(validity.get(a["unit_id"], {}), validity.get(b["unit_id"], {})):
                continue
            out.append({"code": "FACT_VALUE_CONFLICT", "kind": kind, "subject": subject,
                        "a": {"fact_id": a["fact_id"], "unit_id": a["unit_id"], "value": a["value"], "quote": a["quote"]},
                        "b": {"fact_id": b["fact_id"], "unit_id": b["unit_id"], "value": b["value"], "quote": b["quote"]}})
    return out
