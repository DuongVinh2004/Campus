from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum

from campus247.application.conversation.messages import (
    ConversationMessageService,
    SenderType,
)
from campus247.domain.shared.values import generate_uuid7


class FeedbackRating(StrEnum):
    HELPFUL = "HELPFUL"
    NOT_HELPFUL = "NOT_HELPFUL"


class FeedbackStorageError(Exception):
    pass


@dataclass(frozen=True)
class AnswerFeedbackReference:
    answer_id: str
    source_document_version_ids: list[str]
    model_version: str
    prompt_version: str


@dataclass(frozen=True)
class AnswerFeedbackReceipt:
    id: str
    conversation_id: str
    rating: FeedbackRating
    comment_recorded: bool
    answer_reference: AnswerFeedbackReference
    recorded_at: datetime


class FeedbackService:
    def __init__(self, conv_service: ConversationMessageService, repository=None) -> None:
        self._conv_service = conv_service
        self._feedbacks: dict[str, AnswerFeedbackReceipt] = {}
        self.simulate_storage_failure = False
        self._repository = repository

    async def record_feedback(
        self,
        actor_id: str,
        conversation_id: str,
        message_id: str,
        rating: FeedbackRating | str,
        comment: str | None = None,
        client_id: str | None = None,
    ) -> AnswerFeedbackReceipt:
        conv = await self._conv_service.get_conversation(conversation_id)
        if not conv:
            raise KeyError("Conversation not found")

        if conv.owner_user_id != actor_id:
            raise PermissionError("Forbidden: not conversation owner")

        messages = await self._conv_service.list_messages(conversation_id)
        target_msg = next((m for m in messages if m.id == message_id), None)
        if not target_msg:
            raise KeyError("Message not found")
        if target_msg.sender_type != SenderType.ASSISTANT:
            raise ValueError("Feedback requires an assistant answer")

        if self.simulate_storage_failure:
            raise FeedbackStorageError("Storage subsystem temporarily unavailable")

        if self._repository is not None:
            return self._repository.record(actor_id,conversation_id,target_msg,rating,comment,client_id)

        receipt_id = generate_uuid7()
        now = datetime.now(timezone.utc)
        frating = FeedbackRating(rating)

        receipt = AnswerFeedbackReceipt(
            id=receipt_id,
            conversation_id=conversation_id,
            rating=frating,
            comment_recorded=bool(comment and comment.strip()),
            answer_reference=AnswerFeedbackReference(
                answer_id=message_id,
                source_document_version_ids=[],
                model_version="provider-fake-llm-v1",
                prompt_version="campus247-chat-system-v1",
            ),
            recorded_at=now,
        )

        self._feedbacks[receipt_id] = receipt
        return receipt

    async def read_feedback(self, actor_id, conversation_id, message_id, feedback_id):
        conv = await self._conv_service.get_conversation(conversation_id)
        if not conv or conv.owner_user_id != actor_id:
            raise KeyError("Feedback not found")
        if not any(m.id == message_id for m in await self._conv_service.list_messages(conversation_id)):
            raise KeyError("Feedback not found")
        if self._repository is not None:
            return self._repository.read(actor_id,conversation_id,message_id,feedback_id)
        receipt = self._feedbacks.get(feedback_id)
        if receipt is None or (receipt.conversation_id,receipt.answer_reference.answer_id) != (conversation_id,message_id):
            raise KeyError("Feedback not found")
        return receipt
