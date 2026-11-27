"""Readable Markdown layout for a grounded answer (presentation only).

The words are the verified claims, unchanged; the markup is fixed; section headings are the user's own words from the
question. The layout is built after the output guard has checked the plain text, and only from a draft whose text is
exactly its claims, so it can never show anything that was not checked.
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

# "Chương trình CLC, từ K67: 533.000 đồng/tín chỉ": the part before the colon names what the value is for.
_LABEL = re.compile(r"^(?P<label>[^:\[\]*`\n]{2,70}?):\s+(?=\S)")
_LABEL_MAX_WORDS = 6
# Values a reader scans for: amounts of money, full dates, clock times.
_KEY_VALUE = re.compile(
    r"\d{1,3}(?:\.\d{3})+(?:,\d+)?\s*(?:đồng|VNĐ|VND|đ)\b"
    r"(?:/(?:tín chỉ|ĐVHT|tháng|năm học|năm|học kỳ|sinh viên|lần))?"
    r"|\b\d{1,2}/\d{1,2}/\d{4}\b"
    r"|\b\d{1,2}h\d{2}\b")
_MARKDOWN_SPECIAL = re.compile(r"([\\`*_\[\]<>#|~])")
OTHER_HEADING = "Thông tin liên quan"


def _clean(text: str) -> str:
    """One line of text that cannot open a block of its own (list, heading, quote) inside the layout."""
    text = " ".join(text.split())
    text = re.sub(r"^(?:[-+*•]\s+)+", "", text)
    if text[:1] in {"#", ">"}:
        text = "\\" + text
    return re.sub(r"^(\d+)([.)])(\s)", r"\1\\\2\3", text)


def _labelled(text: str) -> re.Match[str] | None:
    match = _LABEL.match(text)
    return match if match and len(match["label"].split()) <= _LABEL_MAX_WORDS else None


def _emphasize(text: str) -> str:
    if "*" in text:
        return text   # the claim carries its own emphasis markers; adding more could pair with them
    if _KEY_VALUE.search(text):
        return _KEY_VALUE.sub(lambda value: f"**{value.group(0)}**", text)
    if label := _labelled(text):
        return f"**{label['label']}:** {text[label.end():]}"
    return text


def _line(text: str, refs: Sequence[str]) -> str:
    cited = " ".join(f"[{ref}]" for ref in refs)
    return _emphasize(_clean(text)) + (" " + cited if cited else "")


def _block(texts: Sequence[str], lines: Sequence[str], *, lead: bool) -> str:
    if len(lines) == 1:
        return lines[0]
    # Several rows of "label: value" read best as one list; a narrative answer keeps its first claim as the lead.
    rows = sum(1 for text in texts if _LABEL.match(_clean(text)) or _KEY_VALUE.search(text))
    if lead and len(lines) >= 3 and rows * 2 < len(lines):
        return lines[0] + "\n\n" + "\n".join("- " + line for line in lines[1:])
    return "\n".join("- " + line for line in lines)


def _heading(ask: str) -> str:
    text = " ".join(ask.split()).rstrip(" ?.!,;:")
    text = re.sub(r"\s+ạ$", "", text).rstrip(" ?.!,;:")
    text = text[:1].upper() + text[1:]
    return _MARKDOWN_SPECIAL.sub(r"\\\1", text)


def _sections(groups: Any, count: int) -> list[tuple[str, list[int]]] | None:
    """Valid groups cover each claim once; anything malformed falls back to the flat layout."""
    if not isinstance(groups, (tuple, list)) or len(groups) < 2:
        return None
    seen: set[int] = set()
    sections: list[tuple[str, list[int]]] = []
    for group in groups:
        if not (isinstance(group, (tuple, list)) and len(group) == 2 and isinstance(group[0], str)
                and isinstance(group[1], (tuple, list))):
            return None
        indexes = [i for i in group[1] if type(i) is int and 0 <= i < count and i not in seen]
        seen.update(indexes)
        if indexes:
            sections.append((group[0], indexes))
    rest = [i for i in range(count) if i not in seen]
    if rest:
        sections.append(("", rest))
    return sections if sum(1 for ask, _ in sections if ask) >= 2 else None


def layout_claims(claims: Sequence[tuple[str, Sequence[str]]], groups: Any = ()) -> str:
    texts = [text for text, _ in claims]
    lines = [_line(text, refs) for text, refs in claims]
    sections = _sections(groups, len(lines))
    if sections is None:
        return _block(texts, lines, lead=True)
    # A heading echoes the user's words; typed without Vietnamese diacritics it reads badly as a title, so the
    # parts are then only set apart, in the same order.
    headed = all(not ask or any(ord(char) > 127 for char in ask) for ask, _ in sections)
    parts = []
    for ask, indexes in sections:
        block = _block([texts[i] for i in indexes], [lines[i] for i in indexes], lead=False)
        if headed:
            block = "### " + (_heading(ask) if ask else OTHER_HEADING) + "\n\n" + block
        parts.append(block)
    return "\n\n".join(parts)


def layout_grounded_draft(draft: Any) -> str | None:
    """The laid-out answer, or None when the draft text is not exactly its grounded claims (then it is shown as is)."""
    claims = getattr(draft, "grounded_claims", None)
    if not claims:
        return None
    try:
        pairs = [(claim.text, tuple(claim.citation_ids)) for claim in claims]
    except (AttributeError, TypeError):
        return None
    if not all(isinstance(text, str) and all(isinstance(ref, str) for ref in refs) for text, refs in pairs):
        return None
    plain = "\n".join(text + " " + " ".join(f"[{ref}]" for ref in refs) for text, refs in pairs)
    if plain != getattr(draft, "text", None):
        return None
    return layout_claims(pairs, getattr(draft, "claim_groups", ()))


def quote(text: str) -> str:
    """Server notes (scope caveat, partial-answer note) as a quote block, set apart from the answer."""
    return "\n".join("> " + line if line.strip() else ">" for line in text.strip().split("\n"))
