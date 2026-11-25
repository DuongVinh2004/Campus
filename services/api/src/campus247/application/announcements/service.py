"""Announcements (F1.3-F1.5): draft, preview, confirm, approve, batch publish, revise, withdraw, read, acknowledge, statistics, jobs.

Deterministic code only. All rows live in the campus-ops SQLite file so a delivery and its inbox notification are written in the
same transaction. Rows are never deleted: a draft is hidden with `deleted_at`, and every state change appends an audit row.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from campus247.domain import announcements as dom
from campus247.domain.announcements import AnnouncementInvalid, AudienceSpec, Recipient
from campus247.ports.campus_ops import OpsError, uuid7
from campus247.ports.identity import IdentityContext, IdentityRole

SCHEMA = """
CREATE TABLE IF NOT EXISTS ann_announcements(
  id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE, title TEXT NOT NULL, body TEXT NOT NULL,
  category TEXT NOT NULL, priority TEXT NOT NULL, issuer_unit TEXT NOT NULL,
  author_subject_id TEXT NOT NULL, audience TEXT NOT NULL, audience_hash TEXT NOT NULL,
  publish_at TEXT, expires_at TEXT NOT NULL, requires_ack INTEGER NOT NULL DEFAULT 0, ack_deadline TEXT,
  source_ref TEXT NOT NULL DEFAULT '{}', links TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1, knowledge_version_id TEXT,
  injection_flagged INTEGER NOT NULL DEFAULT 0, publish_cursor TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, published_at TEXT, withdrawn_at TEXT, withdrawn_reason TEXT,
  deleted_at TEXT, row_version INTEGER NOT NULL DEFAULT 1);
CREATE INDEX IF NOT EXISTS ann_status_publish ON ann_announcements(status, publish_at);
CREATE INDEX IF NOT EXISTS ann_author ON ann_announcements(author_subject_id, created_at DESC);
CREATE TABLE IF NOT EXISTS ann_revisions(
  announcement_id TEXT NOT NULL REFERENCES ann_announcements(id), revision INTEGER NOT NULL,
  title TEXT NOT NULL, body TEXT NOT NULL, links TEXT NOT NULL, expires_at TEXT NOT NULL, ack_deadline TEXT,
  change_note TEXT NOT NULL, material INTEGER NOT NULL, actor_subject_id TEXT NOT NULL, at TEXT NOT NULL,
  PRIMARY KEY(announcement_id, revision));
CREATE TABLE IF NOT EXISTS ann_deliveries(
  announcement_id TEXT NOT NULL REFERENCES ann_announcements(id), recipient_subject_id TEXT NOT NULL,
  faculty_code TEXT, cohort TEXT, role TEXT NOT NULL,
  delivered_at TEXT NOT NULL, read_at TEXT, read_revision INTEGER, acked_at TEXT, acked_revision INTEGER,
  added_by TEXT NOT NULL DEFAULT 'PUBLISH',
  PRIMARY KEY(announcement_id, recipient_subject_id));
CREATE INDEX IF NOT EXISTS ann_delivery_recipient ON ann_deliveries(recipient_subject_id, delivered_at DESC);
CREATE TABLE IF NOT EXISTS ann_approvals(
  id TEXT PRIMARY KEY, announcement_id TEXT NOT NULL, approver_subject_id TEXT NOT NULL,
  verdict TEXT NOT NULL, note TEXT NOT NULL, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ann_previews(
  id TEXT PRIMARY KEY, actor_subject_id TEXT NOT NULL, action TEXT NOT NULL, announcement_id TEXT NOT NULL,
  payload TEXT NOT NULL DEFAULT '{}', payload_hash TEXT NOT NULL, row_version INTEGER NOT NULL, expires_at TEXT NOT NULL, used_at TEXT);
CREATE TABLE IF NOT EXISTS ann_idempotency(
  actor_subject_id TEXT NOT NULL, key TEXT NOT NULL, result TEXT NOT NULL, at TEXT NOT NULL,
  PRIMARY KEY(actor_subject_id, key))
"""

STAFF = {IdentityRole.SUPPORT_OFFICER, IdentityRole.KNOWLEDGE_ADMIN, IdentityRole.SYSTEM_ADMIN}
ADMIN = {IdentityRole.KNOWLEDGE_ADMIN, IdentityRole.SYSTEM_ADMIN}
PREVIEW_TTL = timedelta(minutes=10)
PER_AUTHOR_PER_DAY, URGENT_PER_UNIT_PER_DAY = 20, 3
ROLE_UNIT = {"SUPPORT_OFFICER": "Cán bộ Một cửa", "KNOWLEDGE_ADMIN": "Quản trị tri thức", "SYSTEM_ADMIN": "Quản trị hệ thống", "LECTURER": "Giảng viên"}


class AnnouncementError(OpsError):
    def __init__(self, status: int, code: str, detail: str, errors: list | None = None, extra: dict | None = None):
        super().__init__(status, code, detail)
        self.errors, self.extra = errors or [], extra or {}


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def _parse(value: Any, field: str) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise AnnouncementInvalid([{"field": field, "code": "DATETIME_INVALID"}]) from None
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


class AnnouncementService:
    def __init__(self, store, directory, *, enabled: Callable[[str], bool] = lambda key: True, clock: Callable[[], datetime] | None = None,
                 signing_key: str = "announcements-local", injection_check: Callable[[str], bool] | None = None, knowledge_sync=None):
        self.store, self.directory, self.enabled = store, directory, enabled
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._key, self._injected, self.knowledge_sync = signing_key.encode(), injection_check or (lambda text: False), knowledge_sync
        self._snapshots: dict[str, list[Recipient]] = {}
        with store.tx() as c:
            for statement in [s for s in SCHEMA.split(";") if s.strip()]:
                c.execute(statement)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _staff(actor: IdentityContext) -> bool:
        return bool(STAFF.intersection(actor.roles))

    @staticmethod
    def _admin(actor: IdentityContext) -> bool:
        return bool(ADMIN.intersection(actor.roles))

    def _can_compose(self, actor: IdentityContext) -> bool:
        return self._staff(actor) or IdentityRole.LECTURER in actor.roles

    def _row(self, announcement_id: str) -> dict:
        row = self.store.one("SELECT * FROM ann_announcements WHERE id=? AND deleted_at IS NULL", (announcement_id,))
        if row is None:
            raise AnnouncementError(404, "ANNOUNCEMENT_NOT_FOUND", "Không tìm thấy thông báo.")
        return row

    def _own(self, actor: IdentityContext, row: dict, *, allow_staff: bool = False) -> None:
        if row["author_subject_id"] == actor.subject_id or self._admin(actor):
            return
        if allow_staff and self._staff(actor):
            return
        raise AnnouncementError(404, "ANNOUNCEMENT_NOT_FOUND", "Không tìm thấy thông báo.")

    def _spec(self, row: dict) -> AudienceSpec:
        return dom.parse_audience(json.loads(row["audience"]))

    def _members(self, spec: AudienceSpec) -> dict[str, set[str]]:
        getter = getattr(self.directory, "_members_for", None)
        return getter(spec) if getter else {}

    def _check_audience(self, actor: IdentityContext, spec: AudienceSpec) -> None:
        if not self._can_compose(actor):
            raise AnnouncementError(403, "FORBIDDEN", "Bạn không có quyền gửi thông báo.")
        if self._staff(actor):
            return
        for index, g in enumerate(spec.groups):  # lecturer: only the class sections they teach
            if not g.offering_ids or g.subjects or any(not self.directory.teaches(actor.subject_id, o) for o in g.offering_ids):
                raise AnnouncementError(403, "ANNOUNCEMENT_FORBIDDEN_AUDIENCE", "Giảng viên chỉ gửi cho lớp học phần mình dạy.", extra={"group": index})
        if spec.include_guests:
            raise AnnouncementError(403, "ANNOUNCEMENT_FORBIDDEN_AUDIENCE", "Không được gửi cho khách.", extra={"group": 0})

    def _fields(self, data: dict, *, now: datetime) -> dict:
        publish_at, expires_at = _parse(data.get("publish_at"), "publish_at"), _parse(data.get("expires_at"), "expires_at")
        ack_deadline = _parse(data.get("ack_deadline"), "ack_deadline")
        links = data.get("links") or []
        category, priority = data.get("category", "ACADEMIC"), data.get("priority", "NORMAL")
        requires_ack = bool(data.get("requires_ack", False))
        errors = dom.validate(title=data.get("title", ""), body=data.get("body", ""), category=category, priority=priority, publish_at=publish_at,
                              expires_at=expires_at, requires_ack=requires_ack, ack_deadline=ack_deadline, links=links, now=now)
        spec_error = None
        try:
            spec = dom.parse_audience(data.get("audience"))
        except AnnouncementInvalid as error:
            errors.extend(error.errors)
            spec = None
        if errors:
            raise AnnouncementError(422, "ANNOUNCEMENT_INVALID", "Nội dung thông báo chưa hợp lệ.", errors)
        assert spec is not None and spec_error is None
        return {"title": data["title"].strip(), "body": data["body"].strip(), "category": category, "priority": priority, "publish_at": publish_at,
                "expires_at": expires_at, "requires_ack": requires_ack, "ack_deadline": ack_deadline, "links": links, "spec": spec,
                "issuer_unit": (data.get("issuer_unit") or "").strip()[:120], "source_ref": data.get("source_ref") or {}}

    def _rate(self, actor: IdentityContext, priority: str, unit: str, now: datetime) -> None:
        since = _iso(now - timedelta(days=1))
        count = self.store.one("SELECT COUNT(*) n FROM ann_announcements WHERE author_subject_id=? AND created_at>=?", (actor.subject_id, since))["n"]
        if count >= PER_AUTHOR_PER_DAY:
            raise AnnouncementError(429, "ANNOUNCEMENT_RATE", "Đã quá số thông báo cho phép trong ngày.")
        if priority == "URGENT":
            urgent = self.store.one("SELECT COUNT(*) n FROM ann_announcements WHERE issuer_unit=? AND priority='URGENT' AND created_at>=?", (unit, since))["n"]
            if urgent >= URGENT_PER_UNIT_PER_DAY:
                raise AnnouncementError(429, "ANNOUNCEMENT_RATE", "Đơn vị đã gửi quá số thông báo khẩn cho phép trong ngày.")

    def _token(self, preview_id: str, actor: str, payload_hash: str) -> str:
        return hmac.new(self._key, f"{preview_id}|{actor}|{payload_hash}".encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def _public(row: dict, *, body: bool = True) -> dict:
        out = {"id": row["id"], "code": row["code"], "title": row["title"], "category": row["category"], "priority": row["priority"],
               "issuer_unit": row["issuer_unit"], "status": row["status"], "revision": row["revision"], "publish_at": row["publish_at"],
               "expires_at": row["expires_at"], "requires_ack": bool(row["requires_ack"]), "ack_deadline": row["ack_deadline"],
               "published_at": row["published_at"], "row_version": row["row_version"], "source_ref": json.loads(row["source_ref"]),
               "links": json.loads(row["links"])}
        if body:
            out["body"] = row["body"]
        return out

    # ------------------------------------------------------------------ drafts
    def create_draft(self, actor: IdentityContext, data: dict) -> dict:
        now = self.clock()
        fields = self._fields(data, now=now)
        self._check_audience(actor, fields["spec"])
        unit = fields["issuer_unit"] or ROLE_UNIT.get(next((r.value for r in actor.roles), ""), "Nhà trường")
        self._rate(actor, fields["priority"], unit, now)
        injected = self._injected(fields["title"] + "\n" + fields["body"])
        announcement_id = uuid7()
        with self.store.tx() as c:
            number = c.execute("SELECT COUNT(*) FROM ann_announcements WHERE code LIKE ?", (f"TB-{now.year}-%",)).fetchone()[0] + 1
            code = f"TB-{now.year}-{number:06d}"
            c.execute("INSERT INTO ann_announcements(id,code,title,body,category,priority,issuer_unit,author_subject_id,audience,audience_hash,publish_at,expires_at,"
                      "requires_ack,ack_deadline,source_ref,links,status,injection_flagged,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'DRAFT',?,?,?)",
                      (announcement_id, code, fields["title"], fields["body"], fields["category"], fields["priority"], unit, actor.subject_id,
                       json.dumps(fields["spec"].canonical(), ensure_ascii=False), fields["spec"].hash(),
                       _iso(fields["publish_at"]) if fields["publish_at"] else None, _iso(fields["expires_at"]), int(fields["requires_ack"]),
                       _iso(fields["ack_deadline"]) if fields["ack_deadline"] else None, json.dumps(fields["source_ref"]), json.dumps(fields["links"], ensure_ascii=False),
                       int(injected), _iso(now), _iso(now)))
            self.store.audit(c, actor.subject_id, "ANNOUNCEMENT_CREATED", announcement_id, {"code": code})
        return {"id": announcement_id, "code": code, "row_version": 1, "injection_flagged": injected}

    def update_draft(self, actor: IdentityContext, announcement_id: str, data: dict, row_version: int) -> dict:
        row = self._row(announcement_id)
        self._own(actor, row)
        if row["status"] != "DRAFT":
            raise AnnouncementError(409, "ANNOUNCEMENT_STATE", "Chỉ sửa được bản nháp.")
        if row["row_version"] != row_version:
            raise AnnouncementError(409, "ANNOUNCEMENT_CONFLICT", "Thông báo đã được sửa ở nơi khác.")
        now = self.clock()
        fields = self._fields(data, now=now)
        self._check_audience(actor, fields["spec"])
        injected = self._injected(fields["title"] + "\n" + fields["body"])
        with self.store.tx() as c:
            changed = c.execute("UPDATE ann_announcements SET title=?,body=?,category=?,priority=?,issuer_unit=?,audience=?,audience_hash=?,publish_at=?,expires_at=?,"
                                "requires_ack=?,ack_deadline=?,source_ref=?,links=?,injection_flagged=?,updated_at=?,row_version=row_version+1 WHERE id=? AND row_version=?",
                                (fields["title"], fields["body"], fields["category"], fields["priority"], fields["issuer_unit"] or row["issuer_unit"],
                                 json.dumps(fields["spec"].canonical(), ensure_ascii=False), fields["spec"].hash(),
                                 _iso(fields["publish_at"]) if fields["publish_at"] else None, _iso(fields["expires_at"]), int(fields["requires_ack"]),
                                 _iso(fields["ack_deadline"]) if fields["ack_deadline"] else None, json.dumps(fields["source_ref"]),
                                 json.dumps(fields["links"], ensure_ascii=False), int(injected), _iso(now), announcement_id, row_version)).rowcount
            if not changed:
                raise AnnouncementError(409, "ANNOUNCEMENT_CONFLICT", "Thông báo đã được sửa ở nơi khác.")
            self.store.audit(c, actor.subject_id, "ANNOUNCEMENT_UPDATED", announcement_id, {})
        return {"id": announcement_id, "row_version": row_version + 1, "injection_flagged": injected}

    def delete_draft(self, actor: IdentityContext, announcement_id: str) -> None:
        row = self._row(announcement_id)
        self._own(actor, row)
        if row["status"] != "DRAFT":
            raise AnnouncementError(409, "ANNOUNCEMENT_STATE", "Chỉ xóa được bản nháp.")
        with self.store.tx() as c:
            c.execute("UPDATE ann_announcements SET deleted_at=?,row_version=row_version+1 WHERE id=?", (_iso(self.clock()), announcement_id))
            self.store.audit(c, actor.subject_id, "ANNOUNCEMENT_DRAFT_HIDDEN", announcement_id, {})

    # ------------------------------------------------------------------ audience
    def audience_preview(self, actor: IdentityContext, announcement_id: str) -> dict:
        row = self._row(announcement_id)
        self._own(actor, row, allow_staff=True)
        return self._audience_stats(self._spec(row))

    def audience_preview_spec(self, actor: IdentityContext, raw: dict) -> dict:
        spec = dom.parse_audience(raw)
        self._check_audience(actor, spec)
        return self._audience_stats(spec)

    def _audience_stats(self, spec: AudienceSpec) -> dict:
        people = list(self.directory.recipients(spec))
        by_role: dict[str, int] = {}
        by_faculty: dict[str, int] = {}
        by_cohort: dict[str, int] = {}
        for who in people:
            for role in who.roles:
                by_role[role] = by_role.get(role, 0) + 1
            by_faculty[who.faculty_code or "—"] = by_faculty.get(who.faculty_code or "—", 0) + 1
            by_cohort[who.cohort or "—"] = by_cohort.get(who.cohort or "—", 0) + 1
        warnings = []
        if not people:
            warnings.append("EMPTY_AUDIENCE")
        if len(people) > dom.LARGE_AUDIENCE:
            warnings.append("LARGE_AUDIENCE")
        fmt = lambda d: [{"key": k, "n": n} for k, n in sorted(dom.group_small_counts(d).items())]  # noqa: E731
        return {"total": len(people), "by_role": fmt(by_role), "by_faculty": fmt(by_faculty), "by_cohort": fmt(by_cohort),
                "guests_included": spec.include_guests, "warnings": warnings}

    # ------------------------------------------------------------------ publish flow
    def _payload_hash(self, row: dict, action: str, extra: dict | None = None) -> str:
        body = {"action": action, "audience": row["audience_hash"], "rv": row["row_version"], "title": row["title"], "body": hashlib.sha256(row["body"].encode()).hexdigest(),
                "publish_at": row["publish_at"], "expires_at": row["expires_at"], "extra": extra or {}}
        return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()

    def _save_preview(self, actor: IdentityContext, row: dict, action: str, payload_hash: str, payload: dict | None = None) -> tuple[str, str, str]:
        preview_id, expires = uuid7(), _iso(self.clock() + PREVIEW_TTL)
        with self.store.tx() as c:
            c.execute("INSERT INTO ann_previews(id,actor_subject_id,action,announcement_id,payload,payload_hash,row_version,expires_at) VALUES(?,?,?,?,?,?,?,?)",
                      (preview_id, actor.subject_id, action, row["id"], json.dumps(payload or {}, ensure_ascii=False), payload_hash, row["row_version"], expires))
        return preview_id, self._token(preview_id, actor.subject_id, payload_hash), expires

    def _link_checks(self, row: dict) -> list[dict]:
        return []  # knowledge_version_id links are checked against the published release by the runtime wiring (F1.6)

    def publish_preview(self, actor: IdentityContext, announcement_id: str) -> dict:
        row = self._row(announcement_id)
        self._own(actor, row)
        if row["status"] != "DRAFT":
            raise AnnouncementError(409, "ANNOUNCEMENT_STATE", "Chỉ gửi được bản nháp.")
        spec = self._spec(row)
        self._check_audience(actor, spec)
        now = self.clock()
        data = {k: row[k] for k in ("title", "body", "category", "priority", "publish_at", "expires_at", "requires_ack", "ack_deadline")}
        errors = dom.validate(title=data["title"], body=data["body"], category=data["category"], priority=data["priority"],
                              publish_at=_parse(data["publish_at"], "publish_at"), expires_at=_parse(data["expires_at"], "expires_at"),
                              requires_ack=bool(data["requires_ack"]), ack_deadline=_parse(data["ack_deadline"], "ack_deadline"),
                              links=json.loads(row["links"]), now=now) + self._link_checks(row)
        if errors:
            raise AnnouncementError(422, "ANNOUNCEMENT_INVALID", "Nội dung thông báo chưa hợp lệ.", errors)
        stats = self._audience_stats(spec)
        if stats["total"] == 0 and not spec.include_guests:
            raise AnnouncementError(422, "ANNOUNCEMENT_INVALID", "Đối tượng không có người nhận.", [{"field": "audience", "code": "AUDIENCE_EMPTY"}])
        approval = dom.needs_second_approval(flag_on=self.enabled("announcements.second_approval"), spec=spec, estimated=stats["total"], priority=row["priority"])
        sync = bool(self.enabled("announcements.knowledge_sync") and dom.is_public(spec) and not row["injection_flagged"])
        warnings = list(stats["warnings"]) + (["INJECTION_FLAGGED_NO_KNOWLEDGE_SYNC"] if row["injection_flagged"] else [])
        preview_id, token, expires = self._save_preview(actor, row, "publish", self._payload_hash(row, "publish"))
        return {"preview_id": preview_id, "confirmation_token": token, "expires_at": expires,
                "summary": {"total": stats["total"], "publish_at": row["publish_at"], "needs_approval": approval, "knowledge_sync": sync}, "warnings": warnings}

    def _consume(self, actor: IdentityContext, preview_id: str, token: str, action: str, c) -> dict:
        p = c.execute("SELECT * FROM ann_previews WHERE id=? AND actor_subject_id=? AND action=?", (preview_id, actor.subject_id, action)).fetchone()
        if p is None or p["used_at"] or p["expires_at"] <= _iso(self.clock()):
            raise AnnouncementError(410, "PREVIEW_EXPIRED", "Bản xem trước đã hết hạn hoặc đã dùng.")
        if not token or not hmac.compare_digest(self._token(preview_id, actor.subject_id, p["payload_hash"]), token):
            raise AnnouncementError(428, "CONFIRMATION_REQUIRED", "Mã xác nhận không đúng.")
        c.execute("UPDATE ann_previews SET used_at=? WHERE id=?", (_iso(self.clock()), preview_id))
        return dict(p)

    def _idempotent(self, actor: IdentityContext, key: str, c) -> dict | None:
        if not key or len(key) > 200:
            raise AnnouncementError(422, "IDEMPOTENCY_KEY_REQUIRED", "Thiếu Idempotency-Key.")
        prior = c.execute("SELECT result FROM ann_idempotency WHERE actor_subject_id=? AND key=?", (actor.subject_id, key)).fetchone()
        return json.loads(prior[0]) if prior else None

    def _remember(self, actor: IdentityContext, key: str, result: dict, c) -> dict:
        c.execute("INSERT INTO ann_idempotency VALUES(?,?,?,?)", (actor.subject_id, key, json.dumps(result), _iso(self.clock())))
        return result

    def publish_confirm(self, actor: IdentityContext, preview_id: str, token: str, idempotency_key: str) -> dict:
        with self.store.tx() as c:
            prior = self._idempotent(actor, idempotency_key, c)
            if prior:
                return {**prior, "replayed": True}
            preview = self._consume(actor, preview_id, token, "publish", c)
            row = c.execute("SELECT * FROM ann_announcements WHERE id=?", (preview["announcement_id"],)).fetchone()
            row = dict(row)
            if row["status"] != "DRAFT" or row["row_version"] != preview["row_version"]:
                raise AnnouncementError(409, "ANNOUNCEMENT_CONFLICT", "Thông báo đã đổi sau khi xem trước.")
            spec = self._spec(row)
            total = len(list(self.directory.recipients(spec)))
            approval = dom.needs_second_approval(flag_on=self.enabled("announcements.second_approval"), spec=spec, estimated=total, priority=row["priority"])
            now = self.clock()
            future = bool(row["publish_at"] and row["publish_at"] > _iso(now))
            action = "submit_approval" if approval else "schedule" if future else "start_publish"
            new = dom.transition("DRAFT", action)
            c.execute("UPDATE ann_announcements SET status=?,updated_at=?,row_version=row_version+1 WHERE id=?", (new, _iso(now), row["id"]))
            self.store.audit(c, actor.subject_id, "ANNOUNCEMENT_SUBMITTED", row["id"], {"status": new})
            result = self._remember(actor, idempotency_key, {"id": row["id"], "status": new}, c)
        if new == "PUBLISHING":
            self.publish_step(row["id"])
            result["status"] = self._row(row["id"])["status"]
        return result

    def approve(self, actor: IdentityContext, announcement_id: str, note: str, row_version: int, *, approve: bool = True) -> dict:
        if not self._staff(actor):
            raise AnnouncementError(403, "FORBIDDEN", "Bạn không có quyền duyệt.")
        if len((note or "").strip()) < 8:
            raise AnnouncementError(422, "ANNOUNCEMENT_INVALID", "Ghi chú tối thiểu 8 ký tự.", [{"field": "note", "code": "NOTE_LENGTH"}])
        with self.store.tx() as c:
            row = c.execute("SELECT * FROM ann_announcements WHERE id=? AND deleted_at IS NULL", (announcement_id,)).fetchone()
            if row is None:
                raise AnnouncementError(404, "ANNOUNCEMENT_NOT_FOUND", "Không tìm thấy thông báo.")
            row = dict(row)
            if row["status"] != "PENDING_APPROVAL":
                raise AnnouncementError(409, "ANNOUNCEMENT_STATE", "Thông báo không ở trạng thái chờ duyệt.")
            if row["author_subject_id"] == actor.subject_id:
                raise AnnouncementError(409, "SAME_PERSON_APPROVAL", "Người soạn không tự duyệt thông báo của mình.")
            if row["row_version"] != row_version:
                raise AnnouncementError(409, "ANNOUNCEMENT_CONFLICT", "Thông báo đã đổi.")
            now = self.clock()
            if approve:
                future = bool(row["publish_at"] and row["publish_at"] > _iso(now))
                new = dom.transition("PENDING_APPROVAL", "approve_schedule" if future else "approve_publish")
            else:
                new = "DRAFT"
            c.execute("INSERT INTO ann_approvals VALUES(?,?,?,?,?,?)", (uuid7(), row["id"], actor.subject_id, "APPROVED" if approve else "REJECTED", note.strip(), _iso(now)))
            c.execute("UPDATE ann_announcements SET status=?,updated_at=?,row_version=row_version+1 WHERE id=?", (new, _iso(now), row["id"]))
            self.store.audit(c, actor.subject_id, "ANNOUNCEMENT_APPROVED" if approve else "ANNOUNCEMENT_REJECTED", row["id"], {})
        if new == "PUBLISHING":
            self.publish_step(announcement_id)
        return {"id": announcement_id, "status": self._row(announcement_id)["status"]}

    def unschedule(self, actor: IdentityContext, announcement_id: str) -> dict:
        row = self._row(announcement_id)
        self._own(actor, row)
        if dom.transition(row["status"], "unschedule") is None:
            raise AnnouncementError(409, "ANNOUNCEMENT_STATE", "Chỉ hủy hẹn được thông báo đã hẹn giờ.")
        with self.store.tx() as c:
            c.execute("UPDATE ann_announcements SET status='DRAFT',updated_at=?,row_version=row_version+1 WHERE id=? AND status='SCHEDULED'", (_iso(self.clock()), announcement_id))
            self.store.audit(c, actor.subject_id, "ANNOUNCEMENT_UNSCHEDULED", announcement_id, {})
        return {"id": announcement_id, "status": "DRAFT"}

    # ------------------------------------------------------------------ batch publishing (job + inline first batch)
    def _snapshot(self, row: dict) -> list[Recipient]:
        people = self._snapshots.get(row["id"])
        if people is None:
            people = sorted(self.directory.recipients(self._spec(row)), key=lambda r: r.subject_id)
            self._snapshots[row["id"]] = people
        return people

    def publish_step(self, announcement_id: str, *, batch: int = dom.BATCH) -> str:
        """Deliver one batch (one transaction). Returns the status afterwards. Safe to repeat after any failure."""
        row = self._row(announcement_id)
        if row["status"] != "PUBLISHING":
            return row["status"]
        people = self._snapshot(row)
        cursor = row["publish_cursor"] or ""
        start = next((i for i, who in enumerate(people) if who.subject_id > cursor), len(people)) if cursor else 0
        chunk = people[start:start + batch]
        now = _iso(self.clock())
        title = ("[Khẩn] " if row["priority"] == "URGENT" else "") + row["title"]
        link = f"/announcements/{row['id']}"
        with self.store.tx() as c:
            for who in chunk:
                inserted = c.execute("INSERT OR IGNORE INTO ann_deliveries(announcement_id,recipient_subject_id,faculty_code,cohort,role,delivered_at,added_by) VALUES(?,?,?,?,?,?,'PUBLISH')",
                                     (row["id"], who.subject_id, who.faculty_code, who.cohort, who.roles[0] if who.roles else "", now)).rowcount
                if inserted:
                    self.store.notify(c, who.subject_id, "ANNOUNCEMENT", title, row["issuer_unit"], link)
            done = start + len(chunk) >= len(people)
            if chunk:
                c.execute("UPDATE ann_announcements SET publish_cursor=? WHERE id=?", (chunk[-1].subject_id, row["id"]))
            if done:
                c.execute("UPDATE ann_announcements SET status='PUBLISHED',published_at=?,updated_at=? WHERE id=? AND status='PUBLISHING'", (now, now, row["id"]))
                self.store.audit(c, "system", "ANNOUNCEMENT_PUBLISHED", row["id"], {"recipients": len(people)})
        if done:
            self._snapshots.pop(row["id"], None)
            if self.knowledge_sync is not None and self.enabled("announcements.knowledge_sync"):
                self._sync(row["id"])
            return "PUBLISHED"
        return "PUBLISHING"

    def _sync(self, announcement_id: str) -> None:
        row = self._row(announcement_id)
        if row["injection_flagged"] or not dom.is_public(self._spec(row)):
            return
        try:
            version = self.knowledge_sync.publish(self._public(row), row)
        except Exception:  # noqa: BLE001 -- the notice is already delivered; a failed sync is retried by the expiry/sync job
            return
        if version:
            with self.store.tx() as c:
                c.execute("UPDATE ann_announcements SET knowledge_version_id=? WHERE id=?", (version, announcement_id))

    def run_publisher_once(self) -> int:
        """Job: start due scheduled notices and continue unfinished publishing. Returns how many notices progressed."""
        now = _iso(self.clock())
        progressed = 0
        with self.store.tx() as c:
            due = [r[0] for r in c.execute("SELECT id FROM ann_announcements WHERE status='SCHEDULED' AND publish_at<=? AND deleted_at IS NULL", (now,)).fetchall()]
            for announcement_id in due:
                c.execute("UPDATE ann_announcements SET status='PUBLISHING',updated_at=? WHERE id=?", (now, announcement_id))
                self.store.audit(c, "system", "ANNOUNCEMENT_PUBLISH_STARTED", announcement_id, {})
        for row in self.store.query("SELECT id FROM ann_announcements WHERE status='PUBLISHING' AND deleted_at IS NULL"):
            while self.publish_step(row["id"]) == "PUBLISHING":
                pass
            progressed += 1
        return progressed

    def run_expiry_once(self) -> int:
        now = _iso(self.clock())
        rows = self.store.query("SELECT id, knowledge_version_id FROM ann_announcements WHERE status='PUBLISHED' AND expires_at<=?", (now,))
        for r in rows:
            with self.store.tx() as c:
                c.execute("UPDATE ann_announcements SET status='EXPIRED',updated_at=? WHERE id=? AND status='PUBLISHED'", (now, r["id"]))
                self.store.audit(c, "system", "ANNOUNCEMENT_EXPIRED", r["id"], {})
            self._revoke_knowledge(r["knowledge_version_id"], "expired")
        return len(rows)

    def _revoke_knowledge(self, version_id: str | None, reason: str) -> None:
        if version_id and self.knowledge_sync is not None:
            try:
                self.knowledge_sync.revoke(version_id, reason)
            except Exception:  # noqa: BLE001
                pass

    def run_reconcile_once(self) -> int:
        """Add people who now match the audience (never remove anyone who already received it)."""
        added = 0
        now = _iso(self.clock())
        for row in self.store.query("SELECT * FROM ann_announcements WHERE status='PUBLISHED' AND expires_at>? AND deleted_at IS NULL", (now,)):
            known = {r["recipient_subject_id"] for r in self.store.query("SELECT recipient_subject_id FROM ann_deliveries WHERE announcement_id=?", (row["id"],))}
            fresh = [who for who in self.directory.recipients(self._spec(row)) if who.subject_id not in known]
            if not fresh:
                continue
            title = ("[Khẩn] " if row["priority"] == "URGENT" else "") + row["title"]
            with self.store.tx() as c:
                for who in fresh:
                    if c.execute("INSERT OR IGNORE INTO ann_deliveries(announcement_id,recipient_subject_id,faculty_code,cohort,role,delivered_at,added_by) VALUES(?,?,?,?,?,?,'RECONCILE')",
                                 (row["id"], who.subject_id, who.faculty_code, who.cohort, who.roles[0] if who.roles else "", now)).rowcount:
                        self.store.notify(c, who.subject_id, "ANNOUNCEMENT", title, row["issuer_unit"], f"/announcements/{row['id']}")
                        added += 1
                self.store.audit(c, "system", "ANNOUNCEMENT_RECONCILED", row["id"], {"added": len(fresh)})
        return added

    def run_ack_reminders_once(self) -> int:
        from campus247.application.campus_ops.reminders import Candidate, deliver, time_left_text
        now = self.clock()
        candidates = []
        for row in self.store.query("SELECT * FROM ann_announcements WHERE status='PUBLISHED' AND requires_ack=1 AND ack_deadline>? AND deleted_at IS NULL", (_iso(now),)):
            deadline = datetime.fromisoformat(row["ack_deadline"])
            for d in self.store.query("SELECT recipient_subject_id FROM ann_deliveries WHERE announcement_id=? AND acked_at IS NULL", (row["id"],)):
                candidates.append(Candidate(
                    item_key=f"ann-ack:{row['id']}", recipient=d["recipient_subject_id"], kind="REMINDER", deadline=deadline,
                    describe=lambda left, r=row: (f"Cần xác nhận đã đọc: {r['title']}", f"Còn {time_left_text(left)} để xác nhận."),
                    link=f"/announcements/{row['id']}", offsets=(timedelta(hours=24), timedelta(hours=2)), pref_kind="ANNOUNCEMENT_ACK"))
        return deliver(self.store, candidates, now=now) if candidates else 0

    # ------------------------------------------------------------------ revise and withdraw
    def revision_preview(self, actor: IdentityContext, announcement_id: str, changes: dict) -> dict:
        row = self._row(announcement_id)
        self._own(actor, row)
        if row["status"] != "PUBLISHED":
            raise AnnouncementError(409, "ANNOUNCEMENT_STATE", "Chỉ sửa được thông báo đã gửi.")
        allowed = {"title", "body", "links", "expires_at", "ack_deadline", "change_note", "material"}
        if set(changes) - allowed:
            raise AnnouncementError(422, "ANNOUNCEMENT_INVALID", "Không được đổi trường này sau khi gửi.", [{"field": k, "code": "FIELD_LOCKED"} for k in set(changes) - allowed])
        if len((changes.get("change_note") or "").strip()) < 5:
            raise AnnouncementError(422, "ANNOUNCEMENT_INVALID", "Cần ghi chú thay đổi.", [{"field": "change_note", "code": "NOTE_LENGTH"}])
        new_expiry = _parse(changes.get("expires_at"), "expires_at") if changes.get("expires_at") else None
        if new_expiry and new_expiry <= self.clock():
            raise AnnouncementError(422, "ANNOUNCEMENT_INVALID", "Hạn mới đã qua.", [{"field": "expires_at", "code": "EXPIRY_RANGE"}])
        merged = {"title": changes.get("title", row["title"]), "body": changes.get("body", row["body"]), "links": changes.get("links", json.loads(row["links"])),
                  "expires_at": changes.get("expires_at", row["expires_at"]), "ack_deadline": changes.get("ack_deadline", row["ack_deadline"]),
                  "change_note": changes["change_note"].strip(), "material": bool(changes.get("material", False))}
        errors = dom.validate(title=merged["title"], body=merged["body"], category=row["category"], priority=row["priority"], publish_at=None,
                              expires_at=_parse(merged["expires_at"], "expires_at"), requires_ack=bool(row["requires_ack"]),
                              ack_deadline=_parse(merged["ack_deadline"], "ack_deadline"), links=merged["links"], now=_parse(row["published_at"], "x") or self.clock())
        errors = [e for e in errors if e["code"] not in {"PUBLISH_IN_PAST"}]
        if errors:
            raise AnnouncementError(422, "ANNOUNCEMENT_INVALID", "Nội dung chưa hợp lệ.", errors)
        preview_id, token, expires = self._save_preview(actor, row, "revision", self._payload_hash(row, "revision", merged), merged)
        return {"preview_id": preview_id, "confirmation_token": token, "expires_at": expires, "summary": {"material": merged["material"], "revision": row["revision"] + 1}}

    def revision_confirm(self, actor: IdentityContext, preview_id: str, token: str, idempotency_key: str) -> dict:
        with self.store.tx() as c:
            prior = self._idempotent(actor, idempotency_key, c)
            if prior:
                return {**prior, "replayed": True}
            preview = self._consume(actor, preview_id, token, "revision", c)
            row = dict(c.execute("SELECT * FROM ann_announcements WHERE id=?", (preview["announcement_id"],)).fetchone())
            if row["status"] != "PUBLISHED" or row["row_version"] != preview["row_version"]:
                raise AnnouncementError(409, "ANNOUNCEMENT_CONFLICT", "Thông báo đã đổi sau khi xem trước.")
            m = json.loads(preview["payload"])
            revision, now = row["revision"] + 1, _iso(self.clock())
            expires = _iso(_parse(m["expires_at"], "expires_at"))
            ack = _iso(_parse(m["ack_deadline"], "ack_deadline")) if m["ack_deadline"] else None
            c.execute("INSERT INTO ann_revisions VALUES(?,?,?,?,?,?,?,?,?,?,?)", (row["id"], revision, m["title"], m["body"], json.dumps(m["links"], ensure_ascii=False), expires, ack,
                                                                                m["change_note"], int(m["material"]), actor.subject_id, now))
            c.execute("UPDATE ann_announcements SET title=?,body=?,links=?,expires_at=?,ack_deadline=?,revision=?,updated_at=?,row_version=row_version+1 WHERE id=?",
                      (m["title"], m["body"], json.dumps(m["links"], ensure_ascii=False), expires, ack, revision, now, row["id"]))
            if m["material"]:
                for d in c.execute("SELECT recipient_subject_id FROM ann_deliveries WHERE announcement_id=?", (row["id"],)).fetchall():
                    self.store.notify(c, d[0], "ANNOUNCEMENT", "Đã cập nhật: " + m["title"], m["change_note"], f"/announcements/{row['id']}")
            self.store.audit(c, actor.subject_id, "ANNOUNCEMENT_REVISED", row["id"], {"revision": revision, "material": bool(m["material"])})
            result = self._remember(actor, idempotency_key, {"id": row["id"], "revision": revision}, c)
        if m["material"] and self.knowledge_sync is not None and self.enabled("announcements.knowledge_sync"):
            self._sync(row["id"])
        return result

    def withdraw_preview(self, actor: IdentityContext, announcement_id: str, reason: str) -> dict:
        row = self._row(announcement_id)
        self._own(actor, row)
        if dom.transition(row["status"], "withdraw") is None:
            raise AnnouncementError(409, "ANNOUNCEMENT_STATE", "Không thu hồi được ở trạng thái này.")
        if len((reason or "").strip()) < 10:
            raise AnnouncementError(422, "ANNOUNCEMENT_INVALID", "Lý do tối thiểu 10 ký tự.", [{"field": "reason", "code": "REASON_LENGTH"}])
        preview_id, token, expires = self._save_preview(actor, row, "withdraw", self._payload_hash(row, "withdraw", {"reason": reason.strip()}), {"reason": reason.strip()})
        delivered = self.store.one("SELECT COUNT(*) n FROM ann_deliveries WHERE announcement_id=?", (announcement_id,))["n"]
        return {"preview_id": preview_id, "confirmation_token": token, "expires_at": expires, "summary": {"delivered": delivered, "knowledge_revoked": bool(row["knowledge_version_id"])}}

    def withdraw_confirm(self, actor: IdentityContext, preview_id: str, token: str, idempotency_key: str) -> dict:
        with self.store.tx() as c:
            prior = self._idempotent(actor, idempotency_key, c)
            if prior:
                return {**prior, "replayed": True}
            preview = self._consume(actor, preview_id, token, "withdraw", c)
            row = dict(c.execute("SELECT * FROM ann_announcements WHERE id=?", (preview["announcement_id"],)).fetchone())
            if dom.transition(row["status"], "withdraw") is None or row["row_version"] != preview["row_version"]:
                raise AnnouncementError(409, "ANNOUNCEMENT_CONFLICT", "Thông báo đã đổi sau khi xem trước.")
            reason, now = json.loads(preview["payload"])["reason"], _iso(self.clock())
            c.execute("UPDATE ann_announcements SET status='WITHDRAWN',withdrawn_at=?,withdrawn_reason=?,updated_at=?,row_version=row_version+1 WHERE id=?", (now, reason, now, row["id"]))
            for d in c.execute("SELECT recipient_subject_id FROM ann_deliveries WHERE announcement_id=?", (row["id"],)).fetchall():
                self.store.notify(c, d[0], "ANNOUNCEMENT", "Đã thu hồi: " + row["title"], reason, f"/announcements/{row['id']}")
            self.store.audit(c, actor.subject_id, "ANNOUNCEMENT_WITHDRAWN", row["id"], {})
            result = self._remember(actor, idempotency_key, {"id": row["id"], "status": "WITHDRAWN"}, c)
        self._snapshots.pop(row["id"], None)
        self._revoke_knowledge(row["knowledge_version_id"], "withdrawn")
        return result

    # ------------------------------------------------------------------ reading
    def authored(self, actor: IdentityContext, status: str | None = None, offset: int = 0, limit: int = 20) -> dict:
        if not self._can_compose(actor):
            raise AnnouncementError(403, "FORBIDDEN", "Bạn không có quyền xem mục này.")
        sql, args = "SELECT * FROM ann_announcements WHERE deleted_at IS NULL AND (author_subject_id=? OR ?)", [actor.subject_id, int(self._admin(actor))]
        if status:
            sql += " AND status=?"
            args.append(status)
        rows = self.store.query(sql + " ORDER BY created_at DESC LIMIT ? OFFSET ?", (*args, limit + 1, offset))
        return {"items": [self._public(r, body=False) for r in rows[:limit]], "next_offset": offset + limit if len(rows) > limit else None}

    def approvals(self, actor: IdentityContext) -> dict:
        if not self._staff(actor):
            raise AnnouncementError(403, "FORBIDDEN", "Bạn không có quyền duyệt.")
        rows = self.store.query("SELECT * FROM ann_announcements WHERE status='PENDING_APPROVAL' AND author_subject_id<>? AND deleted_at IS NULL ORDER BY created_at", (actor.subject_id,))
        return {"items": [self._public(r, body=False) for r in rows]}

    def mine(self, actor: IdentityContext, *, filter: str = "active", category: str | None = None, offset: int = 0, limit: int = 20) -> dict:
        now = _iso(self.clock())
        sql = ("SELECT a.*, d.read_at, d.acked_at, d.acked_revision FROM ann_deliveries d JOIN ann_announcements a ON a.id=d.announcement_id "
               "WHERE d.recipient_subject_id=? AND a.status IN ('PUBLISHED','EXPIRED') AND a.deleted_at IS NULL")
        args: list[Any] = [actor.subject_id]
        if filter in {"active", "unread"}:
            sql += " AND a.status='PUBLISHED' AND a.expires_at>?"
            args.append(now)
        if filter == "unread":
            sql += " AND d.read_at IS NULL"
        if category:
            sql += " AND a.category=?"
            args.append(category)
        sql += " ORDER BY (a.priority='URGENT' AND d.read_at IS NULL) DESC, d.delivered_at DESC, a.id LIMIT ? OFFSET ?"
        rows = self.store.query(sql, (*args, limit + 1, offset))
        items = [{**self._public(r, body=False), "read": r["read_at"] is not None, "acked": r["acked_at"] is not None} for r in rows[:limit]]
        return {"items": items, "next_offset": offset + limit if len(rows) > limit else None}

    def public(self, offset: int = 0, limit: int = 20) -> dict:
        now = _iso(self.clock())
        rows = self.store.query("SELECT * FROM ann_announcements WHERE status='PUBLISHED' AND expires_at>? AND deleted_at IS NULL ORDER BY published_at DESC", (now,))
        rows = [r for r in rows if dom.is_public(self._spec(r))]
        return {"items": [self._public(r, body=False) for r in rows[offset:offset + limit]], "next_offset": offset + limit if len(rows) > offset + limit else None}

    def get(self, actor: IdentityContext, announcement_id: str) -> dict:
        row = self._row(announcement_id)
        delivery = self.store.one("SELECT * FROM ann_deliveries WHERE announcement_id=? AND recipient_subject_id=?", (announcement_id, actor.subject_id))
        if delivery is None:
            if row["author_subject_id"] == actor.subject_id or self._admin(actor):
                return {**self._public(row), "viewer": "manager"}
            raise AnnouncementError(404, "ANNOUNCEMENT_NOT_FOUND", "Không tìm thấy thông báo.")
        if row["status"] == "WITHDRAWN":
            raise AnnouncementError(404, "ANNOUNCEMENT_NOT_FOUND", "Thông báo đã được thu hồi.")
        if delivery["read_at"] is None:
            with self.store.tx() as c:
                c.execute("UPDATE ann_deliveries SET read_at=?,read_revision=? WHERE announcement_id=? AND recipient_subject_id=? AND read_at IS NULL",
                          (_iso(self.clock()), row["revision"], announcement_id, actor.subject_id))
        revisions = self.store.query("SELECT revision,change_note,material,at FROM ann_revisions WHERE announcement_id=? ORDER BY revision", (announcement_id,))
        latest_material = max((r["revision"] for r in revisions if r["material"]), default=0)
        acked_rev = delivery["acked_revision"] or 0
        return {**self._public(row), "viewer": "recipient", "read": True, "acked": bool(delivery["acked_at"]) and acked_rev >= latest_material,
                "needs_ack": bool(row["requires_ack"]) and acked_rev < max(latest_material, 1), "revisions": revisions}

    def ack(self, actor: IdentityContext, announcement_id: str) -> dict:
        row = self._row(announcement_id)
        delivery = self.store.one("SELECT * FROM ann_deliveries WHERE announcement_id=? AND recipient_subject_id=?", (announcement_id, actor.subject_id))
        if delivery is None:
            raise AnnouncementError(404, "ANNOUNCEMENT_NOT_FOUND", "Không tìm thấy thông báo.")
        if not row["requires_ack"]:
            raise AnnouncementError(409, "ANNOUNCEMENT_STATE", "Thông báo này không cần xác nhận.")
        with self.store.tx() as c:
            c.execute("UPDATE ann_deliveries SET acked_at=COALESCE(acked_at,?),acked_revision=?,read_at=COALESCE(read_at,?) WHERE announcement_id=? AND recipient_subject_id=?",
                      (_iso(self.clock()), row["revision"], _iso(self.clock()), announcement_id, actor.subject_id))
        return {"id": announcement_id, "acked": True, "revision": row["revision"]}

    def stats(self, actor: IdentityContext, announcement_id: str) -> dict:
        row = self._row(announcement_id)
        self._own(actor, row, allow_staff=True)
        rows = self.store.query("SELECT faculty_code, cohort, read_at, acked_at FROM ann_deliveries WHERE announcement_id=?", (announcement_id,))
        delivered = len(rows)
        read, acked = sum(1 for r in rows if r["read_at"]), sum(1 for r in rows if r["acked_at"])

        def by(field):
            totals: dict[str, int] = {}
            for r in rows:
                totals[r[field] or "—"] = totals.get(r[field] or "—", 0) + 1
            kept = dom.group_small_counts(totals)
            out = [{"key": k, "delivered": n, "read": sum(1 for r in rows if (r[field] or "—") == k and r["read_at"]),
                    "acked": sum(1 for r in rows if (r[field] or "—") == k and r["acked_at"])} for k, n in sorted(kept.items()) if k != "khác"]
            if "khác" in kept:
                small = {k for k, n in totals.items() if n < dom.MIN_GROUP_FOR_STATS}
                out.append({"key": "khác", "delivered": kept["khác"], "read": sum(1 for r in rows if (r[field] or "—") in small and r["read_at"]),
                            "acked": sum(1 for r in rows if (r[field] or "—") in small and r["acked_at"])})
            return out

        timeline: dict[str, int] = {}
        for r in rows:
            if r["read_at"]:
                hour = r["read_at"][:13]
                timeline[hour] = timeline.get(hour, 0) + 1
        return {"delivered": delivered, "read": read, "acked": acked, "read_rate": round(read / delivered, 4) if delivered else 0.0,
                "by_faculty": by("faculty_code"), "by_cohort": by("cohort"), "timeline": [{"hour": h, "reads": n} for h, n in sorted(timeline.items())]}

    def pending_acks(self, actor: IdentityContext, announcement_id: str, lookup_name: Callable[[str], dict] | None = None) -> dict:
        row = self._row(announcement_id)
        self._own(actor, row)
        if not row["requires_ack"]:
            raise AnnouncementError(409, "ANNOUNCEMENT_STATE", "Thông báo này không cần xác nhận.")
        people = self.store.query("SELECT recipient_subject_id FROM ann_deliveries WHERE announcement_id=? AND acked_at IS NULL ORDER BY recipient_subject_id LIMIT 500", (announcement_id,))
        with self.store.tx() as c:
            self.store.audit(c, actor.subject_id, "ANNOUNCEMENT_PENDING_ACKS_VIEWED", announcement_id, {"count": len(people)})
        names = {r.subject_id: r for r in self.directory.all_recipients()}
        return {"items": [{"subject_id": p["recipient_subject_id"], "class_code": names[p["recipient_subject_id"]].class_code if p["recipient_subject_id"] in names else None,
                           **(lookup_name(p["recipient_subject_id"]) if lookup_name else {})} for p in people]}
