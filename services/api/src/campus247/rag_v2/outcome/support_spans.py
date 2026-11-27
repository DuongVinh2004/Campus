"""Find the part of a source unit that supports a statement (F4.2). Pure and deterministic: no model, no I/O.

1. If the statement (whitespace normalised) is a substring of the unit text, that position is the span.
2. Otherwise score each sentence of the unit by how many of the statement's numbers, codes and dates it contains (weight 3)
   plus the share of the statement's folded tokens it covers (weight 1), and take the best window of up to three
   consecutive sentences, preferring a window that holds every number of the statement.
The span always lies inside the unit text. It is only for display and never changes what a citation quotes.
"""
from __future__ import annotations

import re
import unicodedata

MAX_WINDOW = 3
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_TOKEN = re.compile(r"[a-z0-9]+")
_SENTENCE_END = re.compile(r"(?<![\d])[.;:]\s+|\n+|(?<=\d)[.;]\s+(?=[A-ZÀ-Ỵ])")


def fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def numbers(text: str) -> list[str]:
    """Numbers as digit strings with separators removed, so '580.500' and '580,500' compare equal."""
    return [re.sub(r"[.,]", "", n) for n in _NUMBER.findall(text)]


def _sentences(text: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    for match in _SENTENCE_END.finditer(text):
        end = match.start() + (1 if text[match.start():match.start() + 1] in ".;:" else 0)
        if text[start:end].strip():
            spans.append((start, end))
        start = match.end()
    if text[start:].strip():
        spans.append((start, len(text)))
    return spans or [(0, len(text))]


def _normalised_find(statement: str, text: str) -> tuple[int, int] | None:
    """Substring search ignoring differences in whitespace; returns offsets in the original text."""
    words = statement.split()
    if not words:
        return None
    pattern = r"\s+".join(re.escape(w) for w in words)
    match = re.search(pattern, text)
    return (match.start(), match.end()) if match else None


def find_support(statement: str, unit_text: str) -> tuple[int, int] | None:
    """(start, end) of the supporting passage inside `unit_text`, or None when nothing in it overlaps the statement."""
    if not statement.strip() or not unit_text.strip():
        return None
    exact = _normalised_find(statement, unit_text)
    if exact:
        return exact
    wanted_numbers = set(numbers(statement))
    wanted_tokens = set(_TOKEN.findall(fold(statement)))
    spans = _sentences(unit_text)

    def score(span: tuple[int, int]) -> float:
        piece = unit_text[span[0]:span[1]]
        have = set(numbers(piece))
        tokens = set(_TOKEN.findall(fold(piece)))
        coverage = len(wanted_tokens & tokens) / len(wanted_tokens) if wanted_tokens else 0.0
        return 3 * len(wanted_numbers & have) + coverage

    best, best_key = None, (-1.0, 0)
    for i in range(len(spans)):
        for size in range(1, MAX_WINDOW + 1):
            if i + size > len(spans):
                break
            window = (spans[i][0], spans[i + size - 1][1])
            piece_numbers = set(numbers(unit_text[window[0]:window[1]]))
            total = sum(score(s) for s in spans[i:i + size])
            holds_all = 1 if wanted_numbers <= piece_numbers else 0
            key = (holds_all * 1000 + total - 0.01 * size, -size)
            if key > best_key:
                best, best_key = window, key
    if best is None:
        return None
    start, end = best
    window_text = unit_text[start:end]
    if not (wanted_numbers & set(numbers(window_text))) and not (wanted_tokens & set(_TOKEN.findall(fold(window_text)))):
        return None  # nothing in the unit overlaps the statement
    while start < end and unit_text[start].isspace():
        start += 1
    while end > start and unit_text[end - 1].isspace():
        end -= 1
    return (start, end) if end > start else None


def holds_every_number(statement: str, unit_text: str, span: tuple[int, int]) -> bool:
    """Gold check used by tests and evals: the span contains every number of the statement that the unit contains at all."""
    in_unit = set(numbers(unit_text))
    needed = [n for n in numbers(statement) if n in in_unit]
    have = set(numbers(unit_text[span[0]:span[1]]))
    return all(n in have for n in needed)
