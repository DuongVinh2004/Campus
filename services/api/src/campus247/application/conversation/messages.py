from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Callable, Protocol

from campus247.domain.shared.values import generate_uuid7, is_valid_uuid7
from campus247.application.conversation.stream_result import FinalChatResult, StreamCitation


class ConversationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    HANDED_OVER = "HANDED_OVER"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


class SenderType(StrEnum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    STAFF = "STAFF"
    SYSTEM = "SYSTEM"


class ContentFormat(StrEnum):
    PLAIN_TEXT = "PLAIN_TEXT"
    MARKDOWN_SAFE = "MARKDOWN_SAFE"


class ConversationStorageUnavailable(TimeoutError):
    """A dependency failure must not become successful empty history."""


class ConversationStorageCorrupt(ConversationStorageUnavailable):
    pass


class ConversationConflict(ValueError):
    pass


@dataclass(frozen=True)
class ConversationRecord:
    id: str
    owner_user_id: str
    status: ConversationStatus
    channel: str
    created_at: datetime
    updated_at: datetime
    retention_expires_at: datetime
    version: int = 1
    last_message_at: datetime | None = None
    # Missing legacy metadata stays unknown; never infer memory permission.
    mode: str | None = None


@dataclass(frozen=True)
class MessageRecord:
    id: str
    conversation_id: str
    sequence_no: int
    sender_type: SenderType
    content_redacted: str
    content_format: ContentFormat
    created_at: datetime
    sender_user_id: str | None = None
    citation_set_id: str | None = None
    redacted_at: datetime | None = None
    finish_status: str | None = None
    response_class: str | None = None
    citations: tuple[StreamCitation, ...] = ()
    agent_run_id: str | None = None
    turn_client_id: str | None = None
    turn_intent_sha256: str | None = None


class ConversationRepository(Protocol):
    async def save_conversation(self, conv: ConversationRecord) -> None:
        ...

    async def get_conversation(self, conv_id: str) -> ConversationRecord | None:
        ...

    async def save_message(self, msg: MessageRecord) -> None:
        ...

    async def list_messages(self, conv_id: str) -> list[MessageRecord]:
        ...

    async def get_next_sequence_no(self, conv_id: str) -> int:
        ...


class InMemoryConversationRepository:
    def __init__(self) -> None:
        self._conversations: dict[str, ConversationRecord] = {}
        self._messages: dict[str, list[MessageRecord]] = {}

    async def save_conversation(self, conv: ConversationRecord) -> None:
        self._conversations[conv.id] = conv
        if conv.id not in self._messages:
            self._messages[conv.id] = []

    async def get_conversation(self, conv_id: str) -> ConversationRecord | None:
        return self._conversations.get(conv_id)

    async def save_message(self, msg: MessageRecord) -> None:
        if msg.conversation_id not in self._messages:
            self._messages[msg.conversation_id] = []
        self._messages[msg.conversation_id].append(msg)

    async def list_messages(self, conv_id: str) -> list[MessageRecord]:
        return list(self._messages.get(conv_id, []))

    async def get_next_sequence_no(self, conv_id: str) -> int:
        msgs = self._messages.get(conv_id, [])
        if not msgs:
            return 1
        return max(m.sequence_no for m in msgs) + 1


class ConversationMessageService:
    def __init__(self, repository: ConversationRepository | None = None, *,
                 minimize_content: Callable[[str], str | None] | None = None) -> None:
        self._repo = repository if repository is not None else InMemoryConversationRepository()
        self._minimize_content = minimize_content

    def can_persist_content(self, content: str) -> bool:
        """Read-only preflight; append_message rechecks the same policy at commit."""
        return isinstance(content, str) and bool(content.strip()) and (
            self._minimize_content is None or self._minimize_content(content) == content)

    async def create_conversation(
        self,
        owner_user_id: str,
        channel: str = "WEB",
        retention_days: int = 30,
        *, client_id: str | None = None, mode: str = "persistent",
    ) -> ConversationRecord:
        if not is_valid_uuid7(owner_user_id):
            raise ValueError(f"owner_user_id must be a valid UUIDv7 string, got: {owner_user_id}")
        if channel != "WEB":
            raise ValueError(f"Unsupported channel: {channel}")
        if mode not in {"persistent", "temporary"} or retention_days != 30:
            raise ValueError("Explicit chat mode and current 30-day retention required")

        now = datetime.now(timezone.utc)
        if client_id is not None and not is_valid_uuid7(client_id):
            raise ValueError("client ID must be UUIDv7")
        record = ConversationRecord(
            id=client_id or generate_uuid7(),
            owner_user_id=owner_user_id,
            status=ConversationStatus.ACTIVE,
            channel=channel,
            created_at=now,
            updated_at=now,
            retention_expires_at=now + timedelta(days=retention_days),
            version=1,
            last_message_at=None,
            mode=mode,
        )
        if client_id is not None:
            writer = getattr(self._repo, "create_conversation_atomic", None)
            if not callable(writer):
                raise ConversationStorageUnavailable("STABLE_CREATE_NOT_CONFIGURED")
            return await writer(record)
        await self._repo.save_conversation(record)
        return record

    async def append_message(
        self,
        conversation_id: str,
        sender_type: SenderType | str,
        content: str,
        sender_user_id: str | None = None,
        content_format: ContentFormat | str = ContentFormat.MARKDOWN_SAFE,
        citation_set_id: str | None = None,
        *,
        message_id: str | None = None,
        final_result: FinalChatResult | None = None,
        turn_client_id: str | None = None,
    ) -> MessageRecord:
        conv = await self._repo.get_conversation(conversation_id)
        if not conv:
            raise ValueError(f"Conversation not found: {conversation_id}")

        if conv.status in (ConversationStatus.CLOSED, ConversationStatus.ARCHIVED):
            raise ValueError(f"Cannot append message to {conv.status} conversation")

        if not content or not content.strip():
            raise ValueError("Message content cannot be empty")

        if message_id is not None:
            if not is_valid_uuid7(message_id):
                raise ValueError("message_id must be UUIDv7")
            if turn_client_id is None and any(message.id == message_id for message in await self._repo.list_messages(conversation_id)):
                raise ValueError("message_id already persisted")
        if turn_client_id is not None and not is_valid_uuid7(turn_client_id):
            raise ValueError("turn client ID must be UUIDv7")
        if turn_client_id is not None and not callable(getattr(self._repo, "turn_receipt", None)):
            raise ConversationStorageUnavailable("STABLE_TURN_NOT_CONFIGURED")
        if final_result is not None:
            if SenderType(sender_type) != SenderType.ASSISTANT or content != final_result.content:
                raise ValueError("final result must match the immutable assistant content")

        import hashlib
        intent_sha256 = hashlib.sha256(content.encode()).hexdigest() if turn_client_id and SenderType(sender_type) == SenderType.USER else None
        if self._minimize_content is not None:
            minimized = self._minimize_content(content)
            if final_result is not None and minimized != content:
                raise ValueError("final result failed persistence content policy")
            content = minimized or "[Nội dung đã loại khỏi lịch sử theo chính sách dữ liệu]"

        now = datetime.now(timezone.utc)
        seq_no = await self._repo.get_next_sequence_no(conversation_id)
        stype = SenderType(sender_type)
        cformat = ContentFormat(content_format)

        msg = MessageRecord(
            id=message_id or generate_uuid7(),
            conversation_id=conversation_id,
            sequence_no=seq_no,
            sender_type=stype,
            content_redacted=content,
            content_format=cformat,
            created_at=now,
            sender_user_id=sender_user_id,
            citation_set_id=citation_set_id or (generate_uuid7() if final_result and final_result.citations else None),
            finish_status=final_result.status if final_result else None,
            response_class=final_result.response_class if final_result else None,
            citations=final_result.citations if final_result else (),
            agent_run_id=final_result.agent_run_id if final_result else None,
            turn_client_id=turn_client_id,
            turn_intent_sha256=intent_sha256,
        )
        atomic_append = getattr(self._repo, "append_message_atomic", None)
        if callable(atomic_append):
            # The durable repository allocates sequence and updates the parent
            # under one database transaction, rather than two separate writes.
            return await atomic_append(msg)
        await self._repo.save_message(msg)

        updated_conv = replace(
            conv,
            last_message_at=now,
            updated_at=now,
            version=conv.version + 1,
        )
        await self._repo.save_conversation(updated_conv)
        return msg

    async def turn_receipt(self, actor_id, conversation_id, client_id):
        reader = getattr(self._repo, "turn_receipt", None)
        if not callable(reader):
            raise ConversationStorageUnavailable("TURN_RECEIPT_NOT_CONFIGURED")
        return await reader(actor_id, conversation_id, client_id)

    async def interrupt_turn(self, actor_id, conversation_id, client_id):
        writer = getattr(self._repo, "interrupt_turn", None)
        if not callable(writer):
            raise ConversationStorageUnavailable("TURN_RECEIPT_NOT_CONFIGURED")
        return await writer(actor_id, conversation_id, client_id)

    async def get_conversation(self, conversation_id: str) -> ConversationRecord | None:
        return await self._repo.get_conversation(conversation_id)

    async def list_messages(self, conversation_id: str) -> list[MessageRecord]:
        return await self._repo.list_messages(conversation_id)

    async def list_owned_conversations(self, actor_id: str):
        reader = getattr(self._repo, "list_owned_conversations", None)
        if not callable(reader):
            raise ConversationStorageUnavailable("HISTORY_DISCOVERY_NOT_CONFIGURED")
        return await reader(actor_id)

    async def list_owned_page(self, actor_id: str, conversation_id: str, *, cursor: str | None = None,
                              limit: int = 20) -> tuple[list[MessageRecord], str | None, bool]:
        from campus247.application.authorization.concealment import ResourceNotFoundError
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("invalid message page limit")
        conv = await self._repo.get_conversation(conversation_id)
        if conv is None or conv.owner_user_id != actor_id:
            raise ResourceNotFoundError()
        if conv.retention_expires_at <= datetime.now(timezone.utc):
            return [], None, False
        messages = await self._repo.list_messages(conversation_id)
        if any(m.conversation_id != conversation_id for m in messages):
            raise ValueError("invalid message page scope")
        offset = 0
        if cursor is not None:
            if not is_valid_uuid7(cursor):
                raise ValueError("invalid message cursor")
            position = next((n for n, m in enumerate(messages) if m.id == cursor), None)
            if position is None:
                raise ValueError("invalid message cursor")
            offset = position + 1
        items = messages[offset:offset + limit]
        more = offset + limit < len(messages)
        return items, items[-1].id if more else None, more
