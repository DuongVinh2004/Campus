"""Fresh, bounded server projections; never join actors, roles or resources."""
from datetime import datetime, timedelta, timezone
import json

from pydantic import model_validator, Field

from campus247.application.assistance.contracts import StrictDTO, ResourceRef
from campus247.application.assistance.state_storage import digest
from campus247.application.assistance.unified_contracts import UUID
from campus247.application.document_request.certificates import CertificateError
from campus247.ports.identity import IdentityRole


class ContextRequest(StrictDTO):
    conversation_id: UUID | None = None
    before_message_id: UUID | None = None
    resource: ResourceRef | None = None
    grant_id: UUID | None = None
    operation_id: UUID
    memory_terms: list[str] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def bindings(self):
        if any(not term.strip() or len(term) > 80 for term in self.memory_terms):
            raise ValueError("bounded explicit memory search terms required")
        if ((self.conversation_id is None) != (self.before_message_id is None)
                or (self.resource is None) != (self.grant_id is None)
                or self.conversation_id is None and self.resource is None):
            raise ValueError("exact chat boundary or granted resource required")
        return self


class ScopedContextService:
    max_bytes = 12000

    def __init__(self, *, preferences, grants, conversations=None, history=None, minimize=lambda text: text):
        self.preferences, self.grants = preferences, grants
        self.conversations, self.history, self.minimize = conversations, history, minimize
        self.memory = None

    async def conversation(self, actor, conversation_id):
        self.preferences.scope(actor)
        # Staff chat has no role/assignment metadata in this legacy repository.
        # Do not infer a staff channel from an actor who used to be a student.
        if set(actor.roles) != {IdentityRole.STUDENT} or self.conversations is None:
            raise CertificateError(403, "CHAT_SCOPE_UNAVAILABLE", "Chưa có chat cùng vai trò được xác nhận")
        record = await self.conversations.get_conversation(conversation_id)
        if record is None or record.owner_user_id != actor.subject_id:
            raise CertificateError(404, "RESOURCE_NOT_FOUND", "Không tìm thấy chat")
        if record.retention_expires_at <= datetime.now(timezone.utc):
            raise CertificateError(409, "CHAT_RETENTION_EXPIRED", "Chat không còn trong thời hạn context")
        return record

    async def compose(self, actor, request):
        request = ContextRequest.model_validate(request)
        self.preferences.scope(actor)
        audience = self.preferences.audience(actor)
        history, presentation, chat_ref = [], None, None
        if request.conversation_id is not None:
            conv = await self.conversation(actor, request.conversation_id)
            messages = await self.conversations.list_messages(conv.id)
            if not any(row.id == request.before_message_id and row.conversation_id == conv.id for row in messages):
                raise CertificateError(404, "MESSAGE_BOUNDARY_UNAVAILABLE", "Không tìm thấy mốc chat")
            chat_ref = {"id": conv.id, "version": conv.version, "before_message_id": request.before_message_id}
            presentation = self.preferences.resolve(actor, conv.id)
            if (self.preferences.consented(actor, "CONVERSATION_HISTORY")
                    and (self.memory is None or not self.memory.history_suppression_stamp(actor, conv.id))):
                if self.history is None:
                    raise CertificateError(503, "HISTORY_NOT_CONFIGURED", "Context history chưa được cấu hình")
                context = await self.history.load(actor.subject_id, conv.id, before_message_id=request.before_message_id)
                history = [{"id": row.turn_id, "role": row.role, "text": row.content,
                            "classification": "private_conversation_untrusted"} for row in context.turns]
        resource, receipt = None, None
        content = {"schema_version": "scoped-context.v1", "audience": audience, "conversation": chat_ref,
            "history": history, "resource": None,
            "presentation": presentation.preferences.model_dump(mode="json") if presentation else None,
            "presentation_version": presentation.version if presentation else None,
            "excluded": ["other_chats", "private_memory", "staff_notes", "grant_tokens", "legacy_imports", "unsaved_fields"],
            "action_authority": "none"}

        def check_budget(projected):
            content["resource"] = projected
            while history and len(json.dumps(content, ensure_ascii=False).encode()) > self.max_bytes:
                history.pop(0)
            if len(json.dumps(content, ensure_ascii=False).encode()) > self.max_bytes:
                raise CertificateError(422, "CONTEXT_BUDGET_EXCEEDED", "Context vượt giới hạn; cần thu hẹp tài nguyên")

        if request.resource is not None:
            if self.grants is None:
                raise CertificateError(503, "GRANTS_NOT_CONFIGURED", "Chưa cấu hình consumer tài nguyên")
            def project(observation):
                guidance = self.minimize(observation.guidance)
                if not isinstance(guidance, str):
                    guidance = ""
                guidance = guidance.encode("utf-8")[:4500].decode("utf-8", errors="ignore")
                projected = {"resource": observation.resource.model_dump(mode="json"),
                    "evidence": [item.model_dump(mode="json") for item in observation.evidence],
                    "guidance": guidance, "guidance_truncated": len(guidance) < len(observation.guidance),
                    "classification": "authorized_resource_untrusted"}
                # Validate inside the use transaction: a rejected/oversized
                # projection must not consume a one-time grant.
                check_budget(projected)
                return projected
            used = self.grants.use(actor, request.grant_id, operation_id=request.operation_id,
                capability="read_source", resource=request.resource, intent=request.model_dump(mode="json"), consume=project)
            resource, receipt = used["result"], used["receipt"]
        if request.memory_terms:
            if self.memory is None:
                raise CertificateError(503, "MEMORY_CONTEXT_UNAVAILABLE", "Chưa cấu hình consumer memory; context hiện có vẫn được giữ")
            from campus247.domain.assistant_memory import MemoryQuery
            query = MemoryQuery(conversation_id=request.conversation_id, terms=request.memory_terms, resource=request.resource)
            selected = self.memory.retrieve(actor, query)
            def consume(fresh):
                content["personal_memory"] = {"items": fresh["items"], "classification": "untrusted_personal_declaration", "action_authority": "none"}
                check_budget(resource)
                return None
            self.memory.use(actor, query, selected.get("sha256"), consume)
            content["excluded"] = [v for v in content["excluded"] if v != "private_memory"]
        check_budget(resource)
        size = len(json.dumps(content, ensure_ascii=False).encode())
        now = datetime.now(timezone.utc)
        # This hash describes data, not a bearer capability. Every future use
        # recomposes and reauthorizes; cached manifests cannot bypass revoke.
        return {"content": content, "manifest": {"sha256": digest(content), "bytes": size,
            "budget_bytes": self.max_bytes, "generated_at": now.isoformat(),
            "expires_at": (now+timedelta(seconds=60)).isoformat(), "freshness": "revalidate_every_use"},
            "receipt": receipt.model_dump(mode="json") if receipt else None}

    async def revalidate(self, actor, request, expected_sha256):
        value = await self.compose(actor, request)
        if value["manifest"]["sha256"] != expected_sha256:
            raise CertificateError(409, "CONTEXT_CHANGED", "Context đã thay đổi; cần đọc lại")
        return value
