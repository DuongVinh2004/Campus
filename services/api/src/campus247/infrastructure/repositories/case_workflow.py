"""Checksummed append-only revisions/previews/receipts in the business DB."""
from campus247.infrastructure.repositories.sqlite_service_operations import OperationsTransaction
from campus247.application.knowledge.operations import digest
from campus247.application.document_request.certificates import CertificateError

class CaseWorkflowRepository:
    def read(self, tx, kind, key):
        value = OperationsTransaction(tx.connection).item("case_" + kind, key)
        if value is not None:
            checksum = value.pop("checksum", None)
            if value.get("id") != key or checksum != digest(value):
                raise CertificateError(503, "CASE_STATE_CORRUPT", "Chưa xác minh được trạng thái; giữ nháp, đọc receipt trước khi thử lại")
        return value

    def insert(self, tx, kind, value):
        OperationsTransaction(tx.connection).insert("case_" + kind, {**value, "checksum": digest(value)})

    def records(self, tx, kind):
        return [self.read(tx, kind, row["id"]) for row in OperationsTransaction(tx.connection).items("case_" + kind)]

    def event(self, tx, record, actor, event):
        # No form, note, profile, model content or raw PII enters this feed.
        self.insert(tx, "event", {"id": event["id"], "tenant": actor.tenant_id,
            "resource_id": record["id"], "resource_kind": "certificate_request" if record["document_type"] == "STUDENT_CERTIFICATE" else "service_request",
            "student_id": record["student_user_id"], "queue": record.get("queue", "HUCE_GENERAL"),
            "assigned_actor": record["assigned_user_id"], "version": record["version"],
            "status": record["status"], "action": event["action"], "occurred_at": event["occurred_at"],
            "invalidate": ["business", "workflow", "staff_workspace", "draft_binding", "supplement", "queue", "tracking"]})
        if event["action"] not in {"request.submitted", "request.supplement", "request.accept", "request.claim", "request.assign",
                "request.transfer", "request.respond", "request.request_information", "request.request_supplement",
                "request.resolve", "request.approve", "request.reject"}:
            return
        from campus247.domain.shared.values import generate_uuid7
        source_hash = digest({"resource_id": record["id"], "version": record["version"], "status": record["status"], "action": event["action"]})
        recipients = [(record["student_user_id"], "student")]
        if record["assigned_user_id"]:
            recipients.append((record["assigned_user_id"], "staff"))
        trigger = "supplement" if event["action"] in {"request.request_information", "request.request_supplement", "request.supplement"} else "feedback" if event["action"] == "request.respond" else "status"
        for recipient, audience in recipients:
            identifier = generate_uuid7()
            self.insert(tx, "tracking_event", {"id": identifier, "event_id": identifier, "tenant": actor.tenant_id,
                "recipient_id": recipient, "audience": audience,
                "resource": {"kind": "certificate_request" if record["document_type"] == "STUDENT_CERTIFICATE" else "service_request", "id": record["id"], "expected_version": record["version"]},
                "trigger": trigger, "source_id": event["id"], "source_sha256": source_hash, "changed_at": event["occurred_at"],
                "classification": "public_student" if audience == "student" else "internal_staff"})
