"""Conversation-local passive context, never knowledge or authorization."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from typing import Callable, TYPE_CHECKING

from campus247.application.conversation.context import BoundedContextBuilder, TurnItem
from campus247.agent.prompts.composer import PromptBlock, PromptComposer, TrustDomain

if TYPE_CHECKING:
    from campus247.application.conversation.messages import ConversationMessageService


@dataclass(frozen=True)
class HistoryContext:
    actor_id: str
    conversation_id: str
    turns: tuple[TurnItem, ...]
    token_count: int
    token_count_mode: str
    policy_version: str = "DOC-AI-005@1.0.0"

    def block(self, actor_id: str, conversation_id: str) -> PromptBlock | None:
        if self.actor_id != actor_id or self.conversation_id != conversation_id:
            raise ValueError("history scope mismatch")
        if any(t.untrusted is not True or t.role not in {"user", "assistant"} for t in self.turns):
            raise ValueError("invalid passive history")
        if not self.turns:
            return None
        # Item IDs belong in the local context manifest, not provider payloads.
        content = json.dumps([{"role": t.role, "content": t.content} for t in self.turns], ensure_ascii=False)
        return PromptBlock(TrustDomain.MEMORY, content, "conversation-history")


class ConversationHistoryService:
    def __init__(self, messages: ConversationMessageService, *, minimize: Callable[[str], str | None],
                 count_tokens: Callable[[str], int] | None = None, max_tokens: int = 4000):
        if not callable(minimize) or type(max_tokens) is not int or not 0 < max_tokens <= 4000:
            raise ValueError("bounded history policy required")
        self._messages, self._minimize = messages, minimize
        # A UTF-8 byte bound is conservative for byte/subword tokenizers; it is
        # explicitly labeled, and an exact approved tokenizer can be injected.
        self._count = count_tokens or (lambda text: len(text.encode("utf-8")))
        self._mode = "injected_tokenizer" if count_tokens else "utf8_byte_upper_bound"
        self._budget = max_tokens

    async def load(self, actor_id: str, conversation_id: str, *, before_message_id: str,
                   now: datetime | None = None) -> HistoryContext:
        from campus247.application.conversation.messages import SenderType
        instant = now or datetime.now(timezone.utc)
        conv = await self._messages.get_conversation(conversation_id)
        if conv is None or conv.owner_user_id != actor_id:
            raise ValueError("history unavailable")
        empty = HistoryContext(actor_id, conversation_id, (), 0, self._mode)
        if conv.retention_expires_at <= instant:
            return empty
        messages = await self._messages.list_messages(conversation_id)
        cutoff = next((m.sequence_no for m in messages if m.id == before_message_id), None)
        if cutoff is None:
            raise ValueError("current history boundary unavailable")
        turns = []
        for message in messages:
            if (message.conversation_id != conversation_id or message.sequence_no >= cutoff
                    or message.created_at > instant or message.created_at <= instant - timedelta(days=90)
                    or message.redacted_at is not None
                    or message.sender_type not in {SenderType.USER, SenderType.ASSISTANT}
                    or (message.sender_type == SenderType.USER and message.sender_user_id != actor_id)):
                continue
            text = self._minimize(message.content_redacted)
            if isinstance(text, str) and text.strip():
                turns.append(TurnItem(message.id, str(message.sender_type).lower(), text, True))
        selected = BoundedContextBuilder().build(conversation_id, turns).turns
        while selected:
            candidate = HistoryContext(actor_id, conversation_id, selected, 0, self._mode)
            block = candidate.block(actor_id, conversation_id)
            rendered = PromptComposer().compose([block]).composed_user_prompt
            count = self._count(rendered)
            if type(count) is not int or count < 0:
                raise ValueError("invalid history token count")
            if count <= self._budget:
                return HistoryContext(actor_id, conversation_id, selected, count, self._mode)
            selected = selected[1:]
        return empty
