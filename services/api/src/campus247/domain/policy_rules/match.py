"""Pure helpers that spot a policy topic in a student's sentence and pull values out of it.

Nothing here decides anything: it only proposes a topic and prefill values, and a value is
proposed only when its digits appear in the sentence right next to a unit word that maps to
exactly one variable of the form.  The student still reviews every value in the simulator.
"""
from __future__ import annotations

import re
import unicodedata

_STOP = {"khong", "nhung", "nhieu", "nhat", "cua", "cho", "voi", "duoc", "nhu", "thi", "neu", "sau", "khi", "trong", "cung", "phai", "bao"}
_UNIT_WORDS = {"percent": r"(?:%|phần trăm|phan tram)", "period": r"(?:tiết|tiet)", "credit": r"(?:tín chỉ|tin chi|tc)\b",
               "point10": r"(?:điểm|diem)", "point4": r"(?:điểm|diem)"}


def fold(text: str) -> str:
    text = unicodedata.normalize("NFD", (text or "").lower().replace("đ", "d"))
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]{4,}", fold(text)) if t not in _STOP}


def rank_topics(text: str, topics: list[dict], extra_words: dict[str, str] | None = None, *, min_shared: int = 2) -> list[dict]:
    """Topics sharing at least ``min_shared`` words with the sentence, best first; a tie with no margin returns all tied."""
    words = tokens(text)
    scored = []
    for t in topics:
        corpus = " ".join([t.get("label", ""), t.get("description", ""), (extra_words or {}).get(t["topic"], "")])
        shared = words & tokens(corpus)
        if len(shared) >= min_shared:
            scored.append((len(shared), t["topic"], t))
    scored.sort(key=lambda s: (-s[0], s[1]))
    return [{"topic": t["topic"], "label": t["label"], "score": n} for n, _, t in scored[:3]]


def extract_values(text: str, fields: list[dict]) -> tuple[dict, list[dict]]:
    """``{var: value}`` for numbers written next to a unit word, only when that unit names exactly one numeric field.

    Returns ``(values, evidence)`` where evidence lists the literal snippet of the sentence for each value."""
    by_unit: dict[str, list[dict]] = {}
    for f in fields:
        if f.get("type") in {"integer", "number"} and f.get("unit") in _UNIT_WORDS:
            by_unit.setdefault(f["unit"], []).append(f)
    point_fields = by_unit.get("point10", []) + by_unit.get("point4", [])
    values, evidence = {}, []
    for unit, fs in by_unit.items():
        pool = point_fields if unit in {"point10", "point4"} else fs
        if len(pool) != 1:
            continue
        f = pool[0]
        m = re.search(r"(?<![\w.,])(\d+(?:[.,]\d+)?)\s*" + _UNIT_WORDS[unit], text, re.IGNORECASE)
        if not m:
            continue
        number = float(m.group(1).replace(",", "."))
        if f["type"] == "integer":
            if number != int(number):
                continue
            number = int(number)
        lo, hi = f.get("min"), f.get("max")
        if (lo is not None and number < lo) or (hi is not None and number > hi):
            continue
        values[f["var"]] = number
        evidence.append({"var": f["var"], "snippet": m.group(0)})
    return values, evidence
