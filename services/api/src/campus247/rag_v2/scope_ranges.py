"""Cohort ranges written in source text ("K70 trở về trước", "từ K69", "K65 đến K68").

A fee or curriculum row often names its cohorts as a range. The declared scope then lists only the cohorts it
spells out, so a question about a cohort inside the range (K69 for "K70 trở về trước") looked out of scope and the
row was dropped. The ranges come only from the unit's own text; nothing is inferred beyond what the source states.
"""
from __future__ import annotations

import re
import unicodedata

_K = r"k\s*(\d{2,3})"
_PATTERNS = (
    (re.compile(_K + r"\s*(?:\(\w+\)\s*)?(?:tro ve truoc|tro xuong|va truoc|tro ve k\d+)"), "le"),
    (re.compile(r"(?:tu|ap dung tu)\s+(?:khoa\s+)?" + _K + r"(?!\s*(?:den|-|–)\s*k)"), "ge"),
    (re.compile(_K + r"\s*(?:tro di|tro len|tro ve sau|va sau)"), "ge"),
    (re.compile(r"(?:truoc)\s+(?:khoa\s+)?" + _K), "lt"),
)
_SPAN = re.compile(_K + r"\s*(?:den|-|–|toi)\s*k?\s*(\d{2,3})")


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text.casefold()).replace("đ", "d")
    return re.sub(r"\s+", " ", "".join(c for c in text if unicodedata.category(c) != "Mn"))


def covers(text: str, cohort: str) -> bool:
    """True when ``text`` states a cohort range that contains ``cohort`` ("K69", "k69", "69")."""
    digits = re.sub(r"\D", "", cohort or "")
    if not digits:
        return False
    number = int(digits)
    folded = _fold(text)
    for pattern, kind in _PATTERNS:
        for match in pattern.finditer(folded):
            bound = int(match.group(1))
            if (kind == "le" and number <= bound) or (kind == "ge" and number >= bound) or (kind == "lt" and number < bound):
                return True
    for match in _SPAN.finditer(folded):
        low, high = sorted((int(match.group(1)), int(match.group(2))))
        if low <= number <= high:
            return True
    return False
