"""Private manual drafts; saved text is never a public response or approval."""
from campus247.application.assistance.contracts import ResourceRef
from campus247.application.assistance.state_storage import (
    StaffDraftSnapshot,
    StateScope,
)
from campus247.application.assistance.workflow import WorkflowResolveRequest
from campus247.application.document_request.certificates import CertificateError
from campus247.domain.shared.values import is_valid_uuid7
from campus247.ports.identity import IdentityRole
from campus247.application.knowledge.operations import digest


class StaffDraftService:
    def __init__(self, store, *, tenant, resources, workflow):
        self.store,self.tenant,self.resources,self.workflow = store,tenant,resources,workflow

    def current(self, actor, target, *, transaction=None):
        target = ResourceRef.model_validate(target)
        service = self.resources[target.kind]
        service.authorize(actor,IdentityRole.SUPPORT_OFFICER)
        if actor.tenant_id != self.tenant:
            raise CertificateError(403,"TENANT_REQUIRED","Cần đúng tenant")
        record = service._owned(transaction,actor,target.id,staff=True) if transaction else service.read(actor,target.id,staff=True)
        if record.get("queue","HUCE_GENERAL") not in actor.unit_ids:
            raise CertificateError(404,"RESOURCE_NOT_FOUND","Hồ sơ không thuộc hàng đợi đang được cấp")
        if record["assigned_user_id"] != actor.subject_id:
            raise CertificateError(404,"RESOURCE_NOT_FOUND","Nháp thuộc cán bộ đang phụ trách hồ sơ")
        if record["version"] != target.expected_version:
            raise CertificateError(409,"STALE_VERSION","Hồ sơ đã đổi phiên bản; giữ nội dung đang soạn và đọc lại")
        return target,record,StateScope(self.tenant,actor.subject_id)

    def input_hash(self, record, target):
        return digest({"kind": target.kind, "id": target.id, "student": record["student_user_id"],
            "payload": record["payload"], "profile": record["profile"], "criteria_version": "staff-criteria.v1",
            "snapshot": record.get("snapshot"),
            "latest_profile": self.resources[target.kind].profile_reader(record["student_user_id"])})

    def read(self, actor, target, *, revalidate=None):
        target = ResourceRef.model_validate(target)
        with self.resources[target.kind].repository.transaction() as tx:
            actor = revalidate(tx) if revalidate else actor
            return self._read(tx, actor, target)

    def _read(self, tx, actor, target):
        target,record,scope = self.current(actor,target,transaction=tx)
        value = self.store.get(scope,"staff_draft",target.id)
        if value is None:
            return {"draft_version":0,"business_version":record["version"],"text":"","saved":False,
                    "binding_stale":False,"action_authority":"none","actor_id":scope.owner,"tenant":scope.tenant}
        snapshot = StaffDraftSnapshot.model_validate(value.payload)
        if (snapshot.assigned_actor != actor.subject_id or snapshot.resource.resource.id != target.id
                or snapshot.resource.resource.kind != target.kind):
            from campus247.application.assistance.state_storage import StorageCorrupt
            raise StorageCorrupt("STAFF_DRAFT_BINDING_INVALID")
        current = self.workflow.resolve(actor,WorkflowResolveRequest(resource=target),transaction=tx,tolerate_source_errors=True)
        return {"draft_version":value.version,"business_version":snapshot.resource.resource.version,
                "text":snapshot.text,"saved":True,"binding_stale":snapshot.resource != current or snapshot.queue != record.get("queue","HUCE_GENERAL") or snapshot.input_sha256 != self.input_hash(record,target),
                "action_authority":"none","committed_at":value.committed_at,"actor_id":scope.owner,"tenant":scope.tenant}

    def save(self, actor, target, text, expected_version, client_id, *, revalidate=None):
        target = ResourceRef.model_validate(target)
        # Lock the durable business record through the private CAS commit. A
        # concurrent transfer cannot slip between the ownership check and save.
        with self.resources[target.kind].repository.transaction() as tx:
            actor = revalidate(tx) if revalidate else actor
            return self._save(tx, actor, target, text, expected_version, client_id)

    def _save(self, tx, actor, target, text, expected_version, client_id):
        target,record,scope = self.current(actor,target,transaction=tx)
        if not is_valid_uuid7(client_id):
            raise ValueError("stable client UUIDv7 required")
        snapshot = StaffDraftSnapshot(resource=self.workflow.resolve(actor,WorkflowResolveRequest(resource=target),transaction=tx,tolerate_source_errors=True),
            assigned_actor=actor.subject_id,queue=record.get("queue","HUCE_GENERAL"),text=text,input_sha256=self.input_hash(record,target))
        # Manual autosave changes only this private draft; action endpoints
        # retain their independent authorization/version/confirmation gates.
        receipt = self.store.commit(scope,"staff_draft",target.id,expected_version,snapshot.model_dump(mode="json"),client_id)
        return {"draft_version":receipt.version,"business_version":target.expected_version,"saved":True,
                "receipt_id":receipt.receipt_id,"is_replay":receipt.is_replay,"action_authority":"none",
                "committed_at":receipt.committed_at}
