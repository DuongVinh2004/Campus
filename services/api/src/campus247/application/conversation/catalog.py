"""Actor metadata overlays preserve the held writer's immutable history."""
from datetime import datetime, timezone
import hashlib
import json

from campus247.application.assistance.durable_services import ConfirmedStateService
from campus247.application.assistance.state_storage import ConversationMetadata
from campus247.application.document_request.certificates import CertificateError
from campus247.application.conversation.messages import SenderType
from campus247.ports.identity import IdentityRole


class ConversationCatalogService(ConfirmedStateService):
    namespaces = frozenset({"conversation_metadata"})

    def __init__(self, *args, conversations, **kwargs):
        super().__init__(*args, **kwargs)
        self.conversations = conversations

    def student(self, actor):
        self.scope(actor)
        if set(actor.roles) != {IdentityRole.STUDENT}:
            raise CertificateError(403, "CHAT_SCOPE_UNAVAILABLE", "Lịch sử chat cán bộ chưa có consumer phù hợp")
        if self.conversations is None:
            raise CertificateError(503, "HISTORY_NOT_CONFIGURED", "Chưa cấu hình lịch sử")

    async def owned(self, actor, conversation_id):
        self.student(actor)
        record = await self.conversations.get_conversation(conversation_id)
        if record is None or record.owner_user_id != actor.subject_id:
            raise CertificateError(404, "RESOURCE_NOT_FOUND", "Không tìm thấy hội thoại")
        return record

    async def project(self, actor, conversation):
        self.student(actor)
        if conversation.owner_user_id != actor.subject_id:
            raise CertificateError(404, "RESOURCE_NOT_FOUND", "Không tìm thấy hội thoại")
        record = self.store.get(self.scope(actor), "conversation_metadata", conversation.id)
        expired = conversation.retention_expires_at <= datetime.now(timezone.utc)
        legacy_title = "Hội thoại " + conversation.created_at.strftime("%d/%m/%Y %H:%M")
        value = ConversationMetadata.model_validate(record.payload) if record else ConversationMetadata(
            conversation_id=conversation.id, title="Hội thoại mới")
        # Derive the default from stored, redacted history; explicit renames win.
        # This also updates legacy date labels without rewriting their metadata.
        if not record or value.title == legacy_title:
            title = "Hội thoại mới"
            if not expired:
                messages = await self.conversations.list_messages(conversation.id)
                first = next((message for message in sorted(messages, key=lambda message: message.sequence_no)
                              if message.sender_type == SenderType.USER
                              and message.conversation_id == conversation.id
                              and message.sender_user_id == actor.subject_id), None)
                if first is not None and first.redacted_at is None:
                    title = "".join(char for char in " ".join(first.content_redacted.split()) if ord(char) >= 32)[:120] or title
            value = value.model_copy(update={"title": title})
        self.revalidate(actor, "conversation_metadata", conversation.id, value.model_dump(mode="json"))
        return {**value.model_dump(mode="json"), "id": conversation.id, "version": record.version if record else 0,
            "history_version": conversation.version, "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat(), "status": str(conversation.status),
            "retention_expires_at": conversation.retention_expires_at.isoformat(),
            "retention_state": "expired" if expired else "available", "saved": True,
            "mode": conversation.mode,
            "can_continue": not expired and not value.archived and str(conversation.status) not in {"CLOSED", "ARCHIVED"}}

    async def read(self, actor, conversation_id):
        return await self.project(actor, await self.owned(actor, conversation_id))

    async def page(self, actor, *, title="", archived=False, cursor=None, limit=20):
        self.student(actor)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("bounded catalog page required")
        title = title.strip().casefold()
        binding = hashlib.sha256(json.dumps([actor.tenant_id, actor.subject_id, title, archived]).encode()).hexdigest()[:24]
        rows = [await self.project(actor, row) for row in await self.conversations.list_owned_conversations(actor.subject_id)
                if row.mode != "temporary"]
        rows = sorted((row for row in rows if row["archived"] == archived and title in row["title"].casefold()),
                      key=lambda row: row["id"])
        offset = 0
        if cursor:
            try:
                identity, fingerprint = cursor.split(":")
                if fingerprint != binding:
                    raise ValueError()
                offset = next(i + 1 for i, row in enumerate(rows) if row["id"] == identity)
            except (ValueError, StopIteration):
                raise CertificateError(422, "CURSOR_INVALID", "Cursor không thuộc danh sách hiện tại") from None
        items = rows[offset:offset+limit]
        more = offset+limit < len(rows)
        return {"items": items, "page": {"next_cursor": items[-1]["id"]+":"+binding if more else None,
            "has_more": more, "limit": limit}, "order": "stable_conversation_id", "retention_effect": "preserve_source_no_deletion"}

    async def prepare(self, actor, conversation_id, metadata, expected_version, client_id):
        await self.owned(actor, conversation_id)
        value = ConversationMetadata(conversation_id=conversation_id, **metadata)
        return self.preview(actor, "conversation_metadata", conversation_id, expected_version, value.model_dump(mode="json"), client_id)

    def revalidate(self, actor, namespace, key, payload):
        self.student(actor)
        value = ConversationMetadata.model_validate(payload)
        if value.conversation_id != key:
            raise CertificateError(409, "CHAT_BINDING_INVALID", "Metadata không thuộc hội thoại")
