"""P2: a student reports "missing information" and agrees to send the question, with personal data hidden.

What is kept: the redacted question, the time, an expiry 90 days later and a hash of a delete code the student receives.
NOT kept: who reported, which conversation, the answer. Because nothing links a report to a person, the delete code is the only way
for a student to withdraw it. A question that still looks personal after redaction is counted but its text is dropped.
"""
from __future__ import annotations

import hashlib
import re
import secrets
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from campus247.application.knowledge.crawl.pii import CCCD, EMAIL, PHONE, _fold

CONSENT_VERSION = "p2-2026-11-21"
RETENTION = timedelta(days=90)
MIN_QUESTION, MAX_QUESTION = 3, 500
DAILY_LIMIT = 200  # across everyone: a per-student limit would need to know who they are
HIDDEN = "[đã ẩn]"
LONG_NUMBER = re.compile(r"(?<!\d)\d{6,}(?!\d)")
ID_LIKE = re.compile(r"\b[A-Za-z]{1,4}[ -]?\d{5,}\b")


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


def redact(text: str) -> str | None:
    """The text with phones, emails, identity numbers and long numbers hidden; None when it contains something like a student code."""
    if ID_LIKE.search(text):  # a prefix plus digits looks like a student code: keep no text at all
        return None
    result = EMAIL.sub(HIDDEN, text)
    result = CCCD.sub(HIDDEN, result)
    result = PHONE.sub(HIDDEN, result)
    result = LONG_NUMBER.sub(HIDDEN, result)
    return result


@dataclass(frozen=True)
class Receipt:
    report_id: int
    delete_code: str
    question: str | None
    text_kept: bool
    expires_at: str


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


class GapReportStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        with closing(self._connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS gap_reports(id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, expires_at TEXT NOT NULL,
                          question_redacted TEXT, consent_version TEXT NOT NULL, code_hash TEXT NOT NULL UNIQUE)""")
            db.execute("CREATE INDEX IF NOT EXISTS gap_reports_expiry ON gap_reports(expires_at)")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def submit(self, question: str, *, at: datetime | None = None) -> Receipt:
        """Store one report. ValueError: question length. OverflowError: today's limit reached."""
        text = question.strip()
        if not MIN_QUESTION <= len(text) <= MAX_QUESTION:
            raise ValueError("question length")
        moment = at or datetime.now(UTC)
        kept = redact(text)
        code = secrets.token_urlsafe(18)
        expires = _stamp(moment + RETENTION)
        with closing(self._connect()) as db, db:
            db.execute("DELETE FROM gap_reports WHERE expires_at <= ?", (_stamp(moment),))
            today = db.execute("SELECT COUNT(*) FROM gap_reports WHERE at >= ?", (_stamp(moment - timedelta(days=1)),)).fetchone()[0]
            if today >= DAILY_LIMIT:
                raise OverflowError("daily limit")
            row = db.execute("INSERT INTO gap_reports(at, expires_at, question_redacted, consent_version, code_hash) VALUES (?,?,?,?,?)",
                             (_stamp(moment), expires, kept, CONSENT_VERSION, _hash(code)))
        return Receipt(report_id=row.lastrowid, delete_code=code, question=kept, text_kept=kept is not None, expires_at=expires)

    def delete(self, delete_code: str) -> bool:
        with closing(self._connect()) as db, db:
            return db.execute("DELETE FROM gap_reports WHERE code_hash = ?", (_hash(delete_code),)).rowcount > 0

    def purge(self, *, now: datetime) -> int:
        with closing(self._connect()) as db, db:
            return db.execute("DELETE FROM gap_reports WHERE expires_at <= ?", (_stamp(now),)).rowcount

    def total(self, *, now: datetime) -> int:
        with closing(self._connect()) as db:
            return db.execute("SELECT COUNT(*) FROM gap_reports WHERE expires_at > ?", (_stamp(now),)).fetchone()[0]

    def samples(self, *, now: datetime, limit: int = 50) -> list[dict[str, Any]]:
        with closing(self._connect()) as db:
            rows = db.execute("""SELECT id, at, expires_at, question_redacted FROM gap_reports
                                 WHERE expires_at > ? AND question_redacted IS NOT NULL ORDER BY at DESC, id DESC LIMIT ?""", (_stamp(now), limit)).fetchall()
        return [{"id": r[0], "at": r[1], "expires_at": r[2], "question": r[3]} for r in rows]


SAME_QUESTION = 0.6  # share of words two questions must have in common (Jaccard) to land in one group


def _words(text: str) -> frozenset[str]:
    return frozenset(w for w in re.findall(r"[a-z0-9]+", _fold(text)) if len(w) > 1 or w == "o")


def group_samples(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group questions that share most of their words, ignoring accents and case. Cheap and deterministic: no model is called.

    The most recent question represents its group. Biggest group first, then the most recently reported.
    """
    groups: list[dict[str, Any]] = []
    for sample in sorted(samples, key=lambda s: (s["at"], s["id"]), reverse=True):
        words = _words(sample["question"])
        for group in groups:
            union = words | group["_words"]
            if union and len(words & group["_words"]) / len(union) >= SAME_QUESTION:
                group["ids"].append(sample["id"])
                break
        else:
            groups.append({"question": sample["question"], "ids": [sample["id"]], "last_at": sample["at"], "_words": words})
    for group in groups:
        group["count"] = len(group["ids"])
        del group["_words"]
    groups.sort(key=lambda g: (g["count"], g["last_at"]), reverse=True)
    return groups
