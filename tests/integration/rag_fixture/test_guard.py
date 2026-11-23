"""Bounded offline guards and an explicit opt-in real fixture verification.

Use Python 3.12/3.13. A skipped live case is not fixture readiness evidence.
"""
from __future__ import annotations

import asyncio
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
TOOL = ROOT / "infra/local/rag-fixture/fixture.py"
spec = importlib.util.spec_from_file_location("rag_fixture_tool", TOOL)
assert spec is not None and spec.loader is not None
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class FixtureGuardTests(unittest.TestCase):
    def test_missing_dsn_does_not_fallback_to_project_configuration(self):
        with patch.dict(os.environ, {"DATABASE_URL": "deliberately-not-a-fixture"}, clear=True):
            with self.assertRaisesRegex(fixture.FixtureError, "fallback forbidden"):
                fixture.validate_dsn(os.environ.get(fixture.DSN_ENV), {"password": "a" * 32})

    def test_endpoint_guard_rejects_other_database_host_port_and_driver(self):
        state = {"password": "a" * 32}
        valid = f"postgresql+asyncpg://rag_fixture:{state['password']}@127.0.0.1:15433/campus247_rag_fixture"
        self.assertEqual(fixture.validate_dsn(valid, state), valid)
        for invalid in (
            valid.replace("campus247_rag_fixture", "campus247_local"),
            valid.replace("127.0.0.1", "localhost"),
            valid.replace("15433", "5433"),
            valid.replace("postgresql+asyncpg", "postgresql"),
            valid + "?options=-csearch_path=another_schema",
            valid.replace("rag_fixture:", "another_user:"),
            valid.replace(state["password"], "b" * 32),
        ):
            with self.assertRaises(fixture.FixtureError) as error:
                fixture.validate_dsn(invalid, state)
            self.assertEqual(str(error.exception), "fixture endpoint or database identity rejected")

    def test_unsupported_runtime_fails_before_docker_or_any_write(self):
        for version in ((3, 11), (3, 14), (4, 0)):
            with patch.object(fixture, "run_cli") as command:
                with self.assertRaisesRegex(fixture.FixtureError, "no mutation performed"):
                    fixture.check_runtime(version)
                command.assert_not_called()
        fixture.check_runtime((3, 12))
        fixture.check_runtime((3, 13))

    def test_failed_external_command_suppresses_sensitive_details(self):
        with patch.object(fixture.subprocess, "run") as process:
            process.return_value.returncode = 1
            process.return_value.stdout = "sensitive stdout"
            process.return_value.stderr = "sensitive stderr"
            with self.assertRaises(fixture.FixtureError) as error:
                fixture.run_cli(["docker", "version"])
            self.assertEqual(str(error.exception), "external command failed; output suppressed")

    def test_guard_rejects_wrong_database_before_marker_or_data_queries(self):
        class Result:
            def one(self):
                return ("campus247_local", "rag_fixture", "public")

        with patch.object(fixture, "sql", return_value=Result()) as query:
            with self.assertRaisesRegex(fixture.FixtureError, "database/user/schema rejected"):
                fixture.guard_database(object(), set(), fresh=True)
            self.assertEqual(query.call_count, 1)

    def test_changed_migration_source_is_blocked_before_db_write(self):
        with patch.object(fixture, "REVIEWED", {}):
            with self.assertRaisesRegex(fixture.FixtureError, "stop before DB mutation"):
                fixture.reviewed_sources()

    def test_reviewed_addition_preserves_historical_baseline_and_ancestry(self):
        _, script, head, tables = fixture.chain()
        # Later reviewed additive revisions extend the chain; ancestry of 0010-0013 is unchanged.
        self.assertEqual(head, "0032")   # 0023-0031 (learning) owner-approved 2026-11-16, 0032 on 2026-11-21; see fixture.REVIEWED_ADDITIONS
        self.assertEqual(script.get_revision("0013").down_revision, "0012")
        self.assertEqual(script.get_revision("0012").down_revision, "0011")
        self.assertEqual(script.get_revision("0011").down_revision, "0010")
        self.assertEqual(script.get_revision("0010").down_revision, "0009")
        self.assertEqual(len(fixture.REVIEWED), 10)
        self.assertNotIn("0011_embedding_index_manifest.py", fixture.REVIEWED)
        self.assertTrue({"0011_embedding_index_manifest.py", "0012_retrieval_scope.py"} <= set(fixture.REVIEWED_ADDITIONS))
        self.assertTrue({"retrieval_profile", "embedding_index_manifest",
                         "embedding_index_active_pointer"} <= tables)

    def test_additive_source_drift_is_blocked_before_db_write(self):
        original = Path.read_bytes

        def drift(path):
            data = original(path)
            return data + b"\n# unreviewed drift\n" if path.name == "0011_embedding_index_manifest.py" else data

        with patch.object(Path, "read_bytes", drift), patch.object(fixture, "sql") as query:
            with self.assertRaisesRegex(fixture.FixtureError, "stop before DB mutation"):
                fixture.chain()
            query.assert_not_called()

    def test_unknown_migration_is_blocked_before_db_write(self):
        original = Path.glob
        directory = ROOT / "services/api/migrations/versions"
        unknown = SimpleNamespace(name="0012_unreviewed.py", read_bytes=lambda: b"unreviewed")

        def extra_source(path, pattern):
            existing = list(original(path, pattern))
            return iter([*existing, unknown]) if path == directory and pattern == "*.py" else iter(existing)

        with patch.object(Path, "glob", extra_source), patch.object(fixture, "sql") as query:
            with self.assertRaisesRegex(fixture.FixtureError, "stop before DB mutation"):
                fixture.chain()
            query.assert_not_called()

    def test_existing_fixture_revision_mismatch_never_executes_upgrade(self):
        with patch.object(fixture, "guard_database"), patch.object(fixture, "sql") as query, \
                patch.object(fixture, "inspect_seed") as inspect, \
                patch("alembic.runtime.environment.EnvironmentContext") as upgrade:
            query.return_value.scalar.return_value = "alembic_version"
            query.return_value.all.return_value = [("0010",)]
            with self.assertRaisesRegex(fixture.FixtureError, "no implicit migration of existing data"):
                fixture.prepare(object(), object(), object(), "0011", set())
            inspect.assert_not_called()
            upgrade.assert_not_called()

    def test_existing_container_collision_blocks_resource_creation(self):
        with patch.object(fixture, "preflight"), patch.object(Path, "exists", return_value=False), \
                patch.object(fixture, "docker", return_value=fixture.CONTAINER), \
                patch.object(fixture, "run_cli") as command, patch.object(Path, "open") as write:
            with self.assertRaisesRegex(fixture.FixtureError, "target collision"):
                fixture.start()
            command.assert_not_called()
            write.assert_not_called()

    def test_foreign_docker_owner_is_rejected(self):
        container = {"Config": {"Labels": {"campus247.fixture": fixture.MARKER,
                                           "campus247.fixture.owner": "foreign-owner"}}}
        with patch.object(fixture, "receipt", return_value={"owner": "expected-owner"}), \
                patch.object(fixture, "docker", side_effect=[fixture.json.dumps([container]), "[{}]", "[{}]"]):
            with self.assertRaisesRegex(fixture.FixtureError, "Docker ownership mismatch"):
                fixture.owned()

    @unittest.skipUnless(os.environ.get(fixture.DSN_ENV), "verified fixture DSN absent: live evidence unavailable")
    def test_real_postgres_fixture_opt_in(self):
        fixture.preflight()
        before = asyncio.run(fixture.database_action("verify"))
        asyncio.run(fixture.database_action("seed"))
        after = asyncio.run(fixture.database_action("verify"))
        self.assertEqual(before, after)


if __name__ == "__main__":
    fixture.check_runtime()
    unittest.main(verbosity=2)
