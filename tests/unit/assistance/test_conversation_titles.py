from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from campus247.application.conversation.catalog import ConversationCatalogService
from campus247.application.conversation.messages import ConversationRecord, ConversationStatus, MessageRecord, SenderType, ContentFormat
from campus247.application.document_request.certificates import CertificateError
from campus247.domain.shared.values import generate_uuid7
from campus247.ports.identity import IdentityContext, IdentityRole


def fixture(*, title=None, expired=False):
    now = datetime.now(timezone.utc)
    actor = IdentityContext(generate_uuid7(), "synthetic", "test", (IdentityRole.STUDENT,), "Test",
                            now, now + timedelta(hours=1), tenant_id="test", session_id="test", student_code="TEST")
    conversation = ConversationRecord(generate_uuid7(), actor.subject_id, ConversationStatus.ACTIVE,
                                      "web", now, now, now + timedelta(days=-1 if expired else 1))
    def message(sequence, text, sender=SenderType.USER):
        return MessageRecord(generate_uuid7(), conversation.id, sequence, sender, text,
                             ContentFormat.PLAIN_TEXT, now, sender_user_id=actor.subject_id)
    # Deliberately unordered: title follows the first user question, not the last turn.
    messages = [message(3, "Câu hỏi thứ hai"), message(1, "Điều kiện\n xét học bổng?"),
                message(0, "System context", SenderType.SYSTEM)]
    record = SimpleNamespace(version=1, payload={"conversation_id": conversation.id, "title": title}) if title else None
    repository = SimpleNamespace(list_messages=AsyncMock(return_value=messages),
                                 get_conversation=AsyncMock(return_value=conversation),
                                 list_owned_conversations=AsyncMock(return_value=[conversation]))
    service = ConversationCatalogService(SimpleNamespace(get=lambda *args: record), tenant="test",
                                          authorize=lambda actor: None, tokens=None, conversations=repository)
    return actor, conversation, repository, service


@pytest.mark.asyncio
async def test_first_question_is_title_in_list_read_and_search():
    actor, conversation, repository, service = fixture()
    assert (await service.read(actor, conversation.id))["title"] == "Điều kiện xét học bổng?"
    assert (await service.page(actor, title="học bổng"))["items"][0]["title"] == "Điều kiện xét học bổng?"
    assert (await service.page(actor, title="thứ hai"))["items"] == []
    repository.list_messages.return_value.append(replace(repository.list_messages.return_value[0], sequence_no=4, content_redacted="Một câu hỏi khác"))
    assert (await service.read(actor, conversation.id))["title"] == "Điều kiện xét học bổng?"


@pytest.mark.asyncio
async def test_explicit_rename_wins_without_reading_messages():
    actor, conversation, repository, service = fixture(title="Học bổng HUCE")
    assert (await service.read(actor, conversation.id))["title"] == "Học bổng HUCE"
    repository.list_messages.assert_not_called()


@pytest.mark.asyncio
async def test_legacy_date_title_derives_question_without_metadata_write():
    actor, conversation, repository, service = fixture()
    service.store.get = lambda *args: SimpleNamespace(version=2, payload={"conversation_id": conversation.id,
        "title": "Hội thoại " + conversation.created_at.strftime("%d/%m/%Y %H:%M"), "pinned": True})
    result = await service.read(actor, conversation.id)
    assert result["title"] == "Điều kiện xét học bổng?" and result["version"] == 2 and result["pinned"]


@pytest.mark.asyncio
@pytest.mark.parametrize("unavailable", ["empty", "expired", "redacted"])
async def test_unavailable_first_question_has_safe_fallback(unavailable):
    actor, conversation, repository, service = fixture(expired=unavailable == "expired")
    if unavailable == "empty": repository.list_messages.return_value = []
    if unavailable == "redacted": repository.list_messages.return_value[1] = replace(repository.list_messages.return_value[1], redacted_at=datetime.now(timezone.utc))
    assert (await service.read(actor, conversation.id))["title"] == "Hội thoại mới"
    if unavailable == "expired": repository.list_messages.assert_not_called()


@pytest.mark.asyncio
async def test_other_owner_cannot_expose_question():
    actor, conversation, repository, service = fixture()
    repository.get_conversation.return_value = replace(conversation, owner_user_id=generate_uuid7())
    with pytest.raises(CertificateError): await service.read(actor, conversation.id)
    repository.list_messages.assert_not_called()


@pytest.mark.asyncio
async def test_long_question_is_bounded_and_controls_normalized():
    actor, conversation, repository, service = fixture()
    repository.list_messages.return_value = [replace(repository.list_messages.return_value[1], content_redacted="A\x00" + "B" * 200)]
    title = (await service.read(actor, conversation.id))["title"]
    assert len(title) == 120 and "\x00" not in title
