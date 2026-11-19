"""A local process restart retains confirmed content and final citation bindings."""
import pytest

from campus247.application.conversation.messages import ConversationMessageService, SenderType
from campus247.application.conversation.stream_result import FinalChatResult
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.repositories.sqlite_conversations import SQLiteConversationRepository


@pytest.mark.asyncio
async def test_local_repository_survives_reconstruction_without_overwriting_messages(tmp_path):
    path = tmp_path / "conversations.sqlite3"
    owner = generate_uuid7()
    first = ConversationMessageService(repository=SQLiteConversationRepository(path))
    conv = await first.create_conversation(owner)
    user = await first.append_message(conv.id, SenderType.USER, "Xin bảng điểm ở đâu?", owner)
    final = FinalChatResult("abstained", "clarification_request", "Bạn cần bảng điểm học kỳ hay tích lũy?")
    assistant = await first.append_message(conv.id, SenderType.ASSISTANT, final.content, final_result=final)
    restored = ConversationMessageService(repository=SQLiteConversationRepository(path))
    messages = await restored.list_messages(conv.id)
    assert [item.id for item in messages] == [user.id, assistant.id]
    assert [item.sequence_no for item in messages] == [1, 2]
    assert messages[1].response_class == "clarification_request"
    assert (await restored.get_conversation(conv.id)).owner_user_id == owner
