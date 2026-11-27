"""Signal providers (F6.2/F6.3): exams, announcement acknowledgements, urgent unread notices, tickets that need information,
procedure drafts left idle, exit tickets about to close and practice questions due for review."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Sequence

from campus247.application.proactive.engine import VN, ActionItem

SLA_DAYS = 7


def _dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _in(ids: Sequence[str]) -> str:
    return ",".join("?" * len(ids))


class ExamProvider:
    kind, feature = "EXAM", "schedule.personal"

    def __init__(self, store, student_to_subject: Callable[[str], str | None], horizon: timedelta = timedelta(hours=96)):
        self.store, self.resolve, self.horizon = store, student_to_subject, horizon

    def items(self, subject_ids: Sequence[str], now: datetime):
        wanted = set(subject_ids)
        rows = self.store.query("SELECT id, owner_key, course_name, starts_at, location FROM ops_schedule WHERE kind='EXAM' AND deleted_at IS NULL AND starts_at>? AND starts_at<=?",
                                (now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"), (now + self.horizon).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")))
        for r in rows:
            subject = self.resolve(r["owner_key"])
            if subject in wanted:
                local = _dt(r["starts_at"]).astimezone(VN)
                yield ActionItem(f"exam:{r['id']}", subject, "EXAM", f"Sắp đến giờ thi: {r['course_name']}",
                                 f"Vì bạn có lịch thi môn {r['course_name']} lúc {local:%H:%M} ngày {local:%d/%m/%Y}.", _dt(r["starts_at"]), "/schedule")


class AnnouncementProvider:
    kind, feature = "ANNOUNCEMENT_ACK", "announcements.inbox"

    def __init__(self, store):
        self.store = store

    def items(self, subject_ids: Sequence[str], now: datetime):
        if not subject_ids:
            return
        iso = now.astimezone(timezone.utc).isoformat(timespec="seconds")
        ack = self.store.query(
            f"SELECT a.id, a.title, a.ack_deadline, d.recipient_subject_id s FROM ann_deliveries d JOIN ann_announcements a ON a.id=d.announcement_id "
            f"WHERE d.recipient_subject_id IN ({_in(subject_ids)}) AND a.status='PUBLISHED' AND a.requires_ack=1 AND a.ack_deadline>? AND d.acked_at IS NULL", (*subject_ids, iso))
        for r in ack:
            yield ActionItem(f"ann-ack:{r['id']}", r["s"], "ANNOUNCEMENT_ACK", f"Cần xác nhận đã đọc: {r['title']}",
                             "Vì thông báo này yêu cầu bạn xác nhận đã đọc và hiểu.", _dt(r["ack_deadline"]), f"/announcements?id={r['id']}")
        cutoff = (now - timedelta(hours=2)).astimezone(timezone.utc).isoformat(timespec="seconds")
        urgent = self.store.query(
            f"SELECT a.id, a.title, d.recipient_subject_id s FROM ann_deliveries d JOIN ann_announcements a ON a.id=d.announcement_id "
            f"WHERE d.recipient_subject_id IN ({_in(subject_ids)}) AND a.status='PUBLISHED' AND a.priority='URGENT' AND a.expires_at>? AND d.read_at IS NULL AND d.delivered_at<=?",
            (*subject_ids, iso, cutoff))
        for r in urgent:
            yield ActionItem(f"ann-urgent:{r['id']}", r["s"], "ANNOUNCEMENT_URGENT_UNREAD", f"Thông báo khẩn chưa đọc: {r['title']}",
                             "Vì đây là thông báo khẩn gửi cho bạn và bạn chưa mở.", None, f"/announcements?id={r['id']}")


class TicketProvider:
    kind, feature = "TICKET_NEED_INFO", "tickets.student"

    def __init__(self, store):
        self.store = store

    def items(self, subject_ids: Sequence[str], now: datetime):
        if not subject_ids:
            return
        for r in self.store.query(f"SELECT id, code, title, owner_subject_id, updated_at FROM ops_tickets WHERE status='NEED_INFO' AND owner_subject_id IN ({_in(subject_ids)})", tuple(subject_ids)):
            yield ActionItem(f"ticket:{r['id']}", r["owner_subject_id"], "TICKET_NEED_INFO", f"Phiếu {r['code']} cần bạn bổ sung thông tin",
                             f"Vì cán bộ đã yêu cầu bổ sung thông tin cho phiếu \"{r['title']}\".", _dt(r["updated_at"]) + timedelta(days=SLA_DAYS), "/tickets")


class ProcedureDraftProvider:
    """A procedure the student started and has not touched for 3 days, while it can still be finished (F5 runs)."""
    kind, feature = "PROCEDURE_DRAFT", "agent.procedures"
    IDLE = timedelta(days=3)

    def __init__(self, store, title: Callable[[str], str | None]):
        self.store, self.title = store, title

    def items(self, subject_ids: Sequence[str], now: datetime):
        if not subject_ids:
            return
        from campus247.domain.procedures import EDITABLE
        iso = lambda moment: moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        try:
            rows = self.store.query(
                f"SELECT id, owner_subject_id, procedure_id, updated_at, expires_at FROM proc_runs WHERE owner_subject_id IN ({_in(subject_ids)}) "
                f"AND state IN ({_in(sorted(EDITABLE))}) AND updated_at<=? AND expires_at>?", (*subject_ids, *sorted(EDITABLE), iso(now - self.IDLE), iso(now)))
        except sqlite3.OperationalError:
            return                                   # the procedures feature has never run here: no table yet
        for r in rows:
            name = self.title(r["procedure_id"]) or r["procedure_id"]
            yield ActionItem(f"procedure:{r['id']}", r["owner_subject_id"], "PROCEDURE_DRAFT", f"Hồ sơ đang làm dở: {name}",
                             "Vì bạn đã bắt đầu thủ tục này và chưa gửi; hồ sơ sẽ hết hạn nếu để quá lâu.", _dt(r["expires_at"]),
                             f"/services/procedures?run={r['id']}")


def sqlite_learning_snapshot(database: Path, tenant_id: str) -> Callable[[], dict | None]:
    """Read-only view of the local learning store (SQLite), for the providers below; None when it cannot be read."""
    def read():
        try:
            with sqlite3.connect(f"file:{Path(database).as_posix()}?mode=ro", uri=True, timeout=2) as db:
                row = db.execute("SELECT payload FROM learning_state WHERE tenant_id=?", (tenant_id,)).fetchone()
            return json.loads(row[0]) if row else None
        except (sqlite3.Error, ValueError, OSError):
            return None
    return read


def _students(state: dict, offering_id: str, wanted: set[str]) -> set[str]:
    return {m["actor_subject_id"] for m in state.get("members", {}).values()
            if m.get("offering_id") == offering_id and m.get("status") == "ACTIVE" and m.get("role") == "STUDENT" and m.get("actor_subject_id") in wanted}


class ExitTicketProvider:
    """An exit ticket that is open now and the student has not answered yet; due when it closes."""
    kind, feature = "EXIT_TICKET_CLOSING", "learning.exit_tickets"

    def __init__(self, snapshot: Callable[[], dict | None]):
        self.snapshot = snapshot

    def items(self, subject_ids: Sequence[str], now: datetime):
        state = self.snapshot() if subject_ids else None
        if not state:
            return
        wanted = set(subject_ids)
        submissions = state.get("exit_submissions", {})
        for ticket in state.get("exit_tickets", {}).values():
            try:
                opens, closes = _dt(ticket["opens"]["utc"]), _dt(ticket["closes"]["utc"])
            except (KeyError, TypeError, ValueError):
                continue
            if ticket.get("status") != "PUBLISHED" or not opens <= now < closes:
                continue
            for student in sorted(_students(state, ticket["offering_id"], wanted)):
                if f"{ticket['id']}:{student}" in submissions:
                    continue
                local = closes.astimezone(VN)
                yield ActionItem(f"exit:{ticket['id']}", student, "EXIT_TICKET_CLOSING", "Phiếu ra lớp sắp đóng",
                                 f"Vì phiếu ra lớp của buổi học đang mở và đóng lúc {local:%H:%M} ngày {local:%d/%m}; bạn chưa trả lời.",
                                 closes, "/learning")


class PracticeDueProvider:
    """Practice questions whose spaced review is due (SM-2 next review passed), one reminder per set and due day."""
    kind, feature = "PRACTICE_DUE", "learning.practice"

    def __init__(self, snapshot: Callable[[], dict | None]):
        self.snapshot = snapshot

    def items(self, subject_ids: Sequence[str], now: datetime):
        state = self.snapshot() if subject_ids else None
        if not state:
            return
        wanted = set(subject_ids)
        items, sets = state.get("practice_items", {}), state.get("practice_sets", {})
        due: dict[tuple[str, str], list[datetime]] = {}
        for key, review in state.get("practice_reviews", {}).items():
            item_id, _, student = key.partition(":")
            item = items.get(item_id)
            if student not in wanted or item is None or sets.get(item["set_id"], {}).get("status") != "PUBLISHED":
                continue
            try:
                when = _dt(review["due_at"])
            except (KeyError, TypeError, ValueError):
                continue
            if when <= now:
                due.setdefault((student, item["set_id"]), []).append(when)
        for (student, set_id), moments in sorted(due.items()):
            first = min(moments)
            yield ActionItem(f"practice:{set_id}:{first.astimezone(VN):%Y-%m-%d}", student, "PRACTICE_DUE",
                             f"{len(moments)} câu ôn tập đến hạn: {sets[set_id].get('title', 'bộ câu hỏi')}",
                             "Vì theo lịch ôn ngắt quãng, đây là lúc nên ôn lại để nhớ lâu.", None, "/learning", urgency_hint="LOW")
