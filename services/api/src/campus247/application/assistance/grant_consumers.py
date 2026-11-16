"""Only minimal reads and validated candidates; all business writes stay separate."""
from campus247.application.assistance.contracts import ResourceRef
from campus247.application.assistance.unified_contracts import DraftProposal
from campus247.application.document_request.certificates import CertificateError


class GrantConsumerService:
    def __init__(self, grants, proposals):
        self.grants, self.proposals = grants, proposals

    def read_own(self, actor, grant_id, resource, operation_id):
        target = ResourceRef.model_validate(resource)
        def project(observation):
            record = self.grants.resource(actor, target)
            if record["student_user_id"] != actor.subject_id:
                raise CertificateError(404, "RESOURCE_NOT_FOUND", "Không tìm thấy hồ sơ riêng")
            fields = ({"purpose", "recipient", "quantity", "delivery_method"} if target.kind == "certificate_request"
                      else {"reason", "course_record_id", "contact_preference", "question", "unresolved"})
            return {"resource": observation.resource.model_dump(mode="json"),
                    "fields": {key: value for key, value in record["payload"].items() if key in fields},
                    "action_authority": "none", "classification": "private_owner_untrusted"}
        return self.grants.use(actor, grant_id, operation_id=operation_id, capability="read_own_resource",
                               resource=target, intent={"consumer": "read_own_resource", "resource": target.model_dump(mode="json")}, consume=project)

    def prepare_candidate(self, actor, grant_id, proposal, operation_id):
        proposal = DraftProposal.model_validate(proposal)
        from campus247.agent.tools.executor import ScopedSpecialistExecutor
        from campus247.agent.tools.registry import ToolRegistry, ToolDefinition
        from campus247.application.assistance.state_storage import ProposalBundle
        registry = ToolRegistry({"prepare_draft": ToolDefinition("prepare_draft", "prepare_draft",
            "Prepare a read-only validated proposal", False, False)})
        def authorize(tool, candidate):
            if tool != "prepare_draft" or self.proposals is None:
                raise CertificateError(503, "PROPOSAL_CONSUMER_UNAVAILABLE", "Chưa có consumer đề xuất")
            self.proposals.resource(actor, candidate.target)
        def prepare(_):
            return ScopedSpecialistExecutor(registry, authorize=authorize).execute("prepare_draft",
                proposal, DraftProposal, ProposalBundle, lambda candidate: self.proposals.bundle(actor, candidate)).model_dump(mode="json")
        return self.grants.use(actor, grant_id, operation_id=operation_id, capability="prepare_draft",
            resource=proposal.target, intent={"consumer": "prepare_draft", "proposal": proposal.model_dump(mode="json")},
            consume=prepare)
