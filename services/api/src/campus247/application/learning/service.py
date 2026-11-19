from __future__ import annotations

import asyncio
import copy
import hashlib
import hmac
import json
import re
import sqlite3
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from campus247.application.learning.accessible_text import (
    OCR_READS,
    OCR_WRITES,
    LearningAccessibleText,
)
from campus247.application.learning.exit_tickets import (
    EXIT_TICKET_READS,
    EXIT_TICKET_WRITES,
    LearningExitTickets,
)
from campus247.application.learning.explanation import LearningExplanation
from campus247.application.learning.extensions import LearningExtensions
from campus247.application.learning.idea_cards import (
    IDEA_READS,
    IDEA_WRITES,
    LearningIdeaCards,
)
from campus247.application.learning.page_feedback import (
    LearningPageFeedback,
    feedback_clock,
)
from campus247.application.learning.scan_lifecycle import QUARANTINED, LearningScanLifecycle
from campus247.application.learning.version_changes import LearningVersionChanges
from campus247.domain.learning import LearningError, require
from campus247.domain.shared.values import generate_uuid7
from campus247.application.learning.scanner import UnavailableScanner
from campus247.application.learning.telemetry import record
from campus247.ports.learning_rendition import PDF_MEDIA_TYPE, PPTX_MEDIA_TYPE

PROCESSING_TIMEOUT_SECONDS = 120
INCOMPLETE_UPLOAD_STATES = {"CREATED", "RECEIVING", "RECEIVED"}


def now():
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def upload_expired(upload, instant=None):
    return (not upload.get("version_id") and upload["state"] in INCOMPLETE_UPLOAD_STATES
            and datetime.fromisoformat(upload["expires_at"]) <= (instant or datetime.now(UTC)))


def expire_upload(upload):
    if upload["state"] == "CREATED":
        upload["reservation_released"] = True
    upload["state"] = "EXPIRED"


def reserved_upload_bytes(uploads, offering):
    return sum(row["byte_size"] for row in uploads.values()
               if row["offering_id"] == offering and not row.get("reservation_released"))


class LearningService(LearningScanLifecycle, LearningExtensions, LearningExplanation, LearningPageFeedback, LearningVersionChanges, LearningExitTickets, LearningIdeaCards, LearningAccessibleText):
    def __init__(self, repository, blob_store, *, tenant_id, signing_key, scanner=None, directory=None, ai_gateway=None, ai_verifier=None, ai_source_hashes=(), optimize_pdf=False, pptx_converter=None, page_feedback_offerings=(), page_explanations_available=True, version_change_offerings=(), exit_ticket_offerings=(), idea_card_offerings=(), accessible_text_offerings=(), accessible_text_ocr_paused_offerings=(), accessible_text_pipeline=None, accessible_text_byte_quota=12 * 1024**3):
        require(bool(signing_key) and bool(tenant_id), 503, "LEARNING_UNAVAILABLE", "Chưa cấu hình học liệu.")
        self.repository, self.blobs, self.tenant_id = repository, blob_store, tenant_id
        self.signing_key = signing_key.encode()
        self.scanner = scanner or UnavailableScanner()
        self.directory = directory if callable(directory) else list(directory or [])
        self.ai_gateway, self.ai_verifier = ai_gateway, ai_verifier
        self.ai_source_hashes = frozenset(ai_source_hashes)
        self.optimize_pdf = optimize_pdf
        self.pptx_converter = pptx_converter
        self.page_feedback_offerings = frozenset(page_feedback_offerings)
        self.page_explanations_available = page_explanations_available
        self.version_change_offerings = frozenset(version_change_offerings)
        self.idea_card_offerings = frozenset(idea_card_offerings)
        self.accessible_text_offerings = frozenset(accessible_text_offerings)
        self.accessible_text_ocr_paused_offerings = frozenset(accessible_text_ocr_paused_offerings)
        self.accessible_text_pipeline = accessible_text_pipeline
        self.accessible_text_byte_quota = accessible_text_byte_quota
        self.exit_ticket_offerings = frozenset(exit_ticket_offerings)

    @property
    def pptx_available(self):
        return bool(self.pptx_converter is not None and self.pptx_converter.available)

    def directory_items(self):
        return self.directory() if callable(self.directory) else self.directory

    def identity(self, actor):
        require(actor is not None, 401, "AUTHENTICATION_REQUIRED", "Vui lòng đăng nhập.")
        require(actor.is_active and actor.tenant_id == self.tenant_id, 403, "FORBIDDEN", "Tài khoản không thuộc phạm vi học liệu.")
        require(actor.expires_at > datetime.now(UTC) and bool(actor.session_id), 401, "AUTHENTICATION_REQUIRED", "Phiên đăng nhập không còn hiệu lực.")

    def recheck(self, actor, still_valid):
        """Re-read the caller's identity inside a storage transaction.

        The router checks the session once, before the request may wait for the storage lock. A session revoked during
        that wait must not write, so the same session is read again after the lock is held and the fresh identity
        (current roles) is used from here on.
        """
        if still_valid is None:
            return actor
        try:
            fresh = still_valid()
        except LearningError:
            raise
        except Exception:  # noqa: BLE001 -- any failed revalidation denies the write
            raise LearningError(401, "AUTHENTICATION_REQUIRED", "Phiên đăng nhập không còn hiệu lực.") from None
        require(fresh.subject_id == actor.subject_id and fresh.session_id == actor.session_id,
                401, "READER_SESSION_CHANGED", "Phiên đăng nhập đã thay đổi.")
        self.identity(fresh)
        return fresh

    def admin(self, actor):
        self.identity(actor)
        require(actor.has_role("SYSTEM_ADMIN"), 403, "FORBIDDEN", "Cần quyền quản trị lớp.")

    def access(self, s, actor, offering_id, *, write=False):
        self.identity(actor)
        offering = s["offerings"].get(offering_id)
        require(offering is not None)
        member = next((r for r in s["members"].values() if r["offering_id"] == offering_id and r["actor_subject_id"] == actor.subject_id and r["status"] == "ACTIVE"), None)
        require(member is not None)
        require((member["role"] == "INSTRUCTOR" and actor.has_role("LECTURER")) or (member["role"] == "STUDENT" and actor.has_role("STUDENT")))
        if write:
            require(member["role"] == "INSTRUCTOR" and actor.has_role("LECTURER"), 403, "FORBIDDEN", "Bạn không được quản lý lớp này.")
            require(offering["status"] == "ACTIVE", 409, "CLASS_ARCHIVED", "Lớp đã được lưu trữ.")
        return offering, member

    def material(self, s, actor, material_id, write=False):
        material = s["materials"].get(material_id)
        require(material is not None)
        offering, member = self.access(s, actor, material["offering_id"], write=write)
        require(write or member["role"] == "INSTRUCTOR" or material["visibility"] == "VISIBLE")
        return material, offering, member

    def version(self, s, actor, version_id):
        version = s["versions"].get(version_id)
        require(version is not None)
        material, offering, member = self.material(s, actor, version["material_id"])
        require(member["role"] == "INSTRUCTOR" or version["publication_state"] == "PUBLISHED")
        return version, material, offering, member

    def dto_version(self, s, actor, version):
        version, material, offering, member = self.version(s, actor, version["id"])
        ocr_available = (offering["id"] in self.accessible_text_offerings and version["processing_state"] == "READY"
                         and version["publication_state"] not in {"RETRACTED", QUARANTINED}
                         and version.get("source_media_type", PDF_MEDIA_TYPE) == PDF_MEDIA_TYPE)
        result = {k: copy.deepcopy(v) for k, v in version.items() if k not in {
            "storage_key", "sha256", "byte_size", "uploaded_by", "view_blob_id", "idea_source_epoch", "accessible_text_release_id",
            "scan_receipts", "scan_quarantine",
        }}
        result.update(version_id=version["id"], title=material["title"], offering_id=offering["id"],
            current_published_version_id=material["current_published_version_id"],
            content_path=f'/v1/learning/versions/{version["id"]}/content',
            capabilities={"read": version["processing_state"] == "READY", "manage": member["role"] == "INSTRUCTOR",
                "download": offering["download_allowed"], "explain": self.ai_allowed(actor, version.get("sha256", "")),
                "version_changes": offering["id"] in self.version_change_offerings and version["processing_state"] == "READY",
                "idea_cards": offering["id"] in self.idea_card_offerings and member["role"] == "STUDENT"
                    and version["processing_state"] == "READY" and version["publication_state"] == "PUBLISHED",
                "accessible_text": ocr_available and material["visibility"] == "VISIBLE" and version["publication_state"] == "PUBLISHED",
                "manage_accessible_text": ocr_available and member["role"] == "INSTRUCTOR",
                "page_feedback": offering["id"] in self.page_feedback_offerings and member["role"] == "STUDENT"
                    and version["processing_state"] == "READY" and version["publication_state"] == "PUBLISHED"})
        return result

    def ai_allowed(self, actor, digest=None):
        return actor.is_synthetic and bool(self.ai_source_hashes) and self.ai_gateway is not None and self.ai_verifier is not None and (digest is None or digest in self.ai_source_hashes)

    def dto_material(self, s, actor, material):
        material, _, member = self.material(s, actor, material["id"])
        versions = [v for v in s["versions"].values() if v["material_id"] == material["id"] and (member["role"] == "INSTRUCTOR" or v["publication_state"] == "PUBLISHED")]
        if member["role"] != "INSTRUCTOR":
            require(any(v["id"] == material["current_published_version_id"] for v in versions))
        return {k: copy.deepcopy(v) for k, v in material.items() if k != "idea_visibility_epoch"} | {
            "versions": [self.dto_version(s, actor, v) for v in sorted(versions, key=lambda x: x["version_no"], reverse=True)],
        }

    def dto_offering(self, s, offering, member):
        role = member["role"] if member else None
        timezone = s["terms"].get(offering["term_id"], {}).get("timezone") or "Asia/Bangkok"
        return copy.deepcopy(offering) | {
            "timezone": timezone, "member_role": role,
            "capabilities": {"read": member is not None, "manage": role == "INSTRUCTOR",
                "exit_tickets": member is not None and offering["id"] in self.exit_ticket_offerings,
                "page_feedback": role == "INSTRUCTOR" and offering["id"] in self.page_feedback_offerings,
                "page_explanations": self.page_explanations_available and member is not None
                    and offering["id"] in self.page_feedback_offerings},
        }

    async def query(self, actor, kind, target=None, **params):
        self.identity(actor)
        if kind in OCR_READS:
            require(bool(self.accessible_text_offerings))
            view = self.repository.read_view(actor, kind, target, params) if hasattr(self.repository, "read_view") else self.repository.transaction()
            async with view as s:
                return copy.deepcopy(self.read_accessible_text(s, actor, kind, target, params))
        if kind in IDEA_READS:
            require(bool(self.idea_card_offerings))
            async with self.repository.transaction() as s:
                self.identity(actor)
                idea_result = copy.deepcopy(self.read_ideas(s, actor, kind, target))
            require(idea_result is not None)
            return idea_result
        if kind in EXIT_TICKET_READS:
            require(bool(self.exit_ticket_offerings))
            view = self.repository.read_view(actor, kind, target, params) if hasattr(self.repository, "read_view") else self.repository.transaction()
            async with view as s:
                return self.read_exit_tickets(s, actor, kind, target)
        if kind == "version_changes":
            require(bool(self.version_change_offerings))
            async with self.repository.transaction() as s:
                return self.read_version_changes(s, actor, target)
        if kind == "page_explanations":
            require(self.page_explanations_available and bool(self.page_feedback_offerings))
            async with self.repository.transaction() as s:
                return self.read_page_explanations(s, actor, target)
        if kind in {"page_feedback", "feedback_window", "feedback_summary"}:
            require(bool(self.page_feedback_offerings))
            async with self.repository.transaction() as s:
                return self.read_page_feedback(s, actor, kind, target, params)
        view = self.repository.read_view(actor, kind, target, params) if hasattr(self.repository, "read_view") else self.repository.transaction()
        async with view as s:
            if kind == "capabilities":
                return {"available": True, "read": True, "manage": actor.has_role("LECTURER"), "admin": actor.has_role("SYSTEM_ADMIN"), "max_file_bytes": self.blobs.max_bytes, "max_pages": 500, "scanner": self.scanner.name, "supported_types": [PDF_MEDIA_TYPE] + ([PPTX_MEDIA_TYPE] if self.pptx_available else []), "ai_available": self.ai_allowed(actor), "pptx_available": self.pptx_available, "session_contexts": True, "idea_cards": bool(self.idea_card_offerings)}
            if kind in {"terms", "courses", "admin_offerings", "directory"}:
                self.admin(actor)
                if kind == "directory":
                    return copy.deepcopy(self.directory_items())
                if kind == "admin_offerings":
                    rows = []
                    for offering in s["offerings"].values():
                        member = next((r for r in s["members"].values() if r["offering_id"] == offering["id"] and r["actor_subject_id"] == actor.subject_id and r["status"] == "ACTIVE"), None)
                        rows.append(self.dto_offering(s, offering, member))
                    return rows
                return list(copy.deepcopy(s["offerings" if kind == "admin_offerings" else kind]).values())
            if kind == "offerings":
                result = []
                for offering in s["offerings"].values():
                    try:
                        _, member = self.access(s, actor, offering["id"])
                    except LearningError:
                        continue
                    result.append(self.dto_offering(s, offering, member))
                return result
            if kind == "offering":
                offering, member = self.access(s, actor, target)
                return self.dto_offering(s, offering, member)
            if kind == "members":
                if not actor.has_role("SYSTEM_ADMIN"):
                    self.access(s, actor, target, write=True)
                else:
                    self.admin(actor)
                return [copy.deepcopy(x) for x in s["members"].values() if x["offering_id"] == target]
            if kind == "sessions":
                self.access(s, actor, target)
                return sorted([copy.deepcopy(x) for x in s["sessions"].values() if x["offering_id"] == target], key=lambda x: x["sequence_no"])
            if kind == "materials":
                session = s["sessions"].get(target)
                require(session is not None)
                self.access(s, actor, session["offering_id"])
                result = []
                for link in s["links"].values():
                    if link["session_id"] != target or not link.get("active", True):
                        continue
                    try:
                        result.append(self.dto_material(s, actor, s["materials"][link["material_id"]]) | {"kind": link["kind"], "sort_order": link["sort_order"]})
                    except LearningError:
                        pass
                return sorted(result, key=lambda x: x["sort_order"])
            if kind == "material":
                material, _, _ = self.material(s, actor, target)
                return self.dto_material(s, actor, material)
            if kind == "versions":
                material, _, member = self.material(s, actor, target)
                return [self.dto_version(s, actor, v) for v in s["versions"].values() if v["material_id"] == material["id"] and (member["role"] == "INSTRUCTOR" or v["publication_state"] == "PUBLISHED")]
            if kind == "session_contexts":
                _, material, offering, _ = self.version(s, actor, target)
                return self.session_contexts(s, offering["id"], material["id"])
            if kind in {"version", "content", "reader_state"}:
                version, material, offering, member = self.version(s, actor, target)
                if kind == "content":
                    require(version["publication_state"] != QUARANTINED, 423, "FILE_QUARANTINED", "Tệp đang bị cách ly vì chưa vượt qua kiểm tra an toàn.")
                    require(version["processing_state"] == "READY", 409, "FILE_NOT_READY", "Tệp chưa sẵn sàng.")
                    if params.get("download"):
                        require(offering["download_allowed"], 403, "DOWNLOAD_DISABLED", "Lớp chưa bật tải bản gốc.")
                    content = copy.deepcopy(version) | {"title": material["title"], "original_sha256": version["sha256"]}
                    content['content_type'] = version.get('source_media_type', PDF_MEDIA_TYPE)
                    if not params.get('download') and content['content_type'] == PPTX_MEDIA_TYPE:
                        require(bool(version.get('view_blob_id')), 503, 'RENDITION_UNAVAILABLE', 'Bản PDF của bài trình chiếu chưa sẵn sàng.')
                    if not params.get("download") and version.get('view_blob_id'):
                        view_blob = s['blobs'].get(version['view_blob_id'])
                        require(view_blob is not None and view_blob.get('derived_from_blob_id') == version['blob_id'], 503, 'VIEW_SOURCE_MISMATCH', 'Bản xem không khớp tài liệu gốc.')
                        content.update({field: view_blob[field] for field in ('storage_key', 'sha256', 'byte_size')})
                        content['content_type'] = PDF_MEDIA_TYPE
                    return content
                if kind == "reader_state":
                    return copy.deepcopy(s["reader_states"].get(actor.subject_id + ":" + target, {"version_id": target, "page_no": 1, "offset_x": 0, "offset_y": 0, "zoom_mode": "page-width", "zoom_value": 1, "rotation": 0, "scroll_mode": "vertical", "revision": 0}))
                return self.dto_version(s, actor, version)
            if kind == "upload":
                row = s["uploads"].get(target)
                require(row is not None and row["actor_id"] == actor.subject_id)
                self.material(s, actor, row["material_id"], write=True)
                result = {k: v for k, v in row.items() if k not in {"storage_key", "sha256", "reservation_released"}}
                if upload_expired(row):
                    result["state"] = "EXPIRED"
                return result
            if kind in {"bookmarks", "notifications"}:
                result = []
                for row in s[kind].values():
                    if row["actor_id"] != actor.subject_id or row.get("status", "ACTIVE") != "ACTIVE":
                        continue
                    try:
                        if kind == "notifications":
                            self.notification_access(s, actor, row)
                        else:
                            self.version(s, actor, row["version_id"])
                    except LearningError:
                        continue
                    if params.get("version_id") and row["version_id"] != params["version_id"]:
                        continue
                    result.append(copy.deepcopy(row))
                return result
            return self.query_extension(s, actor, kind, target, params)

    def verify_preview(self, s, actor, action, target, payload, supplied):
        preview = s["previews"].get(supplied.get("preview_id"))
        require(preview is not None, 409, "CONFIRMATION_REQUIRED", "Cần xem trước và xác nhận thao tác.")
        expected = {"action": action, "target_id": target, "payload": payload}
        require(preview["actor_id"] == actor.subject_id and preview["session_id"] == actor.session_id and preview["expires_at"] > now() and not preview["consumed"], 409, "STALE_PREVIEW", "Bản xem trước đã hết hiệu lực.")
        require(preview["fingerprint"] == fingerprint(expected), 409, "STALE_PREVIEW", "Nội dung xác nhận đã thay đổi.")
        token = hmac.new(self.signing_key, preview["id"].encode() + preview["fingerprint"].encode(), hashlib.sha256).hexdigest()
        require(hmac.compare_digest(token, str(supplied.get("confirmation_token", ""))), 409, "INVALID_CONFIRMATION", "Xác nhận không hợp lệ.")
        preview["consumed"] = True

    def retraction_options(self, s, version, material, replacement_id):
        require(version["publication_state"] == "PUBLISHED", 409, "INVALID_STATE", "Chỉ có thể thu hồi phiên bản đã công bố.")
        current = material["current_published_version_id"] == version["id"]
        candidates = [
            {"id": item["id"], "version_no": item["version_no"]}
            for item in s["versions"].values()
            if current and item["id"] != version["id"] and item["material_id"] == material["id"]
            and item["publication_state"] == "PUBLISHED" and item["processing_state"] == "READY"
        ]
        require(replacement_id is None or any(item["id"] == replacement_id for item in candidates),
                409, "INVALID_REPLACEMENT", "Chỉ chọn bản đã công bố của cùng học liệu khi thu hồi bản hiện hành.")
        return {"is_current": current, "candidates": sorted(candidates, key=lambda item: item["version_no"], reverse=True)}

    async def preview(self, actor, action, target, payload):
        self.identity(actor)
        async with self.repository.transaction() as s:
            details = {}
            if action in {"publish", "retract", "cancel-publication"}:
                version, material, _, _ = self.version(s, actor, target)
                self.material(s, actor, material["id"], write=True)
                if action == "retract":
                    details["retraction"] = self.retraction_options(s, version, material, payload.get("replacement_version_id"))
                if action == "publish" and payload.get("change_set_revision") is not None:
                    changes = self.release_change_set(s, version, material, payload["change_set_revision"])
                    details["change_set"] = self.change_projection(changes, base_visible=True)
                payload = dict(payload) | {"expected_revision": material["revision"]}
            elif action in {"archive", "member-update"}:
                self.admin(actor)
            elif action == "material-update":
                self.material(s, actor, target, write=True)
            elif action == "question-update":
                details["sharing"] = self.question_scope_preview(s, actor, target, payload)
            elif action == "annotation-share":
                details["sharing"] = self.annotation_share_preview(s, actor, target, payload)
            elif action == "page-explanation-update":
                row = self.explanation_for_write(s, actor, target)
                require(payload.get("publish") and row["status"] == "DRAFT", 409, "INVALID_STATE", "Chỉ xem trước công bố bản nháp.")
                require(row["revision"] == payload["revision"], 409, "REVISION_CONFLICT", "Lời giải đã thay đổi.")
                details["page_explanation"] = self.explanation_view(row)
            elif action == "version-change-save":
                _, row = self.prepare_version_changes(s, actor, target, payload)
                details["change_set"] = self.change_projection(row, base_visible=True)
            elif action in {"exit-ticket-update", "exit-review-save"}:
                details = self.preview_exit_action(s, actor, action, target, payload)
            elif action in EXIT_TICKET_WRITES:
                raise LearningError(422, "PREVIEW_UNSUPPORTED", "Thao tác này không cần bản xem trước.")
            elif action == "idea-share-create":
                guard, details["idea_share"] = self.preview_idea_share(s, actor, target, payload)
                payload = payload | {"_idea_guard": guard}
            elif action in IDEA_WRITES:
                raise LearningError(422, "PREVIEW_UNSUPPORTED", "Thao tác này không cần bản xem trước.")
            elif action in OCR_WRITES:
                guard, details = self.preview_accessible_text(s, actor, action, target, payload)
                payload = payload | {"_ocr_guard": guard}
            else:
                self.authorize_action(s, actor, action, target)
            pid = generate_uuid7()
            value = {"action": action, "target_id": target, "payload": payload}
            record = {"id": pid, "actor_id": actor.subject_id, "session_id": actor.session_id, "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"), "fingerprint": fingerprint(value), "payload": payload, "consumed": False}
            s["previews"][pid] = record
            token = hmac.new(self.signing_key, pid.encode() + record["fingerprint"].encode(), hashlib.sha256).hexdigest()
            return {"preview_id": pid, "confirmation_token": token, "payload": {k: v for k, v in payload.items() if k not in {"_idea_guard", "_ocr_guard"}},
                    "action": action, "target_id": target, "expires_at": record["expires_at"]} | details

    async def command(self, actor, action, target, payload, *, key=None, still_valid=None):
        self.identity(actor)
        supplied = {k: payload[k] for k in ("preview_id", "confirmation_token") if k in payload}
        payload = {k: v for k, v in payload.items() if k not in supplied}
        receipt_key = actor.subject_id + ":" + action + ":" + str(key or "")
        if action == "exit-submission-save" and not supplied and hasattr(self.repository, "exit_submission_transaction"):
            transaction = self.repository.exit_submission_transaction(actor.subject_id, target, receipt_key)
        else:
            transaction = self.repository.transaction()
        async with transaction as s:
            actor = self.recheck(actor, still_valid)
            request_payload = {k: v for k, v in payload.items() if k != "_idea_source"}
            stamp = fingerprint({"target": target, "payload": request_payload})
            if key:
                require(16 <= len(key) <= 128 and key.isascii(), 422, "INVALID_IDEMPOTENCY_KEY", "Khóa thao tác không hợp lệ.")
                existing = s["receipts"].get(receipt_key)
                if existing:
                    if action in EXIT_TICKET_WRITES:
                        self.authorize_exit_action(s, actor, action, target)
                        require(existing["fingerprint"] == stamp, 409, "IDEMPOTENCY_CONFLICT", "Khóa thao tác đã dùng cho nội dung khác.")
                        return copy.deepcopy(self.replay_exit_action(s, actor, action, target, existing["result"]))
                    require(existing["fingerprint"] == stamp, 409, "IDEMPOTENCY_CONFLICT", "Khóa thao tác đã dùng cho nội dung khác.")
                    # A receipt is not an authorization grant.
                    if action == "idea-card-create":
                        return self.idea_card_receipt(s, actor, existing["result"])
                    self.authorize_action(s, actor, action, target)
                    if action == "page-explanation-create":
                        self.explanation_for_write(s, actor, existing["result"]["id"])
                    if action == "version-change-save":
                        version, material, _ = self.version_change_access(s, actor, target, write=True)
                        row = existing["result"]
                        visible = self.change_base(s, version, material, row.get("base_version_id")) is not None
                        return copy.deepcopy(self.change_projection(row, base_visible=visible))
                    if action == "idea-card-update":
                        return self.idea_card_receipt(s, actor, existing["result"])
                    if action in {"idea-share-create", "idea-share-withdraw"}:
                        share = self.idea_owned(s, "idea_shares", existing["result"]["id"], actor)
                        directory = {item["subject_id"]: item for item in self.directory_items()}
                        live = self.idea_share_owner_view(s, share, directory)
                        return {field: live[field] for field in ("id", "card_id", "status", "revision")}
                    return copy.deepcopy(existing["result"])
            self.authorize_action(s, actor, action, target)
            mandatory_preview = {"term-create", "course-create", "offering-create", "member-create", "annotation-share", "feedback-window-open"}
            internally_verified = {"publish", "retract", "cancel-publication", "archive", "member-update", "question-update", "page-explanation-update", "version-change-save", "exit-ticket-update", "exit-review-save", "idea-share-create", "ocr-release-update"}
            if action in mandatory_preview or (supplied and action not in internally_verified and not (action == "material-update" and "visibility" in payload)):
                self.verify_preview(s, actor, action, target, payload, supplied)
            result = self._command(s, actor, action, target, payload, supplied)
            if self.idea_card_offerings or self.accessible_text_offerings or s.get("idea_shares") or s.get("ocr_releases"):
                self.advance_idea_source_guard(s, action, target, payload)
            self.track_feedback_scope_change(s, action, target, result)
            audit_id = generate_uuid7()
            s["audit"][audit_id] = {"id": audit_id, "actor_id": actor.subject_id, "action": action, "target_id": target, "at": now()}
            if key:
                s["receipts"][receipt_key] = {"fingerprint": stamp, "result": copy.deepcopy(result), "created_at": now()}
            result = copy.deepcopy(result)
        if action == "publish" and result["publication_state"] == "PUBLISHED":
            record("learning.publication", count=1, mode="immediate")
        return result

    def idea_card_receipt(self, state, actor, result):
        row = self.idea_owned(state, "idea_cards", result["id"], actor)
        live = self.idea_card_view(state, actor, row)
        return copy.deepcopy(result) | {field: live[field] for field in ("source", "source_available")}

    async def replay_idea_creation(self, actor, payload, key):
        self.identity(actor)
        require(16 <= len(key) <= 128 and key.isascii(), 422, "INVALID_IDEMPOTENCY_KEY", "Khóa thao tác không hợp lệ.")
        original = {field: value for field, value in payload.items() if field not in {"preview_id", "confirmation_token"}}
        async with self.repository.transaction() as state:
            self.identity(actor)
            existing = state["receipts"].get(f"{actor.subject_id}:idea-card-create:{key}")
            if existing is None:
                return None
            require(existing["fingerprint"] == fingerprint({"target": None, "payload": original}),
                    409, "IDEMPOTENCY_CONFLICT", "Khóa thao tác đã dùng cho nội dung khác.")
            return self.idea_card_receipt(state, actor, existing["result"])

    def authorize_action(self, s, actor, action, target):
        if action in {"term-create", "course-create", "offering-create", "member-create", "member-update", "archive"}:
            self.admin(actor)
        elif action in {"session-create", "session-order"}:
            self.access(s, actor, target, write=True)
        elif action in {"session-update", "material-links"}:
            require(target in s["sessions"])
            self.access(s, actor, s["sessions"][target]["offering_id"], write=True)
        elif action in {"material-create"}:
            self.access(s, actor, target, write=True)
        elif action in {"material-update", "upload-create"}:
            self.material(s, actor, target, write=True)
        elif action in {"publish", "retract", "cancel-publication"}:
            _version, material, _, _ = self.version(s, actor, target)
            self.material(s, actor, material["id"], write=True)
        elif action == "reader-state" or action == "bookmark-create":
            self.version(s, actor, target)
        elif action in {"bookmark-update", "notification-update"}:
            row = s["bookmarks" if action == "bookmark-update" else "notifications"].get(target)
            require(row is not None and row["actor_id"] == actor.subject_id)
            if action == "notification-update":
                self.notification_access(s, actor, row)
            else:
                self.version(s, actor, row["version_id"])
        elif action in {"feedback-window-open", "page-feedback-save", "page-feedback-withdraw"}:
            self.authorize_page_feedback(s, actor, action, target)
        elif action == "page-explanation-create":
            self.explanation_session(s, actor, target, manage=True)
        elif action == "page-explanation-update":
            self.explanation_for_write(s, actor, target)
        elif action == "version-change-save":
            self.version_change_access(s, actor, target, write=True)
        elif action in EXIT_TICKET_WRITES:
            self.authorize_exit_action(s, actor, action, target)
        elif action in IDEA_WRITES:
            self.authorize_idea_action(s, actor, action, target)
        elif action in OCR_WRITES:
            self.authorize_accessible_text(s, actor, action, target)
        else:
            self.authorize_extension(s, actor, action, target)

    def _command(self, s, actor, action, target, p, supplied):
        if action in OCR_WRITES:
            return self.command_accessible_text(s, actor, action, target, p, supplied)
        if action in IDEA_WRITES:
            return self.command_idea(s, actor, action, target, p, supplied)
        if action in EXIT_TICKET_WRITES:
            return self.command_exit_ticket(s, actor, action, target, p, supplied)
        if action == "version-change-save":
            return self.save_version_changes(s, actor, target, p, supplied)
        if action in {"page-explanation-create", "page-explanation-update"}:
            return self.command_page_explanation(s, actor, action, target, p, supplied)
        if action in {"feedback-window-open", "page-feedback-save", "page-feedback-withdraw"}:
            return self.command_page_feedback(s, actor, action, target, p)
        identifier = generate_uuid7()
        base = {"id": identifier, "revision": 1, "created_at": now()}
        if action == "term-create":
            require(p["start_date"] <= p["end_date"], 422, "INVALID_DATES", "Ngày kết thúc không được trước ngày bắt đầu.")
            row = base | p
            s["terms"][identifier] = row
            return row
        if action == "course-create":
            require(not any(r["code"] == p["code"] for r in s["courses"].values()), 409, "DUPLICATE_COURSE", "Mã môn đã tồn tại.")
            row = base | p
            s["courses"][identifier] = row
            return row
        if action == "offering-create":
            require(p["term_id"] in s["terms"] and p["course_id"] in s["courses"], 422, "INVALID_CATALOG", "Học kỳ hoặc môn chưa tồn tại.")
            require(not any(all(r[k] == p[k] for k in ("term_id", "course_id", "section_code")) for r in s["offerings"].values()), 409, "DUPLICATE_OFFERING", "Lớp đã tồn tại.")
            row = base | p | {"status": "ACTIVE", "title": p.get("title") or s["courses"][p["course_id"]]["name"], "download_allowed": p.get("download_allowed", True)}
            s["offerings"][identifier] = row
            return row
        if action == "member-create":
            require(target in s["offerings"])
            candidate = next((x for x in self.directory_items() if x["subject_id"] == p["actor_subject_id"]), None)
            require(candidate is not None, 422, "UNKNOWN_ACTOR", "Tài khoản chưa có trong danh bạ được chỉ định.")
            role = "LECTURER" if p["role"] == "INSTRUCTOR" else "STUDENT"
            require(role in candidate["roles"], 422, "INVALID_ROLE", "Tài khoản chưa có vai trò phù hợp.")
            require(not any(x["offering_id"] == target and x["actor_subject_id"] == p["actor_subject_id"] for x in s["members"].values()), 409, "MEMBER_EXISTS", "Thành viên đã được ghi nhận.")
            row = base | p | {"offering_id": target, "status": "ACTIVE", "display_name": candidate["display_name"]}
            s["members"][identifier] = row
            return row
        if action in {"member-update", "archive"}:
            self.verify_preview(s, actor, action, target, p, supplied)
            row = s["members" if action == "member-update" else "offerings"].get(target)
            require(row is not None)
            require(row["revision"] == p["revision"], 409, "REVISION_CONFLICT", "Dữ liệu đã thay đổi.")
            row.update(status=p.get("status", "ARCHIVED"), revision=row["revision"] + 1)
            return row
        if action == "session-create":
            sequence = p.get("sequence_no") or 1 + max((r["sequence_no"] for r in s["sessions"].values() if r["offering_id"] == target), default=0)
            require(not any(r["offering_id"] == target and r["sequence_no"] == sequence for r in s["sessions"].values()), 409, "DUPLICATE_SESSION", "Thứ tự buổi đã tồn tại.")
            row = base | {"offering_id": target, "title": p["title"], "description": p.get("description", ""), "starts_at": p.get("starts_at"), "sequence_no": sequence}
            s["sessions"][identifier] = row
            return row
        if action == "session-update":
            row = s["sessions"][target]
            require(row["revision"] == p.pop("revision"), 409, "REVISION_CONFLICT", "Buổi học đã thay đổi.")
            row.update(p, revision=row["revision"] + 1)
            return row
        if action == "session-order":
            rows = [r for r in s["sessions"].values() if r["offering_id"] == target]
            ids = p["session_ids"]
            require(len(ids) == len(set(ids)) == len(rows) and set(ids) == {r["id"] for r in rows}, 409, "INVALID_ORDER", "Danh sách buổi đã thay đổi.")
            for index, sid in enumerate(ids, 1):
                s["sessions"][sid].update(sequence_no=index, revision=s["sessions"][sid]["revision"] + 1)
            return {"saved": True}
        if action == "material-create":
            row = base | {"offering_id": target, "title": p["title"], "description": p.get("description", ""), "visibility": "VISIBLE", "current_published_version_id": None}
            s["materials"][identifier] = row
            if p.get("session_id"):
                session = s["sessions"].get(p["session_id"])
                require(session is not None and session["offering_id"] == target, 422, "INVALID_SESSION", "Buổi học không thuộc lớp.")
                self.link(s, p["session_id"], identifier)
            return row
        if action == "material-update":
            row = s["materials"][target]
            require(row["revision"] == p.get("revision"), 409, "REVISION_CONFLICT", "Học liệu đã thay đổi.")
            if "visibility" in p:
                self.verify_preview(s, actor, action, target, p, supplied)
            row.update({k: v for k, v in p.items() if k != "revision"}, revision=row["revision"] + 1)
            return row
        if action == "material-links":
            session = s["sessions"][target]
            ids = p["material_ids"]
            require(len(ids) == len(set(ids)), 422, "DUPLICATE_LINK", "Danh sách tài liệu bị trùng.")
            for mid in ids:
                require(mid in s["materials"] and s["materials"][mid]["offering_id"] == session["offering_id"], 422, "CROSS_CLASS_LINK", "Tài liệu không thuộc lớp.")
            # Preserve prior links as inactive, never remove records.
            for link in s["links"].values():
                if link["session_id"] == target:
                    link["active"] = False
            for index, mid in enumerate(ids):
                self.link(s, target, mid, index)
            return {"saved": True}
        if action == "upload-create":
            source_type = p.get('content_type', PDF_MEDIA_TYPE)
            extension = '.pptx' if source_type == PPTX_MEDIA_TYPE else '.pdf'
            require(source_type in {PDF_MEDIA_TYPE, PPTX_MEDIA_TYPE} and p['filename'].lower().endswith(extension),
                415, 'UNSUPPORTED_MEDIA_TYPE', 'Định dạng hoặc phần mở rộng tệp không hợp lệ.')
            require(source_type != PPTX_MEDIA_TYPE or self.pptx_available, 503, 'PPTX_CONVERTER_UNAVAILABLE', 'Chuyển đổi PowerPoint chưa được cấu hình an toàn.')
            require(0 < p["byte_size"] <= self.blobs.max_bytes, 413, "PAYLOAD_TOO_LARGE", "Dung lượng PDF không hợp lệ.")
            offering = s["materials"][target]["offering_id"]
            instant = datetime.now(UTC)
            for upload in s["uploads"].values():
                if upload_expired(upload, instant):
                    expire_upload(upload)
            view_bytes = sum(s["blobs"][v["view_blob_id"]]["byte_size"] for v in s["versions"].values()
                if v["offering_id"] == offering and v.get("view_blob_id"))
            require(reserved_upload_bytes(s["uploads"], offering) + view_bytes + p["byte_size"] <= 2 * 1024**3, 413, "QUOTA_EXCEEDED", "Lớp đã đạt giới hạn lưu trữ.")
            active = [u for u in s["uploads"].values() if u["actor_id"] == actor.subject_id and u["state"] in INCOMPLETE_UPLOAD_STATES and not u.get("version_id")]
            require(len(active) < 2, 429, "UPLOAD_LIMIT", "Có quá nhiều lượt tải chưa hoàn tất.")
            row = base | p | {"offering_id": offering, "material_id": target, "actor_id": actor.subject_id, "state": "CREATED", "expires_at": (datetime.now(UTC) + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"), "content_path": f"/v1/learning/upload-intents/{identifier}/content"}
            s["uploads"][identifier] = row
            return row
        if action in {"publish", "retract", "cancel-publication"}:
            version, material, offering, _ = self.version(s, actor, target)
            preview = s["previews"].get(supplied.get("preview_id"))
            require(preview is not None, 409, "CONFIRMATION_REQUIRED", "Cần xem trước thao tác.")
            expected = preview["payload"]
            require(material["revision"] == expected.get("expected_revision"), 409, "STALE_PREVIEW", "Học liệu đã thay đổi; hãy xem trước lại.")
            require(p.get("scheduled_at") == expected.get("scheduled_at"), 409, "STALE_PREVIEW", "Thời điểm công bố đã thay đổi.")
            replacement = p.get("replacement_version_id")
            require(replacement == expected.get("replacement_version_id"), 409, "STALE_PREVIEW", "Bản thay thế đã thay đổi. Hãy xem trước lại.")
            change_revision = p.get("change_set_revision")
            require(change_revision == expected.get("change_set_revision"), 409, "STALE_PREVIEW", "Mô tả thay đổi đã thay đổi.")
            self.verify_preview(s, actor, action, target, expected, supplied)
            if action == "publish":
                require(version["processing_state"] == "READY", 409, "FILE_NOT_READY", "Tài liệu chưa vượt qua kiểm tra.")
                require(version["publication_state"] != "PUBLISHED", 409, "INVALID_STATE", "Phiên bản này đã được công bố.")
                require(version["publication_state"] != QUARANTINED, 409, "FILE_QUARANTINED", "Tệp đang bị cách ly nên không thể công bố. Hãy tải bản mới.")
                require(self.scan_is_current(version), 503, "SCAN_NOT_CURRENT", "Đang cập nhật kiểm tra an toàn cho tệp; hãy thử lại sau ít phút.")
                if change_revision is not None:
                    self.release_change_set(s, version, material, change_revision)
                if p.get("scheduled_at"):
                    require(p["scheduled_at"] > now(), 422, "INVALID_SCHEDULE", "Thời điểm công bố phải ở tương lai.")
                    version.pop("schedule_error", None)
                    version.update(publication_state="SCHEDULED", scheduled_at=p["scheduled_at"], scheduled_by=actor.subject_id)
                    if change_revision is not None:
                        version.update(scheduled_change_set_revision=change_revision,
                                       scheduled_change_current=material["current_published_version_id"])
                    else:
                        version.pop("scheduled_change_set_revision", None)
                        version.pop("scheduled_change_current", None)
                else:
                    if change_revision is not None:
                        version["change_set_revision"] = change_revision
                    self.publish(s, version, material)
            elif action == "cancel-publication":
                require(version["publication_state"] == "SCHEDULED", 409, "INVALID_STATE", "Phiên bản chưa hẹn công bố.")
                version.update(publication_state="DRAFT", scheduled_at=None)
                version.pop("scheduled_change_set_revision", None)
                version.pop("scheduled_change_current", None)
            else:
                options = self.retraction_options(s, version, material, replacement)
                version.update(publication_state="RETRACTED", revision=version["revision"] + 1)
                if options["is_current"]:
                    material["current_published_version_id"] = replacement
                for presentation in s["presentations"].values():
                    if presentation["version_id"] == target and presentation["status"] == "ACTIVE":
                        presentation.update(status="ENDED", updated_at=now(),
                                            sequence=presentation["sequence"] + 1, revision=presentation["revision"] + 1)
            material["revision"] += 1
            return self.dto_version(s, actor, version)
        if action == "reader-state":
            version, _, _, _ = self.version(s, actor, target)
            require(1 <= p["page_no"] <= version.get("page_count", 0), 422, "INVALID_PAGE", "Trang không hợp lệ.")
            record_key = actor.subject_id + ":" + target
            existing = s["reader_states"].get(record_key, {"revision": 0})
            require(p.get("revision", 0) == existing["revision"], 409, "REVISION_CONFLICT", "Vị trí đã thay đổi trên thiết bị khác.")
            row = dict(p) | {"version_id": target, "revision": existing["revision"] + 1, "updated_at": now()}
            s["reader_states"][record_key] = row
            return row
        if action == "bookmark-create":
            version, _, _, _ = self.version(s, actor, p["version_id"])
            require(1 <= p["page_no"] <= version.get("page_count", 0), 422, "INVALID_PAGE", "Trang không hợp lệ.")
            row = base | p | {"actor_id": actor.subject_id, "status": "ACTIVE"}
            s["bookmarks"][identifier] = row
            return row
        if action in {"bookmark-update", "notification-update"}:
            row = s["bookmarks" if action == "bookmark-update" else "notifications"].get(target)
            require(row is not None and row["actor_id"] == actor.subject_id)
            self.version(s, actor, row["version_id"])
            require(p.get("revision", row["revision"]) == row["revision"], 409, "REVISION_CONFLICT", "Dữ liệu đã thay đổi.")
            row.update(p, revision=row["revision"] + 1)
            return row
        return self.command_extension(s, actor, action, target, p, supplied)

    @staticmethod
    def session_contexts(s, offering_id, material_id):
        linked_ids = {
            link["session_id"]
            for link in s["links"].values()
            if link["material_id"] == material_id and link["offering_id"] == offering_id and link.get("active", True)
        }
        contexts = [
            {key: session[key] for key in ("id", "offering_id", "title", "sequence_no")}
            for session in s["sessions"].values()
            if session["id"] in linked_ids and session["offering_id"] == offering_id
        ]
        return sorted(contexts, key=lambda row: (row["sequence_no"], row["id"]))

    def link(self, s, session_id, material_id, order=None):
        key = session_id + ":" + material_id
        if order is None:
            order = sum(1 for r in s["links"].values() if r["session_id"] == session_id and r.get("active", True))
        s["links"][key] = {"session_id": session_id, "material_id": material_id, "offering_id": s["sessions"][session_id]["offering_id"], "sort_order": order, "kind": "PRIMARY" if order == 0 else "SUPPLEMENT", "active": True}

    def publish(self, s, version, material):
        version.pop("schedule_error", None)
        version.update(publication_state="PUBLISHED", published_at=now(), scheduled_at=None, revision=version["revision"] + 1)
        material["current_published_version_id"] = version["id"]
        event_id = generate_uuid7()
        s.setdefault("outbox", {})[event_id] = {"id": event_id, "event_type": "MATERIAL_PUBLISHED", "version_id": version["id"], "material_id": material["id"], "revision": version["revision"], "created_at": now(), "delivered_at": now()}
        for member in s["members"].values():
            if member["offering_id"] == material["offering_id"] and member["status"] == "ACTIVE":
                key = generate_uuid7()
                first_link = next((r for r in s["links"].values() if r["material_id"] == material["id"] and r.get("active", True)), None)
                s["notifications"][key] = {"id": key, "event_id": event_id, "actor_id": member["actor_subject_id"], "offering_id": material["offering_id"], "session_id": first_link["session_id"] if first_link else None, "version_id": version["id"], "material_id": material["id"], "title": material["title"], "read_at": None, "created_at": now(), "revision": 1}

    async def receive(self, actor, upload_id, chunks):
        self.identity(actor)
        async with self.repository.transaction() as s:
            upload = s["uploads"].get(upload_id)
            require(upload is not None and upload["actor_id"] == actor.subject_id)
            self.material(s, actor, upload["material_id"], write=True)
            require(upload["state"] != "EXPIRED" and not upload_expired(upload), 409, "UPLOAD_EXPIRED", "Lượt tải đã hết hạn. Hãy tạo lượt tải mới.")
            require(upload["state"] == "CREATED", 409, "UPLOAD_NOT_WRITABLE", "Lượt tải không còn nhận dữ liệu.")
            upload["state"] = "RECEIVING"
            expected = upload["byte_size"]
            content_type = upload.get('content_type', PDF_MEDIA_TYPE)
            deadline = datetime.fromisoformat(upload["expires_at"])
        try:
            async with asyncio.timeout(max(0, (deadline - datetime.now(UTC)).total_seconds())):
                blob = await self.blobs.receive(chunks, expected_size=expected, content_type=content_type)
        except BaseException as error:
            async with self.repository.transaction() as s:
                upload = s["uploads"][upload_id]
                if upload["state"] == "RECEIVING":
                    if isinstance(error, TimeoutError) or upload_expired(upload):
                        expire_upload(upload)
                    else:
                        upload["state"] = "ABORTED"
            if isinstance(error, TimeoutError):
                raise LearningError(409, "UPLOAD_EXPIRED", "Lượt tải đã hết hạn. Hãy tạo lượt tải mới.") from error
            raise
        async with self.repository.transaction() as s:
            upload = s["uploads"][upload_id]
            self.material(s, actor, upload["material_id"], write=True)
            aborted = upload["state"] == "ABORTED"
            expired = upload["state"] == "EXPIRED" or upload_expired(upload)
            blob_id = generate_uuid7()
            s.setdefault("blobs", {})[blob_id] = {"id": blob_id, **blob}
            upload.update(blob, blob_id=blob_id)
            if not aborted:
                upload["state"] = "EXPIRED" if expired else "RECEIVED"
        require(not aborted, 409, "UPLOAD_NOT_WRITABLE", "Lượt tải đã được hủy.")
        require(not expired, 409, "UPLOAD_EXPIRED", "Lượt tải đã hết hạn. Hãy tạo lượt tải mới.")
        return {"id": upload_id, "state": "RECEIVED", "byte_size": blob["byte_size"]}

    async def complete(self, actor, upload_id, key=None, still_valid=None):
        self.identity(actor)
        async with self.repository.transaction() as s:
            actor = self.recheck(actor, still_valid)
            upload = s["uploads"].get(upload_id)
            require(upload is not None and upload["actor_id"] == actor.subject_id)
            material, _, _ = self.material(s, actor, upload["material_id"], write=True)
            receipt_key = None
            stamp = fingerprint({"target": upload_id})
            if key:
                require(16 <= len(key) <= 128 and key.isascii(), 422, "INVALID_IDEMPOTENCY_KEY", "Khóa thao tác không hợp lệ.")
                receipt_key = actor.subject_id + ":upload-complete:" + key
                existing = s["receipts"].get(receipt_key)
                require(existing is None or existing["fingerprint"] == stamp, 409, "IDEMPOTENCY_CONFLICT", "Khóa thao tác đã dùng cho lượt tải khác.")
            require(upload["state"] != "EXPIRED" and not upload_expired(upload), 409, "UPLOAD_EXPIRED", "Lượt tải đã hết hạn. Hãy tạo lượt tải mới.")
            require(upload["state"] == "RECEIVED", 409, "UPLOAD_INCOMPLETE", "Tệp chưa nhận đầy đủ.")
            vid = upload.get("version_id")
            if not vid:
                vid = generate_uuid7()
                row = {"id": vid, "material_id": material["id"], "offering_id": material["offering_id"], "version_no": 1 + max((v["version_no"] for v in s["versions"].values() if v["material_id"] == material["id"]), default=0), "processing_state": "QUEUED", "publication_state": "DRAFT", "storage_key": upload["storage_key"], "sha256": upload["sha256"], "byte_size": upload["byte_size"], "page_count": 0, "has_text_layer": False, "revision": 1, "uploaded_by": actor.subject_id}
                s["versions"][vid] = row
                row["blob_id"] = upload["blob_id"]
                row['source_media_type'] = upload.get('content_type', PDF_MEDIA_TYPE)
                row['rendition_id'] = upload['blob_id'] if row['source_media_type'] == PDF_MEDIA_TYPE else None
                upload["version_id"] = vid
                s["jobs"][vid] = {"id": vid, "state": "QUEUED", "attempt": 0}
            if receipt_key and receipt_key not in s["receipts"]:
                s["receipts"][receipt_key] = {"fingerprint": stamp, "result": {"version_id": vid}, "created_at": now()}
        return await self.query(actor, "version", vid)

    async def process_version(self, version_id):
        async with self.repository.transaction() as s:
            version, job = s["versions"][version_id], s["jobs"][version_id]
            if version["processing_state"] == "READY":
                return
            if job["state"] == "PROCESSING" and job.get("lease_until", "") > now():
                return
            require(job["attempt"] < 3, 409, "RETRY_LIMIT", "Tệp đã hết số lần thử tự động.")
            job.update(state="PROCESSING", attempt=job["attempt"] + 1, lease_until=(datetime.now(UTC) + timedelta(minutes=3)).isoformat().replace("+00:00", "Z"))
            attempt = job["attempt"]
            version["processing_state"] = "SCANNING"
            storage_key = version["storage_key"]
            source_type, source_sha256 = version.get('source_media_type', PDF_MEDIA_TYPE), version['sha256']
            if source_type == PPTX_MEDIA_TYPE:
                version['processing_state'] = 'CONVERTING'
        started = time.perf_counter()
        format_name = "pptx" if source_type == PPTX_MEDIA_TYPE else "pdf"
        try:
            info, view_info = await self._inspect_version(storage_key, source_type, source_sha256)
        except (LearningError, TimeoutError) as failure:
            error = failure if isinstance(failure, LearningError) else LearningError(503, "PROCESSING_TIMEOUT", "Quá thời gian xử lý bài giảng.")
            async with self.repository.transaction() as s:
                if s["jobs"][version_id]["attempt"] != attempt:
                    return
                s["versions"][version_id].update(processing_state="REJECTED" if error.status == 422 else "FAILED", error_code=error.code, error_detail=error.detail)
                s["jobs"][version_id].update(state="REJECTED" if error.status == 422 else "FAILED", error_code=error.code)
            record("learning.upload_job", duration_ms=round((time.perf_counter() - started) * 1000),
                result="rejected" if error.status == 422 else "failed", code=error.code, file_type=format_name, attempt=attempt)
            return
        async with self.repository.transaction() as s:
            if s["jobs"][version_id]["attempt"] != attempt:
                return
            version = s['versions'][version_id]
            if view_info.get('optimized'):
                reserved = reserved_upload_bytes(s["uploads"], version["offering_id"])
                derived = sum(s['blobs'][row['view_blob_id']]['byte_size'] for row in s['versions'].values()
                    if row['offering_id'] == version['offering_id'] and row.get('view_blob_id'))
                if reserved + derived + view_info['byte_size'] > 2 * 1024**3:
                    s['jobs'][version_id]['retained_view_artifact'] = view_info['storage_key']
                    if source_type == PPTX_MEDIA_TYPE:
                        version.update(processing_state='FAILED', error_code='CLASS_STORAGE_QUOTA', error_detail='Không đủ dung lượng giữ bản PDF chuyển đổi.')
                        s['jobs'][version_id].update(state='REJECTED', error_code='CLASS_STORAGE_QUOTA')
                        record("learning.upload_job", duration_ms=round((time.perf_counter() - started) * 1000),
                            result="rejected", code="CLASS_STORAGE_QUOTA", file_type=format_name, attempt=attempt)
                        return
                    view_info = {'optimized': False, 'reason': 'CLASS_STORAGE_QUOTA'}
            if view_info.get('optimized'):
                view_id = generate_uuid7()
                s['blobs'][view_id] = {'id': view_id, **{key: view_info[key] for key in ('storage_key', 'sha256', 'byte_size')},
                    'derived_from_blob_id': version['blob_id'], 'created_at': now()}
                version['view_blob_id'] = view_id
                version['rendition_id'] = view_info.get('rendition_id', view_id)
                version['web_optimized'] = source_type == PDF_MEDIA_TYPE
            else:
                version['web_optimized'] = False
                version['view_reason'] = view_info.get('reason', 'UNAVAILABLE')
            s["versions"][version_id].update(info, processing_state="READY")
            s["jobs"][version_id]["state"] = "DONE"
        record("learning.upload_job", duration_ms=round((time.perf_counter() - started) * 1000),
            result="ready", file_type=format_name, attempt=attempt)

    @staticmethod
    def scan_evidence(receipts):
        """Receipts of the scans that cleared this version (none for scanners that return no receipt)."""
        rows = [receipt.as_dict() if hasattr(receipt, "as_dict") else dict(receipt) for receipt in receipts if receipt]
        return {"scan_receipts": rows} if rows else {}

    async def _inspect_version(self, storage_key, source_type=PDF_MEDIA_TYPE, source_sha256=None):
        async with asyncio.timeout(PROCESSING_TIMEOUT_SECONDS):
            if source_sha256:
                await self.blobs.verify(storage_key, source_sha256, self.blobs.path(storage_key).stat().st_size)
            receipts = [await self.scanner.scan(self.blobs.path(storage_key))]
            if source_type == PPTX_MEDIA_TYPE:
                require(self.pptx_available, 503, 'PPTX_CONVERTER_UNAVAILABLE', 'Chuyển đổi PowerPoint chưa được cấu hình an toàn.')
                try:
                    rendition = await self.pptx_converter.convert(self.blobs.path(storage_key), source_sha256)
                except ValueError as failure:
                    code = str(failure)
                    if not re.fullmatch(r'PPTX_[A-Z0-9_]{1,60}', code):
                        code = 'PPTX_CONVERSION_FAILED'
                    unavailable = {'PPTX_CONVERSION_TIMEOUT', 'PPTX_CONVERTER_UNAVAILABLE', 'PPTX_SANDBOX_UNAVAILABLE', 'PPTX_SANDBOX_CANCEL_UNVERIFIED', 'PPTX_SANDBOX_BINARY_CHANGED'}
                    raise LearningError(503 if code in unavailable else 422,
                        code, 'Chưa chuyển đổi được PowerPoint thành bản PDF được kiểm tra.') from None
                require(rendition.source_sha256 == source_sha256, 503, 'RENDITION_SOURCE_MISMATCH', 'Bản xem không khớp PowerPoint gốc.')
                await self.blobs.verify(storage_key, source_sha256, self.blobs.path(storage_key).stat().st_size)
                try:
                    rendition_id = str(UUID(rendition.rendition_id))
                except (ValueError, TypeError, AttributeError):
                    raise LearningError(503, 'RENDITION_ID_INVALID', 'Chưa xác minh được mã bản xem.') from None
                blob = await self.blobs.import_pdf(Path(rendition.pdf_path), expected_sha256=rendition.pdf_sha256, expected_size=rendition.pdf_bytes)
                receipts.append(await self.scanner.scan(self.blobs.path(blob['storage_key'])))
                info = await self.blobs.inspect(blob['storage_key'])
                require(info['page_count'] == rendition.slide_count, 422, 'PPTX_SLIDE_COUNT_MISMATCH', 'Số trang bản xem không khớp số slide nguồn.')
                info.update(converter_version=rendition.converter_version, converter_sha256=rendition.converter_sha256,
                            **self.scan_evidence(receipts))
                return info, blob | {'optimized': True, 'rendition_id': rendition_id}
            info = await self.blobs.inspect(storage_key)
            view_info = await self.blobs.web_view(storage_key) if self.optimize_pdf else {'optimized': False, 'reason': 'NOT_CONFIGURED'}
            if view_info.get('optimized'):
                receipts.append(await self.scanner.scan(self.blobs.path(view_info['storage_key'])))
                await self.blobs.verify(view_info['storage_key'], view_info['sha256'], view_info['byte_size'])
            info.update(self.scan_evidence(receipts))
            return info, view_info

    async def abort(self, actor, upload_id, still_valid=None):
        self.identity(actor)
        async with self.repository.transaction() as s:
            actor = self.recheck(actor, still_valid)
            upload = s["uploads"].get(upload_id)
            require(upload is not None and upload["actor_id"] == actor.subject_id)
            self.material(s, actor, upload["material_id"], write=True)
            require(not upload.get("version_id"), 409, "VERSION_EXISTS", "Tệp đã tạo phiên bản.")
            if upload_expired(upload):
                expire_upload(upload)
            elif upload["state"] != "EXPIRED":
                if upload["state"] == "CREATED":
                    upload["reservation_released"] = True
                upload["state"] = "ABORTED"
            return {"id": upload_id, "state": upload["state"]}

    async def serve_accessible_text(self):
        """Process OCR independently of document intake and scheduled publication."""
        while True:
            try:
                await self.tick_accessible_text()
            except asyncio.CancelledError:
                raise
            except (LearningError, OSError, sqlite3.Error) as error:
                record("learning.ocr_worker_error", error_type=type(error).__name__)
            await asyncio.sleep(2)

    async def tick(self):
        """Explicit caller-owned scheduler; no identities or authority are minted."""
        async with self.repository.transaction() as s:
            instant = datetime.now(UTC)
            self.finalize_feedback_windows(s, feedback_clock())
            for upload in s["uploads"].values():
                if upload_expired(upload, instant):
                    expire_upload(upload)
            pending = [job["id"] for job in s["jobs"].values() if (job["state"] in {"QUEUED", "FAILED"} or (job["state"] == "PROCESSING" and job.get("lease_until", "") <= now())) and job["attempt"] < 3]
        for version_id in pending[:2]:
            await self.process_version(version_id)
        published = 0
        async with self.repository.transaction() as s:
            directory = self.directory_items()
            for version in s["versions"].values():
                if version["publication_state"] != "SCHEDULED" or version.get("scheduled_at", "z") > now():
                    continue
                material = s["materials"][version["material_id"]]
                offering = s["offerings"][material["offering_id"]]
                member = next((r for r in s["members"].values() if r["offering_id"] == offering["id"] and r["actor_subject_id"] == version["scheduled_by"] and r["role"] == "INSTRUCTOR" and r["status"] == "ACTIVE"), None)
                candidate = next((r for r in directory if r["subject_id"] == version["scheduled_by"] and "LECTURER" in r["roles"]), None)
                if member is None or candidate is None or offering["status"] != "ACTIVE" or material["visibility"] != "VISIBLE":
                    version.update(publication_state="DRAFT", schedule_error="AUTHORITY_UNAVAILABLE", scheduled_at=None)
                    continue
                if version["processing_state"] == "READY" and not self.scan_is_current(version):
                    continue  # the daily re-scan refreshes it; publishing on a days-old verdict is not allowed
                if version["processing_state"] == "READY":
                    change_revision = version.pop("scheduled_change_set_revision", None)
                    pinned_current = version.pop("scheduled_change_current", None)
                    if change_revision is not None:
                        try:
                            require(pinned_current == material["current_published_version_id"], 409, "CHANGE_SET_STALE")
                            self.release_change_set(s, version, material, change_revision)
                        except LearningError:
                            version.update(publication_state="DRAFT", schedule_error="CHANGE_SET_STALE", scheduled_at=None)
                            continue
                        version["change_set_revision"] = change_revision
                    self.publish(s, version, material)
                    material["revision"] += 1
                    self.track_feedback_scope_change(s, "publish", version["id"], version)
                    published += 1
        if published:
            record("learning.publication", count=published, mode="scheduled")
        outcome = await self.rescan_due()
        if outcome["scanned"] or outcome["quarantined"]:
            record("learning.rescan", **outcome)
