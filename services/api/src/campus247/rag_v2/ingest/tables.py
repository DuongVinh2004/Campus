"""Structural pipe-table headers, column paths and conservative merged labels."""
from __future__ import annotations

import json
import re

TABLE_MARKER = "⟦RAG_V2_TABLE⟧"


def cells(line):
    values = line.strip().split("|")
    if line.strip().startswith("|") and line.strip().endswith("|"):
        values = values[1:-1]
    return [value.strip() for value in values]


def _header(values):
    text = " ".join(values)
    letters = sum(c.isalpha() for c in text)
    digits = sum(c.isdigit() for c in text)
    return letters > digits and not any(re.match(r"\d", v) for v in values)


def table_contexts(text):
    """Map source line offsets to (header path, inherited labels).

    Text without numeric data may be a table of labels; it remains quotable but
    cannot create numeric facts. Empty numeric cells are never forward-filled.
    """
    result, headers, prior, active, offset = {}, [], [], False, 0
    for line in text.splitlines(keepends=True):
        if "|" not in line:
            # Group labels between rows keep a schema; an empty line ends it.
            if not line.strip():
                headers, prior, active = [], [], False
            offset += len(line)
            continue
        values = cells(line)
        separator = all(not v or re.fullmatch(r"[:\- ]+", v) for v in values)
        if separator:
            offset += len(line)
            continue
        is_header = _header(values)
        if is_header:
            if active or (headers and len(headers) != len(values)):
                headers, prior = [], []
            if not headers:
                headers = values
            else:
                # Empty top cells are explicit horizontal spans only when their
                # lower tier supplies a label. Keep blank identifier cells blank.
                top = ""
                merged = []
                for parent, child in zip(headers, values):
                    top = parent or top
                    merged.append(" / ".join(dict.fromkeys(v for v in (parent or (top if child else ""), child) if v)))
                headers = merged
            active = False
            result[offset] = (" | ".join(headers), {})
        else:
            result[offset] = ("", {})
            if headers and len(values) == len(headers):
                inherited = {}
                if len(prior) == len(values):
                    for i, value in enumerate(values):
                        if not value and prior[i] and re.search(r"chương trình|ngành|tên|đối tượng|nhóm", headers[i], re.I):
                            inherited[str(i)] = prior[i]
                prior = [value or inherited.get(str(i), "") for i, value in enumerate(values)]
                result[offset] = (" | ".join(headers), inherited)
            active = True
        offset += len(line)
    return result


def encode_inheritance(values):
    return TABLE_MARKER + json.dumps(values, ensure_ascii=False, separators=(",", ":")) if values else ""


def inherited_cells(context):
    for line in context.splitlines():
        if line.startswith(TABLE_MARKER):
            try:
                values = json.loads(line[len(TABLE_MARKER):])
                return values if isinstance(values, dict) else {}
            except ValueError:
                return {}
    return {}
