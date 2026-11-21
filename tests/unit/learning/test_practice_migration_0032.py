"""Migration 0032 (practice questions): structure checked offline, without a database.

The real SQL is executed in tests/learning_entry/test_practice_postgres.py (opt-in, needs the local PostgreSQL).
"""
import importlib.util
import re
from pathlib import Path

import pytest

from campus247.application.learning.practice_sets import PRACTICE_COLLECTIONS
from campus247.infrastructure.learning.repository import PostgresLearningRepository

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "services/api/migrations/versions/0032_learning_practice.py"


@pytest.fixture(scope="module")
def migration():
    spec = importlib.util.spec_from_file_location("learning_practice_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    statements = []

    class Operations:
        execute = statements.append

    module.op = Operations()
    module.upgrade()
    return module, statements


def test_it_follows_0031_and_creates_exactly_the_practice_collections(migration):
    module, statements = migration
    assert (module.revision, module.down_revision) == ("0032", "0031")
    created = {m.group(1) for s in statements for m in [re.search(r"CREATE TABLE learning\.([a-z_]+)", s)] if m}
    assert created == set(PRACTICE_COLLECTIONS) == set(module.PRACTICE_TABLES)


def test_it_is_additive_and_forward_only(migration):
    module, statements = migration
    sql = "\n".join(statements).upper()
    for forbidden in ("DROP ", "DELETE FROM", "TRUNCATE", "ALTER TABLE", "UPDATE LEARNING."):
        assert forbidden not in sql, forbidden
    with pytest.raises(RuntimeError, match="forward-only"):
        module.downgrade()


def test_every_table_is_retained_and_tied_to_its_class(migration):
    _, statements = migration
    sql = "\n".join(statements)
    for table in PRACTICE_COLLECTIONS:
        assert f"BEFORE DELETE ON learning.{table}" in sql
        assert re.search(rf"CREATE TABLE learning\.{table} \(\s*tenant_id text NOT NULL REFERENCES learning\.tenant_state", sql)
    # Sets point at the session, version and material of the same class; questions and answers at their set.
    for name in ("fk_learning_practice_set_session_scope", "fk_learning_practice_set_version_scope", "fk_learning_practice_set_version_material",
                 "fk_learning_practice_item_set_scope", "fk_learning_practice_attempt_item", "fk_learning_practice_attempt_set_scope",
                 "fk_learning_practice_review_item"):
        assert name in sql
    assert sql.count("DEFERRABLE INITIALLY DEFERRED") >= 8  # the repository writes collections one after another in one transaction


def test_the_guard_reads_the_payload_not_generated_columns(migration):
    # In a BEFORE trigger the generated columns of NEW are not computed yet.
    _, statements = migration
    function = next(s for s in statements if "preserve_practice_record" in s and "CREATE FUNCTION" in s)
    assert not re.search(r"NEW\.(status|set_id|offering_id|ordinal|item_id|student_id)\b", function)


def test_the_repository_reads_and_writes_the_practice_tables_only_when_the_schema_is_there():
    without = PostgresLearningRepository(object(), tenant_id="t")
    assert not set(PRACTICE_COLLECTIONS) & set(without.collections)
    full = PostgresLearningRepository(object(), tenant_id="t", accessible_text_schema=True, practice_schema=True)
    assert full.collections[-len(PRACTICE_COLLECTIONS):] == PRACTICE_COLLECTIONS
