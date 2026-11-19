"""SQLite restart/concurrency/faults on fresh retained fixtures only."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import sqlite3

import pytest

from campus247.application.conversation.messages import (ConversationMessageService, InMemoryConversationRepository, SenderType,
    ConversationStorageUnavailable, ConversationStorageCorrupt, MessageRecord, ContentFormat)
from campus247.bootstrap.conversation_storage import conversation_storage
from campus247.bootstrap.settings import Settings
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.repositories.sqlite_conversations import SQLiteConversationRepository, encode
from campus247.infrastructure.repositories.sqlite_agent_runs import SQLiteAgentRunStore, RunConflict


def settings(**extra):
    return Settings(_env_file=None,ENVIRONMENT="development",DEMO_MODE=True,OPENAI_API_KEY=None,GEMINI_API_KEY=None,DEEPSEEK_API_KEY=None,**extra)


def test_configured_storage_is_explicit_and_failure_never_becomes_memory(tmp_path):
    repository,profile=conversation_storage(settings(CONVERSATION_STORAGE_MODE="sqlite",CONVERSATION_SQLITE_PATH=tmp_path / "history.sqlite3"))
    assert isinstance(repository,SQLiteConversationRepository) and profile=={"mode":"sqlite","durability":"durable","fallback":False}
    with pytest.raises(ValueError,match="path required"):conversation_storage(settings(CONVERSATION_STORAGE_MODE="sqlite"))
    with pytest.raises(ConversationStorageUnavailable):
        conversation_storage(settings(CONVERSATION_STORAGE_MODE="sqlite",CONVERSATION_SQLITE_PATH=tmp_path / "missing/history.sqlite3"))
    assert not (tmp_path / "missing").exists()
    with pytest.raises(ValueError,match="repository missing"):conversation_storage(settings(CONVERSATION_STORAGE_MODE="injected"))
    memory,profile=conversation_storage(settings())
    assert isinstance(memory,InMemoryConversationRepository) and profile["durability"]=="ephemeral"


def test_falsey_injected_repository_is_preserved_instead_of_memory_fallback(tmp_path):
    class FalseyRepository(SQLiteConversationRepository):
        def __bool__(self):return False
    repository=FalseyRepository(tmp_path / "falsey.sqlite3")
    resolved,profile=conversation_storage(settings(CONVERSATION_STORAGE_MODE="injected"),repository)
    assert resolved is repository and profile["durability"]=="durable"
    first=ConversationMessageService(repository)
    record=asyncio.run(first.create_conversation(generate_uuid7()))
    assert asyncio.run(SQLiteConversationRepository(repository.path).get_conversation(record.id))==record


def test_explicit_storage_modes_do_not_allow_conflicting_injection_or_production_memory(tmp_path):
    with pytest.raises(ValueError,match="not both"):
        conversation_storage(settings(CONVERSATION_STORAGE_MODE="sqlite",CONVERSATION_SQLITE_PATH=tmp_path / "unused.sqlite3"),InMemoryConversationRepository())
    assert not (tmp_path / "unused.sqlite3").exists()
    secure=Settings(_env_file=None,ENVIRONMENT="production",DEMO_MODE=False,IDENTITY_SECRET_KEY="fixture-secure-identity-value",CONFIRMATION_SIGNING_KEY="fixture-secure-confirmation-value")
    with pytest.raises(ValueError,match="durable conversation repository required"):conversation_storage(secure)


def test_concurrent_messages_allocate_unique_sequences_and_parent_versions(tmp_path):
    path=tmp_path / "race.sqlite3";repository=SQLiteConversationRepository(path)
    service=ConversationMessageService(repository);owner=generate_uuid7()
    record=asyncio.run(service.create_conversation(owner))
    def append(index):
        return asyncio.run(ConversationMessageService(SQLiteConversationRepository(path)).append_message(record.id,SenderType.USER,"Fixture "+str(index),owner))
    with ThreadPoolExecutor(max_workers=4) as pool:messages=list(pool.map(append,range(8)))
    restarted=ConversationMessageService(SQLiteConversationRepository(path))
    stored=asyncio.run(restarted.list_messages(record.id));parent=asyncio.run(restarted.get_conversation(record.id))
    assert sorted(m.sequence_no for m in messages)==list(range(1,9))
    assert [m.sequence_no for m in stored]==list(range(1,9)) and parent.version==9
    assert parent.updated_at==max([record.updated_at]+[m.created_at for m in stored])


def test_parent_update_failure_rolls_back_message_and_sequence(tmp_path):
    path=tmp_path / "rollback.sqlite3";service=ConversationMessageService(SQLiteConversationRepository(path));owner=generate_uuid7()
    record=asyncio.run(service.create_conversation(owner))
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TRIGGER fixture_parent_fail BEFORE UPDATE ON conversation BEGIN SELECT RAISE(ABORT,'fixture failure'); END")
    with pytest.raises(sqlite3.IntegrityError):asyncio.run(service.append_message(record.id,SenderType.USER,"Fixture",owner))
    assert asyncio.run(service.list_messages(record.id))==[] and asyncio.run(service.get_conversation(record.id))==record


def test_conversation_owner_column_binding_corruption_is_rejected(tmp_path):
    path=tmp_path / "binding.sqlite3";repository=SQLiteConversationRepository(path)
    record=asyncio.run(ConversationMessageService().create_conversation(generate_uuid7()))
    with sqlite3.connect(path) as connection:
        connection.execute("INSERT INTO conversation VALUES(?,?,?)",(record.id,generate_uuid7(),encode(record)))
    with pytest.raises(ConversationStorageCorrupt,match="binding mismatch"):asyncio.run(repository.get_conversation(record.id))


def test_message_column_binding_corruption_is_rejected(tmp_path):
    path=tmp_path / "message-binding.sqlite3";repository=SQLiteConversationRepository(path);service=ConversationMessageService(repository)
    record=asyncio.run(service.create_conversation(generate_uuid7()))
    saved=MessageRecord(id=generate_uuid7(),conversation_id=record.id,sequence_no=1,sender_type=SenderType.USER,
        content_redacted="Fixture",content_format=ContentFormat.PLAIN_TEXT,created_at=datetime.now(timezone.utc))
    with sqlite3.connect(path) as connection:connection.execute("INSERT INTO message VALUES(?,?,?,?)",(saved.id,record.id,99,encode(saved)))
    with pytest.raises(ConversationStorageCorrupt,match="message binding mismatch"):asyncio.run(repository.list_messages(record.id))


def test_initial_malformed_json_is_dependency_corruption_not_client_input(tmp_path):
    path=tmp_path / "malformed.sqlite3";repository=SQLiteConversationRepository(path)
    cid,owner=generate_uuid7(),generate_uuid7()
    with sqlite3.connect(path) as connection:connection.execute("INSERT INTO conversation VALUES(?,?,?)",(cid,owner,"{"))
    with pytest.raises(ConversationStorageCorrupt,match="conversation record invalid"):
        asyncio.run(repository.get_conversation(cid))


def test_run_restart_ownership_compare_and_swap_and_atomic_event(tmp_path):
    path=tmp_path / "runs.sqlite3";store=SQLiteAgentRunStore(path)
    run,owner,conversation=generate_uuid7(),generate_uuid7(),generate_uuid7()
    assert store.create(run,owner,conversation,{"goal":"Fixture"},10)==1
    assert store.save(run,owner,conversation,1,"waiting_user",{"goal":"Fixture"},event={"type":"fixture_checkpoint"})==2
    restarted=SQLiteAgentRunStore(path)
    assert restarted.get(run,generate_uuid7(),conversation) is None
    assert restarted.get(run,owner,generate_uuid7()) is None
    assert restarted.get(run,owner,conversation)["events"]==[{"seq":1,"type":"fixture_checkpoint"}]
    with pytest.raises(RunConflict):restarted.save(run,owner,conversation,1,"completed",{})
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TRIGGER fixture_event_fail BEFORE INSERT ON agent_event BEGIN SELECT RAISE(ABORT,'fixture failure'); END")
    with pytest.raises(sqlite3.IntegrityError):restarted.save(run,owner,conversation,2,"completed",{},event={"type":"failed"})
    assert restarted.get(run,owner,conversation)["version"]==2


@pytest.mark.parametrize("kind",["conversation","run"])
def test_missing_existing_repository_file_is_not_silently_recreated(tmp_path,kind):
    repository=SQLiteConversationRepository(tmp_path / "conversation.sqlite3") if kind=="conversation" else SQLiteAgentRunStore(tmp_path / "run.sqlite3")
    missing=tmp_path / "missing.sqlite3";repository.path=missing
    with pytest.raises(ConversationStorageUnavailable if kind=="conversation" else sqlite3.OperationalError):
        if kind=="conversation":asyncio.run(repository.get_conversation(generate_uuid7()))
        else:repository.get(generate_uuid7(),generate_uuid7(),generate_uuid7())
    assert not missing.exists()
