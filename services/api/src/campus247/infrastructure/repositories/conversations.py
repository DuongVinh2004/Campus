"""Explicit-pool PostgreSQL chat storage; no DSN, migration or policy defaults.

Requires the reviewed final-message schema and an explicitly supplied content
validator. Construction does not grant database access or activate this adapter.
"""
from __future__ import annotations

import asyncio
from dataclasses import replace
from functools import wraps
import json
import re
from typing import Callable

from campus247.application.conversation.messages import (
    ContentFormat, ConversationRecord, ConversationStatus, MessageRecord, SenderType,
)
from campus247.application.conversation.stream_result import ApiCitation, StreamCitation


def _bounded_operation(method):
    @wraps(method)
    async def bounded(self, *args, **kwargs):
        # One deadline includes pool wait, row lock, all queries and rollback.
        # Per-query timeouts alone could multiply the operation's budget.
        async with asyncio.timeout(self._timeout):
            return await method(self, *args, **kwargs)
    return bounded


def _conversation(row) -> ConversationRecord | None:
    if row is None:
        return None
    return ConversationRecord(
        id=str(row["id"]), owner_user_id=str(row["owner_user_id"]),
        status=ConversationStatus(row["status"]), channel=row["channel"],
        created_at=row["created_at"], updated_at=row["updated_at"],
        retention_expires_at=row["retention_expires_at"], version=row["version"],
        last_message_at=row["last_message_at"],
    )


def _citations(value) -> tuple[StreamCitation, ...]:
    items = json.loads(value) if isinstance(value, str) else value
    if not isinstance(items, list) or len(items) > 20:
        raise ValueError("invalid persisted citation map")
    result = []
    for item in items:
        if not isinstance(item, dict) or set(item) != {"turn_citation_id", "citation"}:
            raise ValueError("invalid persisted citation map")
        local = item["turn_citation_id"]
        if not isinstance(local, str) or re.fullmatch(r"CIT-[0-9]{3,}", local) is None:
            raise ValueError("invalid persisted citation identity")
        citation = ApiCitation.model_validate(item["citation"])
        result.append(StreamCitation(local, citation.model_dump_json(exclude_none=True)))
    if (len({item.turn_citation_id for item in result}) != len(result)
            or len({json.loads(item.citation_json)["citation_id"] for item in result}) != len(result)):
        raise ValueError("duplicate persisted citation identity")
    return tuple(result)


def _message(row) -> MessageRecord:
    return MessageRecord(
        id=str(row["id"]), conversation_id=str(row["conversation_id"]),
        sequence_no=row["sequence_no"], sender_type=SenderType(row["sender_type"]),
        content_redacted=row["content_redacted"], content_format=ContentFormat(row["content_format"]),
        created_at=row["created_at"], sender_user_id=str(row["sender_user_id"]) if row["sender_user_id"] else None,
        citation_set_id=str(row["citation_set_id"]) if row["citation_set_id"] else None,
        redacted_at=row["redacted_at"], finish_status=row["finish_status"],
        response_class=row["response_class"], citations=_citations(row["citations"]),
    )


class PostgresConversationRepository:
    def __init__(self, *, pool, validate_content: Callable[[str], bool], timeout_seconds: float = 2.0):
        if pool is None or not callable(validate_content):
            raise ValueError("explicit pool and reviewed content validator required")
        if isinstance(timeout_seconds, bool) or not 0 < timeout_seconds <= 5:
            raise ValueError("bounded database timeout required")
        self._pool, self._validate_content, self._timeout = pool, validate_content, timeout_seconds

    @_bounded_operation
    async def save_conversation(self, conv: ConversationRecord) -> None:
        # Creation only. Existing IDs are never overwritten by this adapter.
        async with self._pool.acquire(timeout=self._timeout) as conn:
            await conn.execute(
                "INSERT INTO conversation (id,owner_user_id,status,channel,created_at,updated_at,"
                "retention_expires_at,version,last_message_at) VALUES ($1::uuid,$2::uuid,$3,$4,$5,$6,$7,$8,$9)",
                conv.id, conv.owner_user_id, str(conv.status), conv.channel, conv.created_at,
                conv.updated_at, conv.retention_expires_at, conv.version, conv.last_message_at,
                timeout=self._timeout,
            )

    @_bounded_operation
    async def get_conversation(self, conv_id: str) -> ConversationRecord | None:
        async with self._pool.acquire(timeout=self._timeout) as conn:
            return _conversation(await conn.fetchrow("SELECT * FROM conversation WHERE id=$1::uuid", conv_id,
                                                     timeout=self._timeout))

    @_bounded_operation
    async def list_messages(self, conv_id: str) -> list[MessageRecord]:
        async with self._pool.acquire(timeout=self._timeout) as conn:
            rows = await conn.fetch("SELECT * FROM message WHERE conversation_id=$1::uuid ORDER BY sequence_no", conv_id,
                                    timeout=self._timeout)
        return [_message(row) for row in rows]

    @_bounded_operation
    async def get_next_sequence_no(self, conv_id: str) -> int:
        async with self._pool.acquire(timeout=self._timeout) as conn:
            return await conn.fetchval("SELECT COALESCE(MAX(sequence_no),0)+1 FROM message WHERE conversation_id=$1::uuid",
                                       conv_id, timeout=self._timeout)

    async def save_message(self, msg: MessageRecord) -> None:
        raise ValueError("durable message writes require atomic append")

    @_bounded_operation
    async def append_message_atomic(self, msg: MessageRecord) -> MessageRecord:
        if self._validate_content(msg.content_redacted) is not True:
            raise ValueError("message content failed reviewed persistence policy")
        payload = [citation.to_dict() for citation in msg.citations]
        citations = _citations(payload)
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        async with self._pool.acquire(timeout=self._timeout) as conn:
            async with conn.transaction():
                # Serialize all appenders on the same parent, including another
                # process. Unique constraints still reject conflicting IDs.
                parent = await conn.fetchrow("SELECT * FROM conversation WHERE id=$1::uuid FOR UPDATE",
                                             msg.conversation_id, timeout=self._timeout)
                conversation = _conversation(parent)
                if conversation is None or conversation.status in {ConversationStatus.CLOSED, ConversationStatus.ARCHIVED}:
                    raise ValueError("conversation unavailable for append")
                sequence = await conn.fetchval(
                    "SELECT COALESCE(MAX(sequence_no),0)+1 FROM message WHERE conversation_id=$1::uuid",
                    msg.conversation_id, timeout=self._timeout,
                )
                stored = replace(msg, sequence_no=sequence, citations=citations)
                await conn.execute(
                    "INSERT INTO message (id,conversation_id,sequence_no,sender_type,content_redacted,content_format,"
                    "created_at,sender_user_id,citation_set_id,redacted_at,finish_status,response_class,citations) "
                    "VALUES ($1::uuid,$2::uuid,$3,$4,$5,$6,$7,$8::uuid,$9::uuid,$10,$11,$12,$13::jsonb)",
                    stored.id, stored.conversation_id, stored.sequence_no, str(stored.sender_type), stored.content_redacted,
                    str(stored.content_format), stored.created_at, stored.sender_user_id, stored.citation_set_id,
                    stored.redacted_at, stored.finish_status, stored.response_class, encoded, timeout=self._timeout,
                )
                await conn.execute(
                    "UPDATE conversation SET last_message_at=$2,updated_at=$2,version=version+1 WHERE id=$1::uuid",
                    stored.conversation_id, stored.created_at, timeout=self._timeout,
                )
                return stored
