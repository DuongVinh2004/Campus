"""Reuse durable conversations without mutating retained runtime databases."""
import asyncio
from datetime import timedelta

from campus247.application.conversation.messages import ConversationMessageService, SenderType
from campus247.infrastructure.repositories.sqlite_conversations import SQLiteConversationRepository


def test_committed_history_survives_repository_restart_with_retention(tmp_path):
    async def run():
        db = tmp_path / "unified-history.sqlite3"
        owner = "4b419a1b-6d41-7dfb-8943-2edd9f071385"
        first = ConversationMessageService(SQLiteConversationRepository(db))
        conversation = await first.create_conversation(owner)
        assert conversation.retention_expires_at - conversation.created_at == timedelta(days=30)
        message = await first.append_message(conversation_id=conversation.id, sender_type=SenderType.USER,
                                             sender_user_id=owner, content="Câu hỏi mô phỏng")
        restarted = ConversationMessageService(SQLiteConversationRepository(db))
        restored = await restarted.get_conversation(conversation.id)
        assert restored.owner_user_id == owner
        rows = await restarted.list_messages(conversation.id)
        assert [(r.id, r.sequence_no, r.content_redacted) for r in rows] == [(message.id, 1, "Câu hỏi mô phỏng")]
        assert restored.retention_expires_at == conversation.retention_expires_at
    asyncio.run(run())
