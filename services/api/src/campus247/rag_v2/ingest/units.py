"""Lossless structural slicing. Context is explicitly outside the quotable body."""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import replace
from hashlib import sha256

from campus247.rag_v2.types import Scope, Unit
from campus247.rag_v2.ingest.tables import encode_inheritance, table_contexts

CONTEXT_START = "⟦RAG_V2_CONTEXT⟧\n"
SOURCE_SEPARATOR = "\n⟦RAG_V2_SOURCE⟧\n"
SPLITTER_VERSION = "structural-spans-v2"
SPAN = re.compile(r"⟦RAG_V2_SPAN:(\d+):(\d+)⟧")
_ARTICLE = re.compile(r"^\s*Điều\s+(\d+)\s*[.:]?\s*", re.IGNORECASE)
_CLAUSE = re.compile(r"^\s*(\d+)[.)]\s+")
_POINT = re.compile(r"^\s*([a-zđ])[)]\s+", re.IGNORECASE)
_SECTION = re.compile(r"^\s*(?:\d+(?:\.\d+)+\.?|[IVX]+[.)])\s+\S")
_COURSE = re.compile(r"^\s*\d{6}[a-z]?\s*[–—-]\s*\d", re.IGNORECASE)


def source_text(unit: Unit) -> str:
    """The only part eligible for quotations and source coverage checks."""
    if unit.text.startswith(CONTEXT_START) and SOURCE_SEPARATOR in unit.text:
        return unit.text.split(SOURCE_SEPARATOR, 1)[1]
    return unit.text


def context_text(unit: Unit) -> str:
    if unit.text.startswith(CONTEXT_START) and SOURCE_SEPARATOR in unit.text:
        return unit.text[len(CONTEXT_START):].split(SOURCE_SEPARATOR, 1)[0]
    return ""


def extract_scope(text: str) -> Scope:
    cohorts = set(re.findall(r"\bK\d{2}\b", text, re.IGNORECASE))
    for start, end in re.findall(r"\bK(\d{2})\s*(?:đến|[-–—])\s*K(\d{2})\b", text, re.IGNORECASE):
        if 0 <= int(end) - int(start) <= 15:
            cohorts.update(f"K{i}" for i in range(int(start), int(end) + 1))
    return Scope(tuple(sorted(c.upper() for c in cohorts)),
                 tuple(sorted(set(re.findall(r"\b7\d{6}\b", text)))),
                 tuple(sorted({re.sub(r"\s*[–—-]\s*", "-", y) for y in
                               re.findall(r"(?<!\d)20\d{2}\s*[–—-]\s*20\d{2}(?!\d)", text)})))


def _pieces(text: str, limit: int):
    """Keep contiguous spans; prefer paragraphs/sentences, then word boundaries."""
    start = 0
    while len(text) - start > limit:
        window = text[start:start + limit + 1]
        breaks = [m.end() for m in re.finditer(r"\n\s*\n|[.!?;]\s+|\n", window)]
        end = max((b for b in breaks if limit // 3 <= b <= limit), default=0)
        if not end:
            end = window.rfind(" ", limit // 3, limit + 1)
        if end <= 0:
            end = limit
        yield start, text[start:start + end]
        start += end
    if text[start:]:
        yield start, text[start:]


def _segments(chunk: dict):
    text = chunk.get("content_text", chunk.get("text", ""))
    family = chunk.get("doc_family", "khac")
    section = chunk.get("section_label") or ""
    article = ""
    article_name = ""
    clause = ""
    header = ""
    table_group = ""
    row_context = ""
    item_context = ""
    inherited = re.search(r"Điều\s+\d+\b", section, re.IGNORECASE)
    if inherited:
        article_name = inherited.group()
        article = section
    current = None
    start = 0
    offset = 0
    tables = table_contexts(text)
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        a, c, p = _ARTICLE.match(line), _CLAUSE.match(line), _POINT.match(line)
        new = None
        if re.match(r"\s*STT\s+\S", line, re.IGNORECASE) and "|" not in line:
            header = stripped
            new = ("table_row", f"{section} > Tiêu đề bảng", header)
        elif a:
            article_name = f"Điều {a[1]}"
            article, clause = stripped, ""
            new = ("article", article_name, article)
        elif article_name and c:
            clause = f"Khoản {c[1]}"
            new = ("clause", f"{article_name} > {clause}", article)
        elif article_name and p:
            new = ("clause", " > ".join(filter(None, (article_name, clause, f"Điểm {p[1]}"))), article)
        elif "|" in line:
            inherited = ""
            if offset in tables:
                header, values = tables[offset]
                inherited = encode_inheritance(values)
            new = ("table_row", f"{section} > Dòng {offset}", "\n".join(filter(None, (header, table_group, inherited))))
            row_context = stripped if re.search(r"phụ thu", line, re.IGNORECASE) else ""
        elif _SECTION.match(line):
            item_context = stripped
            if re.match(r"\s*[IVX]+[.)]", line):
                table_group = stripped
            new = ("table_row" if header else "handbook_section" if family == "so_tay" else "notice",
                   stripped, "\n".join(filter(None, (header, stripped))))
        elif _COURSE.match(line):
            new = ("curriculum_row", f"{section} > Học phần {stripped}", item_context)
        elif c and not article_name:
            item_context = stripped
            new = ("table_row" if header else "handbook_section" if family == "so_tay" else "notice",
                   stripped, "\n".join(filter(None, (header, stripped))))
        elif header and stripped:
            # Keep non-pipe supplementary fee rows and their grouping labels separate.
            new = ("table_row", f"{section} > Dòng {offset}", "\n".join(filter(None, (header, table_group, item_context, row_context))))
        if new is not None:
            if offset > start:
                yield start, text[start:offset], current
            start, current = offset, new
        offset += len(line)
    if offset > start:
        yield start, text[start:offset], current


def build_units(chunks: Iterable[dict]) -> list[Unit]:
    """Deterministic, input-order-independent units; identical source rows share IDs.

    Scope records literal cohort mentions (closed ranges are expanded). Open
    cohort constraints remain in source text, never silently expanded to all cohorts.
    """
    result: dict[str, Unit] = {}
    for chunk in chunks:
        text = chunk.get("content_text", chunk.get("text", ""))
        if not isinstance(text, str):
            raise TypeError("INVALID_CHUNK_TEXT")
        if SOURCE_SEPARATOR in text or text.startswith(CONTEXT_START):
            raise ValueError("RESERVED_SOURCE_MARKER")
        section = chunk.get("section_label") or ""
        title = chunk.get("doc_title", "")
        for start, body, structure in _segments(chunk):
            kind, path, context = structure or ("page", section or title, "")
            page = chunk.get("page")
            path = f"{path} > tr.{page}" if page is not None else path
            # Bound context too; complete context is still available via doc_title/path.
            context = "\n".join(dict.fromkeys(s for s in (title, context) if s))[:500]
            # Reserve room for the explicit source span; never count context as
            # source coverage or infer coverage for repeated occurrences.
            prefix_size = (len(CONTEXT_START) + len(context) + 1 + len(SOURCE_SEPARATOR)
                           + len(f"⟦RAG_V2_SPAN:{len(text)}:{len(text)}⟧"))
            for relative, piece in _pieces(body, max(100, 1200 - prefix_size)):
                if not piece.strip():
                    continue
                span = f"⟦RAG_V2_SPAN:{start + relative}:{start + relative + len(piece)}⟧"
                prefix = CONTEXT_START + context + "\n" + span + SOURCE_SEPARATOR
                locator = f"{chunk['document_id']}|{page}|{path}|{start + relative}"
                unit_id = sha256(f"{chunk['version_id']}|{locator}|{sha256(piece.encode()).hexdigest()}".encode()).hexdigest()[:16]
                unit = Unit(unit_id, (str(chunk["chunk_id"]),), str(chunk["document_id"]),
                            str(chunk["version_id"]), title, chunk.get("doc_family", "khac"),
                            kind, path, page, prefix + piece,
                            chunk.get("effective_from"), chunk.get("effective_until"),
                            extract_scope(title + "\n" + context + "\n" + piece))
                if unit_id in result:
                    prior = result[unit_id]
                    if replace(prior, chunk_ids=unit.chunk_ids) != unit:
                        raise ValueError("UNIT_ID_COLLISION")
                    unit = replace(prior, chunk_ids=tuple(sorted(set(prior.chunk_ids + unit.chunk_ids))))
                result[unit_id] = unit
    return sorted(result.values(), key=lambda u: u.unit_id)
