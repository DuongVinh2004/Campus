"""Business rules for rooms, personal timetable, notifications and ticket handling.

Deterministic code only: routes authenticate, this module authorizes, validates and writes through
the store inside one transaction, appending an audit row for every state change.
"""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from campus247.ports.campus_ops import ICT, CampusOpsStorePort, OpsError, now_iso, uuid7
from campus247.ports.identity import IdentityContext, IdentityRole

OPEN_TIME, CLOSE_TIME = time(7, 0), time(21, 0)
MIN_MINUTES, MAX_MINUTES, STEP_MINUTES = 30, 240, 15
HORIZON_DAYS = 14
MAX_ACTIVE_BOOKINGS = 3
MAX_BATCH_ROOMS = 60
PREVIEW_TTL = timedelta(minutes=10)
STAFF_ROLES = {IdentityRole.SUPPORT_OFFICER, IdentityRole.SYSTEM_ADMIN}
ADMIN_ROLES = {IdentityRole.SYSTEM_ADMIN, IdentityRole.KNOWLEDGE_ADMIN}

SERVICE_KINDS = {
    "STUDENT_CERTIFICATE": "Giấy xác nhận sinh viên đang học",
    "GRADE_APPEAL": "Phúc khảo kết quả học tập",
    "GENERAL_SUPPORT": "Hỗ trợ thủ tục học vụ",
}
TICKET_OPEN = ("SUBMITTED", "IN_REVIEW", "NEED_INFO")
TICKET_STATUSES = TICKET_OPEN + ("RESOLVED", "REJECTED", "CANCELLED")
STAFF_TARGETS = {"IN_REVIEW", "NEED_INFO", "RESOLVED", "REJECTED"}
STATUS_LABELS = {"SUBMITTED": "Đã gửi, chờ tiếp nhận", "IN_REVIEW": "Đang xử lý", "NEED_INFO": "Cần bổ sung thông tin",
                 "RESOLVED": "Đã giải quyết", "REJECTED": "Từ chối", "CANCELLED": "Đã hủy"}
ROLE_LABELS = {"STUDENT": "Sinh viên", "SUPPORT_OFFICER": "Cán bộ Một cửa", "SYSTEM_ADMIN": "Quản trị hệ thống",
               "KNOWLEDGE_ADMIN": "Quản trị tri thức"}
SLA_DAYS = 7


def _parse(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        raise OpsError(422, "INVALID_DATETIME", f"Giá trị '{field}' không phải thời điểm hợp lệ.") from None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ICT)
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def is_staff(identity: IdentityContext) -> bool:
    return bool(STAFF_ROLES.intersection(identity.roles))


def require_staff(identity: IdentityContext) -> None:
    if not is_staff(identity):
        raise OpsError(403, "FORBIDDEN", "Chỉ cán bộ được phân quyền mới dùng chức năng này.")


def require_admin(identity: IdentityContext) -> None:
    if not ADMIN_ROLES.intersection(identity.roles):
        raise OpsError(403, "FORBIDDEN", "Chỉ quản trị viên mới xem được trang này.")


def require_student(identity: IdentityContext) -> str:
    if IdentityRole.STUDENT not in identity.roles or not identity.student_code:
        raise OpsError(403, "FORBIDDEN", "Chức năng này dành cho tài khoản sinh viên.")
    return identity.student_code


def _role_label(identity: IdentityContext) -> str:
    for role in (IdentityRole.SYSTEM_ADMIN, IdentityRole.SUPPORT_OFFICER, IdentityRole.KNOWLEDGE_ADMIN, IdentityRole.STUDENT):
        if role in identity.roles:
            return role.value
    return "UNKNOWN"


class CampusOpsService:
    def __init__(self, store: CampusOpsStorePort):
        self.store = store

    # ------------------------------------------------------------------ rooms
    def list_rooms(self, *, building: str | None, kind: str | None, min_capacity: int | None, q: str | None) -> dict[str, Any]:
        rows = self.store.query("SELECT * FROM ops_rooms ORDER BY building, code")
        items = []
        for r in rows:
            if building and r["building"] != building:
                continue
            if kind and r["kind"] != kind:
                continue
            if min_capacity and r["capacity"] < min_capacity:
                continue
            if q and q.casefold() not in f"{r['code']} {r['name']} {r['building']}".casefold():
                continue
            items.append(self._room_view(r))
        buildings = sorted({r["building"] for r in rows})
        return {"items": items, "buildings": buildings,
                "source": rows[0]["source"] if rows else "", "limits": self.booking_limits()}

    @staticmethod
    def booking_limits() -> dict[str, Any]:
        return {"open": "07:00", "close": "21:00", "min_minutes": MIN_MINUTES, "max_minutes": MAX_MINUTES,
                "step_minutes": STEP_MINUTES, "horizon_days": HORIZON_DAYS, "max_active_bookings": MAX_ACTIVE_BOOKINGS}

    @staticmethod
    def _room_view(r: dict[str, Any]) -> dict[str, Any]:
        return {"id": r["id"], "room_code": r["code"], "display_name": r["name"], "building": r["building"],
                "floor": r["floor"], "capacity": r["capacity"], "kind": r["kind"], "features": json.loads(r["features"]),
                "status": r["status"], "source": r["source"]}

    def _room(self, room_id: str) -> dict[str, Any]:
        room = self.store.one("SELECT * FROM ops_rooms WHERE id=?", (room_id,))
        if room is None:
            raise OpsError(404, "ROOM_NOT_FOUND", "Không tìm thấy phòng.")
        return room

    def _busy(self, room: dict[str, Any], start_utc: datetime, end_utc: datetime, *, conn=None) -> list[dict[str, Any]]:
        sql_b = """SELECT id, starts_at, ends_at, purpose FROM ops_room_bookings
                   WHERE room_id=? AND status='CONFIRMED' AND starts_at<? AND ends_at>?"""
        sql_s = """SELECT DISTINCT starts_at, ends_at, course_code, course_name, kind FROM ops_schedule
                   WHERE location=? AND deleted_at IS NULL AND kind IN ('CLASS','EXAM') AND starts_at<? AND ends_at>?"""
        args = (room["id"], _iso(end_utc), _iso(start_utc))
        if conn is None:
            bookings = self.store.query(sql_b, args)
            classes = self.store.query(sql_s, (room["code"], _iso(end_utc), _iso(start_utc)))
        else:
            bookings = [dict(x) for x in conn.execute(sql_b, args).fetchall()]
            classes = [dict(x) for x in conn.execute(sql_s, (room["code"], _iso(end_utc), _iso(start_utc))).fetchall()]
        busy = [{"starts_at": b["starts_at"], "ends_at": b["ends_at"], "type": "BOOKING", "label": "Đã có người đặt"} for b in bookings]
        busy += [{"starts_at": s["starts_at"], "ends_at": s["ends_at"], "type": "EXAM" if s["kind"] == "EXAM" else "CLASS",
                  "label": f"{s['course_code']} · {s['course_name']}"} for s in classes]
        return sorted(busy, key=lambda x: x["starts_at"])

    def availability(self, room_id: str, day: str) -> dict[str, Any]:
        room = self._room(room_id)
        try:
            d = date.fromisoformat(day)
        except ValueError:
            raise OpsError(422, "INVALID_DATE", "Ngày phải có dạng YYYY-MM-DD.") from None
        start = datetime.combine(d, OPEN_TIME, tzinfo=ICT).astimezone(timezone.utc)
        end = datetime.combine(d, CLOSE_TIME, tzinfo=ICT).astimezone(timezone.utc)
        return {"room": self._room_view(room), "date": day, "open": "07:00", "close": "21:00",
                "busy": self._busy(room, start, end), "limits": self.booking_limits()}

    def availability_many(self, room_ids: list[str], day: str) -> dict[str, Any]:
        """Same answer as `availability` for each room, in a constant number of queries (one page load asks for ~34 rooms)."""
        try:
            d = date.fromisoformat(day)
        except ValueError:
            raise OpsError(422, "INVALID_DATE", "Ngày phải có dạng YYYY-MM-DD.") from None
        if (not room_ids or len(room_ids) > MAX_BATCH_ROOMS or len(set(room_ids)) != len(room_ids)
                or any(not isinstance(i, str) or not i or len(i) > 64 for i in room_ids)):
            raise OpsError(422, "INVALID_ROOM_IDS", f"Cần từ 1 đến {MAX_BATCH_ROOMS} mã phòng, không trùng nhau.")
        start = datetime.combine(d, OPEN_TIME, tzinfo=ICT).astimezone(timezone.utc)
        end = datetime.combine(d, CLOSE_TIME, tzinfo=ICT).astimezone(timezone.utc)
        marks = ",".join("?" * len(room_ids))
        rooms = {r["id"]: r for r in self.store.query(f"SELECT * FROM ops_rooms WHERE id IN ({marks})", room_ids)}
        found = [rooms[i] for i in room_ids if i in rooms]
        busy: dict[str, list[dict[str, Any]]] = {r["id"]: [] for r in found}
        if found:
            by_code = {r["code"]: r["id"] for r in found}
            id_marks, code_marks = ",".join("?" * len(found)), ",".join("?" * len(by_code))
            bookings = self.store.query(
                f"""SELECT room_id, starts_at, ends_at FROM ops_room_bookings
                    WHERE room_id IN ({id_marks}) AND status='CONFIRMED' AND starts_at<? AND ends_at>?""",
                [r["id"] for r in found] + [_iso(end), _iso(start)])
            classes = self.store.query(
                f"""SELECT DISTINCT location, starts_at, ends_at, course_code, course_name, kind FROM ops_schedule
                    WHERE location IN ({code_marks}) AND deleted_at IS NULL AND kind IN ('CLASS','EXAM') AND starts_at<? AND ends_at>?""",
                list(by_code) + [_iso(end), _iso(start)])
            for b in bookings:
                busy[b["room_id"]].append({"starts_at": b["starts_at"], "ends_at": b["ends_at"], "type": "BOOKING", "label": "Đã có người đặt"})
            for s in classes:
                busy[by_code[s["location"]]].append({"starts_at": s["starts_at"], "ends_at": s["ends_at"],
                                                     "type": "EXAM" if s["kind"] == "EXAM" else "CLASS",
                                                     "label": f"{s['course_code']} · {s['course_name']}"})
        return {"date": day, "open": "07:00", "close": "21:00", "limits": self.booking_limits(),
                "items": [{"room": self._room_view(r), "busy": sorted(busy[r["id"]], key=lambda x: x["starts_at"])} for r in found],
                "missing": [i for i in room_ids if i not in rooms]}

    def _validate_slot(self,room: dict[str, Any], day: str, start: str, end: str, attendees: int) -> tuple[datetime, datetime]:
        try:
            d = date.fromisoformat(day)
            t0, t1 = time.fromisoformat(start), time.fromisoformat(end)
        except ValueError:
            raise OpsError(422, "INVALID_SLOT", "Ngày hoặc giờ không hợp lệ.") from None
        if room["status"] != "ACTIVE":
            raise OpsError(409, "ROOM_UNAVAILABLE", "Phòng đang bảo trì, chưa nhận đặt chỗ.")
        if not (OPEN_TIME <= t0 < t1 <= CLOSE_TIME):
            raise OpsError(422, "OUTSIDE_HOURS", "Chỉ nhận đặt chỗ trong khung 07:00–21:00.")
        minutes = (datetime.combine(d, t1) - datetime.combine(d, t0)).seconds // 60
        if minutes < MIN_MINUTES or minutes > MAX_MINUTES or t0.minute % STEP_MINUTES or t1.minute % STEP_MINUTES:
            raise OpsError(422, "INVALID_DURATION", f"Thời lượng từ {MIN_MINUTES} đến {MAX_MINUTES} phút, theo bước {STEP_MINUTES} phút.")
        if attendees < 1 or attendees > room["capacity"]:
            raise OpsError(422, "CAPACITY_EXCEEDED", f"Số người phải từ 1 đến sức chứa của phòng ({room['capacity']}).")
        starts = datetime.combine(d, t0, tzinfo=ICT).astimezone(timezone.utc)
        ends = datetime.combine(d, t1, tzinfo=ICT).astimezone(timezone.utc)
        now = datetime.now(timezone.utc)
        if starts <= now:
            raise OpsError(422, "IN_THE_PAST", "Không đặt được khung giờ đã qua.")
        if starts > now + timedelta(days=HORIZON_DAYS):
            raise OpsError(422, "TOO_FAR", f"Chỉ đặt trước tối đa {HORIZON_DAYS} ngày.")
        return starts, ends

    def preview_booking(self, identity: IdentityContext, body: dict[str, Any]) -> dict[str, Any]:
        room = self._room(str(body.get("room_id", "")))
        purpose = str(body.get("purpose", "")).strip()
        if not 3 <= len(purpose) <= 200:
            raise OpsError(422, "INVALID_PURPOSE", "Mục đích sử dụng cần từ 3 đến 200 ký tự.")
        try:
            attendees = int(body.get("attendees", 1))
        except (TypeError, ValueError):
            raise OpsError(422, "INVALID_ATTENDEES", "Số người tham gia không hợp lệ.") from None
        starts, ends = self._validate_slot(room, str(body.get("date", "")), str(body.get("start", "")), str(body.get("end", "")), attendees)
        conflicts = self._busy(room, starts, ends)
        active = self.store.one("SELECT COUNT(*) n FROM ops_room_bookings WHERE owner_subject_id=? AND status='CONFIRMED' AND ends_at>?",
                                (identity.subject_id, now_iso()))["n"]
        problems = []
        if conflicts:
            problems.append("Khung giờ trùng với lịch đã có của phòng.")
        if active >= MAX_ACTIVE_BOOKINGS:
            problems.append(f"Bạn đã có {MAX_ACTIVE_BOOKINGS} lượt đặt phòng còn hiệu lực; hủy bớt trước khi đặt thêm.")
        payload = {"room_id": room["id"], "starts_at": _iso(starts), "ends_at": _iso(ends), "purpose": purpose, "attendees": attendees}
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        preview_id = uuid7()
        expires = datetime.now(timezone.utc) + PREVIEW_TTL
        with self.store.tx() as c:
            c.execute("INSERT INTO ops_booking_previews(id,owner_subject_id,payload,payload_hash,expires_at) VALUES(?,?,?,?,?)",
                      (preview_id, identity.subject_id, json.dumps(payload), digest, _iso(expires)))
        return {"preview_id": preview_id, "can_confirm": not problems, "problems": problems, "conflicts": conflicts,
                "expires_at": _iso(expires), "summary": {**payload, "room_code": room["code"], "room_name": room["name"]},
                "notice": "Chưa ghi nhận cho đến khi bạn xác nhận."}

    def confirm_booking(self, identity: IdentityContext, preview_id: str, idempotency_key: str) -> dict[str, Any]:
        if not idempotency_key or len(idempotency_key) > 120:
            raise OpsError(422, "IDEMPOTENCY_REQUIRED", "Thiếu khóa chống gửi trùng (Idempotency-Key).")
        with self.store.tx() as c:
            replay = c.execute("SELECT * FROM ops_room_bookings WHERE owner_subject_id=? AND idempotency_key=?",
                               (identity.subject_id, idempotency_key)).fetchone()
            if replay is not None:
                return {**self._booking_view(dict(replay)), "replayed": True}
            preview = c.execute("SELECT * FROM ops_booking_previews WHERE id=?", (preview_id,)).fetchone()
            if preview is None or preview["owner_subject_id"] != identity.subject_id:
                raise OpsError(404, "PREVIEW_NOT_FOUND", "Không tìm thấy bản xem trước; hãy xem trước lại.")
            if preview["used_at"] is not None:
                raise OpsError(409, "PREVIEW_USED", "Bản xem trước này đã được dùng.")
            if preview["expires_at"] <= now_iso():
                raise OpsError(410, "PREVIEW_EXPIRED", "Bản xem trước đã hết hạn; hãy xem trước lại.")
            payload = json.loads(preview["payload"])
            if hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest() != preview["payload_hash"]:
                raise OpsError(409, "PREVIEW_TAMPERED", "Nội dung xem trước không khớp.")
            room = dict(c.execute("SELECT * FROM ops_rooms WHERE id=?", (payload["room_id"],)).fetchone())
            starts, ends = _parse(payload["starts_at"], "starts_at"), _parse(payload["ends_at"], "ends_at")
            self._validate_slot(room, starts.astimezone(ICT).date().isoformat(), starts.astimezone(ICT).strftime("%H:%M"),
                                ends.astimezone(ICT).strftime("%H:%M"), payload["attendees"])
            if self._busy(room, starts, ends, conn=c):
                raise OpsError(409, "SLOT_TAKEN", "Khung giờ vừa có người đặt trước; hãy chọn khung khác.")
            active = c.execute("SELECT COUNT(*) n FROM ops_room_bookings WHERE owner_subject_id=? AND status='CONFIRMED' AND ends_at>?",
                               (identity.subject_id, now_iso())).fetchone()["n"]
            if active >= MAX_ACTIVE_BOOKINGS:
                raise OpsError(409, "BOOKING_LIMIT", f"Bạn đã có {MAX_ACTIVE_BOOKINGS} lượt đặt phòng còn hiệu lực.")
            booking_id, code = uuid7(), "BK-" + starts.astimezone(ICT).strftime("%y%m%d") + "-" + secrets.token_hex(2).upper()
            c.execute("""INSERT INTO ops_room_bookings(id,code,room_id,owner_subject_id,owner_display,starts_at,ends_at,purpose,attendees,status,idempotency_key,created_at)
                         VALUES(?,?,?,?,?,?,?,?,?,'CONFIRMED',?,?)""",
                      (booking_id, code, room["id"], identity.subject_id, identity.display_name, payload["starts_at"], payload["ends_at"],
                       payload["purpose"], payload["attendees"], idempotency_key, now_iso()))
            c.execute("UPDATE ops_booking_previews SET used_at=? WHERE id=?", (now_iso(), preview_id))
            when = starts.astimezone(ICT).strftime("%H:%M %d/%m/%Y")
            self.store.notify(c, identity.subject_id, "ROOM_BOOKING", "Đã đặt phòng " + room["code"],
                              f"Mã {code} · {when} · {payload['purpose']}", "/rooms")
            self.store.audit(c, identity.subject_id, "room.book", booking_id, {"room": room["code"], "code": code})
            row = dict(c.execute("SELECT * FROM ops_room_bookings WHERE id=?", (booking_id,)).fetchone())
        return {**self._booking_view(row), "replayed": False}

    def _booking_view(self, b: dict[str, Any]) -> dict[str, Any]:
        room = self.store.one("SELECT code,name,building FROM ops_rooms WHERE id=?", (b["room_id"],)) or {}
        return {"id": b["id"], "booking_id": b["id"], "code": b["code"], "room_id": b["room_id"], "room_code": room.get("code", ""),
                "room_name": room.get("name", ""), "building": room.get("building", ""), "starts_at": b["starts_at"],
                "ends_at": b["ends_at"], "purpose": b["purpose"], "attendees": b["attendees"], "status": b["status"],
                "created_at": b["created_at"], "cancelled_at": b["cancelled_at"],
                "can_cancel": b["status"] == "CONFIRMED" and b["starts_at"] > now_iso()}

    def my_bookings(self, identity: IdentityContext) -> dict[str, Any]:
        rows = self.store.query("SELECT * FROM ops_room_bookings WHERE owner_subject_id=? ORDER BY starts_at DESC LIMIT 100",
                                (identity.subject_id,))
        return {"items": [self._booking_view(r) for r in rows]}

    def cancel_booking(self, identity: IdentityContext, booking_id: str, reason: str) -> dict[str, Any]:
        with self.store.tx() as c:
            row = c.execute("SELECT * FROM ops_room_bookings WHERE id=?", (booking_id,)).fetchone()
            if row is None or (row["owner_subject_id"] != identity.subject_id and not is_staff(identity)):
                raise OpsError(404, "BOOKING_NOT_FOUND", "Không tìm thấy lượt đặt phòng.")
            if row["status"] != "CONFIRMED":
                return {**self._booking_view(dict(row)), "already": True}
            if row["starts_at"] <= now_iso():
                raise OpsError(409, "ALREADY_STARTED", "Lượt đặt đã bắt đầu, không hủy được.")
            c.execute("UPDATE ops_room_bookings SET status='CANCELLED', cancelled_at=?, cancel_reason=? WHERE id=?",
                      (now_iso(), reason.strip()[:200], booking_id))
            self.store.notify(c, row["owner_subject_id"], "ROOM_BOOKING", "Đã hủy đặt phòng", f"Mã {row['code']} đã được hủy.", "/rooms")
            self.store.audit(c, identity.subject_id, "room.cancel", booking_id, {"code": row["code"]})
            updated = dict(c.execute("SELECT * FROM ops_room_bookings WHERE id=?", (booking_id,)).fetchone())
        return self._booking_view(updated)

    # --------------------------------------------------------------- schedule
    def list_schedule(self, identity: IdentityContext, frm: str, to: str) -> dict[str, Any]:
        code = require_student(identity)
        start, end = _parse(frm, "from"), _parse(to, "to")
        if start >= end or end - start > timedelta(days=370):
            raise OpsError(422, "INVALID_RANGE", "Khoảng thời gian không hợp lệ (tối đa 370 ngày).")
        rows = self.store.query("""SELECT * FROM ops_schedule WHERE owner_key=? AND deleted_at IS NULL AND starts_at<? AND ends_at>?
                                   ORDER BY starts_at LIMIT 2000""", (code, _iso(end), _iso(start)))
        return {"items": [self._event_view(r) for r in rows], "page": {"next_cursor": None, "has_more": False, "limit": 2000},
                "sources": sorted({r["source"] for r in rows})}

    def schedule_ics(self, identity: IdentityContext, frm: str, to: str) -> str:
        """The caller's own timetable for a range as an iCalendar file. Same access and range rules as list_schedule."""
        from campus247.application.campus_ops.ics import IcsEvent, build_ics

        def moment(text: str) -> datetime:
            value = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

        events = []
        for item in self.list_schedule(identity, frm, to)["items"]:
            exam = item["kind"] == "EXAM"
            details = [f"Giảng viên: {item['instructor_display_name']}"] if item["instructor_display_name"] else []
            if item["note"]:
                details.append(item["note"])
            details.append(f"Nguồn: {item['source_system']} (không phải lịch chính thức của trường nếu là dữ liệu tổng hợp)")
            events.append(IcsEvent(id=item["id"], title=("[Thi] " if exam else "") + f"{item['course_name']} ({item['course_code']})",
                                   starts_at=moment(item["starts_at"]), ends_at=moment(item["ends_at"]), location=item["location_label"] or "",
                                   description="\n".join(details)))
        return build_ics(events, now=datetime.now(timezone.utc))[0]

    @staticmethod
    def _event_view(r: dict[str, Any]) -> dict[str, Any]:
        return {"id": r["id"], "kind": r["kind"], "course_code": r["course_code"], "course_name": r["course_name"],
                "starts_at": r["starts_at"], "ends_at": r["ends_at"], "location_label": r["location"],
                "instructor_display_name": r["instructor"], "note": r["note"], "source_system": r["source"],
                "editable": r["kind"] == "PERSONAL"}

    def _event_fields(self, body: dict[str, Any]) -> dict[str, Any]:
        title = str(body.get("title", "")).strip()
        if not 1 <= len(title) <= 120:
            raise OpsError(422, "INVALID_TITLE", "Tên sự kiện cần từ 1 đến 120 ký tự.")
        start, end = _parse(str(body.get("starts_at", "")), "starts_at"), _parse(str(body.get("ends_at", "")), "ends_at")
        if end <= start or end - start > timedelta(hours=24):
            raise OpsError(422, "INVALID_RANGE", "Giờ kết thúc phải sau giờ bắt đầu và không quá 24 giờ.")
        return {"title": title, "starts_at": _iso(start), "ends_at": _iso(end),
                "location": str(body.get("location", "")).strip()[:120], "note": str(body.get("note", "")).strip()[:500]}

    def create_event(self, identity: IdentityContext, body: dict[str, Any]) -> dict[str, Any]:
        code = require_student(identity)
        f = self._event_fields(body)
        stamp, event_id = now_iso(), uuid7()
        with self.store.tx() as c:
            if c.execute("SELECT COUNT(*) n FROM ops_schedule WHERE owner_key=? AND kind='PERSONAL' AND deleted_at IS NULL", (code,)).fetchone()["n"] >= 500:
                raise OpsError(409, "EVENT_LIMIT", "Đã đạt giới hạn 500 sự kiện cá nhân.")
            c.execute("""INSERT INTO ops_schedule(id,owner_key,kind,course_code,course_name,starts_at,ends_at,location,instructor,note,source,created_at,updated_at)
                         VALUES(?,?,'PERSONAL','CÁ NHÂN',?,?,?,?,?,?,'USER',?,?)""",
                      (event_id, code, f["title"], f["starts_at"], f["ends_at"], f["location"], identity.display_name, f["note"], stamp, stamp))
            self.store.audit(c, identity.subject_id, "schedule.create", event_id, {})
            row = dict(c.execute("SELECT * FROM ops_schedule WHERE id=?", (event_id,)).fetchone())
        return self._event_view(row)

    def _own_event(self, c, identity: IdentityContext, event_id: str):
        code = require_student(identity)
        row = c.execute("SELECT * FROM ops_schedule WHERE id=? AND owner_key=? AND deleted_at IS NULL", (event_id, code)).fetchone()
        if row is None:
            raise OpsError(404, "EVENT_NOT_FOUND", "Không tìm thấy sự kiện.")
        if row["kind"] != "PERSONAL":
            raise OpsError(403, "EVENT_READ_ONLY", "Lịch học và lịch thi chỉ đọc; chỉ sự kiện cá nhân mới sửa được.")
        return row

    def update_event(self, identity: IdentityContext, event_id: str, body: dict[str, Any]) -> dict[str, Any]:
        f = self._event_fields(body)
        with self.store.tx() as c:
            self._own_event(c, identity, event_id)
            c.execute("UPDATE ops_schedule SET course_name=?,starts_at=?,ends_at=?,location=?,note=?,updated_at=? WHERE id=?",
                      (f["title"], f["starts_at"], f["ends_at"], f["location"], f["note"], now_iso(), event_id))
            self.store.audit(c, identity.subject_id, "schedule.update", event_id, {})
            row = dict(c.execute("SELECT * FROM ops_schedule WHERE id=?", (event_id,)).fetchone())
        return self._event_view(row)

    def delete_event(self, identity: IdentityContext, event_id: str) -> dict[str, Any]:
        with self.store.tx() as c:
            self._own_event(c, identity, event_id)
            c.execute("UPDATE ops_schedule SET deleted_at=?,updated_at=? WHERE id=?", (now_iso(), now_iso(), event_id))
            self.store.audit(c, identity.subject_id, "schedule.delete", event_id, {})
        return {"id": event_id, "deleted": True}

    # ---------------------------------------------------------- notifications
    REMINDER_KINDS = ("exam", "sources")

    def reminder_preferences(self, identity: IdentityContext) -> dict[str, bool]:
        """Which kinds of reminders the caller receives. Everything is on until the person switches it off."""
        from campus247.application.campus_ops.reminders import PREFS_SCHEMA
        with self.store.tx() as c:
            c.execute(PREFS_SCHEMA)
            stored = {row[0]: bool(row[1]) for row in c.execute("SELECT kind, enabled FROM ops_reminder_prefs WHERE subject_id = ?", (identity.subject_id,))}
        return {kind: stored.get(kind, True) for kind in self.REMINDER_KINDS}

    def set_reminder_preferences(self, identity: IdentityContext, body: dict[str, Any]) -> dict[str, bool]:
        from campus247.application.campus_ops.reminders import PREFS_SCHEMA
        if not body or set(body) - set(self.REMINDER_KINDS) or any(type(value) is not bool for value in body.values()):
            raise OpsError(422, "INVALID_PREFERENCE", "Chỉ được bật hoặc tắt các loại nhắc: " + ", ".join(self.REMINDER_KINDS) + ".")
        with self.store.tx() as c:
            c.execute(PREFS_SCHEMA)
            for kind, enabled in body.items():
                c.execute("""INSERT INTO ops_reminder_prefs(subject_id, kind, enabled, updated_at) VALUES (?,?,?,?)
                             ON CONFLICT(subject_id, kind) DO UPDATE SET enabled = excluded.enabled, updated_at = excluded.updated_at""",
                          (identity.subject_id, kind, int(enabled), now_iso()))
            self.store.audit(c, identity.subject_id, "reminders.preferences", identity.subject_id, {kind: enabled for kind, enabled in body.items()})
        return self.reminder_preferences(identity)

    def list_notifications(self, identity: IdentityContext, unread_only: bool, limit: int) -> dict[str, Any]:
        where = "recipient_subject_id=?" + (" AND read_at IS NULL" if unread_only else "")
        rows = self.store.query(f"SELECT * FROM ops_notifications WHERE {where} ORDER BY created_at DESC LIMIT ?",
                                (identity.subject_id, max(1, min(limit, 100))))
        unread = self.store.one("SELECT COUNT(*) n FROM ops_notifications WHERE recipient_subject_id=? AND read_at IS NULL",
                                (identity.subject_id,))["n"]
        return {"items": [{"id": r["id"], "kind": r["kind"], "title": r["title"], "body": r["body"], "link": r["link"],
                           "created_at": r["created_at"], "read": r["read_at"] is not None} for r in rows], "unread_count": unread}

    def mark_read(self, identity: IdentityContext, notification_id: str | None) -> dict[str, Any]:
        with self.store.tx() as c:
            if notification_id is None:
                n = c.execute("UPDATE ops_notifications SET read_at=? WHERE recipient_subject_id=? AND read_at IS NULL",
                              (now_iso(), identity.subject_id)).rowcount
            else:
                n = c.execute("UPDATE ops_notifications SET read_at=? WHERE id=? AND recipient_subject_id=? AND read_at IS NULL",
                              (now_iso(), notification_id, identity.subject_id)).rowcount
        return {"updated": n}

    # ---------------------------------------------------------------- tickets
    def _ticket_view(self, t: dict[str, Any], *, include_assignee: bool = True) -> dict[str, Any]:
        return {"id": t["id"], "code": t["code"], "service_kind": t["service_kind"],
                "service_label": SERVICE_KINDS.get(t["service_kind"], t["service_kind"]), "title": t["title"],
                "summary": t["summary"], "fields": json.loads(t["fields"]), "status": t["status"], "priority": t["priority"],
                "owner_display": t["owner_display"], "owner_code": t["owner_code"],
                "assignee_display": t["assignee_display"] if include_assignee else None,
                "created_at": t["created_at"], "updated_at": t["updated_at"], "due_at": t["due_at"],
                "overdue": bool(t["due_at"] and t["status"] in TICKET_OPEN and t["due_at"] < now_iso())}

    @staticmethod
    def _readable_body(kind: str, body: str) -> str:
        """Status-change events were stored with the raw codes ("SUBMITTED → NEED_INFO"); show the Vietnamese labels, old rows included."""
        if kind != "STATUS_CHANGE":
            return body
        for code, label in STATUS_LABELS.items():
            body = body.replace(code, label)
        return body

    def _events(self, ticket_id: str, *, internal: bool, viewer_subject_id: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM ops_ticket_events WHERE ticket_id=?" + ("" if internal else " AND visibility='PUBLIC'") + " ORDER BY created_at, rowid"
        return [{"id": e["id"], "kind": e["kind"], "actor_role": e["actor_role"],
                 "actor_role_label": ROLE_LABELS.get(e["actor_role"], "Hệ thống"),
                 "actor_kind": "student" if e["actor_role"] == "STUDENT" else ("system" if e["actor_role"] == "UNKNOWN" else "staff"),
                 "is_mine": viewer_subject_id is not None and e["actor_subject_id"] == viewer_subject_id,
                 "actor_display": e["actor_display"], "body": self._readable_body(e["kind"], e["body"]),
                 "visibility": e["visibility"], "created_at": e["created_at"]} for e in self.store.query(sql, (ticket_id,))]

    @staticmethod
    def _add_event(c, ticket_id: str, identity: IdentityContext, kind: str, body: str, visibility: str = "PUBLIC") -> None:
        c.execute("INSERT INTO ops_ticket_events(id,ticket_id,actor_subject_id,actor_role,actor_display,kind,body,visibility,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                  (uuid7(), ticket_id, identity.subject_id, _role_label(identity), identity.display_name, kind, body, visibility, now_iso()))

    def submit_ticket(self, identity: IdentityContext, body: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        code = require_student(identity)
        if not idempotency_key or len(idempotency_key) > 120:
            raise OpsError(422, "IDEMPOTENCY_REQUIRED", "Thiếu khóa chống gửi trùng (Idempotency-Key).")
        kind = str(body.get("service_kind", ""))
        if kind not in SERVICE_KINDS:
            raise OpsError(422, "INVALID_SERVICE", "Loại thủ tục không hợp lệ.")
        title = str(body.get("title", "")).strip() or SERVICE_KINDS[kind]
        summary = str(body.get("summary", "")).strip()
        if not 10 <= len(summary) <= 4000 or len(title) > 150:
            raise OpsError(422, "INVALID_CONTENT", "Nội dung cần từ 10 đến 4000 ký tự và tiêu đề tối đa 150 ký tự.")
        raw_fields = body.get("fields") or {}
        if not isinstance(raw_fields, dict) or len(raw_fields) > 20:
            raise OpsError(422, "INVALID_FIELDS", "Các trường bổ sung không hợp lệ.")
        fields = {str(k)[:60]: str(v)[:500] for k, v in raw_fields.items()}
        with self.store.tx() as c:
            replay = c.execute("SELECT * FROM ops_tickets WHERE owner_subject_id=? AND idempotency_key=?", (identity.subject_id, idempotency_key)).fetchone()
            if replay is not None:
                return {**self._ticket_view(dict(replay)), "replayed": True}
            open_count = c.execute("SELECT COUNT(*) n FROM ops_tickets WHERE owner_subject_id=? AND status IN ('SUBMITTED','IN_REVIEW','NEED_INFO')",
                                   (identity.subject_id,)).fetchone()["n"]
            if open_count >= 10:
                raise OpsError(409, "TICKET_LIMIT", "Bạn đang có 10 hồ sơ chưa xử lý xong; đợi xử lý bớt trước khi gửi thêm.")
            total = c.execute("SELECT COUNT(*) n FROM ops_tickets").fetchone()["n"]
            ticket_id, now = uuid7(), datetime.now(timezone.utc)
            ticket_code = f"HS-{now.astimezone(ICT).year}-{total + 1:06d}"
            c.execute("""INSERT INTO ops_tickets(id,code,owner_subject_id,owner_display,owner_code,service_kind,title,summary,fields,status,priority,
                         created_at,updated_at,due_at,idempotency_key) VALUES(?,?,?,?,?,?,?,?,?,'SUBMITTED','NORMAL',?,?,?,?)""",
                      (ticket_id, ticket_code, identity.subject_id, identity.display_name, code, kind, title, summary,
                       json.dumps(fields, ensure_ascii=False), _iso(now), _iso(now), _iso(now + timedelta(days=SLA_DAYS)), idempotency_key))
            self._add_event(c, ticket_id, identity, "CREATED", "Sinh viên gửi hồ sơ.")
            self.store.notify(c, identity.subject_id, "TICKET", f"Đã gửi hồ sơ {ticket_code}", f"{title} — đang chờ cán bộ tiếp nhận.", f"/tickets?id={ticket_id}")
            self.store.audit(c, identity.subject_id, "ticket.submit", ticket_id, {"code": ticket_code, "kind": kind})
            row = dict(c.execute("SELECT * FROM ops_tickets WHERE id=?", (ticket_id,)).fetchone())
        return {**self._ticket_view(row), "replayed": False}

    def my_tickets(self, identity: IdentityContext) -> dict[str, Any]:
        rows = self.store.query("SELECT * FROM ops_tickets WHERE owner_subject_id=? ORDER BY created_at DESC LIMIT 200", (identity.subject_id,))
        return {"items": [self._ticket_view(r) for r in rows]}

    def ticket_detail(self, identity: IdentityContext, ticket_id: str) -> dict[str, Any]:
        row = self.store.one("SELECT * FROM ops_tickets WHERE id=?", (ticket_id,))
        staff = is_staff(identity)
        if row is None or (row["owner_subject_id"] != identity.subject_id and not staff):
            raise OpsError(404, "TICKET_NOT_FOUND", "Không tìm thấy hồ sơ.")
        return {**self._ticket_view(row), "events": self._events(ticket_id, internal=staff, viewer_subject_id=identity.subject_id),
                "allowed_actions": self._allowed(row, identity)}

    def _allowed(self, t: dict[str, Any], identity: IdentityContext) -> list[str]:
        if is_staff(identity):
            if t["status"] not in TICKET_OPEN:
                return ["note"]
            mine = t["assignee_subject_id"] == identity.subject_id
            return ["reply", "status", "note"] if mine else ["claim", "reply", "status", "note"]
        if t["owner_subject_id"] != identity.subject_id:
            return []
        actions = []
        if t["status"] in TICKET_OPEN:
            actions.append("cancel")
        if t["status"] in ("NEED_INFO", "IN_REVIEW", "SUBMITTED"):
            actions.append("reply")
        return actions

    def student_reply(self, identity: IdentityContext, ticket_id: str, text: str) -> dict[str, Any]:
        text = text.strip()
        if not 1 <= len(text) <= 2000:
            raise OpsError(422, "INVALID_BODY", "Nội dung phản hồi cần từ 1 đến 2000 ký tự.")
        with self.store.tx() as c:
            t = c.execute("SELECT * FROM ops_tickets WHERE id=? AND owner_subject_id=?", (ticket_id, identity.subject_id)).fetchone()
            if t is None:
                raise OpsError(404, "TICKET_NOT_FOUND", "Không tìm thấy hồ sơ.")
            if t["status"] not in TICKET_OPEN:
                raise OpsError(409, "TICKET_CLOSED", "Hồ sơ đã đóng, không thêm phản hồi được.")
            self._add_event(c, ticket_id, identity, "STUDENT_REPLY", text)
            new_status = "IN_REVIEW" if t["status"] == "NEED_INFO" else t["status"]
            c.execute("UPDATE ops_tickets SET status=?, updated_at=? WHERE id=?", (new_status, now_iso(), ticket_id))
            self.store.audit(c, identity.subject_id, "ticket.student_reply", ticket_id, {})
        return self.ticket_detail(identity, ticket_id)

    def cancel_ticket(self, identity: IdentityContext, ticket_id: str, reason: str) -> dict[str, Any]:
        with self.store.tx() as c:
            t = c.execute("SELECT * FROM ops_tickets WHERE id=? AND owner_subject_id=?", (ticket_id, identity.subject_id)).fetchone()
            if t is None:
                raise OpsError(404, "TICKET_NOT_FOUND", "Không tìm thấy hồ sơ.")
            if t["status"] not in TICKET_OPEN:
                raise OpsError(409, "TICKET_CLOSED", "Hồ sơ đã đóng, không hủy được.")
            c.execute("UPDATE ops_tickets SET status='CANCELLED', updated_at=? WHERE id=?", (now_iso(), ticket_id))
            self._add_event(c, ticket_id, identity, "STATUS_CHANGE", "Sinh viên hủy hồ sơ." + (f" Lý do: {reason.strip()[:300]}" if reason.strip() else ""))
            self.store.notify(c, identity.subject_id, "TICKET", f"Đã hủy hồ sơ {t['code']}", "Hồ sơ đã được hủy theo yêu cầu của bạn.", f"/tickets?id={ticket_id}")
            self.store.audit(c, identity.subject_id, "ticket.cancel", ticket_id, {})
        return self.ticket_detail(identity, ticket_id)

    # ------------------------------------------------------------------ staff
    def staff_queue(self, identity: IdentityContext, status: str | None, mine: bool, q: str | None) -> dict[str, Any]:
        require_staff(identity)
        rows = self.store.query("SELECT * FROM ops_tickets ORDER BY (status IN ('SUBMITTED','IN_REVIEW','NEED_INFO')) DESC, due_at, created_at LIMIT 500")
        counts = {s: 0 for s in TICKET_STATUSES}
        for r in rows:
            counts[r["status"]] += 1
        items = []
        for r in rows:
            if status and status != "OPEN" and r["status"] != status:
                continue
            if status == "OPEN" and r["status"] not in TICKET_OPEN:
                continue
            if mine and r["assignee_subject_id"] != identity.subject_id:
                continue
            if q and q.casefold() not in f"{r['code']} {r['title']} {r['owner_display']} {r['owner_code']}".casefold():
                continue
            items.append(self._ticket_view(r))
        return {"items": items, "counts": counts, "overdue": sum(1 for i in items if i["overdue"])}

    def staff_claim(self, identity: IdentityContext, ticket_id: str) -> dict[str, Any]:
        require_staff(identity)
        with self.store.tx() as c:
            t = c.execute("SELECT * FROM ops_tickets WHERE id=?", (ticket_id,)).fetchone()
            if t is None:
                raise OpsError(404, "TICKET_NOT_FOUND", "Không tìm thấy hồ sơ.")
            if t["status"] not in TICKET_OPEN:
                raise OpsError(409, "TICKET_CLOSED", "Hồ sơ đã đóng.")
            if t["assignee_subject_id"] not in (None, identity.subject_id):
                raise OpsError(409, "ALREADY_CLAIMED", f"Hồ sơ đang do {t['assignee_display']} xử lý.")
            if t["assignee_subject_id"] != identity.subject_id:
                c.execute("UPDATE ops_tickets SET assignee_subject_id=?, assignee_display=?, status='IN_REVIEW', updated_at=? WHERE id=?",
                          (identity.subject_id, identity.display_name, now_iso(), ticket_id))
                self._add_event(c, ticket_id, identity, "CLAIMED", "Cán bộ tiếp nhận hồ sơ.")
                self.store.notify(c, t["owner_subject_id"], "TICKET", f"Hồ sơ {t['code']} đang được xử lý",
                                  f"{identity.display_name} đã tiếp nhận hồ sơ của bạn.", f"/tickets?id={ticket_id}")
                self.store.audit(c, identity.subject_id, "ticket.claim", ticket_id, {})
        return self.ticket_detail(identity, ticket_id)

    def staff_reply(self, identity: IdentityContext, ticket_id: str, text: str, set_status: str | None) -> dict[str, Any]:
        require_staff(identity)
        text = text.strip()
        if not 1 <= len(text) <= 2000:
            raise OpsError(422, "INVALID_BODY", "Nội dung phản hồi cần từ 1 đến 2000 ký tự.")
        if set_status is not None and set_status not in STAFF_TARGETS:
            raise OpsError(422, "INVALID_STATUS", "Trạng thái đích không hợp lệ.")
        with self.store.tx() as c:
            t = c.execute("SELECT * FROM ops_tickets WHERE id=?", (ticket_id,)).fetchone()
            if t is None:
                raise OpsError(404, "TICKET_NOT_FOUND", "Không tìm thấy hồ sơ.")
            if t["status"] not in TICKET_OPEN:
                raise OpsError(409, "TICKET_CLOSED", "Hồ sơ đã đóng.")
            if t["assignee_subject_id"] not in (None, identity.subject_id):
                raise OpsError(409, "ALREADY_CLAIMED", f"Hồ sơ đang do {t['assignee_display']} xử lý.")
            self._add_event(c, ticket_id, identity, "STAFF_REPLY", text)
            status = set_status or ("IN_REVIEW" if t["status"] == "SUBMITTED" else t["status"])
            assignee = (identity.subject_id, identity.display_name) if t["assignee_subject_id"] is None else (t["assignee_subject_id"], t["assignee_display"])
            c.execute("UPDATE ops_tickets SET status=?, assignee_subject_id=?, assignee_display=?, updated_at=? WHERE id=?",
                      (status, assignee[0], assignee[1], now_iso(), ticket_id))
            if status != t["status"]:
                self._add_event(c, ticket_id, identity, "STATUS_CHANGE", f"Trạng thái: {STATUS_LABELS[t['status']]} → {STATUS_LABELS[status]}")
            self.store.notify(c, t["owner_subject_id"], "TICKET", f"Phản hồi mới cho hồ sơ {t['code']}", text[:140], f"/tickets?id={ticket_id}")
            self.store.audit(c, identity.subject_id, "ticket.staff_reply", ticket_id, {"status": status})
        return self.ticket_detail(identity, ticket_id)

    def staff_set_status(self, identity: IdentityContext, ticket_id: str, status: str, reason: str) -> dict[str, Any]:
        if status in ("RESOLVED", "REJECTED") and not reason.strip():
            raise OpsError(422, "REASON_REQUIRED", "Cần ghi kết quả hoặc lý do khi đóng hồ sơ.")
        return self.staff_reply(identity, ticket_id, reason.strip() or f"Chuyển trạng thái sang {status}.", status)

    def staff_note(self, identity: IdentityContext, ticket_id: str, text: str) -> dict[str, Any]:
        require_staff(identity)
        text = text.strip()
        if not 1 <= len(text) <= 2000:
            raise OpsError(422, "INVALID_BODY", "Ghi chú cần từ 1 đến 2000 ký tự.")
        with self.store.tx() as c:
            if c.execute("SELECT 1 FROM ops_tickets WHERE id=?", (ticket_id,)).fetchone() is None:
                raise OpsError(404, "TICKET_NOT_FOUND", "Không tìm thấy hồ sơ.")
            self._add_event(c, ticket_id, identity, "NOTE", text, "INTERNAL")
            self.store.audit(c, identity.subject_id, "ticket.note", ticket_id, {})
        return self.ticket_detail(identity, ticket_id)

    def _readable_audit(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """The audit table keeps ids; the operations page shows a person's name and the business code (HS-…, BK-…) where one is known."""
        names: dict[str, str] = {}
        for table, id_col, name_col in (("ops_tickets", "owner_subject_id", "owner_display"), ("ops_room_bookings", "owner_subject_id", "owner_display"),
                                        ("ops_ticket_events", "actor_subject_id", "actor_display")):
            for r in self.store.query(f"SELECT DISTINCT {id_col} AS i, {name_col} AS n FROM {table}"):
                names.setdefault(r["i"], r["n"])
        codes = {r["id"]: r["code"] for r in self.store.query("SELECT id, code FROM ops_tickets")}
        codes.update({r["id"]: r["code"] for r in self.store.query("SELECT id, code FROM ops_room_bookings")})
        kinds = (("schedule.", "Sự kiện lịch cá nhân"), ("reminders.", "Cài đặt nhắc nhở"), ("ticket.", "Hồ sơ"), ("room.", "Đặt phòng"))

        def resource(row: dict[str, Any]) -> str:
            value = row["resource"]
            if value in codes:
                return codes[value]
            if len(str(value)) >= 32 and str(value).count("-") == 4:  # a bare id: say what kind of thing it was instead
                return next((label for prefix, label in kinds if str(row["action"]).startswith(prefix)), "—")
            return value

        return [{**r, "actor": "Hệ thống" if str(r["actor"]).startswith("system") else names.get(r["actor"]) or f"Tài khoản …{str(r['actor'])[-4:]}",
                 "resource": resource(r)} for r in rows]

    # ------------------------------------------------------------------ admin
    def admin_overview(self, identity: IdentityContext) -> dict[str, Any]:
        require_admin(identity)
        statuses = {r["status"]: r["n"] for r in self.store.query("SELECT status, COUNT(*) n FROM ops_tickets GROUP BY status")}
        now = now_iso()
        overdue = self.store.one("SELECT COUNT(*) n FROM ops_tickets WHERE status IN ('SUBMITTED','IN_REVIEW','NEED_INFO') AND due_at<?", (now,))["n"]
        bookings = {r["status"]: r["n"] for r in self.store.query("SELECT status, COUNT(*) n FROM ops_room_bookings GROUP BY status")}
        upcoming = self.store.one("SELECT COUNT(*) n FROM ops_room_bookings WHERE status='CONFIRMED' AND starts_at>?", (now,))["n"]
        rooms = {r["status"]: r["n"] for r in self.store.query("SELECT status, COUNT(*) n FROM ops_rooms GROUP BY status")}
        audit = self.store.query("SELECT at, actor, action, resource FROM ops_audit ORDER BY id DESC LIMIT 20")
        audit = self._readable_audit(audit)
        return {"tickets": {"by_status": statuses, "overdue": overdue, "total": sum(statuses.values())},
                "bookings": {"by_status": bookings, "upcoming": upcoming},
                "rooms": {"by_status": rooms, "total": sum(rooms.values())},
                "schedule_entries": self.store.one("SELECT COUNT(*) n FROM ops_schedule WHERE deleted_at IS NULL")["n"],
                "recent_audit": audit,
                "data_sources": {"rooms": "LOCAL_SYNTHETIC", "timetable": "LOCAL_SYNTHETIC",
                                 "note": "Dữ liệu phòng và lịch là dữ liệu mô phỏng nội bộ, chưa kết nối hệ thống HUCE."}}
