"""Durable local conversations, append-only messages and atomic sequence allocation."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path

from campus247.application.conversation.messages import (
    ConversationRecord, ConversationStatus, MessageRecord, SenderType, ContentFormat,
    ConversationStorageUnavailable, ConversationStorageCorrupt, ConversationConflict,
)
from campus247.application.conversation.stream_result import StreamCitation
from campus247.infrastructure.repositories.sqlite_certificates import workspace_path


def encode(record):
    return json.dumps(asdict(record), default=lambda value: value.isoformat(), ensure_ascii=False)


def conversation(data):
    value = json.loads(data)
    value["status"] = ConversationStatus(value["status"])
    for key in ("created_at", "updated_at", "retention_expires_at", "last_message_at"):
        if value[key] is not None:
            value[key] = datetime.fromisoformat(value[key])
    return ConversationRecord(**value)


def message(data):
    value = json.loads(data)
    value["sender_type"] = SenderType(value["sender_type"])
    value["content_format"] = ContentFormat(value["content_format"])
    value["created_at"] = datetime.fromisoformat(value["created_at"])
    if value.get("redacted_at") is not None:
        value["redacted_at"] = datetime.fromisoformat(value["redacted_at"])
    value["citations"] = tuple(StreamCitation(**item) for item in value["citations"])
    return MessageRecord(**value)


class SQLiteConversationRepository:
    # Read by presentation instead of an isinstance check on this adapter.
    supports_stable_turns = True

    def __init__(self, path: Path, *, tenant=None):
        self.path = workspace_path(path)
        self.tenant = None
        with self.connect(initialize=True) as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='conversation_schema'").fetchone():
                if list(conn.execute("SELECT version FROM conversation_schema")) != [(1,)]:
                    raise ValueError("unsupported conversation schema")
            conn.execute("CREATE TABLE IF NOT EXISTS conversation (id TEXT PRIMARY KEY, owner TEXT NOT NULL, record TEXT NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS message (id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversation(id), sequence INTEGER NOT NULL, record TEXT NOT NULL, UNIQUE(conversation_id, sequence))")
            conn.execute("CREATE INDEX IF NOT EXISTS conversation_owner_id ON conversation(owner,id)")
            conn.execute("CREATE TABLE IF NOT EXISTS conversation_schema(version INTEGER PRIMARY KEY)")
            conn.execute("CREATE TABLE IF NOT EXISTS conversation_turn(client_id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversation(id), owner TEXT NOT NULL, content_sha256 TEXT NOT NULL, receipt TEXT NOT NULL)")
            conn.execute("INSERT OR IGNORE INTO conversation_schema VALUES(1)")
            if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='conversation_tenant'").fetchone():
                rows = conn.execute("SELECT tenant FROM conversation_tenant").fetchall()
                if len(rows) != 1:
                    raise ConversationStorageCorrupt("CONVERSATION_TENANT_INVALID")
                self.tenant = rows[0][0]
        if tenant is not None:
            self.bind_tenant(tenant)

    def bind_tenant(self, tenant):
        from campus247.application.assistance.state_storage import StateScope
        StateScope(tenant,"019a0000-0000-7000-8000-000000000007")
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='conversation_tenant'").fetchone()
            if not exists and conn.execute("SELECT COUNT(*) FROM conversation").fetchone()[0]:
                raise ConversationStorageCorrupt("LEGACY_CONVERSATION_TENANT_UNBOUND")
            if exists and conn.execute("SELECT tenant FROM conversation_tenant").fetchall() != [(tenant,)]:
                raise ConversationStorageCorrupt("CONVERSATION_TENANT_MISMATCH")
            conn.execute("CREATE TABLE IF NOT EXISTS conversation_tenant(tenant TEXT PRIMARY KEY)")
            conn.execute("INSERT OR IGNORE INTO conversation_tenant VALUES(?)",(tenant,))
        self.tenant = tenant

    @contextmanager
    def connect(self, *, initialize=False):
        workspace_path(self.path)
        conn = None
        try:
            conn = sqlite3.connect(self.path.as_uri()+"?mode="+("rwc" if initialize else "rw"), uri=True, timeout=2)
            conn.execute("PRAGMA foreign_keys=ON")
            if not initialize:
                if conn.execute("SELECT version FROM conversation_schema").fetchall() != [(1,)]:
                    raise ConversationStorageCorrupt("CONVERSATION_SCHEMA_UNSUPPORTED")
                if self.tenant is not None and conn.execute("SELECT tenant FROM conversation_tenant").fetchall() != [(self.tenant,)]:
                    raise ConversationStorageCorrupt("CONVERSATION_TENANT_MISMATCH")
            with conn:
                yield conn
        except sqlite3.OperationalError:
            raise ConversationStorageUnavailable("CONVERSATION_STORAGE_UNAVAILABLE") from None
        finally:
            if conn is not None:
                conn.close()

    async def save_conversation(self, conv):
        with self.connect() as conn:
            conn.execute("INSERT INTO conversation (id,owner,record) VALUES (?,?,?)", (conv.id, conv.owner_user_id, encode(conv)))

    async def create_conversation_atomic(self, conv):
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT id,owner,record FROM conversation WHERE id=?", (conv.id,)).fetchone()
            if row:
                previous = self._conversation(row)
                if (previous.owner_user_id != conv.owner_user_id or previous.channel != conv.channel
                        or previous.mode != conv.mode):
                    raise ConversationConflict("CREATE_ID_CONFLICT")
                return previous
            conn.execute("INSERT INTO conversation VALUES(?,?,?)", (conv.id, conv.owner_user_id, encode(conv)))
            return conv

    @staticmethod
    def _turn(row, actor_id, conv_id, client_id):
        if row is None:
            return None
        try:
            receipt = json.loads(row[2])
            if row[:2] != (conv_id, actor_id) or (receipt["conversation_id"], receipt["client_id"], receipt["owner"]) != (conv_id, client_id, actor_id):
                raise ValueError()
            if receipt["state"] not in {"pending", "interrupted", "completed"}:
                raise ValueError()
            from campus247.domain.shared.values import is_valid_uuid7
            if (receipt["user_message_id"] != client_id or receipt["receipt_id"] != client_id
                    or datetime.fromisoformat(receipt["committed_at"]).utcoffset() is None
                    or (receipt["state"] == "completed") != (receipt["assistant_message_id"] is not None)
                    or receipt["assistant_message_id"] is not None and not is_valid_uuid7(receipt["assistant_message_id"])):
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise ConversationStorageCorrupt("TURN_RECEIPT_INVALID") from None
        return receipt

    async def turn_receipt(self, actor_id, conv_id, client_id):
        with self.connect() as conn:
            row = conn.execute("SELECT conversation_id,owner,receipt FROM conversation_turn WHERE client_id=? AND conversation_id=? AND owner=?", (client_id, conv_id, actor_id)).fetchone()
            receipt = self._turn(row, actor_id, conv_id, client_id)
            if receipt is not None:
                stored = conn.execute("SELECT conversation_id,record FROM message WHERE id=?", (receipt["user_message_id"],)).fetchone()
                if not stored or stored[0] != conv_id:
                    raise ConversationStorageCorrupt("TURN_USER_MISSING")
                user = message(stored[1])
                if user.turn_client_id != client_id or user.sender_user_id != actor_id or user.sender_type != SenderType.USER:
                    raise ConversationStorageCorrupt("TURN_USER_BINDING_INVALID")
                if receipt["state"] == "completed":
                    from campus247.application.conversation.read import final_payload, StoredMessageError
                    stored = conn.execute("SELECT conversation_id,record FROM message WHERE id=?", (receipt["assistant_message_id"],)).fetchone()
                    if not stored or stored[0] != conv_id:
                        raise ConversationStorageCorrupt("TURN_FINAL_MISSING")
                    final = message(stored[1])
                    try:
                        if final.turn_client_id != client_id or final_payload(final) is None:
                            raise StoredMessageError()
                    except StoredMessageError:
                        raise ConversationStorageCorrupt("TURN_FINAL_INVALID") from None
            return receipt

    async def interrupt_turn(self, actor_id, conv_id, client_id):
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT conversation_id,owner,receipt FROM conversation_turn WHERE client_id=? AND conversation_id=? AND owner=?", (client_id, conv_id, actor_id)).fetchone()
            receipt = self._turn(row, actor_id, conv_id, client_id)
            if receipt and receipt["state"] == "pending":
                receipt["state"] = "interrupted"
                conn.execute("UPDATE conversation_turn SET receipt=? WHERE client_id=?", (json.dumps(receipt), client_id))
            return receipt

    async def get_conversation(self, conv_id):
        with self.connect() as conn:
            row = conn.execute("SELECT id,owner,record FROM conversation WHERE id=?", (conv_id,)).fetchone()
            return self._conversation(row) if row else None

    def read_owned_mode(self, actor, conv_id):
        from datetime import timezone
        from campus247.ports.identity import IdentityRole
        if (self.tenant is None or actor.tenant_id != self.tenant
                or set(actor.roles) != {IdentityRole.STUDENT}):
            return None
        with self.connect() as conn:
            row = conn.execute('SELECT id,owner,record FROM conversation WHERE id=? AND owner=?',
                (conv_id, actor.subject_id)).fetchone()
            record = self._conversation(row) if row else None
            return record.mode if record and record.retention_expires_at > datetime.now(timezone.utc) else None

    async def list_owned_conversations(self, actor_id):
        with self.connect() as conn:
            return [self._conversation(row) for row in conn.execute(
                "SELECT id,owner,record FROM conversation WHERE owner=? ORDER BY id", (actor_id,))]

    @staticmethod
    def _conversation(row):
        try:
            value = conversation(row[2])
        except (ValueError,TypeError,KeyError):
            raise ConversationStorageCorrupt("conversation record invalid") from None
        if (value.id, value.owner_user_id) != (row[0], row[1]):
            raise ConversationStorageCorrupt("conversation binding mismatch")
        if (type(value.version) is not int or value.version < 1
                or value.mode not in {None, "persistent", "temporary"}
                or any(not isinstance(at,datetime) or at.utcoffset() is None for at in
                       (value.created_at,value.updated_at,value.retention_expires_at))
                or value.last_message_at is not None and value.last_message_at.utcoffset() is None):
            raise ConversationStorageCorrupt("conversation timestamp/version invalid")
        return value

    async def list_messages(self, conv_id):
        with self.connect() as conn:
            result = []
            for row in conn.execute("SELECT id,conversation_id,sequence,record FROM message WHERE conversation_id=? ORDER BY sequence", (conv_id,)):
                try:
                    value = message(row[3])
                except (ValueError,TypeError,KeyError):
                    raise ConversationStorageCorrupt("message record invalid") from None
                if (value.id,value.conversation_id,value.sequence_no) != row[:3]:
                    raise ConversationStorageCorrupt("message binding mismatch")
                if (type(value.sequence_no) is not int or value.sequence_no < 1 or value.created_at.utcoffset() is None
                        or value.redacted_at is not None and value.redacted_at.utcoffset() is None):
                    raise ConversationStorageCorrupt("message timestamp/sequence invalid")
                result.append(value)
            return result

    async def get_next_sequence_no(self, conv_id):
        with self.connect() as conn:
            return conn.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM message WHERE conversation_id=?", (conv_id,)).fetchone()[0]

    async def append_message_atomic(self, msg):
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT id,owner,record FROM conversation WHERE id=?", (msg.conversation_id,)).fetchone()
            if row is None:
                raise ValueError("conversation unavailable")
            parent = self._conversation(row)
            if parent.status in {ConversationStatus.CLOSED, ConversationStatus.ARCHIVED}:
                raise ValueError("conversation closed")
            if parent.retention_expires_at <= msg.created_at:
                raise ConversationConflict("RETENTION_EXPIRED")
            receipt = None
            if msg.turn_client_id is not None:
                row = conn.execute("SELECT conversation_id,owner,receipt,content_sha256 FROM conversation_turn WHERE client_id=?", (msg.turn_client_id,)).fetchone()
                if row and row[:2] != (parent.id, parent.owner_user_id):
                    raise ConversationConflict("TURN_ID_SCOPE_CONFLICT")
                receipt = self._turn(row[:3], parent.owner_user_id, parent.id, msg.turn_client_id) if row else None
                if msg.sender_type == SenderType.USER:
                    if msg.id != msg.turn_client_id or msg.sender_user_id != parent.owner_user_id:
                        raise ConversationConflict("TURN_ACTOR_MISMATCH")
                    fingerprint = msg.turn_intent_sha256
                    if not isinstance(fingerprint, str) or len(fingerprint) != 64 or any(c not in "0123456789abcdef" for c in fingerprint):
                        raise ConversationConflict("TURN_INTENT_REQUIRED")
                    if row:
                        if row[3] != fingerprint:
                            raise ConversationConflict("TURN_INTENT_CHANGED")
                        raise ConversationConflict("TURN_ALREADY_ACCEPTED")
                elif receipt is None or receipt["state"] != "pending" or msg.finish_status is None:
                    raise ConversationConflict("TURN_NOT_PENDING")
            sequence = conn.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM message WHERE conversation_id=?", (msg.conversation_id,)).fetchone()[0]
            saved = replace(msg, sequence_no=sequence)
            conn.execute("INSERT INTO message VALUES (?,?,?,?)", (saved.id, saved.conversation_id, sequence, encode(saved)))
            if saved.turn_client_id is not None:
                if saved.sender_type == SenderType.USER:
                    receipt = {"receipt_id": saved.id, "client_id": saved.turn_client_id, "conversation_id": parent.id,
                        "owner": parent.owner_user_id, "user_message_id": saved.id, "assistant_message_id": None,
                        "state": "pending", "committed_at": saved.created_at.isoformat()}
                    conn.execute("INSERT INTO conversation_turn VALUES(?,?,?,?,?)", (saved.turn_client_id, parent.id, parent.owner_user_id, fingerprint, json.dumps(receipt)))
                else:
                    receipt.update(state="completed", assistant_message_id=saved.id)
                    conn.execute("UPDATE conversation_turn SET receipt=? WHERE client_id=?", (json.dumps(receipt), saved.turn_client_id))
            updated = replace(parent, last_message_at=max(parent.last_message_at or saved.created_at,saved.created_at),
                              updated_at=max(parent.updated_at,saved.created_at), version=parent.version + 1)
            conn.execute("UPDATE conversation SET record=? WHERE id=? AND owner=?", (encode(updated), parent.id, parent.owner_user_id))
            return saved

    async def save_message(self, msg):
        await self.append_message_atomic(msg)
