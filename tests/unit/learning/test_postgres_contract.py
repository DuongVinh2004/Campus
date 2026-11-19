"""Offline migration structure and normalized adapter protocol tests.

These tests do not claim a running PostgreSQL database or SQL execution proof.
"""
from contextlib import asynccontextmanager
import copy
import importlib.util
import json
from pathlib import Path
import re
import unittest

from campus247.domain.learning import LearningError
from campus247.infrastructure.learning.repository import PostgresLearningRepository
from campus247.ports.learning_repository import COLLECTIONS


class FakeConnection:
    def __init__(self):
        self.rows = {name: {} for name in COLLECTIONS}
        self.exists, self.statements = True, []

    @asynccontextmanager
    async def transaction(self):
        before = copy.deepcopy(self.rows)
        try:
            yield self
        except Exception:
            self.rows = before
            raise

    async def fetchrow(self, query, *args):
        self.statements.append((query, args))
        return {"revision": 1} if self.exists else None

    async def fetch(self, query, *args):
        self.statements.append((query, args))
        table = re.search(r"FROM learning\.([a-z_]+)", query).group(1)
        return [{"record_key": key, "payload": value} for key, value in self.rows[table].items()]

    async def execute(self, query, *args):
        self.statements.append((query, args))
        matched = re.search(r"INSERT INTO learning\.([a-z_]+)", query)
        if matched and matched.group(1) in COLLECTIONS:
            self.rows[matched.group(1)][args[1]] = args[2]
        if matched and matched.group(1) == "tenant_state":
            self.exists = True


class FakePool:
    def __init__(self):
        self.connection = FakeConnection()

    @asynccontextmanager
    async def acquire(self):
        yield self.connection


class PostgresAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_normalized_roundtrip_updates_only_changed_rows(self):
        pool = FakePool()
        repo = PostgresLearningRepository(pool, tenant_id="test-tenant")
        async with repo.transaction() as state:
            state["terms"]["term-a"] = {"id": "term-a", "name": "A"}
            state["terms"]["term-b"] = {"id": "term-b", "name": "B"}
        pool.connection.statements.clear()
        async with repo.transaction() as state:
            self.assertEqual(state["terms"]["term-b"]["name"], "B")
            state["terms"]["term-a"]["name"] = "Updated"
        inserts = [(query, args) for query, args in pool.connection.statements if query.startswith("INSERT")]
        self.assertEqual(len(inserts), 1)
        self.assertIn("learning.terms", inserts[0][0])
        self.assertTrue(all(args[0] == "test-tenant" for _, args in pool.connection.statements))
        self.assertTrue(any("FOR UPDATE" in query for query, _ in pool.connection.statements))

    async def test_missing_store_fails_closed_without_provisioning(self):
        pool = FakePool()
        pool.connection.exists = False
        repo = PostgresLearningRepository(pool, tenant_id="test-tenant")
        with self.assertRaises(LearningError):
            async with repo.transaction():
                pass
        self.assertFalse(any(query.startswith("INSERT") for query, _ in pool.connection.statements))

    async def test_no_record_removal_and_rollback(self):
        pool = FakePool()
        repo = PostgresLearningRepository(pool, tenant_id="test-tenant")
        async with repo.transaction() as state:
            state["terms"]["term-a"] = {"id": "term-a", "name": "A"}
        with self.assertRaises(LearningError):
            async with repo.transaction() as state:
                state["terms"] = {}
        self.assertIn("term-a", pool.connection.rows["terms"])

    async def test_explicit_provision_is_separate(self):
        pool = FakePool()
        pool.connection.exists = False
        repo = PostgresLearningRepository(pool, tenant_id="test-tenant")
        await repo.provision_tenant()
        self.assertTrue(pool.connection.exists)
        self.assertEqual(len(pool.connection.statements), 1)


class MigrationStructureTests(unittest.TestCase):
    def setUp(self):
        repo = Path(__file__).resolve().parents[3]
        target = repo / "services/api/migrations/versions/0023_learning_materials.py"
        spec = importlib.util.spec_from_file_location("learning_migration", target)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.statements = []
        class Operations:
            execute = self.statements.append
        self.module.op = Operations()
        self.module.upgrade()

    def test_normalized_entities_match_repository_and_scope_constraints(self):
        tables = set()
        for query in self.statements:
            matched = re.search(r"CREATE TABLE learning\.([a-z_]+)", query)
            if matched:
                tables.add(matched.group(1))
        self.assertEqual(tables, set(COLLECTIONS) | {"tenant_state"})
        sql = "\n".join(self.statements)
        self.assertIn("fk_learning_link_session_id_scope", sql)
        self.assertIn("fk_learning_link_material_id_scope", sql)
        self.assertIn("fk_learning_current_version", sql)
        self.assertIn("fk_learning_instruction_version_scope", sql)
        self.assertIn("DEFERRABLE INITIALLY DEFERRED", sql)
        self.assertIn("learning_version_blob_immutable", sql)
        self.assertIn("BEFORE UPDATE ON learning.audit", sql)

    def test_forward_only_additive_and_retention(self):
        self.assertEqual((self.module.revision, self.module.down_revision), ("0023", "0022"))
        self.assertFalse(any(query.lstrip().upper().startswith(("DROP ", "DELETE ", "TRUNCATE ", "UPDATE PUBLIC.")) for query in self.statements))
        with self.assertRaises(RuntimeError):
            self.module.downgrade()
        for entity in COLLECTIONS:
            self.assertTrue(any(f"BEFORE DELETE ON learning.{entity} " in query for query in self.statements))


class ScopedReadConnection:
    def __init__(self):
        self.statements, self.options = [], []

    @asynccontextmanager
    async def transaction(self, **options):
        self.options.append(options)
        yield self

    async def fetchval(self, query, *args):
        self.statements.append((query, args))
        return 1

    async def fetch(self, query, *args):
        self.statements.append((query, args))
        if "learning.members" in query:
            value = {"id": "member-a", "offering_id": "class-a", "actor_subject_id": "student-a", "role": "STUDENT", "status": "ACTIVE"}
            return [{"record_key": "member-a", "payload": json.dumps(value)}]
        return []


class ScopedReadTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_only_view_resolves_resource_with_authorized_classes(self):
        pool = FakePool()
        pool.connection = ScopedReadConnection()
        repo = PostgresLearningRepository(pool, tenant_id="test-tenant")
        class Actor:
            subject_id = "student-a"
            def has_role(self, role):
                return role == "STUDENT"
        async with repo.read_view(Actor(), "content", "version-in-class-b") as state:
            self.assertEqual(state["versions"], {})
            self.assertEqual(state["materials"], {})
        self.assertEqual(pool.connection.options, [{"readonly": True, "isolation": "repeatable_read"}])
        self.assertFalse(any("FOR UPDATE" in query for query, _ in pool.connection.statements))
        queries = [(query, values) for query, values in pool.connection.statements if "learning.versions" in query]
        self.assertTrue(queries)
        self.assertTrue(all("offering_id=ANY" in query for query, _ in queries))
        self.assertTrue(any("record_key=$2" in query and values[2] == ["class-a"] for query, values in queries))
        self.assertTrue(all(values[0] == "test-tenant" for _, values in pool.connection.statements))

    async def test_private_collection_query_binds_owner_and_versions(self):
        pool = FakePool()
        pool.connection = ScopedReadConnection()
        repo = PostgresLearningRepository(pool, tenant_id="test-tenant")
        class Actor:
            subject_id = "student-a"
            def has_role(self, role):
                return role == "STUDENT"
        async with repo.read_view(Actor(), "annotations", params={"version_id": "version-a"}):
            pass
        query, args = next((query, args) for query, args in pool.connection.statements if "learning.annotations" in query)
        self.assertIn("payload->>'owner_id'=$2", query)
        self.assertIn("version_id=ANY($3::text[])", query)
        self.assertEqual(args, ("test-tenant", "student-a", [], "version-a"))
