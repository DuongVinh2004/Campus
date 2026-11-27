"""Migration 0033 (concepts, mastery, tutor): structure checked offline, without a database.

The real SQL is executed in tests/learning_entry/test_tutor_postgres.py (opt-in, needs the local PostgreSQL).
"""
import importlib.util
import re
from pathlib import Path

import pytest

from campus247.application.learning.tutor import TUTOR_COLLECTIONS

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "services/api/migrations/versions/0033_learning_concepts_tutor.py"


@pytest.fixture(scope="module")
def migration():
    spec = importlib.util.spec_from_file_location("learning_tutor_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    statements = []

    class Operations:
        execute = statements.append

    module.op = Operations()
    module.upgrade()
    return module, statements


def test_it_follows_0032_and_creates_exactly_the_tutor_collections(migration):
    module, statements = migration
    assert (module.revision, module.down_revision) == ("0033", "0032")
    created = {m.group(1) for s in statements for m in [re.search(r"CREATE TABLE learning\.([a-z_]+)", s)] if m}
    assert created == set(TUTOR_COLLECTIONS) == set(module.TUTOR_TABLES)


def test_it_is_additive_and_forward_only(migration):
    module, statements = migration
    sql = "\n".join(statements).upper()
    for forbidden in ("DROP ", "DELETE FROM", "TRUNCATE", "ALTER TABLE", "UPDATE LEARNING."):
        assert forbidden not in sql, forbidden
    with pytest.raises(RuntimeError, match="forward-only"):
        module.downgrade()


def test_every_table_is_retained_guarded_and_tied_to_its_class(migration):
    _, statements = migration
    sql = "\n".join(statements)
    for table in TUTOR_COLLECTIONS:
        assert f"BEFORE DELETE ON learning.{table}" in sql and f"BEFORE UPDATE ON learning.{table}" in sql
        assert re.search(rf"CREATE TABLE learning\.{table} \(\s*tenant_id text NOT NULL REFERENCES learning\.tenant_state", sql)
    for name in ("fk_learning_concept_offering", "fk_learning_mastery_concept", "fk_learning_tutor_settings_offering", "fk_learning_tutor_turn_item"):
        assert name in sql
    assert "tutor hints are append-only" in sql
    assert "CHECK (NOT payload ? 'reply')" in sql          # a student's free-text reply can never be stored, only its hash


def test_the_repository_reads_the_new_collections_only_with_the_schema():
    from campus247.infrastructure.learning.repository import PostgresLearningRepository
    with_schema = PostgresLearningRepository(object(), tenant_id="t", practice_schema=True, tutor_schema=True)
    without = PostgresLearningRepository(object(), tenant_id="t", practice_schema=True)
    assert set(TUTOR_COLLECTIONS) <= set(with_schema.collections) and not set(TUTOR_COLLECTIONS) & set(without.collections)
    assert with_schema.collections.index("practice_items") < with_schema.collections.index("tutor_turns")
