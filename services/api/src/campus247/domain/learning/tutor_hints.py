"""F7: code-side checks of a model-written hint, and the deterministic template hint used when the checks fail. No model here."""
from __future__ import annotations

import re
import unicodedata

MIN_QUOTE_CHARS = 12
MAX_HINT_CHARS = 600
MAX_TURNS = 6
_LINK = re.compile(r"https?://|www\.|\]\(")
_MARKDOWN = re.compile(r"^\s{0,3}(?:#{1,6}\s|[-*+]\s|>\s|\d+\.\s)|`|__|~~|\[[^\]]*\]\(", re.M)
_OPTION_CODE = re.compile(r"\b(?:dap an|phuong an|lua chon|chon)\s*[:\-]?\s*\(?[a-e]\)?(?![a-z])")


def fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text.casefold()).replace("đ", "d")
    return " ".join("".join(c for c in text if unicodedata.category(c) != "Mn").split())


def leaks(text: str, answers) -> bool:
    """Whether the text gives away an answer: a long answer as any substring, a short one ("Nén", "12") as a whole word.

    A whole-word match may also block a harmless text that happens to use the word; the caller then shows less, the safe side."""
    blob = fold(text)
    for answer in answers:
        a = fold(answer)
        if a and (a in blob if len(a) >= 4 else re.search(rf"(?<!\w){re.escape(a)}(?!\w)", blob)):
            return True
    return False


def hint_issues(hint: str, quote: str, page_text: str, *, level: int, correct_answers: list[str], correct_labels: list[str] | None = None) -> list[str]:
    """Reason codes; empty list means the hint may be shown."""
    issues = []
    if len(quote) < MIN_QUOTE_CHARS or quote not in page_text:
        issues.append("QUOTE_NOT_VERBATIM")
    if not hint.strip() or len(hint) > MAX_HINT_CHARS:
        issues.append("HINT_LENGTH")
    if _LINK.search(hint):
        issues.append("HINT_LINK")
    if _MARKDOWN.search(hint):
        issues.append("HINT_MARKDOWN")
    if level in (1, 2):
        if leaks(hint + " " + quote, correct_answers):
            issues.append("LEAKS_ANSWER")
        if _OPTION_CODE.search(fold(hint)) or any(re.search(rf"\b(?:dap an|phuong an)\s*\(?{re.escape(l.casefold())}\)?\b", fold(hint)) for l in correct_labels or ()):
            issues.append("LEAKS_OPTION_CODE")
    return issues


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?;:])\s+|\n+", text)
    return [p.strip() for p in parts if len(p.strip()) >= MIN_QUOTE_CHARS]


def template_hint(page_text: str, question: str, page_no: int, level: int, *, solution: str | None = None, answer: str | None = None,
                  avoid=()) -> dict:
    """Deterministic fallback: the sentence of the page with most word overlap with the question, then the next one, then the solution.

    At levels 1-2 a sentence that gives away an answer in `avoid` is never quoted (the same rule as for a model hint)."""
    sents = _sentences(page_text)
    if level < 3 and avoid:
        sents = [s for s in sents if not leaks(s, avoid)]
    q = set(fold(question).split())
    best = max(range(len(sents)), key=lambda i: (len(q & set(fold(sents[i]).split())), -i), default=None)
    if level >= 3:
        quote = sents[best] if best is not None else ""
        body = solution or (f"Đáp án: {answer}." if answer else "")
        return {"origin": "TEMPLATE", "level": 3, "hint": f"{body} Căn cứ: «{quote}» (trang {page_no})".strip(), "quote": quote, "page": page_no}
    if best is None:
        return {"origin": "TEMPLATE", "level": level, "hint": f"Xem lại trang {page_no}.", "quote": "", "page": page_no}
    quote = sents[best]
    if level == 2 and best + 1 < len(sents):
        quote = quote + " " + sents[best + 1]
    return {"origin": "TEMPLATE", "level": level, "hint": f"Xem lại trang {page_no}: «{quote}»", "quote": quote, "page": page_no}


def level_for(attempt_no: int, *, reveal_after: int, asked_more: bool = False, asked_solution: bool = False) -> int:
    if asked_solution and attempt_no >= 1 or attempt_no >= reveal_after:
        return 3
    if asked_more or attempt_no >= 2:
        return 2
    return 1
