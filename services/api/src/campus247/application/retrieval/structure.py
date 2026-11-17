"""Exact source spans split at paragraphs/sentences, with table rows intact."""
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TextSpan:
    start: int
    end: int
    text: str


def structured_spans(content: str, *, max_chars: int = 1100, overlap_chars: int = 120) -> tuple[TextSpan, ...]:
    if max_chars < 8 or not 0 <= overlap_chars < max_chars:
        raise ValueError("invalid chunk bounds")
    spans = []
    start = 0
    while start < len(content):
        while start < len(content) and content[start].isspace():
            start += 1
        if start == len(content):
            break
        hard_end = min(len(content), start + max_chars)
        end = hard_end
        if hard_end < len(content):
            boundaries = [m.end() for m in re.finditer(r"\n\s*\n|(?<=[.!?;])\s+|\n", content[start:hard_end])]
            meaningful = [offset for offset in boundaries if offset >= max_chars // 3]
            if meaningful:
                end = start + meaningful[-1]
            else:
                space = content.rfind(" ", start + max_chars // 2, hard_end)
                if space > start:
                    end = space
        trimmed = content[start:end].rstrip()
        if trimmed:
            spans.append(TextSpan(start, start + len(trimmed), trimmed))
        if end >= len(content):
            break
        next_start = end
        if overlap_chars:
            # Reuse complete trailing sentences/rows rather than starting in
            # the middle of a condition or shifting canonical source offsets.
            tail = content[max(start, end - overlap_chars):end]
            boundaries = list(re.finditer(r"(?<=[.!?;])\s+|\n", tail))
            if boundaries:
                next_start = max(start, end - overlap_chars) + boundaries[0].end()
        start = max(start + 1, next_start)
    return tuple(spans)
