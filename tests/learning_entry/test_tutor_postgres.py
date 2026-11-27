"""Migration 0033 executed on a real PostgreSQL database, with concepts, mastery and the tutor running on it through the HTTP entry.

Opt-in (CAMPUS247_LEARNING_PG_TEST=1), like test_practice_postgres.py: each test creates a new, empty database named
campus_practice_test_*, applies the learning migrations 0023-0033 to it, and drops it afterwards. The operational database is only
used to issue CREATE DATABASE / DROP DATABASE; nothing in it is read or changed.
"""
import asyncio
import copy
import json
import os
import re
from datetime import datetime, timezone

import pytest

asyncpg = pytest.importorskip("asyncpg")
from campus247.features import runtime  # noqa: E402
from campus247.infrastructure.learning.repository import PostgresLearningRepository  # noqa: E402

import test_practice_postgres as base  # noqa: E402
from test_practice_http import published_set, room  # noqa: E402,F401
from test_session_revocation_boundary import call, env  # noqa: E402,F401
from test_tutor_http import LEAD, answer, concept, enable_tutor, hint, pages  # noqa: E402,F401

MIGRATIONS = base.LEARNING_MIGRATIONS + ("0033",)
pytestmark = base.pytestmark


@pytest.fixture
def flags(monkeypatch):
    monkeypatch.setattr(runtime, "value", lambda key, fallback: {"learning.mastery_map": True}.get(key, fallback))


@pytest.fixture
def database():
    owner = base.owner_connection()
    name = "campus_practice_test_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f") + f"_{os.getpid()}"
    assert re.fullmatch(r"campus_practice_test_[0-9_]+", name)

    async def create():
        admin = await asyncpg.connect(**owner)
        try:
            await admin.execute(f'CREATE DATABASE "{name}"')
        finally:
            await admin.close()
        target = await asyncpg.connect(**(owner | {"database": name}))
        try:
            async with target.transaction():
                for revision in MIGRATIONS:
                    for statement in base.upgrade_statements(revision):
                        await target.execute(statement)
        finally:
            await target.close()

    async def drop():
        admin = await asyncpg.connect(**owner)
        try:
            await admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = $1 AND pid <> pg_backend_pid()", name)
            await admin.execute(f'DROP DATABASE IF EXISTS "{name}"')
        finally:
            await admin.close()

    try:
        asyncio.run(create())
        yield owner | {"database": name}
    finally:
        asyncio.run(drop())


def move_to_postgres(room, dsn):
    source = room.service.repository

    async def copy_state():
        async with source.transaction() as state:
            snapshot = copy.deepcopy(state)
        target = PostgresLearningRepository(base.ConnectPool(dsn), tenant_id=source.tenant_id, page_feedback_schema=True,
                                            page_explanations_schema=True, version_changes_schema=True, exit_tickets_schema=True,
                                            idea_cards_schema=True, accessible_text_schema=True, practice_schema=True, tutor_schema=True)
        await target.provision_tenant()
        async with target.transaction() as state:
            for collection in target.collections:
                state[collection].update(snapshot.get(collection, {}))
        return target

    room.service.repository = room.client.portal.call(copy_state)
    return room.service.repository


def test_concepts_mastery_and_hints_run_on_postgres(room, database, flags):
    repository = move_to_postgres(room, database)
    assert "tutor_turns" in repository.collections
    _, choice_id, _ = published_set(room)
    made = concept(room)
    assert made.status_code == 200, made.text
    assert enable_tutor(room).status_code == 200
    answer(room, choice_id, ["b"])
    given = hint(room, choice_id, reply="Em đoán là chịu kéo")
    assert given.status_code == 200 and given.json()["quote"] == LEAD, given.text
    student = room.accounts["STUDENT"]["subject_id"]
    mastery = base.query(database, "SELECT concept_id, student_id, (payload->>'attempts')::int AS n FROM learning.concept_mastery")
    assert [(r["concept_id"], r["student_id"], r["n"]) for r in mastery] == [(made.json()["id"], student, 1)]
    turns = base.query(database, "SELECT payload FROM learning.tutor_turns")
    assert len(turns) == 1 and "Em đoán" not in json.dumps(json.loads(turns[0]["payload"]), ensure_ascii=False)
    settings = base.query(database, "SELECT (payload->>'tutor_enabled')::boolean AS on FROM learning.tutor_settings")
    assert [r["on"] for r in settings] == [True]


def test_the_database_refuses_what_the_application_refuses(room, database, flags):
    move_to_postgres(room, database)
    _, choice_id, _ = published_set(room)
    cid = concept(room).json()["id"]
    enable_tutor(room)
    answer(room, choice_id, ["b"])
    hint(room, choice_id)
    tenant = room.service.repository.tenant_id
    assert "append-only" in base.refused(database, "UPDATE learning.tutor_turns SET payload = jsonb_set(payload, '{level}', '3')")
    assert "retained" in base.refused(database, "DELETE FROM learning.concepts")
    assert "retained" in base.refused(database, "DELETE FROM learning.concept_mastery")
    assert "only grow" in base.refused(database, "UPDATE learning.concept_mastery SET payload = jsonb_set(payload, '{attempts}', '0')")
    assert "identity is immutable" in base.refused(database, """UPDATE learning.concepts SET payload = payload || jsonb_build_object(
        'offering_id', 'other', 'revision', (payload->>'revision')::int + 1) WHERE record_key = $1""", cid)
    assert "forward only" in base.refused(database, "UPDATE learning.tutor_settings SET payload = jsonb_set(payload, '{tutor_enabled}', 'false')")
    assert "check constraint" in base.refused(database, """INSERT INTO learning.tutor_turns(tenant_id, record_key, payload)
        SELECT $1, 'manual', payload || jsonb_build_object('id', 'manual', 'reply', 'văn bản tự do') FROM learning.tutor_turns LIMIT 1""", tenant)
    # A retired concept is frozen in the database too.
    retired = call(room.client, "PATCH", f"/mastery/concepts/{cid}", room.teacher, json={"revision": 1, "status": "RETIRED"})
    assert retired.status_code == 200, retired.text
    assert "frozen" in base.refused(database, """UPDATE learning.concepts SET payload = payload || jsonb_build_object(
        'label', 'Sửa', 'revision', (payload->>'revision')::int + 1) WHERE record_key = $1""", cid)
