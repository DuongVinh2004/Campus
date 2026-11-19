"""Freshness of the sources in the current release: when each one is due for a look, and who last looked.

Reads the release pointer, never writes to the knowledge database. The only thing written is a human's note that a source was
reviewed, kept in its own small SQLite file next to the other stores. Dates go through `assess_freshness`; nothing here
changes what retrieval returns.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from campus247.application.knowledge.source_freshness import Freshness, assess_freshness

# Columns used here are all defined by migrations 0002, 0015 and 0018. The disposition table is optional (older databases).
CURRENT_SOURCES_SQL = """
SELECT s.id::text AS source_id, s.title, s.owner_unit, v.id::text AS version_id, v.version_label,
       v.effective_from, v.effective_until, v.published_at, v.created_at,
       COALESCE(d.category = 'SOURCE_SCOPE_UNRESOLVED', false) AS applicability_unknown
FROM knowledge_release_pointer p
JOIN knowledge_release_member m ON m.release_id = p.release_id
JOIN knowledge_source s ON s.id = m.source_id
JOIN document_version v ON v.id = m.version_id
LEFT JOIN LATERAL (SELECT category FROM knowledge_source_disposition x
                   WHERE x.tenant_id = p.tenant_id AND x.source_id = s.id
                   ORDER BY x.created_at DESC, x.id DESC LIMIT 1) d ON true
WHERE p.tenant_id = $1 AND p.campus_id = $2 AND NOT s.is_synthetic
ORDER BY s.title
"""
CURRENT_SOURCES_SQL_NO_DISPOSITION = CURRENT_SOURCES_SQL.replace(
    "COALESCE(d.category = 'SOURCE_SCOPE_UNRESOLVED', false)", "false").replace(
    """LEFT JOIN LATERAL (SELECT category FROM knowledge_source_disposition x
                   WHERE x.tenant_id = p.tenant_id AND x.source_id = s.id
                   ORDER BY x.created_at DESC, x.id DESC LIMIT 1) d ON true
""", "")

STATE_CACHE_TTL = timedelta(minutes=5)
SEVERITY = {Freshness.EXPIRED: 0, Freshness.OVERDUE: 1, Freshness.DUE_SOON: 2, Freshness.OK: 3}


class SourceReviewStore:
    """Who confirmed that a source is still right, and when. One row per confirmation; never edited."""

    def __init__(self, path: Path) -> None:
        self.path = path
        with closing(self._connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS source_reviews(
                id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT NOT NULL, reviewer_id TEXT NOT NULL,
                reviewed_at TEXT NOT NULL, note TEXT NOT NULL)""")
            db.execute("CREATE INDEX IF NOT EXISTS source_reviews_source ON source_reviews(source_id, reviewed_at)")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def record(self, source_id: str, reviewer_id: str, note: str, *, at: datetime | None = None) -> dict[str, Any]:
        note = note.strip()
        if not 10 <= len(note) <= 1000:
            raise ValueError("note must be between 10 and 1000 characters")
        stamp = (at or datetime.now(UTC)).astimezone(UTC).isoformat().replace("+00:00", "Z")
        with closing(self._connect()) as db, db:
            db.execute("INSERT INTO source_reviews(source_id, reviewer_id, reviewed_at, note) VALUES (?,?,?,?)",
                       (source_id, reviewer_id, stamp, note))
        return {"source_id": source_id, "reviewed_at": stamp}

    def latest(self) -> dict[str, dict[str, Any]]:
        with closing(self._connect()) as db:
            rows = db.execute("""SELECT source_id, reviewer_id, MAX(reviewed_at), note FROM source_reviews GROUP BY source_id""").fetchall()
        return {source_id: {"reviewer_id": reviewer, "reviewed_at": at, "note": note} for source_id, reviewer, at, note in rows}


def _aware(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def assess_rows(rows: list[dict[str, Any]], reviews: dict[str, dict[str, Any]], *, now: datetime) -> list[dict[str, Any]]:
    """Join the release rows with the review notes and judge each source; most urgent first, then by title."""
    items = []
    for row in rows:
        review = reviews.get(row["source_id"])
        result = assess_freshness(now=now, effective_from=_aware(row.get("effective_from")), effective_until=_aware(row.get("effective_until")),
                                  published_at=_aware(row.get("published_at")) or _aware(row.get("created_at")),
                                  last_reviewed_at=_aware(review["reviewed_at"]) if review else None,
                                  applicability_unknown=bool(row.get("applicability_unknown")))
        items.append({"source_id": row["source_id"], "version_id": row["version_id"], "title": row["title"], "owner_unit": row["owner_unit"],
                      "version_label": row.get("version_label"), "state": result.state.value,
                      "due_at": result.due_at.isoformat().replace("+00:00", "Z") if result.due_at else None,
                      "reason": result.reason.value if result.reason else None, "days_left": result.days_left,
                      "applicability_unknown": result.applicability_unknown,
                      "last_review": {"reviewed_at": review["reviewed_at"], "note": review["note"]} if review else None})
    return sorted(items, key=lambda item: (SEVERITY[Freshness(item["state"])], item["days_left"] if item["days_left"] is not None else 10**9, item["title"]))


def summary(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {state.value: 0 for state in Freshness}
    for item in items:
        counts[item["state"]] += 1
    counts["applicability_unknown"] = sum(1 for item in items if item["applicability_unknown"])
    return counts


class FreshnessService:
    def __init__(self, pool, reviews: SourceReviewStore, *, tenant: str, campus: str = "HUCE") -> None:
        self._pool, self._reviews, self._tenant, self._campus = pool, reviews, tenant, campus
        self._state_cache: tuple[datetime, dict[str, str]] | None = None

    async def current_rows(self) -> list[dict[str, Any]]:
        async with self._pool.acquire() as conn:
            has_dispositions = await conn.fetchval("SELECT to_regclass('knowledge_source_disposition') IS NOT NULL")
            sql = CURRENT_SOURCES_SQL if has_dispositions else CURRENT_SOURCES_SQL_NO_DISPOSITION
            return [dict(row) for row in await conn.fetch(sql, self._tenant, self._campus)]

    async def review_states(self, source_ids: list[str], *, now: datetime | None = None) -> dict[str, str]:
        """State (OK, DUE_SOON, OVERDUE, EXPIRED) of each requested source of the current release; others are left out.

        Readers see only this label next to a citation. The judgement is cached for a few minutes so a busy chat does not
        query the knowledge database for every citation; a recorded review clears the cache."""
        now = now or datetime.now(UTC)
        if self._state_cache is None or now - self._state_cache[0] >= STATE_CACHE_TTL or now < self._state_cache[0]:
            items = assess_rows(await self.current_rows(), self._reviews.latest(), now=now)
            self._state_cache = (now, {item["source_id"]: item["state"] for item in items})
        states = self._state_cache[1]
        return {source_id: states[source_id] for source_id in source_ids if source_id in states}

    async def report(self, *, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(UTC)
        items = assess_rows(await self.current_rows(), self._reviews.latest(), now=now)
        return {"generated_at": now.isoformat().replace("+00:00", "Z"), "summary": summary(items), "items": items}

    async def mark_reviewed(self, source_id: str, reviewer_id: str, note: str) -> dict[str, Any]:
        """Record that a person looked at a source of the current release. Unknown ids are refused, not stored."""
        if source_id not in {row["source_id"] for row in await self.current_rows()}:
            raise LookupError("source is not in the current release")
        recorded = self._reviews.record(source_id, reviewer_id, note)
        self._state_cache = None
        return recorded
