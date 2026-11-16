"""When a student's wording needs cleaning before retrieval, and how a cleaned question is checked.

Clean typed questions keep the fast deterministic path. Only text that is likely to defeat keyword and topic
matching (no diacritics, rambling, no recognised topic) pays for one short model call, and the result is accepted
only when every number, code, name and negation of the original is still there.
"""
from __future__ import annotations

import re
import unicodedata

from campus247.rag_v2.understanding.normalize import fold

_ATOM = re.compile(r"\b(?=\w*\d)\w+(?:[./–—-]\w+)*\b")
_NEGATION = re.compile(r"\b(?:khong|chua|chang|cha|dung|khoi|ngoai tru|tru)\b")
_LINK = re.compile(r"https?:|www\.|@")
LONG_QUESTION = 140
MAX_CLEAN_LENGTH = 400


def has_diacritics(text: str) -> bool:
    return any(unicodedata.combining(c) for c in unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))) \
        or "đ" in text.lower()


def looks_messy(question: str, topics: tuple[str, ...], question_type: str) -> bool:
    """Whether a deterministic read of this question is likely to be unreliable."""
    words = re.findall(r"\w+", question)
    if len(words) < 3 or question_type in {"smalltalk", "oos"}:
        return False
    if len(question) > LONG_QUESTION:
        return True
    if not has_diacritics(question) and len(words) >= 4:
        return True  # typed without diacritics: phrase tables only fire on exact words
    # Nothing recognised at all (no topic and the default question type): the rule-based read has nothing to go on.
    # A typed question with a known intent ("Email phòng đào tạo?") is well formed and keeps the fast path.
    return not topics and question_type in {"lookup", "unclear"}


_NUMBER_WORDS = {1: "mot", 2: "hai", 3: "ba", 4: "bon", 5: "nam", 6: "sau", 7: "bay", 8: "tam", 9: "chin", 10: "muoi"}


def _small_number_word(atom: str) -> str:
    """"1 tc" may become "một tín chỉ": a plain small number is also accepted when written as a word."""
    return " " + _NUMBER_WORDS[int(atom)] + " " if atom.isdigit() and 1 <= int(atom) <= 10 else "\0"


def _atoms(text: str) -> set[str]:
    return {m.group() for m in _ATOM.finditer(fold(text))}


def safe_clean(question: str, cleaned: str) -> bool:
    """A cleaned question may only fix spelling, restore diacritics, expand abbreviations and drop filler."""
    if not 3 <= len(cleaned) <= MAX_CLEAN_LENGTH or _LINK.search(cleaned):
        return False
    original = fold(question)
    rewritten = fold(cleaned)
    if any(atom not in rewritten and _small_number_word(atom) not in rewritten for atom in _atoms(question)):
        return False  # a number, code or name was lost or changed
    if not _atoms(cleaned) <= _atoms(question):
        return False  # a new number or code would be invented
    # A negation must keep the word it governs ("không được" stays together), so moving "không" to the end of the
    # sentence, which turns a rule into a yes/no question, is rejected even though the word count is unchanged.
    negation = _negation_pattern(question)
    for word, governed in re.findall(r"(?<!\w)(" + negation + r")\s+(\w+)", original):
        if (word + " " + governed) not in rewritten:
            return False
    for word in re.findall(r"(?<!\w)(" + negation + r")(?!\w)", original):
        pattern = r"(?<!\w)" + re.escape(word) + r"(?!\w)"
        if len(re.findall(pattern, rewritten)) < len(re.findall(pattern, original)):
            return False
    return True


# Without diacritics "dung", "khoi", "cha", "tru" are also "đúng", "khối", "cha", "trụ": they count as negations only
# when the original really wrote đừng, khỏi, chả or trừ. The unambiguous ones always count.
_SURE_NEGATIONS = ("khong", "chua", "chang", "ngoai tru")
_MARKED_NEGATIONS = (("đừng", "dung"), ("khỏi", "khoi"), ("chả", "cha"), ("trừ", "tru"))


def _negation_pattern(question: str) -> str:
    raw = unicodedata.normalize("NFC", question.lower())
    words = [*_SURE_NEGATIONS, *(folded for marked, folded in _MARKED_NEGATIONS if marked in raw)]
    return "|".join(re.escape(word) for word in words)
