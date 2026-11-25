"""F6: urgency, stages, quiet hours, daily cap, idempotency after restarts, done/snooze, and a 14-day simulation checked against an independent oracle."""
from __future__ import annotations

import json
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "announcements"))
from ann_helpers import demo_accounts, make_service  # noqa: E402,F401

from campus247.application.proactive.engine import VN, ActionItem, ProactiveEngine, in_quiet_hours, score, urgency_of  # noqa: E402
from campus247.infrastructure.repositories.sqlite_campus_ops import CampusOpsStore  # noqa: E402

START = datetime(2026, 12, 1, 0, 0, tzinfo=VN).astimezone(timezone.utc)
ROOT = Path(__file__).resolve().parents[2]


class Scripted:
    def __init__(self, kind, feature, items):
        self.kind, self.feature, self._items = kind, feature, items

    def items(self, subject_ids, now):
        wanted = set(subject_ids)
        return [i for i in self._items if i.subject_id in wanted and (i.due_at is None or i.due_at > now)]


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


def item(key, subject, kind, due, **kw):
    return ActionItem(key, subject, kind, f"Việc {key}", f"Vì {key}", due, "/x", **kw)


def engine(tmp_path, providers, subjects, clock, name="ops.sqlite3", **kw):
    store = CampusOpsStore(tmp_path / name)
    return ProactiveEngine(store, providers, subjects=lambda: subjects, clock=clock, **kw), store


def sent(store):
    return store.query("SELECT key, sent_at FROM ops_reminders_sent WHERE key LIKE 'nudge:%' ORDER BY sent_at, key")


def test_urgency_levels_and_ordering():
    now = START
    assert urgency_of(item("a", "s", "EXAM", now + timedelta(hours=1)), now) == "CRITICAL"
    assert urgency_of(item("a", "s", "EXAM", now + timedelta(hours=20)), now) == "HIGH"
    assert urgency_of(item("a", "s", "EXAM", now + timedelta(hours=60)), now) == "NORMAL"
    assert urgency_of(item("a", "s", "PRACTICE_DUE", now + timedelta(days=9)), now) == "LOW"
    assert urgency_of(item("a", "s", "TICKET_NEED_INFO", None), now) == "HIGH"
    assert urgency_of(item("a", "s", "PRACTICE_DUE", now + timedelta(days=9), urgency_hint="HIGH"), now) == "HIGH"
    soon, later = item("soon", "s", "EXAM", now + timedelta(hours=3)), item("later", "s", "EXAM", now + timedelta(hours=40))
    assert score(soon, now) > score(later, now)


def test_quiet_hours_boundaries_in_vietnam_time():
    def at(h, m):
        return datetime(2026, 12, 1, h, m, tzinfo=VN)
    assert [in_quiet_hours(at(*t)) for t in ((21, 59), (22, 0), (6, 59), (7, 0))] == [False, True, True, False]


def test_stage_flow_one_nudge_per_stage_and_no_backfill(tmp_path):
    clock = Clock(START + timedelta(hours=9))
    due = START + timedelta(days=1, hours=14)  # 14:00 next day
    eng, store = engine(tmp_path, [Scripted("EXAM", "x", [item("e1", "s1", "EXAM", due)])], ["s1"], clock)
    assert eng.run_once()["sent"] == 1  # 29 h left is the NORMAL stage
    keys = [r["key"] for r in sent(store)]
    assert keys == ["nudge:e1:s1:NORMAL"]  # 29 h left: NORMAL
    eng.run_once()
    assert len(sent(store)) == 1  # nothing twice
    clock.now = due - timedelta(hours=23)
    eng.run_once()
    clock.now = due - timedelta(hours=10)  # 04:00: the repeat is due but it is quiet time, so it waits
    eng.run_once()
    clock.now = due - timedelta(hours=6, minutes=30)  # 07:30
    eng.run_once()
    clock.now = due - timedelta(hours=1)
    eng.run_once()
    assert [r["key"].rsplit(":", 1)[1] for r in sent(store)] == ["NORMAL", "HIGH-1", "HIGH-2", "CRITICAL"]
    clock.now = due - timedelta(minutes=30)
    eng.run_once()
    assert len(sent(store)) == 4
    # jumping straight into CRITICAL sends only the critical stage
    eng2, store2 = engine(tmp_path, [Scripted("EXAM", "x", [item("e2", "s1", "EXAM", due)])], ["s1"], Clock(due - timedelta(hours=1)), name="two.sqlite3")
    eng2.run_once()
    assert [r["key"] for r in sent(store2)] == ["nudge:e2:s1:CRITICAL"]


def test_quiet_hours_defer_but_critical_goes_through(tmp_path):
    due = START + timedelta(hours=26, minutes=30)  # 02:30 next night
    clock = Clock(START + timedelta(hours=23, minutes=30))  # 23:30, 3 h before: HIGH, quiet
    eng, store = engine(tmp_path, [Scripted("EXAM", "x", [item("e", "s1", "EXAM", due)])], ["s1"], clock)
    assert eng.run_once() == {"sent": 0, "deferred_quiet": 1, "deferred_cap": 0}
    clock.now = due - timedelta(hours=1, minutes=59)
    assert eng.run_once()["sent"] == 1 and sent(store)[0]["key"].endswith("CRITICAL")


def test_daily_cap_is_three_for_non_critical_and_critical_ignores_it(tmp_path):
    clock = Clock(START + timedelta(hours=9))
    items = [item(f"t{i}", "s1", "TICKET_NEED_INFO", None) for i in range(5)]
    eng, store = engine(tmp_path, [Scripted("TICKET_NEED_INFO", "x", items)], ["s1"], clock)
    assert eng.run_once() == {"sent": 3, "deferred_quiet": 0, "deferred_cap": 2}
    crit = Scripted("EXAM", "x", [item("c", "s1", "EXAM", clock.now + timedelta(hours=1))])
    eng.providers.append(crit)
    assert eng.run_once()["sent"] == 1  # critical goes beyond the cap
    clock.now += timedelta(days=1)
    assert eng.run_once()["sent"] == 3  # next day: the two deferred items and the 12 h repeats compete for the same cap of 3


def test_done_snooze_restore_and_preferences(tmp_path):
    clock = Clock(START + timedelta(hours=9))
    items = [item("a", "s1", "EXAM", clock.now + timedelta(hours=10)), item("p", "s1", "PRACTICE_DUE", clock.now + timedelta(hours=10))]
    eng, store = engine(tmp_path, [Scripted("EXAM", "x", items)], ["s1"], clock)
    assert [i["key"] for i in eng.today("s1")] == ["a"]  # PRACTICE_DUE is off by default
    eng.set_preference("s1", "PRACTICE_DUE", True)
    assert {i["key"] for i in eng.today("s1")} == {"a", "p"}
    eng.mark("s1", "a", "SNOOZED", hours=3)
    assert [i["key"] for i in eng.today("s1")] == ["p"] and eng.run_once()["sent"] == 1
    clock.now += timedelta(hours=3, minutes=1)
    assert "a" in [i["key"] for i in eng.today("s1")]
    eng.mark("s1", "a", "DONE")
    assert "a" not in [i["key"] for i in eng.today("s1")]
    eng.mark("s1", "a", "RESTORED")
    assert "a" in [i["key"] for i in eng.today("s1")]
    eng.set_preference("s1", "EXAM", False)
    assert "a" not in [i["key"] for i in eng.today("s1")] and eng.owns("s1", "a") and not eng.owns("s2", "a")


def test_source_flag_off_drops_that_provider(tmp_path):
    clock = Clock(START + timedelta(hours=9))
    eng, _ = engine(tmp_path, [Scripted("EXAM", "schedule.personal", [item("a", "s1", "EXAM", clock.now + timedelta(hours=10))])], ["s1"], clock,
                    enabled=lambda f: f != "schedule.personal")
    assert eng.today("s1") == [] and eng.run_once()["sent"] == 0


def test_digest_lists_top_items_once_a_day_and_only_for_those_who_opted_in(tmp_path):
    clock = Clock(START + timedelta(hours=8))
    items = [item(f"d{i}", "s1", "TICKET_NEED_INFO", None) for i in range(9)] + [item("o", "s2", "TICKET_NEED_INFO", None)]
    eng, store = engine(tmp_path, [Scripted("TICKET_NEED_INFO", "x", items)], ["s1", "s2"], clock)
    eng.set_preference("s1", "DIGEST", True)
    assert eng.run_digest_once() == 1 and eng.run_digest_once() == 0
    note = store.one("SELECT title, body FROM ops_notifications WHERE recipient_subject_id='s1' AND title LIKE 'Hôm nay%'")
    assert note["title"] == "Hôm nay bạn có 7 việc" and note["body"].count("\n") == 6
    clock.now = START + timedelta(hours=6)  # before 07:00: no digest
    assert eng.run_digest_once() == 0


def build_simulation(accounts):
    """Scripted signals for 14 days: two exams per student, far apart, so the daily cap never binds and the oracle stays simple."""
    rng = random.Random(20261126)
    items = []
    for a in accounts:
        if a["role"] != "STUDENT":
            continue
        for n in range(2):
            day = 2 + n * 6 + rng.randint(0, 2)
            minutes = rng.choice([7 * 60 + 30, 9 * 60, 13 * 60 + 30, 15 * 60])
            items.append(item(f"exam-{a['subject_id'][-4:]}-{n}", a["subject_id"], "EXAM", START + timedelta(days=day, minutes=minutes)))
    return items


def oracle(items, step=timedelta(minutes=5), days=14):
    """Independent, closed-form expectations for EXAM-only scripts: first allowed tick of each window."""
    ticks = [START + step * i for i in range(int(days * 24 * 60 / 5))]

    def first(lo, hi, allowed):
        return next((t for t in ticks if lo <= t < hi and (not allowed or not (t.astimezone(VN).hour >= 22 or t.astimezone(VN).hour < 7))), None)

    expected = {}
    for it in items:
        d = it.due_at
        n = first(d - timedelta(hours=72), d - timedelta(hours=24), True)
        h1 = first(d - timedelta(hours=24), d - timedelta(hours=2), True)
        h2 = first(h1 + timedelta(hours=12), d - timedelta(hours=2), True) if h1 else None
        c = first(d - timedelta(hours=2), d, False)
        for stage, when in (("NORMAL", n), ("HIGH-1", h1), ("HIGH-2", h2), ("CRITICAL", c)):
            if when:
                expected[f"nudge:{it.key}:{it.subject_id}:{stage}"] = when.astimezone(timezone.utc).isoformat(timespec="seconds")
    return expected


def run_days(eng, clock, step, days=14, restart=None):
    for i in range(int(days * 24 * 60 / (step.total_seconds() / 60))):
        clock.now = START + step * i
        (restart() if restart else eng).run_once()


def test_14_day_simulation_matches_the_oracle_and_never_breaks_the_rules(tmp_path):
    accounts = demo_accounts()
    items = build_simulation(accounts)
    subjects = sorted({i.subject_id for i in items})
    clock = Clock(START)
    eng, store = engine(tmp_path, [Scripted("EXAM", "schedule.personal", items)], subjects, clock)
    run_days(eng, clock, timedelta(minutes=5))
    actual = {r["key"]: r["sent_at"] for r in sent(store)}
    expected = oracle(items)
    assert actual == expected, f"{len(set(actual) ^ set(expected))} differences"  # criterion 1: 100 % equal
    # criterion 2 and 3 over the whole run: no more than 3 non-critical a day, none sent in quiet hours except CRITICAL
    per_day: dict[tuple[str, str], int] = {}
    for key, at in actual.items():
        local = datetime.fromisoformat(at).astimezone(VN)
        if not key.endswith("CRITICAL"):
            assert not (local.hour >= 22 or local.hour < 7), key
            per_day[(key.split(":")[2], local.date().isoformat())] = per_day.get((key.split(":")[2], local.date().isoformat()), 0) + 1
    assert max(per_day.values()) <= 3
    notices = store.one("SELECT COUNT(*) n FROM ops_notifications WHERE kind='NUDGE'")["n"]
    assert notices == len(actual)  # one inbox notice per nudge, none doubled


def test_restart_at_every_minute_of_the_first_day_changes_nothing(tmp_path):
    accounts = demo_accounts()
    items = [i for i in build_simulation(accounts) if i.due_at < START + timedelta(days=4)]
    subjects = sorted({i.subject_id for i in items})
    clock = Clock(START)
    steady, steady_store = engine(tmp_path, [Scripted("EXAM", "x", items)], subjects, clock, name="steady.sqlite3")
    run_days(steady, clock, timedelta(minutes=5), days=4)
    clock2 = Clock(START)
    path = tmp_path / "restarting.sqlite3"
    first, store = engine(tmp_path, [Scripted("EXAM", "x", items)], subjects, clock2, name="restarting.sqlite3")

    def fresh():  # a brand-new engine object over the same file: a process restart
        return ProactiveEngine(CampusOpsStore(path), [Scripted("EXAM", "x", items)], subjects=lambda: subjects, clock=clock2)

    for minute in range(24 * 60):  # every minute of day one, restarting each time
        clock2.now = START + timedelta(minutes=minute)
        fresh().run_once()
    for i in range(24 * 12, 4 * 24 * 12):
        clock2.now = START + timedelta(minutes=5 * i)
        fresh().run_once()
    a = {r["key"] for r in sent(steady_store)}
    b = {r["key"] for r in sent(store)}
    assert a == b and store.one("SELECT COUNT(*) n FROM ops_notifications WHERE kind='NUDGE'")["n"] == len(b)


def test_one_pass_for_30000_people_takes_at_most_30_seconds(tmp_path):
    subjects = [f"p{n:05d}" for n in range(30_000)]
    due = START + timedelta(hours=10)
    items = [item(f"e{n}", s, "EXAM", due) for n, s in enumerate(subjects)]
    clock = Clock(START + timedelta(hours=9))
    eng, store = engine(tmp_path, [Scripted("EXAM", "x", items)], subjects, clock)
    started = time.perf_counter()
    result = eng.run_once()
    seconds = time.perf_counter() - started
    out = ROOT / "evals/results/proactive-20261126"
    out.mkdir(parents=True, exist_ok=True)
    (out / "perf.json").write_text(json.dumps({"people": 30000, "seconds": round(seconds, 2), "sent": result["sent"], "method": "synthetic, one process, SQLite WAL"}, indent=2), encoding="utf-8")
    assert result["sent"] == 30_000 and seconds <= 30, f"{seconds:.1f}s"
