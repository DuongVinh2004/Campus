"""Migration 0032 executed on a real PostgreSQL database, with the practice feature running on it through the HTTP entry.

Opt-in (CAMPUS247_LEARNING_PG_TEST=1) because it needs the local PostgreSQL cluster. Each test creates a new, empty database
named campus_practice_test_*, applies the learning migrations 0023-0032 to it, and drops it afterwards. The operational
database is only used to issue CREATE DATABASE / DROP DATABASE; nothing in it is read or changed.

The class, session and published lecture are made through the real API on the SQLite store, copied as-is into PostgreSQL,
and from then on every practice request is served by PostgresLearningRepository.
"""
import asyncio
import copy
import importlib.util
import json
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import pytest

asyncpg = pytest.importorskip("asyncpg")
from campus247.infrastructure.learning.repository import PostgresLearningRepository  # noqa: E402

from test_practice_http import OTHER, QUOTE, add_item, make_set, publish, published_set, room  # noqa: E402,F401
from test_session_revocation_boundary import Class, call, env, make_pdf  # noqa: E402,F401

ROOT = Path(__file__).resolve().parents[2]
CONNECTION = ROOT / "infra/local/knowledge-platform-20261023/local-connection.json"
VERSIONS = ROOT / "services/api/migrations/versions"
LEARNING_MIGRATIONS = ("0023", "0024", "0025", "0026", "0027", "0028", "0029", "0030", "0031", "0032")

pytestmark = pytest.mark.skipif(os.environ.get("CAMPUS247_LEARNING_PG_TEST") != "1" or not CONNECTION.is_file(),
                                reason="needs the local PostgreSQL; set CAMPUS247_LEARNING_PG_TEST=1")


class Dsn(dict):
    """Connection settings that never print the password (pytest shows fixture values when a test fails)."""

    def __repr__(self):
        return f"Dsn(database={self.get('database')!r}, port={self.get('port')!r}, password=<hidden>)"

    __str__ = __repr__

    def __or__(self, other):
        return Dsn(dict(self) | dict(other))


def owner_connection():
    value = json.loads(CONNECTION.read_text(encoding="utf-8"))
    assert (value["host"], value["user"]) == ("127.0.0.1", "knowledge_owner"), "only the loopback task-owned cluster"
    return Dsn({key: value[key] for key in ("host", "port", "user", "password", "database")})


def upgrade_statements(revision):
    (path,) = VERSIONS.glob(f"{revision}_*.py")
    spec = importlib.util.spec_from_file_location(f"learning_migration_{revision}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    statements = []

    class Operations:
        execute = statements.append

    module.op = Operations()
    module.upgrade()
    return statements


@pytest.fixture
def database():
    base = owner_connection()
    name = "campus_practice_test_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f") + f"_{os.getpid()}"
    assert re.fullmatch(r"campus_practice_test_[0-9_]+", name)

    async def create():
        admin = await asyncpg.connect(**base)
        try:
            await admin.execute(f'CREATE DATABASE "{name}"')
        finally:
            await admin.close()
        target = await asyncpg.connect(**(base | {"database": name}))
        try:
            async with target.transaction():
                for revision in LEARNING_MIGRATIONS:
                    for statement in upgrade_statements(revision):
                        await target.execute(statement)
        finally:
            await target.close()

    async def drop():
        admin = await asyncpg.connect(**base)
        try:
            await admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = $1 AND pid <> pg_backend_pid()", name)
            await admin.execute(f'DROP DATABASE IF EXISTS "{name}"')
        finally:
            await admin.close()

    try:
        asyncio.run(create())
        yield base | {"database": name}
    finally:
        asyncio.run(drop())


class ConnectPool:
    """One connection per use, opened on whichever event loop asks (the test client runs the app on its own loop)."""

    def __init__(self, dsn):
        self.dsn = dsn

    @asynccontextmanager
    async def acquire(self):
        connection = await asyncpg.connect(**self.dsn)
        try:
            yield connection
        finally:
            await connection.close()


def move_to_postgres(room, dsn):
    """Copy the class built through the API into PostgreSQL and serve every later request from there."""
    source = room.service.repository

    async def copy_state():
        async with source.transaction() as state:
            snapshot = copy.deepcopy(state)
        target = PostgresLearningRepository(ConnectPool(dsn), tenant_id=source.tenant_id, page_feedback_schema=True,
                                            page_explanations_schema=True, version_changes_schema=True, exit_tickets_schema=True,
                                            idea_cards_schema=True, accessible_text_schema=True, practice_schema=True)
        await target.provision_tenant()
        async with target.transaction() as state:
            for collection in target.collections:
                state[collection].update(snapshot.get(collection, {}))
        return target

    room.service.repository = room.client.portal.call(copy_state)
    return room.service.repository


def query(dsn, sql, *args):
    async def run():
        connection = await asyncpg.connect(**dsn)
        try:
            return await connection.fetch(sql, *args)
        finally:
            await connection.close()
    return asyncio.run(run())


def refused(dsn, sql, *args):
    """Run one statement in its own transaction and return the database's error message ('' if it was accepted)."""
    async def run():
        connection = await asyncpg.connect(**dsn)
        try:
            async with connection.transaction():
                await connection.execute(sql, *args)
            return ""
        except asyncpg.PostgresError as error:
            return str(error)
        finally:
            await connection.close()
    return asyncio.run(run())


def test_the_whole_practice_flow_runs_on_postgres(room, database):
    repository = move_to_postgres(room, database)
    assert "practice_reviews" in repository.collections
    set_id, choice_id, short_id = published_set(room)

    listed = call(room.client, "GET", f"/sessions/{room.sid}/practice-sets", room.student)
    assert listed.status_code == 200, listed.text
    assert [row["id"] for row in listed.json()["items"]] == [set_id]
    session = call(room.client, "GET", f"/practice-sets/{set_id}/session", room.student)
    assert session.status_code == 200, session.text
    assert {item["id"] for item in session.json()["items"]} == {choice_id, short_id}
    assert all("answer" not in item for item in session.json()["items"])  # answers stay hidden before answering

    right = call(room.client, "POST", f"/practice-items/{choice_id}/attempts", room.student, json={"choices": ["a"]})
    wrong = call(room.client, "POST", f"/practice-items/{short_id}/attempts", room.student, json={"text": "gỗ"})
    assert right.status_code == 200 and right.json()["correct"] is True, right.text
    assert wrong.status_code == 200 and wrong.json()["correct"] is False, wrong.text
    stats = call(room.client, "GET", f"/practice-sets/{set_id}/stats", room.teacher)
    assert stats.status_code == 200 and stats.json()["suppressed"] is True  # two students: too few to show per question

    sets = query(database, "SELECT status, session_id, offering_id FROM learning.practice_sets")
    assert [(r["status"], r["session_id"], r["offering_id"]) for r in sets] == [("PUBLISHED", room.sid, room.oid)]
    assert {r["kind"] for r in query(database, "SELECT kind FROM learning.practice_items")} == {"single_choice", "short_answer"}
    attempts = query(database, "SELECT student_id, (payload->>'correct')::boolean AS correct FROM learning.practice_attempts ORDER BY correct")
    student = room.accounts["STUDENT"]["subject_id"]
    assert [(r["student_id"], r["correct"]) for r in attempts] == [(student, False), (student, True)]
    reviews = query(database, "SELECT item_id, student_id FROM learning.practice_reviews ORDER BY item_id")
    assert sorted((r["item_id"], r["student_id"]) for r in reviews) == sorted([(choice_id, student), (short_id, student)])


def test_the_database_refuses_what_the_application_refuses(room, database):
    move_to_postgres(room, database)
    set_id, choice_id, _ = published_set(room)
    call(room.client, "POST", f"/practice-items/{choice_id}/attempts", room.student, json={"choices": ["a"]})
    draft = make_set(room, "Bản nháp")
    draft_item = add_item(room, draft["id"], draft["revision"])
    assert draft_item.status_code == 200, draft_item.text
    tenant = room.service.repository.tenant_id

    assert "append-only" in refused(database, "UPDATE learning.practice_attempts SET payload = jsonb_set(payload, '{correct}', 'false')")
    assert "retained" in refused(database, "DELETE FROM learning.practice_sets WHERE record_key = $1", set_id)
    assert "retained" in refused(database, "DELETE FROM learning.practice_reviews")
    assert "frozen" in refused(database, """UPDATE learning.practice_sets SET payload = payload || jsonb_build_object('title', 'Đổi tên',
        'revision', (payload->>'revision')::int + 1) WHERE record_key = $1""", set_id)
    assert "frozen" in refused(database, """UPDATE learning.practice_sets SET payload = payload || jsonb_build_object('status', 'DRAFT',
        'revision', (payload->>'revision')::int + 1) WHERE record_key = $1""", set_id)
    assert "only while their set is a draft" in refused(database, """UPDATE learning.practice_items SET payload = payload || jsonb_build_object(
        'prompt', 'Sửa sau khi công bố', 'revision', (payload->>'revision')::int + 1) WHERE record_key = $1""", choice_id)
    assert "identity and position" in refused(database, """UPDATE learning.practice_items SET payload = payload || jsonb_build_object(
        'ordinal', 9, 'revision', (payload->>'revision')::int + 1) WHERE record_key = $1""", draft_item.json()["id"])
    assert "only for a published set" in refused(database, """INSERT INTO learning.practice_attempts(tenant_id, record_key, payload)
        VALUES ($1, 'manual-attempt', jsonb_build_object('id', 'manual-attempt', 'item_id', $2::text, 'set_id', $3::text,
        'offering_id', $4::text, 'student_id', 'someone', 'correct', true, 'at', '2026-11-21T00:00:00Z'))""",
        tenant, draft_item.json()["id"], draft["id"], room.oid)
    assert "check constraint" in refused(database, """INSERT INTO learning.practice_reviews(tenant_id, record_key, payload)
        VALUES ($1, 'no-separator', '{"ease": 2.5, "interval_days": 0, "repetitions": 0, "due_at": "x"}')""", tenant)
    # Still accepted: the lecturer keeps editing the draft through the application.
    again = add_item(room, draft["id"], draft_item.json()["set_revision"], prompt="Câu thứ hai")
    assert again.status_code == 200, again.text
