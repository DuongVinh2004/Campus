"""Owned local preparation, independent of unconnected university business APIs.

Reuses the main actor database and signed preview protocol. No university
profile, course, eligibility, publication or submission is manufactured here.
"""
import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from campus247.application.document_request.certificates import preview_entity, serial
from campus247.application.knowledge.platform_models import PlatformError
from campus247.domain.action.preview import create_action_preview
from campus247.domain.shared.values import generate_uuid7
from campus247.ports.identity import IdentityRole


class PreparationForm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["STUDENT_CERTIFICATE", "GRADE_APPEAL", "GENERAL_SUPPORT"]
    purpose: str = Field(default="", max_length=2000)
    recipient: str = Field(default="", max_length=500)
    course: str = Field(default="", max_length=500)
    reason: str = Field(min_length=1, max_length=6000)

    @field_validator("reason")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Nhập nội dung cần chuẩn bị")
        return value.strip()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class LocalPreparationService:
    def __init__(self, store, platform):
        self.store, self.platform = store, platform
        with store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("CREATE TABLE IF NOT EXISTS campus_preparation(tenant TEXT NOT NULL,owner TEXT NOT NULL,id TEXT NOT NULL,version INTEGER NOT NULL,record TEXT NOT NULL,PRIMARY KEY(tenant,owner,id))")
            conn.execute("CREATE TABLE IF NOT EXISTS campus_preparation_revision(tenant TEXT NOT NULL,owner TEXT NOT NULL,id TEXT NOT NULL,version INTEGER NOT NULL,record TEXT NOT NULL,PRIMARY KEY(tenant,owner,id,version))")
            conn.execute("CREATE TABLE IF NOT EXISTS campus_preparation_preview(tenant TEXT NOT NULL,owner TEXT NOT NULL,id TEXT NOT NULL,record TEXT NOT NULL,PRIMARY KEY(tenant,owner,id))")
            conn.execute("CREATE TABLE IF NOT EXISTS campus_preparation_receipt(tenant TEXT NOT NULL,owner TEXT NOT NULL,client_id TEXT NOT NULL,preview_id TEXT NOT NULL,fingerprint TEXT NOT NULL,record TEXT NOT NULL,PRIMARY KEY(tenant,owner,client_id),UNIQUE(tenant,owner,preview_id))")

    def scope(self, actor):
        self.platform.reader(actor)
        if not actor.has_role(IdentityRole.STUDENT) or actor.is_synthetic:
            raise PlatformError(403, "STUDENT_REQUIRED", "Cần tài khoản sinh viên local đang hoạt động")
        return actor.tenant_id, actor.subject_id

    def list(self, actor):
        scope = self.scope(actor)
        with self.store.connect() as conn:
            rows = conn.execute("SELECT record FROM campus_preparation WHERE tenant=? AND owner=? ORDER BY json_extract(record,'$.updated_at') DESC,id DESC", scope).fetchall()
        return {"items": [json.loads(row[0]) for row in rows], "university_connected": False}

    def read(self, actor, identifier):
        scope = self.scope(actor)
        with self.store.connect() as conn:
            row = conn.execute("SELECT record FROM campus_preparation WHERE tenant=? AND owner=? AND id=?", (*scope, identifier)).fetchone()
        if row is None:
            raise PlatformError(404, "NOT_FOUND", "Không tìm thấy nháp của tài khoản này")
        return json.loads(row[0])

    def preview(self, actor, form, identifier=None, expected_version=0):
        scope = self.scope(actor)
        if identifier:
            record = self.read(actor, identifier)
            if record["version"] != expected_version or record["form"]["kind"] != form.kind:
                raise PlatformError(409, "STALE_VERSION", "Nháp đã thay đổi; giữ nội dung và mở lại phiên bản hiện tại")
        elif expected_version != 0:
            raise PlatformError(409, "STALE_VERSION", "Nháp mới phải có phiên bản 0")
        identifier = identifier or generate_uuid7()
        preview = create_action_preview(actor.subject_id, "LOCAL_PREPARATION_SAVE", {
            "tenant": scope[0], "id": identifier, "expected_version": expected_version,
            "form": form.model_dump(), "effect": "draft_saved", "sent_to_university": False,
        }, session_id=actor.session_id)
        with self.store.connect() as conn:
            conn.execute("INSERT INTO campus_preparation_preview VALUES(?,?,?,?)", (*scope, preview.id, encoded(serial(asdict(preview)))))
        return {"preview_id": preview.id, "confirmation_token": self.platform.tokens.mint_token(preview),
                "expires_at": preview.expires_at.isoformat(), "payload": json.loads(preview.normalized_payload)}

    def save(self, actor, preview_id, token, client_id, confirmed, current_identity):
        scope = self.scope(actor)
        if confirmed is not True:
            raise PlatformError(422, "CONFIRMATION_REQUIRED", "Cần xem trước và xác nhận lưu nháp")
        fingerprint = hashlib.sha256(encoded([preview_id, token]).encode()).hexdigest()
        with self.store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            # Recheck the signed principal/revocation under the storage lock.
            current = current_identity()
            if self.scope(current) != scope or current.session_id != actor.session_id:
                raise PlatformError(403, "SESSION_CHANGED", "Phiên đã thay đổi; nội dung chưa lưu được giữ")
            old = conn.execute("SELECT fingerprint,record FROM campus_preparation_receipt WHERE tenant=? AND owner=? AND client_id=?", (*scope, client_id)).fetchone()
            if old:
                if old[0] != fingerprint:
                    raise PlatformError(409, "IDEMPOTENCY_CONFLICT", "Mã lưu đã được dùng cho nội dung khác")
                return {**json.loads(old[1]), "is_replay": True}
            row = conn.execute("SELECT record FROM campus_preparation_preview WHERE tenant=? AND owner=? AND id=?", (*scope, preview_id)).fetchone()
            if not row:
                raise PlatformError(404, "PREVIEW_NOT_FOUND", "Cần xem trước nháp của chính tài khoản này")
            preview = preview_entity(json.loads(row[0]))
            valid = self.platform.tokens.validate_token(token, preview.id, actor.subject_id, actor.session_id,
                preview.conversation_id, preview.action_type, preview.tool_version, preview.policy_version, preview.payload_hash)
            if not valid.is_valid:
                raise PlatformError(409, "PREVIEW_INVALID", "Bản xem trước hết hạn hoặc khác phiên; xem trước lại")
            payload = json.loads(preview.normalized_payload)
            row = conn.execute("SELECT version,record FROM campus_preparation WHERE tenant=? AND owner=? AND id=?", (*scope, payload["id"])).fetchone()
            if (row[0] if row else 0) != payload["expected_version"]:
                raise PlatformError(409, "STALE_VERSION", "Nháp đã thay đổi; giữ nội dung và đối chiếu phiên bản")
            if conn.execute("SELECT 1 FROM campus_preparation_receipt WHERE tenant=? AND owner=? AND preview_id=?", (*scope, preview_id)).fetchone():
                raise PlatformError(409, "PREVIEW_CONSUMED", "Nháp đã lưu; mở lịch sử để đọc lại")
            now = datetime.now(UTC).isoformat()
            record = {"id": payload["id"], "version": payload["expected_version"] + 1,
                "form": payload["form"], "status": "DRAFT", "sent_to_university": False,
                "created_at": json.loads(row[1])["created_at"] if row else now, "updated_at": now}
            receipt = {"receipt_id": generate_uuid7(), "effect": "draft_saved", "preview_id": preview_id,
                "client_id": client_id, "committed_at": now, "document": record, "is_replay": False}
            conn.execute("INSERT INTO campus_preparation VALUES(?,?,?,?,?) ON CONFLICT(tenant,owner,id) DO UPDATE SET version=excluded.version,record=excluded.record", (*scope, record["id"], record["version"], encoded(record)))
            conn.execute("INSERT INTO campus_preparation_revision VALUES(?,?,?,?,?)", (*scope, record["id"], record["version"], encoded(record)))
            conn.execute("INSERT INTO campus_preparation_receipt VALUES(?,?,?,?,?,?)", (*scope, client_id, preview_id, fingerprint, encoded(receipt)))
        return receipt
