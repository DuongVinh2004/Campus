"""Signal providers for sources that exist today (F6.2/F6.3): exams, announcement acknowledgements, urgent unread notices, tickets that need information."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
