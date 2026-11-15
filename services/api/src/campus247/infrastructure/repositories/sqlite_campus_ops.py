"""Durable operations store: rooms, bookings, personal timetable, notifications, tickets and audit.

One SQLite file in the workspace (WAL). Every write is a short IMMEDIATE transaction, rows are never
deleted (cancel/close are status changes) and every state change appends an audit row.
Seed rows are explicitly labelled with ``source`` so the UI can say they are synthetic local data and
not an integration with HUCE systems.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from campus247.infrastructure.sqlite_wal import enable_wal
from campus247.ports.campus_ops import ICT, OpsError, now_iso, uuid7  # noqa: F401 -- re-exported for callers

SEED_SOURCE = "LOCAL_SYNTHETIC"

SCHEMA = """
CREATE TABLE IF NOT EXISTS ops_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ops_rooms(
  id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL, building TEXT NOT NULL, floor INTEGER NOT NULL,
  capacity INTEGER NOT NULL, kind TEXT NOT NULL, features TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ACTIVE',
  source TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ops_room_bookings(
  id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE, room_id TEXT NOT NULL REFERENCES ops_rooms(id),
  owner_subject_id TEXT NOT NULL, owner_display TEXT NOT NULL, starts_at TEXT NOT NULL, ends_at TEXT NOT NULL,
  purpose TEXT NOT NULL, attendees INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL,
  idempotency_key TEXT NOT NULL, created_at TEXT NOT NULL, cancelled_at TEXT, cancel_reason TEXT,
  UNIQUE(owner_subject_id, idempotency_key));
CREATE INDEX IF NOT EXISTS ops_booking_room_time ON ops_room_bookings(room_id, starts_at, ends_at);
CREATE INDEX IF NOT EXISTS ops_booking_owner ON ops_room_bookings(owner_subject_id, starts_at);
CREATE TABLE IF NOT EXISTS ops_booking_previews(
  id TEXT PRIMARY KEY, owner_subject_id TEXT NOT NULL, payload TEXT NOT NULL, payload_hash TEXT NOT NULL,
  expires_at TEXT NOT NULL, used_at TEXT);
CREATE TABLE IF NOT EXISTS ops_schedule(
  id TEXT PRIMARY KEY, owner_key TEXT NOT NULL, kind TEXT NOT NULL, course_code TEXT NOT NULL, course_name TEXT NOT NULL,
  starts_at TEXT NOT NULL, ends_at TEXT NOT NULL, location TEXT NOT NULL, instructor TEXT NOT NULL, note TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT);
CREATE INDEX IF NOT EXISTS ops_schedule_owner_time ON ops_schedule(owner_key, starts_at);
CREATE INDEX IF NOT EXISTS ops_schedule_location_time ON ops_schedule(location, starts_at);
CREATE TABLE IF NOT EXISTS ops_notifications(
  id TEXT PRIMARY KEY, recipient_subject_id TEXT NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
  link TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, read_at TEXT);
CREATE INDEX IF NOT EXISTS ops_notif_recipient ON ops_notifications(recipient_subject_id, created_at DESC);
CREATE TABLE IF NOT EXISTS ops_tickets(
  id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE, owner_subject_id TEXT NOT NULL, owner_display TEXT NOT NULL,
  owner_code TEXT NOT NULL, service_kind TEXT NOT NULL, title TEXT NOT NULL, summary TEXT NOT NULL, fields TEXT NOT NULL,
  status TEXT NOT NULL, priority TEXT NOT NULL DEFAULT 'NORMAL', assignee_subject_id TEXT, assignee_display TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, due_at TEXT, idempotency_key TEXT NOT NULL,
  UNIQUE(owner_subject_id, idempotency_key));
CREATE INDEX IF NOT EXISTS ops_ticket_owner ON ops_tickets(owner_subject_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ops_ticket_status ON ops_tickets(status, created_at);
CREATE TABLE IF NOT EXISTS ops_ticket_events(
  id TEXT PRIMARY KEY, ticket_id TEXT NOT NULL REFERENCES ops_tickets(id), actor_subject_id TEXT NOT NULL,
  actor_role TEXT NOT NULL, actor_display TEXT NOT NULL, kind TEXT NOT NULL, body TEXT NOT NULL,
  visibility TEXT NOT NULL DEFAULT 'PUBLIC', created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ops_ticket_events_ticket ON ops_ticket_events(ticket_id, created_at);
CREATE TABLE IF NOT EXISTS ops_audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL,
  resource TEXT NOT NULL, detail TEXT NOT NULL);
"""


class CampusOpsStore:
    schema_version = 1

    def __init__(self, path: Path | str):
        self.path = Path(path).absolute()
        if self.path.suffix != ".sqlite3" or not self.path.parent.is_dir():
            raise ValueError("explicit existing directory and .sqlite3 filename required")
        with self.tx() as c:
            for statement in [s for s in SCHEMA.split(";") if s.strip()]:
                c.execute(statement)
            c.execute("INSERT OR IGNORE INTO ops_meta(key,value) VALUES('schema_version',?)", (str(self.schema_version),))
        self.seed()

    def _connect(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=15, isolation_level=None, check_same_thread=False)
        c.row_factory = sqlite3.Row
        enable_wal(c)
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA synchronous=NORMAL")
        return c

    @contextmanager
    def tx(self):
        c = self._connect()
        try:
            c.execute("BEGIN IMMEDIATE")
            yield c
            c.execute("COMMIT")
        except BaseException:
            try:
                c.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            c.close()

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        c = self._connect()
        try:
            return [dict(r) for r in c.execute(sql, tuple(params)).fetchall()]
        finally:
            c.close()

    def one(self, sql: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    @staticmethod
    def audit(c: sqlite3.Connection, actor: str, action: str, resource: str, detail: dict[str, Any] | None = None) -> None:
        c.execute("INSERT INTO ops_audit(at,actor,action,resource,detail) VALUES(?,?,?,?,?)",
                  (now_iso(), actor, action, resource, json.dumps(detail or {}, ensure_ascii=False)))

    @staticmethod
    def notify(c: sqlite3.Connection, recipient: str, kind: str, title: str, body: str, link: str = "") -> None:
        c.execute("INSERT INTO ops_notifications(id,recipient_subject_id,kind,title,body,link,created_at) VALUES(?,?,?,?,?,?,?)",
                  (uuid7(), recipient, kind, title, body, link, now_iso()))

    # ------------------------------------------------------------------ seed
    def seed(self) -> None:
        """Idempotent: rooms once; timetable once per synthetic owner key."""
        from campus247.infrastructure.repositories.campus_ops_seed import ROOMS, student_timetable
        with self.tx() as c:
            if not c.execute("SELECT 1 FROM ops_rooms LIMIT 1").fetchone():
                for r in ROOMS:
                    c.execute("INSERT INTO ops_rooms(id,code,name,building,floor,capacity,kind,features,status,source) VALUES(?,?,?,?,?,?,?,?,?,?)",
                              (uuid7(), r["code"], r["name"], r["building"], r["floor"], r["capacity"], r["kind"],
                               json.dumps(r["features"]), r.get("status", "ACTIVE"), SEED_SOURCE))
                self.audit(c, "system", "seed.rooms", "ops_rooms", {"count": len(ROOMS)})
            marker = "seeded_timetable:LOCAL-STUDENT-001"
            if not c.execute("SELECT 1 FROM ops_meta WHERE key=?", (marker,)).fetchone():
                rows = student_timetable("LOCAL-STUDENT-001")
                stamp = now_iso()
                for r in rows:
                    c.execute("""INSERT INTO ops_schedule(id,owner_key,kind,course_code,course_name,starts_at,ends_at,location,instructor,note,source,created_at,updated_at)
                                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                              (uuid7(), "LOCAL-STUDENT-001", r["kind"], r["course_code"], r["course_name"], r["starts_at"],
                               r["ends_at"], r["location"], r["instructor"], r.get("note", ""), SEED_SOURCE, stamp, stamp))
                c.execute("INSERT INTO ops_meta(key,value) VALUES(?,?)", (marker, str(len(rows))))
                self.audit(c, "system", "seed.timetable", "LOCAL-STUDENT-001", {"count": len(rows)})
            if not c.execute("SELECT 1 FROM ops_meta WHERE key='seeded_tickets'").fetchone():
                self._seed_tickets(c)
                c.execute("INSERT INTO ops_meta(key,value) VALUES('seeded_tickets','5')")

    def _seed_tickets(self, c: sqlite3.Connection) -> None:
        """A few clearly synthetic tickets from invented students so the staff queue is not empty on first use."""
        now = datetime.now(timezone.utc)
        iso = lambda dt: dt.isoformat(timespec="seconds")
        # Codes continue after any ticket that already exists, so seeding never collides with real data.
        existing = c.execute("SELECT COUNT(*) FROM ops_tickets").fetchone()[0]
        samples = [
            ("Sinh viên mô phỏng 01", "LOCAL-SYNTH-001", "STUDENT_CERTIFICATE", "Giấy xác nhận sinh viên đang học",
             "Mục đích: Xin tạm hoãn nghĩa vụ quân sự\nĐơn vị nhận: Ban chỉ huy quân sự quận\nNội dung: Em cần giấy xác nhận đang theo học để nộp cho địa phương.",
             {"purpose": "Xin tạm hoãn nghĩa vụ quân sự", "recipient": "Ban chỉ huy quân sự quận"}, "SUBMITTED", None, timedelta(hours=20)),
            ("Sinh viên mô phỏng 02", "LOCAL-SYNTH-002", "GRADE_APPEAL", "Phúc khảo kết quả học tập",
             "Học phần: Cơ sở dữ liệu\nNội dung: Em xin phúc khảo bài thi giữa kỳ vì thấy điểm câu 3 chưa khớp với đáp án công bố.",
             {"course": "Cơ sở dữ liệu"}, "SUBMITTED", None, timedelta(days=9)),
            ("Sinh viên mô phỏng 03", "LOCAL-SYNTH-003", "GENERAL_SUPPORT", "Hỗ trợ thủ tục học vụ",
             "Nội dung: Em muốn hỏi thủ tục đăng ký học phần muộn do trùng lịch thực tập.",
             {"reason": "Đăng ký học phần muộn"}, "NEED_INFO", ("synthetic-officer-01", "Cán bộ Phòng Đào tạo (mô phỏng)"), timedelta(days=3)),
            ("Sinh viên mô phỏng 04", "LOCAL-SYNTH-004", "STUDENT_CERTIFICATE", "Giấy xác nhận sinh viên đang học",
             "Mục đích: Làm hồ sơ vay vốn sinh viên\nĐơn vị nhận: Ngân hàng chính sách xã hội\nNội dung: Cần giấy xác nhận để hoàn thiện hồ sơ vay.",
             {"purpose": "Làm hồ sơ vay vốn sinh viên", "recipient": "Ngân hàng chính sách xã hội"}, "RESOLVED",
             ("synthetic-officer-01", "Cán bộ Phòng Đào tạo (mô phỏng)"), timedelta(days=6)),
            ("Sinh viên mô phỏng 05", "LOCAL-SYNTH-005", "GENERAL_SUPPORT", "Hỗ trợ thủ tục học vụ",
             "Nội dung: Cho em hỏi cách xin bảo lưu kết quả học tập một học kỳ vì lý do sức khỏe.",
             {"reason": "Xin bảo lưu kết quả học tập"}, "SUBMITTED", None, timedelta(hours=3)),
        ]
        for index, (name, code, kind, title, summary, fields, status, assignee, age) in enumerate(samples, start=1):
            created = now - age
            ticket_id, owner = uuid7(), uuid7()
            c.execute("""INSERT INTO ops_tickets(id,code,owner_subject_id,owner_display,owner_code,service_kind,title,summary,fields,status,priority,
                         assignee_subject_id,assignee_display,created_at,updated_at,due_at,idempotency_key) VALUES(?,?,?,?,?,?,?,?,?,?,'NORMAL',?,?,?,?,?,?)""",
                      (ticket_id, f"HS-2026-{existing + index:06d}", owner, name, code, kind, title, summary, json.dumps(fields, ensure_ascii=False),
                       status, assignee[0] if assignee else None, assignee[1] if assignee else None, iso(created),
                       iso(created + timedelta(hours=2 if status != 'SUBMITTED' else 0)), iso(created + timedelta(days=7)), f"seed-{index}"))
            def event(kind_, who, role, body, offset, visibility="PUBLIC"):
                c.execute("INSERT INTO ops_ticket_events(id,ticket_id,actor_subject_id,actor_role,actor_display,kind,body,visibility,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                          (uuid7(), ticket_id, owner if role == "STUDENT" else "synthetic-officer-01", role, who, kind_, body, visibility, iso(created + offset)))
            event("CREATED", name, "STUDENT", "Sinh viên gửi hồ sơ.", timedelta(0))
            if assignee:
                event("CLAIMED", assignee[1], "SUPPORT_OFFICER", "Cán bộ tiếp nhận hồ sơ.", timedelta(minutes=30))
            if status == "NEED_INFO":
                event("STAFF_REPLY", assignee[1], "SUPPORT_OFFICER", "Bạn cho biết thêm học phần nào bị trùng lịch và tên cơ sở thực tập.", timedelta(hours=1))
            if status == "RESOLVED":
                event("STAFF_REPLY", assignee[1], "SUPPORT_OFFICER", "Đã cấp giấy xác nhận, bạn nhận bản giấy tại Phòng Đào tạo trong giờ hành chính.", timedelta(hours=26))
                event("STATUS_CHANGE", assignee[1], "SUPPORT_OFFICER", "Trạng thái: IN_REVIEW → RESOLVED", timedelta(hours=26, seconds=1))
        self.audit(c, "system", "seed.tickets", "ops_tickets", {"count": len(samples), "synthetic": True})
