"""F5: runs of a procedure over the ticket service. The student sees every value and presses confirm; code owns every transition."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Callable

from campus247.domain.procedures import (EDITABLE, StateError, advance, decide_state, missing_required, render_ticket, validate_fields,
    verbatim_extraction, with_defaults, _fold)
from campus247.ports.campus_ops import OpsError, now_iso, uuid7
from campus247.ports.identity import IdentityContext, IdentityRole

PREVIEW_TTL = timedelta(minutes=10)
EXPIRY = timedelta(days=30)
MAX_NEW_RUNS_PER_DAY = 10
SCHEMA = """
CREATE TABLE IF NOT EXISTS proc_runs(
  id TEXT PRIMARY KEY, owner_subject_id TEXT NOT NULL, procedure_id TEXT NOT NULL, procedure_version INTEGER NOT NULL,
  state TEXT NOT NULL, fields TEXT NOT NULL DEFAULT '{}', field_origin TEXT NOT NULL DEFAULT '{}', blocked TEXT NOT NULL DEFAULT '[]',
  ticket_id TEXT, row_version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, expires_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS proc_runs_owner ON proc_runs(owner_subject_id, updated_at DESC);
CREATE TABLE IF NOT EXISTS proc_previews(id TEXT PRIMARY KEY, run_id TEXT NOT NULL, owner TEXT NOT NULL, payload_hash TEXT NOT NULL,
  row_version INTEGER NOT NULL, expires_at TEXT NOT NULL, used_at TEXT);
"""


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


class ProcedureService:
    def __init__(self, store, ops_service, procedures: dict, *, clock: Callable[[], datetime] | None = None, signing_key: str = "dev-procedures-key",
                 enabled: Callable[[str], bool] | None = None):
        self.store, self.ops, self.procedures = store, ops_service, procedures
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._key = signing_key.encode()
        self.enabled = enabled or (lambda key: True)
        conn = self.store._connect()
        try:
            conn.executescript(SCHEMA)
        finally:
            conn.close()

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _student(identity: IdentityContext) -> None:
        if IdentityRole.STUDENT not in identity.roles:
            raise OpsError(403, "FORBIDDEN", "Chỉ sinh viên mới làm thủ tục.")

    def _proc(self, procedure_id: str):
        proc = self.procedures.get(procedure_id)
        if proc is None:
            raise OpsError(404, "PROCEDURE_NOT_FOUND", "Không có thủ tục này.")
        return proc

    def _row(self, identity, run_id) -> dict:
        row = self.store.one("SELECT * FROM proc_runs WHERE id=? AND owner_subject_id=?", (run_id, identity.subject_id))
        if row is None:
            raise OpsError(404, "PROCEDURE_RUN_NOT_FOUND", "Không tìm thấy phiên thủ tục.")
        return row

    def _view(self, row: dict) -> dict:
        proc = self._proc(row["procedure_id"])
        values = json.loads(row["fields"])
        missing = missing_required(proc, with_defaults(proc, values))
        ticket = None
        if row["ticket_id"]:
            t = self.store.one("SELECT code, status FROM ops_tickets WHERE id=?", (row["ticket_id"],))
            ticket = {"id": row["ticket_id"], **(t or {})}
        return {"id": row["id"], "procedure_id": row["procedure_id"], "title": proc.title, "state": row["state"], "fields": values,
            "field_origin": json.loads(row["field_origin"]), "blocked": json.loads(row["blocked"]), "missing": missing, "row_version": row["row_version"],
            "next_step": {"STARTED": "fill", "COLLECTING": "fill", "BLOCKED": "fix_or_ask", "READY_FOR_PREVIEW": "preview", "PREVIEWED": "confirm",
                          "SUBMITTED": "track"}.get(row["state"], "none"), "ticket": ticket, "expires_at": row["expires_at"]}

    def _token(self, preview_id: str, owner: str, payload_hash: str) -> str:
        return hmac.new(self._key, f"{preview_id}|{owner}|{payload_hash}".encode(), hashlib.sha256).hexdigest()

    # ------------------------------------------------------------------ catalogue and starting
    def catalog(self) -> dict:
        return {"items": [p.catalog() for p in self.procedures.values()]}

    def start(self, identity: IdentityContext, procedure_id: str) -> dict:
        self._student(identity)
        proc = self._proc(procedure_id)
        now = self.clock()
        run_id = uuid7()
        with self.store.tx() as c:
            today = c.execute("SELECT COUNT(*) n FROM proc_runs WHERE owner_subject_id=? AND created_at>=?",
                (identity.subject_id, _iso(now - timedelta(days=1)))).fetchone()["n"]
            if today >= MAX_NEW_RUNS_PER_DAY:
                raise OpsError(429, "PROCEDURE_RATE", "Bạn đã bắt đầu quá nhiều thủ tục hôm nay.")
            state, blocked = decide_state(proc, {})
            c.execute("INSERT INTO proc_runs VALUES(?,?,?,?,?,?,?,?,NULL,1,?,?,?)",
                (run_id, identity.subject_id, proc.id, proc.version, "STARTED", "{}", "{}", "[]", _iso(now), _iso(now), _iso(now + EXPIRY)))
            self.store.audit(c, identity.subject_id, "PROCEDURE_STARTED", run_id, {"procedure": proc.id})
        return self._view(self.store.one("SELECT * FROM proc_runs WHERE id=?", (run_id,)))

    def list_runs(self, identity: IdentityContext, state: str | None = None) -> dict:
        self._student(identity)
        rows = self.store.query("SELECT * FROM proc_runs WHERE owner_subject_id=? ORDER BY updated_at DESC LIMIT 100", (identity.subject_id,))
        return {"items": [self._view(r) for r in rows if state in (None, r["state"])]}

    def get(self, identity: IdentityContext, run_id: str) -> dict:
        self._student(identity)
        return self._view(self._row(identity, run_id))

    # ------------------------------------------------------------------ recognise and extract (no model needed; a proposer may be added)
    def from_text(self, identity: IdentityContext, text: str, procedure_id: str | None = None, proposed: dict | None = None) -> dict:
        self._student(identity)
        text = (text or "").strip()
        if not text or len(text) > 1000:
            raise OpsError(422, "PROCEDURE_TEXT_INVALID", "Câu mô tả cần từ 1 đến 1000 ký tự.")
        words = set(re.findall(r"[a-z0-9]{3,}", _fold(text)))
        scored = []
        for p in self.procedures.values():
            vocab = set(re.findall(r"[a-z0-9]{3,}", _fold(p.title + " " + p.description)))
            score = len(words & vocab)
            if score:
                scored.append((score, p))
        scored.sort(key=lambda t: (-t[0], t[1].id))
        suggestions = [{"procedure_id": p.id, "title": p.title} for _, p in scored[:3]]
        chosen = self.procedures.get(procedure_id) if procedure_id else (scored[0][1] if len(scored) == 1 or (len(scored) > 1 and scored[0][0] > scored[1][0] * 2) else None)
        extracted, dropped = {}, []
        if chosen is not None:
            candidates = dict(proposed or {})
            for f in chosen.fields:
                if f.extract and f.key not in candidates and f.pattern:
                    m = re.search(f.pattern.strip("^$").join(["(?<![A-Za-z0-9])", "(?![A-Za-z0-9])"]), text)
                    if m:
                        candidates[f.key] = m.group(0)
            extracted, dropped = verbatim_extraction(text, candidates, chosen)
        return {"suggestions": suggestions, "procedure_id": chosen.id if chosen else None,
                "extracted": [{"field": k, **v} for k, v in extracted.items()], "dropped": dropped}

    # ------------------------------------------------------------------ fields
    def put_fields(self, identity: IdentityContext, run_id: str, fields: dict, row_version: int, confirm_extracted: list[str] | None = None) -> dict:
        self._student(identity)
        row = self._row(identity, run_id)
        if row["state"] not in EDITABLE:
            raise OpsError(409, "PROCEDURE_STATE", "Phiên này không sửa được nữa.")
        if row["row_version"] != row_version:
            raise OpsError(409, "PROCEDURE_CONFLICT", "Phiên đã được cập nhật ở nơi khác.")
        proc = self._proc(row["procedure_id"])
        clean, errors = validate_fields(proc, fields)
        if errors:
            exc = OpsError(422, "PROCEDURE_FIELD_INVALID", "Một số trường chưa hợp lệ.")
            exc.errors = errors
            raise exc
        values = {**json.loads(row["fields"]), **clean}
        origin = json.loads(row["field_origin"])
        confirmed = set(confirm_extracted or ())
        for key in clean:
            origin[key] = "EXTRACTED_CONFIRMED" if key in confirmed else "USER"
        state, blocked = decide_state(proc, values)
        try:
            advance(row["state"], state)
        except StateError:
            raise OpsError(409, "PROCEDURE_STATE", "Không chuyển được trạng thái.") from None
        with self.store.tx() as c:
            cur = c.execute("UPDATE proc_runs SET fields=?, field_origin=?, blocked=?, state=?, row_version=row_version+1, updated_at=? WHERE id=? AND row_version=?",
                (json.dumps(values, ensure_ascii=False), json.dumps(origin), json.dumps(blocked, ensure_ascii=False), state, now_iso(), run_id, row_version))
            if cur.rowcount != 1:
                raise OpsError(409, "PROCEDURE_CONFLICT", "Phiên đã được cập nhật ở nơi khác.")
            self.store.audit(c, identity.subject_id, f"PROCEDURE_{state}", run_id, {"fields": sorted(clean)})
        return self._view(self.store.one("SELECT * FROM proc_runs WHERE id=?", (run_id,)))

    # ------------------------------------------------------------------ preview -> confirm -> ticket
    def submit_preview(self, identity: IdentityContext, run_id: str) -> dict:
        self._student(identity)
        row = self._row(identity, run_id)
        if row["state"] == "BLOCKED":
            exc = OpsError(409, "PROCEDURE_NOT_ELIGIBLE", "Chưa đủ điều kiện theo quy định.")
            exc.errors = json.loads(row["blocked"])
            raise exc
        if row["state"] not in {"READY_FOR_PREVIEW", "PREVIEWED"}:
            raise OpsError(409, "PROCEDURE_STATE", "Cần điền đủ các trường bắt buộc trước.")
        proc = self._proc(row["procedure_id"])
        ticket = render_ticket(proc, json.loads(row["fields"]))
        payload_hash = hashlib.sha256(json.dumps(ticket, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        preview_id, expires = uuid7(), self.clock() + PREVIEW_TTL
        with self.store.tx() as c:
            c.execute("INSERT INTO proc_previews VALUES(?,?,?,?,?,?,NULL)", (preview_id, run_id, identity.subject_id, payload_hash, row["row_version"], _iso(expires)))
            c.execute("UPDATE proc_runs SET state='PREVIEWED', updated_at=? WHERE id=?", (now_iso(), run_id))
            self.store.audit(c, identity.subject_id, "PROCEDURE_PREVIEWED", run_id)
        return {"preview_id": preview_id, "confirmation_token": self._token(preview_id, identity.subject_id, payload_hash), "expires_at": _iso(expires),
                "ticket_preview": {"title": ticket["title"], "summary": ticket["summary"], "fields": ticket["fields"]}}

    def submit_confirm(self, identity: IdentityContext, preview_id: str, token: str, idempotency_key: str) -> dict:
        self._student(identity)
        if not idempotency_key:
            raise OpsError(422, "IDEMPOTENCY_KEY_REQUIRED", "Thiếu Idempotency-Key.")
        if not token:
            raise OpsError(428, "CONFIRMATION_REQUIRED", "Cần xác nhận.")
        pv = self.store.one("SELECT * FROM proc_previews WHERE id=? AND owner=?", (preview_id, identity.subject_id))
        if pv is None or pv["expires_at"] < _iso(self.clock()):
            raise OpsError(410, "PREVIEW_EXPIRED", "Bản xem trước đã hết hạn.")
        if not hmac.compare_digest(self._token(preview_id, identity.subject_id, pv["payload_hash"]), token):
            raise OpsError(428, "CONFIRMATION_REQUIRED", "Mã xác nhận không đúng.")
        row = self._row(identity, pv["run_id"])
        if row["state"] == "SUBMITTED":  # replay of the same confirmation
            return {**self._view(row), "replayed": True}
        if row["state"] != "PREVIEWED" or row["row_version"] != pv["row_version"]:
            raise OpsError(409, "PROCEDURE_CONFLICT", "Phiên đã đổi sau khi xem trước; hãy xem trước lại.")
        proc = self._proc(row["procedure_id"])
        ticket = render_ticket(proc, json.loads(row["fields"]))
        if hashlib.sha256(json.dumps(ticket, sort_keys=True, ensure_ascii=False).encode()).hexdigest() != pv["payload_hash"]:
            raise OpsError(409, "PROCEDURE_CONFLICT", "Nội dung đã đổi sau khi xem trước.")
        made = self.ops.submit_ticket(identity, ticket, f"procedure-run:{row['id']}")  # idempotent: one run, at most one ticket
        with self.store.tx() as c:
            c.execute("UPDATE proc_runs SET state='SUBMITTED', ticket_id=?, row_version=row_version+1, updated_at=? WHERE id=?", (made["id"], now_iso(), row["id"]))
            c.execute("UPDATE proc_previews SET used_at=? WHERE id=?", (now_iso(), preview_id))
            self.store.audit(c, identity.subject_id, "PROCEDURE_SUBMITTED", row["id"], {"ticket": made["id"]})
        return {**self._view(self.store.one("SELECT * FROM proc_runs WHERE id=?", (row["id"],))), "replayed": False}

    def cancel(self, identity: IdentityContext, run_id: str) -> dict:
        self._student(identity)
        row = self._row(identity, run_id)
        try:
            advance(row["state"], "CANCELLED")
        except StateError:
            raise OpsError(409, "PROCEDURE_STATE", "Phiên đã gửi hoặc đã kết thúc, không hủy được.") from None
        with self.store.tx() as c:
            c.execute("UPDATE proc_runs SET state='CANCELLED', fields='{}', row_version=row_version+1, updated_at=? WHERE id=?", (now_iso(), run_id))
            self.store.audit(c, identity.subject_id, "PROCEDURE_CANCELLED", run_id)
        return self._view(self.store.one("SELECT * FROM proc_runs WHERE id=?", (run_id,)))

    def expire_stale(self) -> int:
        """Unsent runs idle for 30 days: field data deleted, state row kept."""
        now = _iso(self.clock())
        with self.store.tx() as c:
            rows = c.execute("SELECT id, owner_subject_id FROM proc_runs WHERE state IN ('STARTED','COLLECTING','BLOCKED','READY_FOR_PREVIEW','PREVIEWED') AND expires_at<?", (now,)).fetchall()
            for r in rows:
                c.execute("UPDATE proc_runs SET state='EXPIRED', fields='{}', field_origin='{}', blocked='[]', updated_at=? WHERE id=?", (now, r["id"]))
                self.store.audit(c, "system", "PROCEDURE_EXPIRED", r["id"])
        return len(rows)
