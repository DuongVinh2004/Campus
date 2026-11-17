"""Which knowledge sources are behind answers people mark "not helpful"?

Every rating on an answer is counted once per source that answer cited. What is kept: the rating, the source version id and the
time. NOT kept: who rated, which conversation, the question, the answer or the comment. Because of that, a question that was
refused (no citations) says nothing about which source is missing; that needs the person's own consent and is a separate decision.

The numbers point a manager at sources to read again. They are not a verdict on a source: a few people can dislike a correct answer.
A source is listed only after a minimum number of ratings.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

RETENTION = timedelta(days=180)
MIN_VOTES = 3


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


class AnswerQualityStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        with closing(self._connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS answer_ratings(id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, version_id TEXT NOT NULL,
                          helpful INTEGER NOT NULL CHECK (helpful IN (0, 1)))""")
            db.execute("CREATE INDEX IF NOT EXISTS answer_ratings_version ON answer_ratings(version_id, at)")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def record(self, *, helpful: bool, version_ids: list[str], at: datetime | None = None) -> int:
        """Count one rating for each distinct cited version. Returns how many rows were written (0 for an answer without citations)."""
        unique = sorted({v for v in version_ids if isinstance(v, str) and 0 < len(v) <= 64})
        if not unique:
            return 0
        moment = at or datetime.now(UTC)
        with closing(self._connect()) as db, db:
            db.executemany("INSERT INTO answer_ratings(at, version_id, helpful) VALUES (?,?,?)", [(_stamp(moment), v, int(helpful)) for v in unique])
            db.execute("DELETE FROM answer_ratings WHERE at < ?", (_stamp(moment - RETENTION),))  # this table's own old rows only
        return len(unique)

    def report(self, *, now: datetime, days: int = 30, min_votes: int = MIN_VOTES) -> dict[str, Any]:
        since = now - timedelta(days=days)
        with closing(self._connect()) as db:
            rows = db.execute("""SELECT version_id, SUM(helpful), SUM(1 - helpful) FROM answer_ratings WHERE at >= ? GROUP BY version_id""", (_stamp(since),)).fetchall()
        sources = [{"version_id": version, "helpful": int(good), "not_helpful": int(bad), "share_not_helpful": round(int(bad) / (int(good) + int(bad)), 3)}
                   for version, good, bad in rows if int(good) + int(bad) >= min_votes]
        sources.sort(key=lambda s: (-s["share_not_helpful"], -s["not_helpful"], s["version_id"]))
        return {"since": _stamp(since), "days": days, "minimum_votes": min_votes, "ratings": sum(int(g) + int(b) for _, g, b in rows), "sources": sources}


def attach_quality_recording(feedback_service, store: AnswerQualityStore, *, on_error: Callable[[Exception], None] = lambda error: None) -> None:
    """Make the feedback service count each saved rating per cited source. A failure here never fails the person's feedback."""
    original = feedback_service.record_feedback

    async def record_feedback(*args, **kwargs):
        receipt = await original(*args, **kwargs)
        try:
            store.record(helpful=receipt.rating.value == "HELPFUL", version_ids=list(receipt.answer_reference.source_document_version_ids or []))
        except Exception as error:  # noqa: BLE001 -- the statistics are secondary to the feedback itself
            on_error(error)
        return receipt

    feedback_service.record_feedback = record_feedback


async def titled_report(store: AnswerQualityStore, freshness_service, *, now: datetime, days: int = 30) -> dict[str, Any]:
    """The report with each source's title and unit, for the versions in the current release (others are shown by id only)."""
    report = store.report(now=now, days=days)
    titles = {row["version_id"]: row for row in await freshness_service.current_rows()}
    for source in report["sources"]:
        known = titles.get(source["version_id"])
        source["title"], source["owner_unit"], source["in_current_release"] = (known["title"], known["owner_unit"], True) if known else (None, None, False)
    return report
