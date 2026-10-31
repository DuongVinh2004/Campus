"""Independent provenance and character-union coverage checks."""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from campus247.rag_v2.ingest.units import source_text
from campus247.rag_v2.types import Unit


@dataclass(frozen=True)
class Issue:
    code: str
    chunk_id: str = ""
    unit_id: str = ""
    detail: str = ""


def _inspect(chunks, units):
    rows = {str(c["chunk_id"]): c for c in chunks}
    masks = {key: bytearray(len(c.get("content_text", c.get("text", "")))) for key, c in rows.items()}
    issues, seen = [], set()
    for unit in units:
        body = source_text(unit)
        if not body.strip():
            issues.append(Issue("EMPTY_UNIT", unit_id=unit.unit_id))
        if unit.unit_id in seen:
            issues.append(Issue("DUPLICATE_UNIT_ID", unit_id=unit.unit_id))
        seen.add(unit.unit_id)
        if not unit.chunk_ids:
            issues.append(Issue("MISSING_CHUNK_IDS", unit_id=unit.unit_id))
        for key in unit.chunk_ids:
            row = rows.get(key)
            if row is None:
                issues.append(Issue("UNKNOWN_CHUNK", key, unit.unit_id))
                continue
            if row["document_id"] != unit.document_id or row["version_id"] != unit.version_id:
                issues.append(Issue("SOURCE_IDENTITY_MISMATCH", key, unit.unit_id))
                continue
            text = row.get("content_text", row.get("text", ""))
            pos = text.find(body) if body else -1
            if pos < 0:
                issues.append(Issue("NON_VERBATIM_UNIT", key, unit.unit_id))
                continue
            # All occurrences, including overlapping repeated source fragments.
            while pos >= 0:
                masks[key][pos:pos + len(body)] = b"\1" * len(body)
                pos = text.find(body, pos + 1)
    coverage = {}
    for key, row in rows.items():
        text = row.get("content_text", row.get("text", ""))
        meaningful = [i for i, c in enumerate(text) if c.isalnum()]
        covered = sum(masks[key][i] for i in meaningful)
        ratio = covered / len(meaningful) if meaningful else 1.0
        coverage[key] = (covered, len(meaningful), ratio)
        if ratio < .98:
            issues.append(Issue("LOW_COVERAGE", key, detail=f"{ratio:.6f}"))
    return rows, issues, coverage


def check_units(chunks: Iterable[dict], units: Iterable[Unit]) -> list[Issue]:
    return _inspect(chunks, units)[1]


def coverage_stats(chunks: Iterable[dict], units: Iterable[Unit]) -> dict:
    units = list(units)
    rows, _, coverage = _inspect(chunks, units)
    families = defaultdict(list)
    for key, row in rows.items():
        families[row.get("doc_family", "khac")].append(coverage[key])
    counts = Counter(u.doc_family for u in units)
    return {family: {"chunks": len(values), "units": counts[family],
                     "meaningful_chars": sum(v[1] for v in values),
                     "covered_chars": sum(v[0] for v in values),
                     "coverage": sum(v[0] for v in values) / max(1, sum(v[1] for v in values)),
                     "min_chunk_coverage": min(v[2] for v in values)}
            for family, values in sorted(families.items())}
