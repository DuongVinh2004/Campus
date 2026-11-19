"""Offline audit reproductions; writes only stdout, not application files/data.

Run from repository root with .venv/Scripts/python.exe -B -X utf8
docs/PROJECT_AUDIT_20261111_REPRO.py. Exit0 means the documented defects were
reproduced with passing controls, NOT that the application is healthy.
Only synthetic actors, in-memory SQLite and ASGI transports are used.
Add --existing-tests to run the 32 selected existing controls with this binding.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import socket
import sqlite3
import sys
import threading
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT), str(ROOT / "services/api/src"),
               str(ROOT / "services/worker/src"), str(ROOT / "packages/synthetic/src")]


def readonly(event, args):
    if event == "open":
        name, mode, flags = args
        if isinstance(name, str) and name.casefold() in {os.devnull.casefold(), os.path.abspath(os.devnull).casefold()}:
            return
        if ((isinstance(mode, str) and any(c in mode for c in "wax+"))
                or isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
            raise RuntimeError("AUDIT_READONLY_FILE_WRITE")
    if event == "sqlite3.connect" and args[0] != ":memory:":
        raise RuntimeError("AUDIT_READONLY_DATABASE")
    if event == "socket.connect":
        caller = sys._getframe(1)
        if caller.f_code.co_name == "_fallback_socketpair" and caller.f_code.co_filename == socket.__file__:
            return  # asyncio's own Windows IPC; no service connection.
        raise RuntimeError("AUDIT_READONLY_NETWORK")
    if event in {"os.remove", "os.rmdir", "os.rename", "os.mkdir", "os.chmod", "os.truncate", "subprocess.Popen"}:
        raise RuntimeError("AUDIT_READONLY_MUTATION")


sys.addaudithook(readonly)

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from campus247.application.action.idempotency import IdempotencyLedger
from campus247.application.audit.writer import AuditWriter
from campus247.application.booking.availability import ExistingBooking, RoomInfo
from campus247.application.ticket.confirm import TicketConfirmationService
from campus247.application.ticket.preview import CreateTicketPayload, TicketPreviewService
from campus247.bootstrap.app import create_app
from campus247.bootstrap.settings import Settings
from campus247.domain.action.confirmation import ConfirmationTokenService
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
from campus247.infrastructure.llm.fake import DeterministicFakeProvider
from campus247.presentation.learning import create_learning_router
from campus247.presentation.rooms import create_rooms_router
from tests.api.test_citation_source import setup as citation_setup, read as citation_read
from tests.learning_review.test_privacy_boundaries import sample


class BorrowedConnection:
    """Keep the same ephemeral SQL database across ledger method calls."""
    def __init__(self, connection):
        self.connection = connection

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def close(self):
        pass  # No file exists; the connection lasts for this process.


class MemoryLedger(IdempotencyLedger):
    """Production SQL/methods on an isolated SQLite database, no disk ledger."""
    def __init__(self):
        self.lock = threading.RLock()
        # TestClient dispatches on another thread; serialize all test SQL use.
        self.connection = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._initialize_schema()

    def _connect(self):
        return BorrowedConnection(self.connection)

    @contextmanager
    def _transaction(self):
        with self.lock, super()._transaction() as connection:
            yield connection


def emit(identifier, **evidence):
    print(json.dumps({"finding": identifier, **evidence}, ensure_ascii=False), flush=True)


async def null_input():
    data = sample.__wrapped__()
    instruction = generate_uuid7()
    data.repo.state["reading_instructions"][instruction] = {
        "id": instruction, "revision": 1, "status": "ACTIVE", "session_id": generate_uuid7(),
        "version_id": data.published, "page_ranges": [{"start": 1, "end": 1}],
        "purpose": "Synthetic reading", "questions": [], "timing": "BEFORE",
    }
    session = data.repo.state["reading_instructions"][instruction]["session_id"]
    data.repo.state["sessions"][session] = {"id": session, "offering_id": data.offering}
    app = FastAPI()

    @app.middleware("http")
    async def identity(request, next_handler):
        request.state.identity = data.teacher
        request.state.revalidate_identity = lambda: data.teacher
        return await next_handler(request)

    app.include_router(create_learning_router(data.service))
    path = f"/v1/learning/reading-instructions/{instruction}"
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://audit.test") as client:
        control = await client.patch(path, json={"revision": 1, "questions": []})
        assert control.status_code == 200
        bad_questions = await client.patch(path, json={"revision": 2, "questions": None})
        bad_pages = await client.patch(path, json={"revision": 2, "page_ranges": None})
    assert bad_questions.status_code == bad_pages.status_code == 500
    assert data.repo.state["reading_instructions"][instruction]["revision"] == 2
    emit("AUD-010", valid_update_status=control.status_code,
         null_questions_status=bad_questions.status_code, null_page_ranges_status=bad_pages.status_code,
         failed_writes_rolled_back=True)


async def citation_boundary():
    data = await citation_setup()
    assert (await citation_read(data))["content_text"] == data[6].value.content_text
    conv, message = data[3], data[4]
    rows = [replace(message, id=generate_uuid7(), sequence_no=i + 1) for i in range(1999)]
    data[2]._repo._messages[conv.id] = rows + [replace(message, sequence_no=2000)]
    assert await citation_read(data)
    rows.append(replace(message, id=generate_uuid7(), sequence_no=2000))
    data[2]._repo._messages[conv.id] = rows + [replace(message, sequence_no=2001)]
    page, _, _ = await data[2].list_owned_page(data[1].subject_id, conv.id, cursor=rows[-1].id, limit=100)
    assert any(item.id == message.id for item in page)
    from campus247.application.authorization.concealment import ResourceNotFoundError
    try:
        await citation_read(data)
    except ResourceNotFoundError:
        pass
    else:
        raise AssertionError("AUD-011 no longer reproduced")
    assert data[6].calls == 2  # The denied deep read did not call the source reader.
    emit("AUD-011", source_at_2000="allowed", source_at_2001="not_found",
         message_at_2001_visible_in_owned_page=True, deep_read_source_calls=0)


async def ticket_query():
    settings = Settings(_env_file=None, ENVIRONMENT="development", DEMO_MODE=True,
        IDENTITY_SECRET_KEY="audit-synthetic-identity", CONFIRMATION_SIGNING_KEY="audit-synthetic-confirmation",
        OPENAI_API_KEY=None, GEMINI_API_KEY=None, DEEPSEEK_API_KEY=None, rag_engine="v1",
        CONVERSATION_STORAGE_MODE="ephemeral", CONSENT_STORAGE_MODE="ephemeral",
        ACTOR_STATE_STORAGE_MODE="ephemeral", AGENT_RUN_STORAGE_MODE="disabled")
    with patch("campus247.bootstrap.app.IdempotencyLedger", MemoryLedger):
        app = create_app(runtime_settings=settings, llm_gateway=DeterministicFakeProvider.default())
    adapter = SyntheticIdentityAdapter(settings.IDENTITY_SECRET_KEY, environment="development")
    headers = {"Authorization": "Bearer " + adapter.mint_token("4b419a1b-6d41-7dfb-8943-2edd9f071385")}
    payload = {"category": "GENERAL_SUPPORT", "priority": "NORMAL",
               "subject": "Synthetic audit ticket", "description": "Synthetic audit details"}
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://audit.test") as client:
        preview = await client.post("/v1/tickets/preview", headers=headers, json=payload)
        assert preview.status_code == 201
        value = preview.json()
        confirmed = await client.post(f"/v1/tickets/{value['preview_id']}/confirm", headers=headers,
            json={"confirmation_token": value["confirmation_token"], "idempotency_key": "audit-ticket-query-0001", "payload": payload})
        assert confirmed.status_code == 201
        ticket_id = confirmed.json()["ticket_id"]
        detail = await client.get(f"/v1/tickets/{ticket_id}", headers=headers)
        listing = await client.get("/v1/tickets?limit=100", headers=headers)
    assert detail.status_code == 404 and listing.status_code == 200
    assert not any(item["id"] == ticket_id for item in listing.json()["items"])
    emit("AUD-012", composition="bootstrap.create_app with ephemeral SQL ledger", preview_status=201,
         confirm_status=201, get_created_ticket_status=404, list_contains_created_ticket=False)


async def ticket_replays():
    data = sample.__wrapped__()
    actor = data.student
    tokens, ledger = ConfirmationTokenService("audit-synthetic-ticket-key"), MemoryLedger()
    payload = CreateTicketPayload("GENERAL_SUPPORT", "NORMAL", "Synthetic replay", "Synthetic request")
    preview = await TicketPreviewService(tokens).preview_create_ticket(actor, payload)

    def service():
        return TicketConfirmationService(tokens, ledger, AuditWriter())

    original = service()
    async def confirm(owner, key):
        return await owner.confirm_ticket(actor, preview.preview_id, preview.confirmation_token, key, payload)

    first = await confirm(original, "audit-ticket-replay-0001")
    same = await confirm(original, "audit-ticket-replay-0001")
    assert same.is_replay and same.ticket.id == first.ticket.id
    recreated = await confirm(service(), "audit-ticket-replay-0001")
    assert not recreated.is_replay and recreated.ticket.id != first.ticket.id
    emit("AUD-013", same_instance_replay_preserves_id=True,
         new_instance_same_ledger_creates_new_ticket=True, new_instance_is_replay=recreated.is_replay)
    another = await confirm(original, "audit-ticket-replay-0002")
    assert another.ticket.id != first.ticket.id and not another.is_replay
    emit("AUD-014", same_preview_and_token=True, different_client_key=True, second_ticket_created=True)


async def room_dates():
    room_id = generate_uuid7()
    app = FastAPI()
    app.include_router(create_rooms_router([RoomInfo(room_id, "SYN-1", "Synthetic room", 10)],
        [ExistingBooking(generate_uuid7(), room_id, datetime(2030, 1, 1, 8, tzinfo=UTC), datetime(2030, 1, 1, 9, tzinfo=UTC))]))
    path = f"/v1/rooms/{room_id}/availability"
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://audit.test") as client:
        control = await client.get(path, params={"from": "2030-01-01T08:00:00Z", "to": "2030-01-01T09:00:00Z"})
        naive = await client.get(path, params={"from": "2030-01-01T08:00:00", "to": "2030-01-01T09:00:00"})
        mixed = await client.get(path, params={"from": "2030-01-01T08:00:00Z", "to": "2030-01-01T09:00:00"})
    assert control.status_code == 200 and len(control.json()["unavailable_intervals"]) == 1
    assert naive.status_code == mixed.status_code == 500
    emit("AUD-015", valid_timezone_status=200, naive_datetime_status=500, mixed_timezone_status=500)


async def main():
    for case in (null_input, citation_boundary, ticket_query, ticket_replays, room_dates):
        await case()
    print(json.dumps({"reproduced_findings": 6, "filesystem_writes": "blocked",
                      "database": ":memory:", "real_service_calls": "blocked"}))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--existing-tests", action="store_true")
    args = parser.parse_args()
    if Path.cwd().resolve() != ROOT:
        raise SystemExit("Run from repository root")
    if args.existing_tests:
        os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        import pytest
        with patch("campus247.application.action.idempotency.IdempotencyLedger", MemoryLedger):
            result = pytest.main(["-p", "pytest_asyncio.plugin", "-p", "no:cacheprovider",
                "--capture=sys", "--tb=short", "-q", "tests/api/test_citation_source.py",
                "tests/api/test_rooms.py", "tests/api/test_ticket_write.py",
                "tests/unit/learning/test_postgres_contract.py"])
        raise SystemExit(result)
    asyncio.run(main())
