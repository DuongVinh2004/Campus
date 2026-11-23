"""In-app reminders before a deadline (an exam, for now), sent once each.

A reminder is a notification in the user's inbox. Each deadline has offsets (24 hours and 2 hours before by default). At every
run the closest offset that has already passed is the one delivered, and every passed offset is marked as sent, so a server that was
down for a day sends one reminder with the real time left rather than two late ones, and a restart never repeats one.
Nothing is sent for a deadline that has passed.
"""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_OFFSETS = (timedelta(hours=24), timedelta(hours=2))
try:
    VN = ZoneInfo("Asia/Ho_Chi_Minh")
except ZoneInfoNotFoundError:  # Windows runtimes without the tzdata package; Vietnam has no daylight saving, so UTC+7 is exact
    VN = timezone(timedelta(hours=7), "ICT")
SCHEMA = "CREATE TABLE IF NOT EXISTS ops_reminders_sent(key TEXT PRIMARY KEY, sent_at TEXT NOT NULL)"
PREFS_SCHEMA = """CREATE TABLE IF NOT EXISTS ops_reminder_prefs(subject_id TEXT NOT NULL, kind TEXT NOT NULL, enabled INTEGER NOT NULL,
                  updated_at TEXT NOT NULL, PRIMARY KEY(subject_id, kind))"""


@dataclass(frozen=True)
class Candidate:
    item_key: str  # stable id of the thing the deadline belongs to, for example "exam:<schedule row id>"
    recipient: str  # subject id of the person to notify
    kind: str
    deadline: datetime
    describe: Callable[[timedelta], tuple[str, str]]  # time left -> (title, body)
    link: str = ""
    offsets: tuple[timedelta, ...] = DEFAULT_OFFSETS
    pref_kind: str | None = None  # the person can switch this kind of reminder off (see reminder_prefs.py)


def _offset_label(offset: timedelta) -> str:
    return f"{int(offset.total_seconds() // 60)}m"


def _enabled(c, subject_id: str, kind: str) -> bool:
    """On unless the person switched it off."""
    row = c.execute("SELECT enabled FROM ops_reminder_prefs WHERE subject_id = ? AND kind = ?", (subject_id, kind)).fetchone()
    return True if row is None else bool(row[0])


def applicable_offsets(deadline: datetime, now: datetime, offsets: tuple[timedelta, ...]) -> list[timedelta]:
    """Offsets whose moment has come and whose deadline has not passed, farthest first."""
    if now >= deadline:
        return []
    return sorted((o for o in offsets if deadline - o <= now), reverse=True)


def time_left_text(left: timedelta) -> str:
    minutes = max(0, math.ceil(left.total_seconds() / 60))
    if minutes < 60:
        return f"{minutes} phút" if minutes > 1 else "chưa đầy 1 phút"
    hours = minutes // 60
    return f"khoảng {hours} giờ"


def deliver(store, candidates: list[Candidate], *, now: datetime) -> int:
    """Send what is due. Returns how many notifications were created. Safe to call every few minutes, from any process."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    sent = 0
    with store.tx() as c:
        c.execute(SCHEMA)
        c.execute(PREFS_SCHEMA)
        for candidate in candidates:
            due = applicable_offsets(candidate.deadline, now, candidate.offsets)
            if not due:
                continue
            if candidate.pref_kind and not _enabled(c, candidate.recipient, candidate.pref_kind):
                continue  # switched off: nothing is sent and nothing is marked, so switching it back on inside the window still works
            fresh = []
            for offset in due:
                key = f"{candidate.item_key}|{candidate.recipient}|{_offset_label(offset)}"
                if c.execute("INSERT OR IGNORE INTO ops_reminders_sent(key, sent_at) VALUES (?, ?)", (key, now.isoformat())).rowcount:
                    fresh.append(offset)
            if not fresh:
                continue  # every applicable offset was handled before
            title, body = candidate.describe(candidate.deadline - now)
            store.notify(c, candidate.recipient, candidate.kind, title, body, candidate.link)
            sent += 1
    return sent


def exit_ticket_candidates(rows: list[dict[str, Any]]) -> list[Candidate]:
    """One candidate per student who still owes an answer; `rows` come from learning.exit_reminders.open_exit_ticket_deadlines."""
    candidates = []
    for row in rows:
        def describe(left: timedelta, row: dict[str, Any] = row) -> tuple[str, str]:
            local = row["closes"].astimezone(VN)
            return (f"Phiếu ra lớp sắp đóng: {row['session_title']}",
                    f"Còn {time_left_text(left)} để nộp. Đóng lúc {local:%H:%M} ngày {local:%d/%m/%Y}.")

        for student in row["students"]:
            candidates.append(Candidate(item_key=f"exit_ticket:{row['ticket_id']}", recipient=student, kind="REMINDER", deadline=row["closes"],
                                        describe=describe, link="/learning", pref_kind="exit_tickets"))
    return candidates


def exam_candidates(store, resolve_recipient: Callable[[str], str | None], *, now: datetime,
                    horizon: timedelta = timedelta(hours=26)) -> list[Candidate]:
    """Upcoming exams in the schedule table. `resolve_recipient` maps a schedule owner key (a student code) to a subject id."""
    window_end = (now + horizon).astimezone(UTC).isoformat().replace("+00:00", "Z")
    window_start = now.astimezone(UTC).isoformat().replace("+00:00", "Z")
    rows = store.query("""SELECT id, owner_key, course_code, course_name, starts_at, location FROM ops_schedule
                          WHERE kind = 'EXAM' AND deleted_at IS NULL AND starts_at > ? AND starts_at <= ? ORDER BY starts_at""",
                       (window_start, window_end))
    candidates = []
    for row in rows:
        recipient = resolve_recipient(row["owner_key"])
        if not recipient:
            continue
        start = datetime.fromisoformat(row["starts_at"].replace("Z", "+00:00"))
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        local = start.astimezone(VN)

        def describe(left: timedelta, row: dict[str, Any] = row, local: datetime = local) -> tuple[str, str]:
            return (f"Sắp đến giờ thi: {row['course_name']}",
                    f"Còn {time_left_text(left)}. Thi lúc {local:%H:%M} ngày {local:%d/%m/%Y}, phòng {row['location'] or 'chưa rõ'}.")

        candidates.append(Candidate(item_key=f"exam:{row['id']}", recipient=recipient, kind="REMINDER", deadline=start,
                                    describe=describe, link="/schedule", pref_kind="exam"))
    return candidates
