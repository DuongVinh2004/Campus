"""Source snapshots, independently reviewed renditions and atomic publication."""
from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime

from campus247.application.document_request.certificates import (
    CertificateError,
    preview_entity,
    serial,
)
from campus247.domain.action.preview import create_action_preview
from campus247.domain.shared.values import generate_uuid7
from campus247.ports.identity import IdentityRole


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def now():
    return datetime.now(UTC).isoformat()


class KnowledgeOperations:
    def __init__(self, repository, authorization, tokens):
        self.repository, self.authorization, self.tokens = repository, authorization, tokens

    def admin(self, actor):
        self.authorization(actor, IdentityRole.KNOWLEDGE_ADMIN)

    def event(self, tx, actor, action, target, note, **details):
        tx.operation_audit({"id": generate_uuid7(), "actor": actor.subject_id, "action": action,
            "target": target, "note": note, "occurred_at": now(), **details})

    def source(self, actor, source_id):
        self.admin(actor)
        with self.repository.transaction() as tx:
            return self._source(tx, source_id)

    def _source(self, tx, source_id):
        value = tx.item("source", source_id)
        if not value:
            raise CertificateError(404, "SOURCE_NOT_FOUND", "Không tìm thấy nguồn")
        raw = base64.b64decode(value["original_base64"], validate=True)
        if digest(raw) != value["original_sha256"]:
            raise CertificateError(409, "SOURCE_HASH_MISMATCH", "Nguồn không khớp checksum; dừng sử dụng")
        return value

    def upload(self, actor, body):
        self.admin(actor)
        value = {"id": generate_uuid7(), **body.model_dump(mode="json"), "created_by": actor.subject_id,
            "created_at": now(), "is_simulation": True, "faculty": "FIT"}
        raw = value.pop("content").encode("utf-8")
        value.update(original_base64=base64.b64encode(raw).decode(), original_sha256=digest(raw), media_type="text/plain")
        with self.repository.transaction() as tx:
            tx.insert("source", value)
            self.event(tx, actor, "source.snapshot", value["id"], "Immutable UTF-8 demo source", checksum=value["original_sha256"])
        return value

    def create_version(self, actor, body):
        self.admin(actor)
        with self.repository.transaction() as tx:
            source = self._source(tx, body.source_id)
            value = {"id": generate_uuid7(), **body.model_dump(mode="json"), "source_sha256": source["original_sha256"],
                "rendition_sha256": digest(body.text.encode()), "created_by": actor.subject_id, "created_at": now(),
                "revision": 1, "state": "DRAFT", "reviews": [], "build": None, "published_at": None,
                "is_simulation": True, "campus": source["campus"], "audience": source["audience"]}
            tx.insert("knowledge_version", value)
            self.event(tx, actor, "version.created", value["id"], body.mapping, revision=1)
            return value

    def _version(self, tx, identifier, expected=None):
        value = tx.item("knowledge_version", identifier)
        if not value:
            raise CertificateError(404, "VERSION_NOT_FOUND", "Không tìm thấy phiên bản")
        if expected is not None and expected != value["revision"]:
            raise CertificateError(409, "STALE_VERSION", "Phiên bản tri thức đã thay đổi; tải lại")
        source = self._source(tx, value["source_id"])
        if source["original_sha256"] != value["source_sha256"] or digest(value["text"].encode()) != value["rendition_sha256"]:
            raise CertificateError(409, "RENDITION_HASH_MISMATCH", "Không thể xác minh rendition")
        return value

    def _editable(self, value):
        if value["state"] not in {"DRAFT", "REVIEWED", "BUILD_FAILED", "BUILT"}:
            raise CertificateError(409, "IMMUTABLE_PUBLICATION", "Tạo rendition/phiên bản mới để sửa nguồn đã xuất bản")

    def review(self, actor, identifier, expected, verdict, note):
        self.admin(actor)
        if verdict not in {"approved", "rejected"} or not note.strip():
            raise CertificateError(422, "REVIEW_REQUIRED", "Cần kết luận và ghi chú đối chiếu original/rendition/mapping")
        with self.repository.transaction() as tx:
            value = self._version(tx, identifier, expected)
            self._editable(value)
            if value["created_by"] == actor.subject_id:
                raise CertificateError(403, "SEPARATION_OF_DUTIES", "Tác giả không được tự review")
            value["revision"] += 1
            value["reviews"].append({"reviewer": actor.subject_id, "verdict": verdict, "note": note,
                "rendition_sha256": value["rendition_sha256"], "source_sha256": value["source_sha256"], "at": now()})
            value["state"], value["build"] = ("REVIEWED" if verdict == "approved" else "DRAFT"), None
            tx.update("knowledge_version", value)
            self.event(tx, actor, "version.reviewed", identifier, note, verdict=verdict, revision=value["revision"])
            return value

    def build(self, actor, identifier, expected):
        self.admin(actor)
        with self.repository.transaction() as tx:
            value = self._version(tx, identifier, expected)
            self._editable(value)
            if not value["reviews"] or value["reviews"][-1]["verdict"] != "approved":
                raise CertificateError(409, "REVIEW_REQUIRED", "Rendition phải được admin khác review trước build")
            # Local lexical candidate only. Generated contextual text never becomes evidence.
            error = None
            original = base64.b64decode(self._source(tx, value["source_id"])["original_base64"]).decode()
            if value["mapping"] == "ORIGINAL_TEXT" and value["text"] != original:
                error = "ORIGINAL_MAPPING_MISMATCH"
            elif value["mapping"] != "ORIGINAL_TEXT" and not value["mapping"].startswith("REVIEWED_RENDITION:"):
                error = "MAPPING_UNVERIFIED"
            elif len(value["text"].strip()) < 30:
                error = "INSUFFICIENT_SOURCE_TEXT"
            manifest = {"id": generate_uuid7(), "version_id": identifier, "source_sha256": value["source_sha256"],
                "rendition_sha256": value["rendition_sha256"], "compatibility": "demo-lexical-v1",
                "evidence_text": value["text"], "candidate_text": value["candidate_text"],
                "terms": sorted(set(value["text"].lower().split())), "error": error, "created_at": now(),
                "graph_hook": "stage5 published graph remains separate; this candidate is not a graph publication"}
            manifest["checksum"] = digest(manifest)
            tx.insert("knowledge_build", manifest)
            value["build"], value["state"] = manifest, "BUILD_FAILED" if error else "BUILT"
            value["revision"] += 1
            tx.update("knowledge_version", value)
            self.event(tx, actor, "version.built", identifier, error or "Eligible local lexical candidate", revision=value["revision"])
            return value

    def _active(self, tx, procedure):
        return tx.item("knowledge_active", procedure) or {"id": procedure, "version_id": None, "generation": 0}

    def current(self, tx, procedure):
        pointer = self._active(tx, procedure)
        if not pointer["version_id"]:
            raise CertificateError(422, "MISSING_SOURCE", "Chưa có nguồn hướng dẫn đang hiệu lực; cần cán bộ hỗ trợ")
        value = self._version(tx, pointer["version_id"])
        at = datetime.now(UTC)
        if (value["state"] != "PUBLISHED" or datetime.fromisoformat(value["effective_from"]) > at
                or value["effective_until"] and at >= datetime.fromisoformat(value["effective_until"])):
            raise CertificateError(422, "SOURCE_NOT_CURRENT", "Nguồn không còn hiệu lực; không suy ra điều kiện nghiệp vụ")
        return {"version_id": value["id"], "source_id": value["source_id"], "source_sha256": value["source_sha256"],
            "rendition_sha256": value["rendition_sha256"], "generation": pointer["generation"],
            "text": value["text"], "locator": self._source(tx, value["source_id"])["locator"], "is_simulation": True}

    def preview(self, actor, identifier, expected, operation="publish"):
        self.admin(actor)
        with self.repository.transaction() as tx:
            value = self._version(tx, identifier, expected)
            self._check_publication(actor, value, operation)
            pointer = self._active(tx, value["procedure"])
            payload = {"version_id": identifier, "revision": expected, "operation": operation,
                "source_sha256": value["source_sha256"], "rendition_sha256": value["rendition_sha256"],
                "build_checksum": value["build"]["checksum"], "active": pointer}
            p = create_action_preview(actor.subject_id, "KNOWLEDGE_" + operation.upper(), payload, session_id=actor.session_id)
            tx.insert("knowledge_preview", {"id": p.id, "preview": serial(asdict(p))})
            return {"preview_id": p.id, "confirmation_token": self.tokens.mint_token(p), "expires_at": p.expires_at.isoformat(), "payload": payload}

    def _check_publication(self, actor, value, operation):
        if value["created_by"] == actor.subject_id:
            raise CertificateError(403, "SEPARATION_OF_DUTIES", "Tác giả không được tự xuất bản/thu hồi")
        if operation not in {"publish", "withdraw"}:
            raise CertificateError(422, "UNKNOWN_ACTION", "Thao tác tri thức không hợp lệ")
        if operation == "publish" and (value["state"] != "BUILT" or not value["build"] or value["build"]["error"]):
            raise CertificateError(409, "BUILD_REQUIRED", "Build chưa thành công; active pointer giữ nguyên")
        if operation == "withdraw" and value["state"] != "PUBLISHED":
            raise CertificateError(409, "INVALID_STATE", "Chỉ nguồn đã xuất bản được thu hồi")
        if not value["reviews"] or value["reviews"][-1]["verdict"] != "approved":
            raise CertificateError(409, "REVIEW_REQUIRED", "Chưa có review hợp lệ")
        manifest = dict(value["build"])
        checksum = manifest.pop("checksum")
        if digest(manifest) != checksum or manifest["compatibility"] != "demo-lexical-v1":
            raise CertificateError(409, "BUILD_HASH_MISMATCH", "Build không khớp checksum/compatibility")

    def publish(self, actor, identifier, preview_id, token, key, confirmed):
        self.admin(actor)
        if not confirmed:
            raise CertificateError(422, "CONFIRMATION_REQUIRED", "Cần xác nhận rõ ràng")
        with self.repository.transaction() as tx:
            raw = tx.item("knowledge_preview", preview_id)
            if not raw:
                raise CertificateError(404, "PREVIEW_NOT_FOUND", "Không có preview")
            p = preview_entity(raw["preview"])
            payload = json.loads(p.normalized_payload)
            if payload["version_id"] != identifier:
                raise CertificateError(422, "PREVIEW_ID_MISMATCH", "Preview khác phiên bản")
            fingerprint = digest({"preview": preview_id, "payload_hash": p.payload_hash})
            replay = tx.replay(actor.subject_id, key)
            valid = self.tokens.validate_token(token, preview_id, actor.subject_id, actor.session_id, "none", p.action_type,
                "1.0", "1.0", p.payload_hash, at_time=p.created_at if replay else None)
            if not valid.is_valid:
                raise CertificateError(422, valid.error_code, "Xác nhận không hợp lệ hoặc hết hạn")
            if replay:
                if replay["fingerprint"] != fingerprint:
                    raise CertificateError(409, "IDEMPOTENCY_CONFLICT", "Mã thử lại đã dùng")
                return {**replay["result"], "is_replay": True}
            if not p.is_active(datetime.now(UTC)):
                raise CertificateError(409, "PREVIEW_CONSUMED", "Preview không còn hoạt động")
            value = self._version(tx, identifier, payload["revision"])
            self._check_publication(actor, value, payload["operation"])
            pointer = self._active(tx, value["procedure"])
            if pointer != payload["active"]:
                raise CertificateError(409, "ACTIVE_VERSION_CHANGED", "Active version đã đổi; xem trước lại")
            if payload["operation"] == "publish":
                if pointer["version_id"]:
                    old = self._version(tx, pointer["version_id"])
                    old["state"], old["revision"] = "SUPERSEDED", old["revision"] + 1
                    tx.update("knowledge_version", old)
                value["state"], value["published_at"] = "PUBLISHED", now()
                value["supersedes"] = pointer["version_id"]
                pointer["version_id"] = value["id"]
            else:
                value["state"] = "WITHDRAWN"
                if pointer["version_id"] == value["id"]:
                    pointer["version_id"] = None
            value["revision"] += 1
            pointer["generation"] += 1
            if tx.item("knowledge_active", pointer["id"]):
                tx.update("knowledge_active", pointer)
            else:
                tx.insert("knowledge_active", pointer)
            raw["preview"]["consumed_at"] = now()
            tx.update("knowledge_preview", raw)
            tx.update("knowledge_version", value)
            self.event(tx, actor, "version." + payload["operation"], identifier, "Explicit confirmation", revision=value["revision"], active=pointer)
            result = {"version": value, "active": pointer, "is_replay": False}
            tx.complete(actor.subject_id, key, fingerprint, result)
            return result

    def list(self, actor):
        self.admin(actor)
        with self.repository.transaction() as tx:
            return {"sources": [self._source(tx, v["id"]) for v in tx.items("source")],
                "versions": [self._version(tx, v["id"]) for v in tx.items("knowledge_version")],
                "active": tx.items("knowledge_active"), "history": tx.items("audit")}

    def guidance(self, actor, procedure):
        self.authorization(actor, IdentityRole.STUDENT)
        with self.repository.transaction() as tx:
            return self.current(tx, procedure)

    def search(self, actor, query):
        self.authorization(actor, IdentityRole.STUDENT)
        terms = set(query.lower().split())
        with self.repository.transaction() as tx:
            items, gaps = [], []
            for procedure in ("GRADE_APPEAL", "GENERAL_SUPPORT"):
                try:
                    evidence = self.current(tx, procedure)
                    value = self._version(tx, evidence["version_id"])
                    score = len(terms & set(value["build"]["terms"]))
                    if score:
                        items.append({**evidence, "score": score, "procedure": procedure})
                except CertificateError as exc:
                    gaps.append({"procedure": procedure, "code": exc.code})
            return {"items": sorted(items, key=lambda row: row["score"], reverse=True), "gaps": gaps,
                "mode": "current_demo_lexical", "cache": "none; active source and checksum reread on every request"}
