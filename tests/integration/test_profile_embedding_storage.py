"""Compile the additive PostgreSQL DDL offline; no database or migration apply."""
import hashlib
import importlib.util
import io
from pathlib import Path
import re

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "services/api/migrations/versions/0013_profile_embedding_storage.py"


def load():
    spec = importlib.util.spec_from_file_location("profile_storage_migration", PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sql():
    output = io.StringIO()
    context = MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output})
    with Operations.context(context):
        load().upgrade()
    return output.getvalue()


def test_separate_1024_storage_without_legacy_conversion_or_data_mutation():
    legacy = ROOT / "services/api/migrations/versions/0009_schedule_and_vectors.py"
    before = hashlib.sha256(legacy.read_bytes()).hexdigest()
    ddl = sql()
    assert "ADD COLUMN embedding_rag_v1 VECTOR(1024)" in ddl
    assert "USING hnsw (embedding_rag_v1 vector_cosine_ops)" in ddl
    assert "WHERE embedding_rag_v1 IS NOT NULL" in ddl
    assert not re.search(r"\b(DROP|DELETE|UPDATE|TRUNCATE|ALTER\s+COLUMN)\b", ddl, re.I)
    assert "Vector(1536)" in legacy.read_text(encoding="utf-8")
    assert hashlib.sha256(legacy.read_bytes()).hexdigest() == before


def test_all_or_none_metadata_and_model_dimension_normalization_guards():
    ddl = sql()
    assert "embedding_model_version IS NOT NULL" in ddl
    assert "embedding_dimension IS NOT NULL" in ddl and "embedded_at IS NOT NULL" in ddl
    assert "COALESCE(" in ddl and "false" in ddl
    assert "embedding_dimension = 1024" in ddl and "vector_dims(embedding_rag_v1)" in ddl
    assert "abs(1 + (embedding_rag_v1 <#> embedding_rag_v1)) <= 0.0001" in ddl
    assert "BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181" in ddl


def test_forward_only_revision_has_no_destructive_recovery():
    migration = load()
    assert (migration.revision, migration.down_revision) == ("0013", "0012")
    with pytest.raises(RuntimeError, match="forward-only"):
        migration.downgrade()
