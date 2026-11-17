"""Reminders are sent once, with the real time left, never after the deadline, and never again after a restart."""
from datetime import UTC, datetime, timedelta

import pytest

from campus247.application.campus_ops import reminders
from campus247.application.campus_ops.reminders import Candidate, applicable_offsets, deliver, exam_candidates, time_left_text
from campus247.infrastructure.repositories.sqlite_campus_ops import CampusOpsStore

EXAM = datetime(2026, 11, 20, 1, 0, tzinfo=UTC)  # 08:00 in Vietnam
H = timedelta(hours=1)


@pytest.fixture
def store(tmp_path):
    return CampusOpsStore(tmp_path / "ops.sqlite3")


def inbox(store, recipient="subject-1"):
    return store.query("SELECT kind, title, body, link FROM ops_notifications WHERE recipient_subject_id=? ORDER BY created_at", (recipient,))


def candidate(deadline=EXAM, recipient="subject-1", key="exam:1"):
    return Candidate(item_key=key, recipient=recipient, kind="REMINDER", deadline=deadline, link="/schedule",
                     describe=lambda left: ("Sắp đến giờ thi", f"Còn {time_left_text(left)}"))


class TestOffsets:
    def test_nothing_applies_before_the_first_offset_or_after_the_deadline(self):
        offsets = reminders.DEFAULT_OFFSETS
        assert applicable_offsets(EXAM, EXAM - 25 * H, offsets) == []
        assert applicable_offsets(EXAM, EXAM, offsets) == [] and applicable_offsets(EXAM, EXAM + H, offsets) == []

    def test_both_apply_inside_the_last_two_hours(self):
        assert applicable_offsets(EXAM, EXAM - 24 * H, reminders.DEFAULT_OFFSETS) == [24 * H]
        assert applicable_offsets(EXAM, EXAM - 90 * timedelta(minutes=1), reminders.DEFAULT_OFFSETS) == [24 * H, 2 * H]

    def test_time_left_text(self):
        assert time_left_text(timedelta(hours=23, minutes=40)) == "khoảng 23 giờ"
        assert time_left_text(timedelta(minutes=45)) == "45 phút" and time_left_text(timedelta(seconds=10)) == "chưa đầy 1 phút"


class TestDelivery:
    def test_the_day_before_and_two_hours_before_each_send_once(self, store):
        assert deliver(store, [candidate()], now=EXAM - 25 * H) == 0
        assert deliver(store, [candidate()], now=EXAM - 23 * H) == 1
        assert deliver(store, [candidate()], now=EXAM - 22 * H) == 0  # same offset, already sent
        assert deliver(store, [candidate()], now=EXAM - 90 * timedelta(minutes=1)) == 1
        assert deliver(store, [candidate()], now=EXAM - timedelta(minutes=30)) == 0
        # Both are created within the same second, so the inbox order is not defined; compare as a set.
        assert sorted(n["body"] for n in inbox(store)) == ["Còn khoảng 1 giờ", "Còn khoảng 23 giờ"]

    def test_a_server_that_was_down_sends_one_reminder_with_the_real_time_left(self, store):
        assert deliver(store, [candidate()], now=EXAM - 90 * timedelta(minutes=1)) == 1  # both offsets passed at once
        assert len(inbox(store)) == 1
        assert deliver(store, [candidate()], now=EXAM - 60 * timedelta(minutes=1)) == 0  # neither is sent again

    def test_nothing_is_sent_after_the_deadline(self, store):
        assert deliver(store, [candidate()], now=EXAM + timedelta(minutes=1)) == 0 and inbox(store) == []

    def test_each_person_and_each_item_has_their_own_reminders(self, store):
        both = [candidate(recipient="a"), candidate(recipient="b"), candidate(key="exam:2", recipient="a")]
        assert deliver(store, both, now=EXAM - 20 * H) == 3
        assert len(inbox(store, "a")) == 2 and len(inbox(store, "b")) == 1

    def test_a_restart_does_not_repeat_a_reminder(self, store, tmp_path):
        deliver(store, [candidate()], now=EXAM - 20 * H)
        again = CampusOpsStore(tmp_path / "ops.sqlite3")
        assert deliver(again, [candidate()], now=EXAM - 19 * H) == 0 and len(inbox(again)) == 1

    def test_a_naive_clock_is_refused(self, store):
        with pytest.raises(ValueError):
            deliver(store, [candidate()], now=datetime(2026, 11, 19))


class TestExamCandidates:
    def insert(self, store, row_id, owner, kind, starts, *, deleted=None, location="H3-401"):
        with store.tx() as c:
            c.execute("""INSERT INTO ops_schedule(id, owner_key, kind, course_code, course_name, starts_at, ends_at, location, instructor,
                         note, source, created_at, updated_at, deleted_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (row_id, owner, kind, "IT3080", "Thi giữa kỳ Mạng máy tính", starts.isoformat().replace("+00:00", "Z"),
                       (starts + H).isoformat().replace("+00:00", "Z"), location, "TS. A", "", "TEST", "x", "x", deleted))

    def test_picks_upcoming_exams_of_known_people_only(self, store):
        now = EXAM - 20 * H
        self.insert(store, "e1", "SV001", "EXAM", EXAM)
        self.insert(store, "e2", "SV002", "EXAM", EXAM)               # nobody maps to this owner
        self.insert(store, "c1", "SV001", "CLASS", EXAM)              # a class, not an exam
        self.insert(store, "e3", "SV001", "EXAM", EXAM, deleted="x")  # deleted
        self.insert(store, "e4", "SV001", "EXAM", now + timedelta(days=5))  # far away
        self.insert(store, "e5", "SV001", "EXAM", now - H)            # already started
        found = exam_candidates(store, {"SV001": "subject-1"}.get, now=now)
        assert [(c.item_key, c.recipient) for c in found] == [("exam:e1", "subject-1")]

    def test_end_to_end_message_uses_vietnam_time_and_the_room(self, store):
        self.insert(store, "e1", "SV001", "EXAM", EXAM, location="H3-401")
        now = EXAM - 20 * H
        assert deliver(store, exam_candidates(store, {"SV001": "subject-1"}.get, now=now), now=now) == 1
        (message,) = inbox(store)
        assert message["title"] == "Sắp đến giờ thi: Thi giữa kỳ Mạng máy tính" and message["link"] == "/schedule"
        assert "Thi lúc 08:00 ngày 20/11/2026, phòng H3-401" in message["body"] and "Còn khoảng 20 giờ" in message["body"]
