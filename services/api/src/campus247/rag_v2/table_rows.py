"""Answer from the rows of a table directly when the question names a scope the table is not written along.

A table is written along some dimensions: programme and cohort, room type, course and cohort. A question may name another one
("học phí ngành X" against a fee table by programme). No row carries that name, so nothing can be picked by it, but every row that applies to
the cohort and year the question gives is a correct, complete answer, and writing them out is not a model's job: each row is rendered as
"column: cell" pairs taken verbatim from the source and checked like any other statement. The caller says the table is not split by the name.
Nothing here knows what a fee, a major or a programme is.
"""
from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from campus247.rag_v2.ingest.tables import cells as table_cells
from campus247.rag_v2.ingest.units import context_text, source_text
from campus247.rag_v2.retrieval.hybrid import scope_allows
from campus247.rag_v2.types import Statement, Unit
from campus247.rag_v2.understanding.normalize import fold

MAX_ROWS = 8


def header_line(unit: Unit) -> str:
    return next((line for line in context_text(unit).splitlines() if "|" in line), "")


def _is_row(unit: Unit) -> bool:
    return unit.kind == "table_row" and bool(header_line(unit)) and "|" in source_text(unit)


def table_key(unit: Unit) -> tuple[str, str]:
    return unit.document_id, header_line(unit)


def sibling_rows(seeds: list[Unit], index: Any) -> dict[tuple[str, str], list[Unit]]:
    """Every row of the tables the seed units belong to (same document, same header)."""
    wanted = {table_key(unit) for unit in seeds if _is_row(unit)}
    if not wanted:
        return {}
    tables: dict[tuple[str, str], list[Unit]] = {key: [] for key in wanted}
    for unit_id in index.all_ids():
        unit = index.get(unit_id)
        if unit is not None and _is_row(unit) and table_key(unit) in tables:
            tables[table_key(unit)].append(unit)
    return tables


def rows_of_chunks(chunk_ids: set[str], index: Any) -> list[Unit]:
    """The table-row units that were cut from the given source chunks (the chunks the generator read)."""
    found = []
    for unit_id in index.all_ids():
        unit = index.get(unit_id)
        if unit is not None and _is_row(unit) and chunk_ids.intersection(unit.chunk_ids):
            found.append(unit)
    return found


def row_pairs(unit: Unit) -> list[tuple[str, str]]:
    """(column, cell) pairs of the row, skipping the running number and empty cells."""
    names = table_cells(header_line(unit))
    values = table_cells(next((line for line in source_text(unit).splitlines() if "|" in line), ""))
    if len(names) != len(values):
        return []
    return [(n, v) for n, v in zip(names, values) if n and v and not re.fullmatch(r"(?i)stt|tt|#", n.strip())]


def row_sentence(unit: Unit) -> str | None:
    pairs = row_pairs(unit)
    return "; ".join(f"{name}: {value}" for name, value in pairs) + "." if len(pairs) >= 2 else None


def carries_term(rows: list[Unit], terms: tuple[str, ...]) -> bool:
    text = fold("\n".join(source_text(row) for row in rows))
    return any(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text) for term in terms)


def answer_rows(u: Any, tables: dict[tuple[str, str], list[Unit]], seed_ids: list[str]) -> tuple[list[Unit], list[Statement]]:
    """The rows (and their sentences) to show: the first table, in seed order, that is not split by any scope name of the question
    and has rows applying to the cohort and year asked. Empty when no table qualifies."""
    if not u.scope_terms:
        return [], []
    if any(carries_term(rows, u.scope_terms) for rows in tables.values()):
        return [], []  # some table found IS written along that name: the normal path answers from its matching row
    return general_rows(u, tables, seed_ids)


def general_rows(u: Any, tables: dict[tuple[str, str], list[Unit]], seed_ids: list[str]) -> tuple[list[Unit], list[Statement]]:
    """Like answer_rows, but for the first table that does not carry the name even when another table does: the rows of a general
    table that complete a general answer the normal path only partly wrote."""
    order = []
    for unit_id in seed_ids:
        for key, rows in tables.items():
            if any(row.unit_id == unit_id for row in rows) and key not in order:
                order.append(key)
    probe = replace(u, program=None)
    for key in order:
        rows = tables[key]
        if carries_term(rows, u.scope_terms):
            continue
        applying = [row for row in rows if (u.cohort or u.academic_year) and scope_allows(probe, row)
                    and (not u.cohort or row.scope.cohorts or re.search(r"\bK\d{2}\b", source_text(row)))
                    and row_sentence(row)]
        if 1 <= len(applying) <= MAX_ROWS:
            applying.sort(key=lambda row: row.unit_id)
            return applying, [Statement(row_sentence(row), (row.unit_id,)) for row in applying]
    return [], []
