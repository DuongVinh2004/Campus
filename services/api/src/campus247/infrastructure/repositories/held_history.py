"""Validated reads from held history without initialization or live migration."""
import sqlite3
from contextlib import contextmanager

from campus247.application.conversation.messages import (
    ConversationStorageCorrupt,
    ConversationStorageUnavailable,
)
from campus247.infrastructure.repositories.sqlite_certificates import workspace_path
from campus247.infrastructure.repositories.sqlite_conversations import (
    SQLiteConversationRepository,
)


class HeldHistoryRepository(SQLiteConversationRepository):
    supports_stable_turns = False

    def __init__(self, path, *, tenant):
        from campus247.application.assistance.state_storage import StateScope
        StateScope(tenant,"019a0000-0000-7000-8000-000000000007")
        self.path,self.tenant = workspace_path(path),tenant
        with self.connect() as connection:
            connection.execute("SELECT id,owner,record FROM conversation LIMIT 1").fetchone()
            connection.execute("SELECT id,conversation_id,sequence,record FROM message LIMIT 1").fetchone()

    @contextmanager
    def connect(self, *, initialize=False):
        if initialize:
            raise ConversationStorageUnavailable("HELD_HISTORY_READ_ONLY")
        workspace_path(self.path);connection = None
        try:
            connection = sqlite3.connect(self.path.as_uri()+"?mode=ro",uri=True,timeout=2)
            connection.execute("PRAGMA temp_store=MEMORY")
            if (connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='conversation_schema'").fetchone()
                    and connection.execute("SELECT version FROM conversation_schema").fetchall() != [(1,)]):
                raise ConversationStorageCorrupt("CONVERSATION_SCHEMA_UNSUPPORTED")
            if (connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='conversation_tenant'").fetchone()
                    and connection.execute("SELECT tenant FROM conversation_tenant").fetchall() != [(self.tenant,)]):
                raise ConversationStorageCorrupt("CONVERSATION_TENANT_MISMATCH")
            yield connection
        except sqlite3.Error:
            raise ConversationStorageUnavailable("HELD_HISTORY_UNAVAILABLE") from None
        finally:
            if connection is not None:connection.close()

    def bind_tenant(self, tenant):
        if tenant != self.tenant:
            raise ConversationStorageCorrupt("CONVERSATION_TENANT_MISMATCH")

    async def save_conversation(self, value):
        raise ConversationStorageUnavailable("HELD_HISTORY_READ_ONLY")

    async def save_message(self, value):
        raise ConversationStorageUnavailable("HELD_HISTORY_READ_ONLY")

    async def append_message_atomic(self, value):
        raise ConversationStorageUnavailable("HELD_HISTORY_READ_ONLY")

    async def create_conversation_atomic(self, value):
        raise ConversationStorageUnavailable("HELD_HISTORY_READ_ONLY")

    async def turn_receipt(self, actor_id, conv_id, client_id):
        raise ConversationStorageUnavailable("HELD_TURN_RECEIPT_NOT_CONFIGURED")

    async def interrupt_turn(self, actor_id, conv_id, client_id):
        raise ConversationStorageUnavailable("HELD_HISTORY_READ_ONLY")
