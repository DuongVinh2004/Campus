"""Bound exact source parts while keeping citation identity and trust boundaries."""
from __future__ import annotations

import json
from collections.abc import Callable, Sequence

from campus247.agent.prompts.composer import (
    MAX_BLOCK_CHARS,
    MAX_PROMPT_BLOCKS,
    PromptBlock,
    PromptComposer,
    TrustDomain,
)
from campus247.application.retrieval.citations import CitationBundle
from campus247.application.retrieval.excerpts import narrow_clause


def _rendered_length(content: str) -> int:
    if len(content) > MAX_BLOCK_CHARS:
        return MAX_BLOCK_CHARS + 1
    block = PromptBlock(TrustDomain.RETRIEVED_EVIDENCE, content, "turn-citations")
    return len(PromptComposer().compose([block]).composed_user_prompt)


def _parts(text: str, render: Callable[[str, int, int], str], *, base: int = 0) -> list[PromptBlock]:
    """Every character occurs in one successive part; nothing is dropped."""
    result, start = [], 0
    while start < len(text):
        if len(result) >= MAX_PROMPT_BLOCKS:
            raise ValueError("evidence part count exceeds prompt bound")
        low, high, best = 1, min(MAX_BLOCK_CHARS, len(text) - start), 0
        while low <= high:
            size = (low + high) // 2
            content = render(text[start:start + size], base + start, base + start + size)
            if _rendered_length(content) <= MAX_BLOCK_CHARS:
                best, low = size, size + 1
            else:
                high = size - 1
        if best == 0:
            raise ValueError("evidence header exceeds prompt bound")
        if start + best < len(text):
            # Prefer a complete line, keeping its newline and all whitespace.
            boundary = text.rfind("\n", start + best // 2, start + best)
            if boundary >= 0:
                best = boundary - start + 1
        end = start + best
        result.append(PromptBlock(TrustDomain.RETRIEVED_EVIDENCE,
            render(text[start:end], base + start, base + end), "turn-citations"))
        start = end
    return result


def evidence_prompt_blocks(bundle: CitationBundle, *, query: str | None = None,
                           citation_ids: Sequence[str] | None = None, semantic: bool = False) -> list[PromptBlock]:
    if not isinstance(bundle, CitationBundle):
        # Existing internal prompt-only protocol; actual API evidence is typed.
        return _parts(bundle.to_prompt_context(), lambda text, _start, _end: text)
    refs = sorted(bundle.citations if citation_ids is None else set(citation_ids))
    from campus247.application.retrieval.contact_minimization import evidence_contact_redactor
    redact_public_contacts = evidence_contact_redactor(bundle)
    blocks = []
    for ref in refs:
        record = bundle.resolve(ref)
        if record is None:
            raise ValueError("unknown evidence citation")
        original = record.content_text
        if query is not None:
            from campus247.application.retrieval.material_support import (
                applicable_fee_row_ranges,
            )
            row_ranges = applicable_fee_row_ranges(original, query)
        else:
            row_ranges = None
        text = narrow_clause(original, query) if query is not None and not semantic else original
        base = original.find(text)
        if base < 0:
            raise ValueError("evidence excerpt is not an exact source span")

        def render(part, start, end, *, citation=ref, source=record, contact_redacted=False):
            if semantic:
                return json.dumps([{"citation_id": citation, "source_title": source.title,
                    "section_path": source.section_path, "start": start, "end": end, "source": part,
                    **({"view": "public_contact_redacted"} if contact_redacted else {}),
                    **({"applicability_note_metadata": source.applicability_note} if source.applicability_note else {})}], ensure_ascii=False)
            section = f" ({source.section_path})" if source.section_path else ""
            scope_note = f"Phạm vi bản nguồn (metadata): {source.applicability_note}\n" if source.applicability_note else ""
            if contact_redacted:
                scope_note += "Bản gửi mô hình dùng nhãn PUBLIC_CONTACT_* thay giá trị liên hệ công khai; vị trí tham chiếu bản gốc giữ tại máy.\n"
            return (f"[{citation}] Nguồn: {source.title}{section}\n{scope_note}"
                f"Phần nguồn tại vị trí {start}:{end} (vị trí không phải dữ kiện).\nNội dung: {part}")

        redacted_text = redact_public_contacts(text)
        if redacted_text != text:
            # Redact the whole bounded parent before any splitting: a contact
            # value must never escape as two unrecognized adjacent fragments.
            rendered = render(redacted_text, base, base + len(text), contact_redacted=True)
            if _rendered_length(rendered) > MAX_BLOCK_CHARS:
                raise ValueError("minimized public contact view exceeds prompt bound")
            blocks.append(PromptBlock(TrustDomain.RETRIEVED_EVIDENCE, rendered, "turn-citations"))
        elif row_ranges and not semantic:
            for start, end in row_ranges:
                blocks.extend(_parts(redact_public_contacts(original[start:end]), render, base=start))
        else:
            blocks.extend(_parts(text, render, base=base))
        if row_ranges:
            if semantic:
                start, end = row_ranges[-1]
                group = row_ranges[1] if len(row_ranges) == 3 else None
                import re
                cells = [{"start": start + match.start() + len(match.group()) - len(match.group().lstrip()),
                          "end": start + match.end() - len(match.group()) + len(match.group().rstrip()),
                          "source": redact_public_contacts(match.group().strip())}
                         for match in re.finditer(r"[^|\n]+", original[start:end])]
                blocks.append(PromptBlock(TrustDomain.RETRIEVED_EVIDENCE,
                    json.dumps({"citation_id": ref, "view": "table_row_focus", "start": start, "end": end,
                        "source": redact_public_contacts(original[start:end]), "header": {"start": row_ranges[0][0], "end": row_ranges[0][1],
                            "source": redact_public_contacts(original[row_ranges[0][0]:row_ranges[0][1]])},
                        "group_header": {"start": group[0], "end": group[1], "source": redact_public_contacts(original[group[0]:group[1]])} if group else None,
                        "cells": cells}, ensure_ascii=False), "turn-table-row"))
            # Keep the mixed header verbatim, but expose its row-local unit as
            # an exact source span so the model need not guess from parentheses.
            from campus247.application.retrieval.material_support import fee_unit_span
            unit_span = fee_unit_span(original, row_ranges)
            if unit_span:
                start, end = unit_span
                blocks.append(PromptBlock(TrustDomain.RETRIEVED_EVIDENCE,
                    f"[{ref}] Đơn vị của dòng bảng đang đối chiếu, nguyên văn tại vị trí {start}:{end}: "
                    + redact_public_contacts(original[start:end]), "turn-table-unit"))
        if len(blocks) > MAX_PROMPT_BLOCKS:
            raise ValueError("evidence block count exceeds prompt bound")
    return blocks


def compose_bounded_inputs(blocks: list[PromptBlock]) -> tuple[str, tuple[dict[str, str], ...]]:
    # Validate the complete block list first; composing each message must not
    # circumvent the existing global 32-block bound.
    composed = PromptComposer().compose(blocks)
    if len(composed.system_prompt) > MAX_BLOCK_CHARS:
        raise ValueError("system message exceeds prompt bound")
    messages, current = [], ""
    for block in blocks:
        rendered = PromptComposer().compose([block]).composed_user_prompt
        if not rendered:
            continue
        if len(rendered) > MAX_BLOCK_CHARS:
            raise ValueError("source message exceeds prompt bound")
        if current and len(current) + 2 + len(rendered) > MAX_BLOCK_CHARS:
            messages.append({"role": "user", "content": current})
            current = ""
        current = current + "\n\n" + rendered if current else rendered
    if current:
        messages.append({"role": "user", "content": current})
    if len(messages) + bool(composed.system_prompt) > MAX_PROMPT_BLOCKS:
        raise ValueError("message count exceeds prompt bound")
    return composed.system_prompt, tuple(messages)
