"""Opt-in, actor-owned baseline measurements. No form/transcript contents.

Recorded intervals describe explicit recorder state, not proven attention or
human identity. Automation and self-declared human sessions remain distinct.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import Field

from campus247.application.assistance.contracts import StrictDTO
from campus247.application.document_request.certificates import CertificateError
from campus247.domain.shared.values import generate_uuid7
from campus247.ports.identity import IdentityRole

ROOT = Path(__file__).resolve().parents[6]
DATASET = ROOT / "evals/datasets/unified-ai-baseline-20261014.json"
PROTOCOL = "unified-baseline-measurement.v1"


class BaselineStart(StrictDTO):
    client_id: str = Field(pattern=r"^baseline:[0-9a-f]{8}-[0-9a-f]{4}-[47][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
    case_id: str = Field(pattern=r"^UB-(0[1-9]|1[0-4])$")
    operator_kind: Literal["human_declared", "automation"]


class BaselineEvent(StrictDTO):
    event_id: str = Field(pattern=r"^event:[0-9a-f]{8}-[0-9a-f]{4}-[47][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
    expected_version: int = Field(ge=1)
    kind: Literal["pause", "resume", "wait", "finish", "field_edit", "correction", "manual_action", "check_source", "assistant_request", "preview", "receipt_observed"]
    field: Literal["reason", "course_record_id", "purpose", "recipient", "staff_note", "target", "outcome", "contact_preference"] | None = None


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class BaselineMeasurementService:
    def __init__(self, repository, authorization, *, clock=None):
        self.repository, self.authorization = repository, authorization
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        raw = DATASET.read_bytes()
        self.dataset_sha256 = hashlib.sha256(raw).hexdigest()
        self.cases = json.loads(raw)["cases"]
        # Only additive tables, in the retained candidate database transaction.
        with repository.transaction() as tx:
            tx.connection.execute("CREATE TABLE IF NOT EXISTS unified_baseline_session(id TEXT PRIMARY KEY,owner TEXT NOT NULL,tenant TEXT NOT NULL,client_id TEXT NOT NULL,fingerprint TEXT NOT NULL,record TEXT NOT NULL,UNIQUE(owner,tenant,client_id))")
            tx.connection.execute("CREATE TABLE IF NOT EXISTS unified_baseline_event(session_id TEXT NOT NULL REFERENCES unified_baseline_session(id),event_id TEXT NOT NULL,sequence INTEGER NOT NULL,fingerprint TEXT NOT NULL,receipt TEXT NOT NULL,PRIMARY KEY(session_id,event_id),UNIQUE(session_id,sequence))")

    def role(self, actor):
        self.authorization(actor)
        if actor.has_role(IdentityRole.STUDENT):
            return "STUDENT"
        if actor.has_role(IdentityRole.SUPPORT_OFFICER):
            return "SUPPORT_OFFICER"
        raise CertificateError(403, "ROLE_REQUIRED", "Phiên đo dành cho sinh viên hoặc cán bộ trong phạm vi local.")

    def available(self, actor):
        role = self.role(actor)
        result = []
        for case in self.cases:
            hint = case["actor"].lower()
            allowed = role == "STUDENT" and ("sv" in hint or "student" in hint) or role == "SUPPORT_OFFICER" and ("of" in hint or "staff" in hint)
            if allowed:
                result.append({"id":case["id"], "category":case["category"], "expected":case["expected"]})
        return {"protocol":PROTOCOL, "dataset_sha256":self.dataset_sha256, "items":result,
                "limitation":"Chỉ ghi số liệu thao tác; chưa xác minh người thử hoặc usefulness."}

    def public(self, record):
        keys = {"id","case_id","role","operator_kind","protocol","dataset_sha256","version","state",
                "created_at","last_at","active_ms","wait_ms","paused_ms","unattributed_ms","counts","fields","event_count","limitation"}
        return {key:value for key,value in record.items() if key in keys}

    def owned(self, tx, actor, identifier):
        role = self.role(actor)
        row = tx.connection.execute("SELECT record FROM unified_baseline_session WHERE id=? AND owner=? AND tenant=?",
                                    (identifier, actor.subject_id, actor.tenant_id)).fetchone()
        if not row:
            raise CertificateError(404, "RESOURCE_NOT_FOUND", "Không có phiên đo trong tài khoản này.")
        record = json.loads(row[0])
        if record["role"] != role:
            raise CertificateError(403, "ROLE_REQUIRED", "Vai trò hiện tại không khớp phiên đo.")
        return record

    def start(self, actor, body: BaselineStart):
        role = self.role(actor)
        if body.case_id not in {case["id"] for case in self.available(actor)["items"]}:
            raise CertificateError(403, "ROLE_REQUIRED", "Ca thử không thuộc vai trò này.")
        fingerprint = digest(body.model_dump())
        with self.repository.transaction() as tx:
            old = tx.connection.execute("SELECT id,fingerprint FROM unified_baseline_session WHERE owner=? AND tenant=? AND client_id=?",
                                        (actor.subject_id, actor.tenant_id, body.client_id)).fetchone()
            if old:
                if old[1] != fingerprint:
                    raise CertificateError(409, "IDEMPOTENCY_CONFLICT", "Mã phiên đo đã dùng với ca thử khác.")
                return {"session":self.public(self.owned(tx, actor, old[0])), "is_replay":True}
            now = self.clock().isoformat()
            record = {"id":generate_uuid7(), "owner":actor.subject_id, "tenant":actor.tenant_id,
                "client_id":body.client_id, "fingerprint":fingerprint, "case_id":body.case_id,
                "role":role, "operator_kind":body.operator_kind, "protocol":PROTOCOL,
                "dataset_sha256":self.dataset_sha256, "version":1, "state":"active", "created_at":now, "last_at":now,
                "active_ms":0, "wait_ms":0, "paused_ms":0, "unattributed_ms":0, "counts":{}, "fields":{}, "event_count":0,
                "limitation":"Thời gian theo trạng thái recorder; human_declared là tự khai, chưa nghiệm thu usefulness."}
            tx.connection.execute("INSERT INTO unified_baseline_session VALUES(?,?,?,?,?,?)",
                                  (record["id"],actor.subject_id,actor.tenant_id,body.client_id,fingerprint,json.dumps(record)))
            return {"session":self.public(record), "is_replay":False}

    def read(self, actor, identifier):
        with self.repository.transaction() as tx:
            return self.public(self.owned(tx, actor, identifier))

    def list(self, actor):
        self.role(actor)
        with self.repository.transaction() as tx:
            ids = tx.connection.execute("SELECT id FROM unified_baseline_session WHERE owner=? AND tenant=? ORDER BY id DESC LIMIT 20",
                                        (actor.subject_id,actor.tenant_id)).fetchall()
            return {"items":[self.public(self.owned(tx,actor,row[0])) for row in ids], "limit":20}

    def event(self, actor, identifier, body: BaselineEvent):
        fingerprint = digest(body.model_dump())
        with self.repository.transaction() as tx:
            record = self.owned(tx,actor,identifier)
            replay = tx.connection.execute("SELECT fingerprint,receipt FROM unified_baseline_event WHERE session_id=? AND event_id=?",
                                          (identifier,body.event_id)).fetchone()
            if replay:
                if replay[0] != fingerprint:
                    raise CertificateError(409,"IDEMPOTENCY_CONFLICT","Event đã dùng cho nội dung khác.")
                return {"session":self.public(record), "receipt":json.loads(replay[1]), "is_replay":True}
            if record["version"] != body.expected_version:
                raise CertificateError(409,"STALE_VERSION","Phiên đo đã thay đổi; đọc lại trước khi ghi.")
            if record["state"] == "finished":
                raise CertificateError(409,"INVALID_STATE","Phiên đo đã kết thúc; giữ nguyên evidence.")
            if record["event_count"] >= 1000 or record["event_count"] >= 999 and body.kind != "finish":
                raise CertificateError(429,"MEASUREMENT_LIMIT","Đạt giới hạn event; không mở rộng dữ liệu ghi.")
            allowed = {"pause":{"active","waiting"}, "wait":{"active","paused"}, "resume":{"paused","waiting"}, "finish":{"active","paused","waiting"}}
            if body.kind in allowed and record["state"] not in allowed[body.kind] or body.kind not in allowed and record["state"] != "active":
                raise CertificateError(409,"INVALID_STATE","Thao tác đo không phù hợp trạng thái.")
            if (body.kind == "field_edit") != (body.field is not None):
                raise CertificateError(422,"INVALID_CONTRACT","Field chỉ có trên event sửa trường.")
            now = self.clock()
            previous_state = record["state"]
            elapsed = int((now - datetime.fromisoformat(record["last_at"])).total_seconds()*1000)
            if elapsed < 0:
                raise CertificateError(409,"CLOCK_CHANGED","Thời gian server thay đổi; chưa ghi số đo.")
            # A long unattended gap is recorded explicitly, not called active
            # attention or silently converted into a usability result.
            if elapsed > 300000:
                record["unattributed_ms"] += elapsed
            else:
                key = {"active":"active_ms","waiting":"wait_ms","paused":"paused_ms"}[record["state"]]
                record[key] += elapsed
            record["last_at"] = now.isoformat()
            record["counts"][body.kind] = record["counts"].get(body.kind,0)+1
            if body.field:
                record["fields"][body.field] = record["fields"].get(body.field,0)+1
            if body.kind in allowed:
                record["state"] = {"pause":"paused","wait":"waiting","resume":"active","finish":"finished"}[body.kind]
            record["version"] += 1
            record["event_count"] += 1
            receipt = {"event_id":body.event_id,"sequence":record["event_count"],"version":record["version"],"committed_at":now.isoformat(),
                       "kind":body.kind,"field":body.field,"previous_state":previous_state,"state":record["state"],
                       "interval_ms":elapsed,"interval_classification":"unattributed" if elapsed > 300000 else previous_state}
            tx.connection.execute("UPDATE unified_baseline_session SET record=? WHERE id=? AND owner=? AND tenant=?",
                                  (json.dumps(record),identifier,actor.subject_id,actor.tenant_id))
            tx.connection.execute("INSERT INTO unified_baseline_event VALUES(?,?,?,?,?)",
                                  (identifier,body.event_id,record["event_count"],fingerprint,json.dumps(receipt)))
            return {"session":self.public(record),"receipt":receipt,"is_replay":False}

    def receipts(self, actor, identifier):
        with self.repository.transaction() as tx:
            self.owned(tx,actor,identifier)
            rows = tx.connection.execute("SELECT receipt FROM unified_baseline_event WHERE session_id=? ORDER BY sequence LIMIT 1000",(identifier,)).fetchall()
            return {"session_id":identifier,"items":[json.loads(row[0]) for row in rows],"limit":1000}
