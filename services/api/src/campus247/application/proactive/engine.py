"""Proactive assistant (F6): turn the signals of one person into "things to do today" and well-timed inbox nudges.

Deterministic code only, no model. Policy: urgency from the deadline, one nudge per stage (CRITICAL, HIGH-1, HIGH-2, NORMAL),
quiet hours 22:00-07:00 Vietnam time except CRITICAL, at most 3 non-critical nudges per person per day, and idempotency keys in
`ops_reminders_sent` so a restart never sends twice. "Done" and "snooze" only hide a task from nudges; they never change source data.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterable, Literal, Protocol, Sequence

VN = timezone(timedelta(hours=7))
URGENCIES = ("LOW", "NORMAL", "HIGH", "CRITICAL")
QUIET_START, QUIET_END = 22, 7
DAILY_CAP = 3
DIGEST_MAX = 7
HIGH_REPEAT = timedelta(hours=12)
DEFAULT_ON = {"EXAM", "ANNOUNCEMENT_ACK", "ANNOUNCEMENT_URGENT_UNREAD", "TICKET_NEED_INFO", "EXIT_TICKET_CLOSING"}
ALL_KINDS = DEFAULT_ON | {"PRACTICE_DUE", "PROCEDURE_DRAFT", "POLICY_CHANGE", "TRACKED_ITEM"}
SCHEMA = (
    "CREATE TABLE IF NOT EXISTS nudge_states(subject_id TEXT NOT NULL, item_key TEXT NOT NULL, state TEXT NOT NULL, until TEXT, updated_at TEXT NOT NULL,"
    " PRIMARY KEY(subject_id, item_key))",
    "CREATE TABLE IF NOT EXISTS nudge_daily(subject_id TEXT NOT NULL, day TEXT NOT NULL, sent INTEGER NOT NULL, PRIMARY KEY(subject_id, day))",
    "CREATE TABLE IF NOT EXISTS ops_reminders_sent(key TEXT PRIMARY KEY, sent_at TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS ops_reminder_prefs(subject_id TEXT NOT NULL, kind TEXT NOT NULL, enabled INTEGER NOT NULL, PRIMARY KEY(subject_id, kind))",
)


@dataclass(frozen=True)
class ActionItem:
    key: str
    subject_id: str
    kind: str
    title: str
    reason: str
    due_at: datetime | None
    link: str
    urgency_hint: Literal["CRITICAL", "HIGH", "NORMAL", "LOW"] | None = None
    done: bool = False


class SignalProvider(Protocol):
    kind: str
    feature: str

    def items(self, subject_ids: Sequence[str], now: datetime) -> Iterable[ActionItem]: ...


def urgency_of(item: ActionItem, now: datetime) -> str:
    hours = (item.due_at - now).total_seconds() / 3600 if item.due_at else None
    if hours is not None and hours <= 2:
        level = "CRITICAL"
    elif (hours is not None and hours <= 24) or item.kind in {"ANNOUNCEMENT_URGENT_UNREAD", "TICKET_NEED_INFO"}:
        level = "HIGH"
    elif (hours is not None and hours <= 72) or item.kind in {"ANNOUNCEMENT_ACK", "POLICY_CHANGE"}:
        level = "NORMAL"
    else:
        level = "LOW"
    if item.urgency_hint and URGENCIES.index(item.urgency_hint) > URGENCIES.index(level):
        level = item.urgency_hint
    return level


def score(item: ActionItem, now: datetime) -> float:
    hours = (item.due_at - now).total_seconds() / 3600 if item.due_at else 999.0
    return URGENCIES.index(urgency_of(item, now)) * 1000 - min(hours, 999.0)


def in_quiet_hours(now: datetime) -> bool:
    hour = now.astimezone(VN).hour
    return hour >= QUIET_START or hour < QUIET_END


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


class ProactiveEngine:
    def __init__(self, store, providers: Sequence[SignalProvider], *, enabled: Callable[[str], bool] = lambda key: True,
                 clock: Callable[[], datetime] | None = None, subjects: Callable[[], Sequence[str]] = lambda: (), batch: int = 500):
        self.store, self.providers, self.enabled = store, list(providers), enabled
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.subjects, self.batch = subjects, batch
        with store.tx() as c:
            for statement in SCHEMA:
                c.execute(statement)

    # ------------------------------------------------------------------ preferences and states
    def _pref_on(self, prefs: dict[str, bool], kind: str) -> bool:
        return prefs.get("nudge:" + kind, kind in DEFAULT_ON)

    def preferences(self, subject_id: str) -> dict[str, bool]:
        rows = {r["kind"]: bool(r["enabled"]) for r in self.store.query("SELECT kind, enabled FROM ops_reminder_prefs WHERE subject_id=?", (subject_id,))}
        out = {kind: self._pref_on(rows, kind) for kind in sorted(ALL_KINDS)}
        out["DIGEST"] = rows.get("nudge:DIGEST", False)
        return out

    def set_preference(self, subject_id: str, kind: str, enabled: bool) -> None:
        if kind not in ALL_KINDS and kind != "DIGEST":
            raise ValueError("unknown nudge kind")
        with self.store.tx() as c:
            c.execute("INSERT INTO ops_reminder_prefs(subject_id,kind,enabled) VALUES(?,?,?) ON CONFLICT(subject_id,kind) DO UPDATE SET enabled=excluded.enabled",
                      (subject_id, "nudge:" + kind, int(enabled)))

    def _hidden(self, subject_id: str, now: datetime) -> set[str]:
        rows = self.store.query("SELECT item_key, state, until FROM nudge_states WHERE subject_id=?", (subject_id,))
        return {r["item_key"] for r in rows if r["state"] == "DONE" or (r["state"] == "SNOOZED" and r["until"] and r["until"] > _iso(now))}

    def mark(self, subject_id: str, item_key: str, state: str, *, hours: int | None = None) -> None:
        if state not in {"DONE", "SNOOZED", "RESTORED"}:
            raise ValueError(state)
        until = _iso(self.clock() + timedelta(hours=hours)) if state == "SNOOZED" else None
        with self.store.tx() as c:
            if state == "RESTORED":
                c.execute("DELETE FROM nudge_states WHERE subject_id=? AND item_key=?", (subject_id, item_key))
            else:
                c.execute("INSERT INTO nudge_states VALUES(?,?,?,?,?) ON CONFLICT(subject_id,item_key) DO UPDATE SET state=excluded.state, until=excluded.until, updated_at=excluded.updated_at",
                          (subject_id, item_key, state, until, _iso(self.clock())))

    # ------------------------------------------------------------------ gathering
    def _gather(self, subject_ids: Sequence[str], now: datetime) -> list[ActionItem]:
        items: list[ActionItem] = []
        for provider in self.providers:
            if not self.enabled(provider.feature):
                continue
            items.extend(i for i in provider.items(subject_ids, now) if not i.done)
        return items

    def today(self, subject_id: str, limit: int = 20) -> list[dict]:
        """Things to do, computed live: not done, not snoozed, kind switched on, most urgent first."""
        now = self.clock()
        prefs = self.preferences(subject_id)
        hidden = self._hidden(subject_id, now)
        rows = [i for i in self._gather([subject_id], now) if i.subject_id == subject_id and i.key not in hidden and prefs.get(i.kind, False)]
        rows.sort(key=lambda i: -score(i, now))
        return [{"key": i.key, "kind": i.kind, "title": i.title, "reason": i.reason, "due_at": _iso(i.due_at) if i.due_at else None,
                 "urgency": urgency_of(i, now), "link": i.link} for i in rows[:limit]]

    def owns(self, subject_id: str, item_key: str) -> bool:
        return any(i.key == item_key and i.subject_id == subject_id for i in self._gather([subject_id], self.clock()))

    # ------------------------------------------------------------------ the job
    def _sent_at(self, c, key: str) -> str | None:
        row = c.execute("SELECT sent_at FROM ops_reminders_sent WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def run_once(self) -> dict[str, int]:
        """One pass over every person. Returns counts: sent, deferred_quiet, deferred_cap."""
        now = self.clock()
        totals = {"sent": 0, "deferred_quiet": 0, "deferred_cap": 0}
        people = list(self.subjects())
        for start in range(0, len(people), self.batch):
            chunk = people[start:start + self.batch]
            by_person: dict[str, list[ActionItem]] = {}
            for item in self._gather(chunk, now):
                by_person.setdefault(item.subject_id, []).append(item)
            if not by_person:
                continue
            with self.store.tx() as c:
                for subject_id, items in by_person.items():
                    self._nudge_person(c, subject_id, items, now, totals)
        return totals

    def _nudge_person(self, c, subject_id: str, items: list[ActionItem], now: datetime, totals: dict[str, int]) -> None:
        rows = {r[0]: bool(r[1]) for r in c.execute("SELECT kind, enabled FROM ops_reminder_prefs WHERE subject_id=?", (subject_id,)).fetchall()}
        hidden_rows = c.execute("SELECT item_key, state, until FROM nudge_states WHERE subject_id=?", (subject_id,)).fetchall()
        hidden = {r[0] for r in hidden_rows if r[1] == "DONE" or (r[1] == "SNOOZED" and r[2] and r[2] > _iso(now))}
        digest_on = rows.get("nudge:DIGEST", False)
        day = now.astimezone(VN).date().isoformat()
        sent_today = (c.execute("SELECT sent FROM nudge_daily WHERE subject_id=? AND day=?", (subject_id, day)).fetchone() or (0,))[0]
        for item in sorted(items, key=lambda i: -score(i, now)):
            if item.key in hidden or not self._pref_on(rows, item.kind):
                continue
            level = urgency_of(item, now)
            if level == "LOW" or (level == "NORMAL" and digest_on):
                continue
            stage = self._stage(c, item, subject_id, level, now)
            if stage is None:
                continue
            if level != "CRITICAL":
                if in_quiet_hours(now):
                    totals["deferred_quiet"] += 1
                    continue
                if sent_today >= DAILY_CAP:
                    totals["deferred_cap"] += 1
                    continue
            key = f"nudge:{item.key}:{subject_id}:{stage}"
            if not c.execute("INSERT OR IGNORE INTO ops_reminders_sent(key,sent_at) VALUES(?,?)", (key, _iso(now))).rowcount:
                continue
            self.store.notify(c, subject_id, "NUDGE", item.title, item.reason, item.link)
            sent_today += 1
            totals["sent"] += 1
            c.execute("INSERT INTO nudge_daily VALUES(?,?,1) ON CONFLICT(subject_id,day) DO UPDATE SET sent=sent+1", (subject_id, day))

    def _stage(self, c, item: ActionItem, subject_id: str, level: str, now: datetime) -> str | None:
        base = f"nudge:{item.key}:{subject_id}:"
        if level == "CRITICAL":
            return "CRITICAL" if self._sent_at(c, base + "CRITICAL") is None else None
        if level == "NORMAL":
            return "NORMAL" if self._sent_at(c, base + "NORMAL") is None else None
        if level == "HIGH":
            first = self._sent_at(c, base + "HIGH-1")
            if first is None:
                return "HIGH-1"
            if self._sent_at(c, base + "HIGH-2") is None and now >= datetime.fromisoformat(first) + HIGH_REPEAT:
                return "HIGH-2"
        return None

    # ------------------------------------------------------------------ morning digest
    def run_digest_once(self) -> int:
        now = self.clock()
        local = now.astimezone(VN)
        if local.hour < QUIET_END:
            return 0
        day = local.date().isoformat()
        sent = 0
        people = list(self.subjects())
        with_digest = [p for p in people if self.preferences(p).get("DIGEST")]
        for start in range(0, len(with_digest), self.batch):
            chunk = with_digest[start:start + self.batch]
            by_person: dict[str, list[ActionItem]] = {}
            for item in self._gather(chunk, now):
                by_person.setdefault(item.subject_id, []).append(item)
            with self.store.tx() as c:
                for subject_id, items in by_person.items():
                    prefs = self.preferences(subject_id)
                    hidden = self._hidden(subject_id, now)
                    todo = sorted((i for i in items if i.key not in hidden and prefs.get(i.kind, False)), key=lambda i: -score(i, now))[:DIGEST_MAX]
                    if not todo:
                        continue
                    if not c.execute("INSERT OR IGNORE INTO ops_reminders_sent(key,sent_at) VALUES(?,?)", (f"digest:{subject_id}:{day}", _iso(now))).rowcount:
                        continue
                    body = "\n".join(f"- {i.title} ({i.reason})" for i in todo)
                    self.store.notify(c, subject_id, "NUDGE", f"Hôm nay bạn có {len(todo)} việc", body, "/")
                    sent += 1
        return sent
