"""Which knowledge sources are behind answers people mark "not helpful"?

Every rating on an answer is counted once per source that answer cited. What is kept: the rating, the source version id and the
time. NOT kept: who rated, which conversation, the question, the answer or the comment. Because of that, a question that was
refused (no citations) says nothing about which source is missing; that needs the person's own consent and is a separate decision.

The numbers point a manager at sources to read again. They are not a verdict on a source: a few people can dislike a correct answer.
A source is listed only after a minimum number of ratings.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

RETENTION = timedelta(days=180)
MIN_VOTES = 3
MIN_GAP_COUNT = 3
GAP_ACTIONS = ("NEEDS_SOURCE", "SOURCE_OUTDATED", "OUT_OF_SCOPE", "RESOLVED")
REASON_PATTERN = re.compile(r"^[a-z_]{1,32}$")


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


class AnswerQualityStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        with closing(self._connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS answer_ratings(id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, version_id TEXT NOT NULL,
                          helpful INTEGER NOT NULL CHECK (helpful IN (0, 1)))""")
            db.execute("CREATE INDEX IF NOT EXISTS answer_ratings_version ON answer_ratings(version_id, at)")
            # Refused answers: which sources the refusal pointed at and why. No person, conversation, question or answer is stored.
            db.execute("""CREATE TABLE IF NOT EXISTS answer_gaps(id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, reason TEXT NOT NULL,
                          cluster_key TEXT NOT NULL, version_ids TEXT NOT NULL)""")
            db.execute("CREATE INDEX IF NOT EXISTS answer_gaps_cluster ON answer_gaps(cluster_key, at)")
            db.execute("""CREATE TABLE IF NOT EXISTS answer_gap_decisions(cluster_key TEXT PRIMARY KEY, at TEXT NOT NULL, action TEXT NOT NULL,
                          note TEXT NOT NULL, release_ref TEXT NOT NULL, actor TEXT NOT NULL)""")

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

    @staticmethod
    def _cluster_key(reason: str, version_ids: list[str]) -> str:
        return hashlib.sha1(json.dumps([reason, sorted(version_ids[:3])]).encode()).hexdigest()  # noqa: S324 -- an identifier, not a secret

    def record_gap(self, *, reason: str, version_ids: list[str], at: datetime | None = None) -> int:
        """Count one refusal. `version_ids` are the sources it pointed at, strongest first (may be empty). Returns 1 if recorded, else 0."""
        if not isinstance(reason, str) or not REASON_PATTERN.match(reason):
            return 0
        unique: list[str] = []
        for value in version_ids:
            if isinstance(value, str) and 0 < len(value) <= 64 and value not in unique:
                unique.append(value)
        unique = unique[:5]
        moment = at or datetime.now(UTC)
        with closing(self._connect()) as db, db:
            db.execute("INSERT INTO answer_gaps(at, reason, cluster_key, version_ids) VALUES (?,?,?,?)",
                       (_stamp(moment), reason, self._cluster_key(reason, unique), json.dumps(unique)))
            db.execute("DELETE FROM answer_gaps WHERE at < ?", (_stamp(moment - RETENTION),))
        return 1

    def gaps_report(self, *, now: datetime, days: int = 30, min_count: int = MIN_GAP_COUNT) -> dict[str, Any]:
        since = now - timedelta(days=days)
        week, two_weeks = _stamp(now - timedelta(days=7)), _stamp(now - timedelta(days=14))
        with closing(self._connect()) as db:
            rows = db.execute("SELECT at, reason, cluster_key, version_ids FROM answer_gaps WHERE at >= ? ORDER BY at", (_stamp(since),)).fetchall()
            previous = db.execute("SELECT cluster_key, COUNT(*) FROM answer_gaps WHERE at >= ? AND at < ? GROUP BY cluster_key", (two_weeks, week)).fetchall()
            decisions = {row[0]: row for row in db.execute("SELECT cluster_key, at, action, note, release_ref, actor FROM answer_gap_decisions")}
        before = dict(previous)
        grouped: dict[str, dict[str, Any]] = {}
        for at, reason, key, versions in rows:
            group = grouped.setdefault(key, {"cluster_key": key, "reason": reason, "version_ids": sorted(json.loads(versions)[:3]),
                                             "count": 0, "count_7d": 0, "last_at": at})
            group["count"] += 1
            group["count_7d"] += at >= week
            group["last_at"] = max(group["last_at"], at)
        clusters = []
        for key, group in grouped.items():
            if group["count"] < min_count:
                continue
            group["previous_7d"] = int(before.get(key, 0))
            group["is_new_trend"] = group["count_7d"] >= MIN_GAP_COUNT and group["count_7d"] > 1.5 * group["previous_7d"]
            decision = decisions.get(key)
            group["decision"] = ({"at": decision[1], "action": decision[2], "note": decision[3], "release_ref": decision[4], "actor": decision[5]}
                                 if decision else None)
            clusters.append(group)
        clusters.sort(key=lambda g: (-g["count_7d"], -g["count"], g["cluster_key"]))
        return {"since": _stamp(since), "days": days, "minimum_count": min_count, "clusters": clusters}

    def decide(self, cluster_key: str, *, action: str, note: str, release_ref: str, actor: str, at: datetime | None = None) -> None:
        """Remember what a manager decided about a cluster. ValueError: bad action, note or no release for RESOLVED. LookupError: unknown cluster."""
        if action not in GAP_ACTIONS or not isinstance(note, str) or not 1 <= len(note.strip()) <= 500 or len(release_ref) > 100:
            raise ValueError("invalid decision")
        if action == "RESOLVED" and not release_ref.strip():
            raise ValueError("a resolved cluster needs the release that changed")
        with closing(self._connect()) as db, db:
            if db.execute("SELECT 1 FROM answer_gaps WHERE cluster_key = ? LIMIT 1", (cluster_key,)).fetchone() is None:
                raise LookupError("unknown cluster")
            db.execute("""INSERT INTO answer_gap_decisions(cluster_key, at, action, note, release_ref, actor) VALUES (?,?,?,?,?,?)
                          ON CONFLICT(cluster_key) DO UPDATE SET at=excluded.at, action=excluded.action, note=excluded.note,
                          release_ref=excluded.release_ref, actor=excluded.actor""",
                       (cluster_key, _stamp(at or datetime.now(UTC)), action, note.strip(), release_ref.strip(), actor))

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


def attach_gap_recording(store: AnswerQualityStore, *, on_error: Callable[[Exception], None] = lambda error: None) -> None:
    """Count each refused answer under the sources it pointed at. Safe to call twice; a failure here never affects the answer."""
    from campus247.agent.nodes import rag_v2

    for existing in rag_v2.OUTCOME_OBSERVERS:
        if getattr(existing, "gap_store", None) is store:
            return

    def observe(outcome, rows) -> None:
        if outcome.kind != "refuse":
            return
        try:
            versions = [rows[citation.chunk_ids[0]]["document_version_id"] for citation in outcome.citations]
            store.record_gap(reason=outcome.reason or "unspecified", version_ids=versions)
        except Exception as error:  # noqa: BLE001 -- the statistics are secondary to the answer
            on_error(error)

    observe.gap_store = store  # type: ignore[attr-defined]
    rag_v2.OUTCOME_OBSERVERS.append(observe)
