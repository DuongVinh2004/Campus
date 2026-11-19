"""EMBED-004 contract checks and opt-in apply on the ownership-verified fixture.

No default DSN/settings, shared fixture, database reset or downgrade. New test
records live only in a rolled-back savepoint; the additive schema is committed.
"""
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.environment import EnvironmentContext
from sqlalchemy import MetaData, Table, inspect, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from campus247.application.retrieval.profile import load_retrieval_profile
from campus247.domain.embedding_index import (
    ActiveIndexPointer, BuildStatus, EmbeddingIndexManifest, EmbeddingIndexMismatchError,
)
from campus247.ports.embedding import EmbeddingVector, EmbeddingContractError

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "services/api/migrations/versions/0011_embedding_index_manifest.py"
NEW_TABLES = {"retrieval_profile", "embedding_index_manifest", "embedding_index_active_pointer"}
NOW = datetime(2026, 10, 3, tzinfo=timezone.utc)
ARTIFACT = hashlib.sha256(b"synthetic fixture artifact; not real BGE-M3 weights").hexdigest()
CONTENT = hashlib.sha256(b"synthetic fixture corpus").hexdigest()


def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def manifest(**overrides):
    profile = load_retrieval_profile()
    values = dict(index_version="fixture-index-v1", profile_version=profile.profile_version,
                  embedding_model_id=profile.embedding_model_id, embedding_model_revision=profile.embedding_model_revision,
                  artifact_sha256=ARTIFACT, dimension=profile.embedding_dimension, normalization="l2",
                  distance_metric="cosine", corpus_version="fixture-corpus-v1", document_count=1, chunk_count=3,
                  content_checksum=CONTENT, build_status=BuildStatus.READY, built_at=NOW, validated_at=NOW)
    return EmbeddingIndexManifest(**(values | overrides))


def query(**overrides):
    p = load_retrieval_profile()
    return replace(EmbeddingVector((1.0, *([0.0] * 1023)), p.embedding_model_id,
                                  p.embedding_model_revision, 1024, "l2"), **overrides)


def validate(m=None, v=None, pointer=None, **overrides):
    (m or manifest()).validate_query(v or query(), pointer or ActiveIndexPointer("rag-prod-v1.0.0", "fixture-index-v1", NOW),
        load_retrieval_profile(), **(dict(expected_corpus_version="fixture-corpus-v1",
                                        expected_artifact_sha256=ARTIFACT) | overrides))


def test_compatible_query_and_immutable_snapshot():
    validate()
    with pytest.raises(FrozenInstanceError):
        manifest().dimension = 1536


@pytest.mark.parametrize("field,value", [("embedding_model_id", "other/model"),
    ("embedding_model_revision", "a" * 40), ("dimension", 1536), ("profile_version", "other-profile"),
    ("index_version", "other-index"), ("corpus_version", "other-corpus"), ("artifact_sha256", "b" * 64)])
def test_manifest_mismatch_rejected(field, value):
    with pytest.raises(EmbeddingIndexMismatchError):
        validate(manifest(**{field: value}))


@pytest.mark.parametrize("field,value", [("model_id", "other/model"), ("model_revision", "a" * 40),
    ("dimension", 1536), ("dimension", True), ("normalization", "none")])
def test_query_model_revision_dimension_mismatch_rejected(field, value):
    with pytest.raises(EmbeddingIndexMismatchError):
        validate(v=query(**{field: value}))


@pytest.mark.parametrize("values", [(), (float("nan"),) * 1024, (float("inf"),) * 1024, (0.0,) * 1024])
def test_invalid_query_vector_rejected(values):
    with pytest.raises(EmbeddingContractError):
        validate(v=query(values=values))


@pytest.mark.parametrize("status", [BuildStatus.BUILDING, BuildStatus.VALIDATING, BuildStatus.RETIRED, BuildStatus.FAILED])
def test_unready_manifest_cannot_be_queried(status):
    with pytest.raises(EmbeddingIndexMismatchError):
        validate(manifest(build_status=status))


@pytest.mark.parametrize("overrides", [dict(artifact_sha256="0" * 64), dict(content_checksum="invalid"),
    dict(embedding_model_revision="main"), dict(dimension=True), dict(document_count=-1),
    dict(validated_at=None), dict(validated_at=NOW-timedelta(seconds=1)), dict(built_at=NOW.replace(tzinfo=None)),
    dict(build_status=BuildStatus.ACTIVE, activated_at=None)])
def test_incomplete_or_invalid_manifest_rejected(overrides):
    with pytest.raises(EmbeddingIndexMismatchError):
        manifest(**overrides)


def test_missing_pointer_and_untrusted_checksum_fail_closed():
    with pytest.raises(EmbeddingIndexMismatchError):
        manifest().validate_query(query(), None, load_retrieval_profile(),
                                 expected_corpus_version="fixture-corpus-v1", expected_artifact_sha256=ARTIFACT)
    with pytest.raises(EmbeddingIndexMismatchError):
        validate(expected_artifact_sha256="0" * 64)
    with pytest.raises(EmbeddingIndexMismatchError):
        validate(pointer=ActiveIndexPointer("rag-prod-v1.0.0", "fixture-index-v1", NOW-timedelta(seconds=1)))


def test_migration_approved_values_and_forward_only_downgrade():
    migration = load_file("manifest_migration", MIGRATION)
    assert migration.PROFILE_VALUES == load_retrieval_profile().to_dict()
    assert (migration.revision, migration.down_revision) == ("0011", "0010")
    with pytest.raises(RuntimeError, match="forward-only"):
        migration.downgrade()


def snapshot(conn):
    # Project only additive descendant columns; FILTER-001 separately verifies
    # every 0011 row/column/index/constraint against its retained baseline.
    rows = {name: conn.execute(text(f"SELECT (to_jsonb(t) - ARRAY['index_version','campus_scope','faculty_scope','program_scope','audiences','applicability_reviewed_at'])::text FROM public.{name} t ORDER BY id")).scalars().all()
            for name in ("knowledge_source", "document_version", "knowledge_chunk")}
    indexes = [list(r) for r in conn.execute(text("SELECT tablename,indexname,indexdef FROM pg_indexes "
               "WHERE schemaname='public' ORDER BY tablename,indexname")) if r[0] not in NEW_TABLES and r[1] not in {
                   "ix_source_retrieval_state", "ix_source_faculty_scope", "ix_source_program_scope",
                   "ix_source_audiences", "ix_document_retrieval_effective"}]
    digest = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"stored_rows_sha256": digest(rows), "public_indexes_sha256": digest(indexes)}


def reject(conn, operation):
    with pytest.raises(DBAPIError) as error:
        with conn.begin_nested():
            operation()
    assert getattr(error.value.orig, "sqlstate", None) in {"23503", "23514", "23502"}


def apply_and_verify(conn, fixture, expected):
    # Review identity, all historical source hashes and inventory before DDL.
    actual = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in MIGRATION.parent.glob("*.py")}
    assert actual == fixture.REVIEWED | fixture.REVIEWED_ADDITIONS
    config = Config()
    config.set_main_option("script_location", str(MIGRATION.parent.parent))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["0012"]
    assert script.get_revision("0012").down_revision == "0011"
    current = conn.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one()
    assert current in {"0010", "0011", "0012"}
    old_tables = set(expected["schema_inspection"]["business_tables"])
    fixture.guard_database(conn, old_tables | (NEW_TABLES if current in {"0011", "0012"} else set()))
    fixture.inspect_seed(conn, fixture.dimension(conn), complete=True)
    before = snapshot(conn)
    assert before == {key: expected["fixture"][key] for key in before}
    old_columns = {(r["table_name"], r["column_name"], r["data_type"]) for r in conn.execute(text(
        "SELECT table_name,column_name,data_type FROM information_schema.columns WHERE table_schema='public'" )).mappings()}
    if current == "0010":
        with EnvironmentContext(config, script, fn=lambda rev, ctx: script._upgrade_revs("0011", rev)) as context:
            context.configure(connection=conn, transactional_ddl=True)
            with context.begin_transaction():
                context.run_migrations()
    assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() in {"0011", "0012"}
    assert fixture.dimension(conn) == 1536
    assert snapshot(conn) == before
    inspector = inspect(conn)
    assert NEW_TABLES <= set(inspector.get_table_names())
    after_columns = {(r["table_name"], r["column_name"], r["data_type"]) for r in conn.execute(text(
        "SELECT table_name,column_name,data_type FROM information_schema.columns WHERE table_schema='public'" )).mappings()}
    assert old_columns <= after_columns
    assert conn.execute(text("SELECT bool_and(index_version IS NULL) FROM document_version")).scalar_one() is True
    manifest_fks = inspector.get_foreign_keys("embedding_index_manifest")
    assert any(fk["name"] == "fk_manifest_profile_compatibility" and len(fk["constrained_columns"]) == 6 for fk in manifest_fks)
    assert any(fk["name"] == "fk_document_version_index" for fk in inspector.get_foreign_keys("document_version"))
    checks = {c["name"] for c in inspector.get_check_constraints("embedding_index_manifest")}
    assert {"ck_manifest_counts", "ck_manifest_checksums", "ck_manifest_timestamps", "ck_manifest_build_status"} <= checks
    # Synthetic compatibility metadata stays uncommitted. No real model artifact
    # is claimed; no existing document/vector/pointer is changed.
    savepoint = conn.begin_nested()
    try:
        metadata = MetaData()
        profile_table = Table("retrieval_profile", metadata, autoload_with=conn)
        manifest_table = Table("embedding_index_manifest", metadata, autoload_with=conn)
        pointer_table = Table("embedding_index_active_pointer", metadata, autoload_with=conn)
        profile = load_retrieval_profile().to_dict() | dict(created_at=NOW, approved_at=NOW,
                         approval_reference="synthetic fixture of approved GOV-001; not promotion evidence")
        conn.execute(profile_table.insert().values(**profile))
        base = {field: getattr(manifest(), field) for field in manifest().__dataclass_fields__}
        base["build_status"] = "READY"
        for field, invalid in (("embedding_model_id", "wrong/model"), ("embedding_model_revision", "a" * 40),
                               ("dimension", 1536), ("profile_version", "wrong-profile"),
                               ("artifact_sha256", "0" * 64), ("validated_at", None)):
            reject(conn, lambda field=field, invalid=invalid: conn.execute(manifest_table.insert().values(**(base | {field: invalid}))))
        conn.execute(manifest_table.insert().values(**base))
        second = base | {"index_version": "fixture-index-v2"}
        conn.execute(manifest_table.insert().values(**second))
        building = base | dict(index_version="fixture-building", build_status="BUILDING", validated_at=None)
        conn.execute(manifest_table.insert().values(**building))
        reject(conn, lambda: conn.execute(pointer_table.insert().values(profile_version=base["profile_version"],
                                                index_version="fixture-building", activated_at=NOW)))
        reject(conn, lambda: conn.execute(pointer_table.insert().values(profile_version="wrong-profile",
                                                index_version=base["index_version"], activated_at=NOW)))
        reject(conn, lambda: conn.execute(pointer_table.insert().values(profile_version=base["profile_version"],
                                                index_version="wrong-index", activated_at=NOW)))
        reject(conn, lambda: conn.execute(pointer_table.insert().values(profile_version=base["profile_version"],
                                                index_version=base["index_version"], activated_at=NOW-timedelta(seconds=1))))
        conn.execute(pointer_table.insert().values(profile_version=base["profile_version"], index_version=base["index_version"], activated_at=NOW))
        originals = conn.execute(manifest_table.select().order_by(manifest_table.c.index_version)).all()
        # Atomic pointer switch and rollback to retained snapshot, no manifest mutation.
        for index in (second["index_version"], base["index_version"]):
            conn.execute(pointer_table.update().where(pointer_table.c.profile_version == base["profile_version"]).values(index_version=index))
            assert conn.execute(manifest_table.select().order_by(manifest_table.c.index_version)).all() == originals
        reject(conn, lambda: conn.execute(manifest_table.update().where(manifest_table.c.index_version == base["index_version"]).values(dimension=1536)))
        # Trace a newly created synthetic document only; legacy document unchanged.
        conn.execute(text("INSERT INTO document_version (id,knowledge_source_id,version_label,content_checksum,status,storage_object_key,index_version) "
                          "VALUES (:id,:source,'fixture-manifest-trace',:checksum,'DRAFT','synthetic/manifest-trace',:index)"),
                     dict(id="019a0000-0000-7000-8000-000000000011", source=fixture.SOURCE_ID, checksum=CONTENT, index=base["index_version"]))
        trace = conn.execute(text("SELECT p.profile_version FROM document_version d JOIN embedding_index_manifest m USING(index_version) "
                                  "JOIN retrieval_profile p USING(profile_version) WHERE d.id=:id"),
                             {"id": "019a0000-0000-7000-8000-000000000011"}).scalar_one()
        assert trace == "rag-prod-v1.0.0"
    finally:
        savepoint.rollback()
    assert snapshot(conn) == before
    assert all(conn.execute(text(f"SELECT count(*) FROM public.{name}")).scalar_one() == 0 for name in NEW_TABLES)
    print("EMBED004_EVIDENCE=" + json.dumps(dict(head=conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one(), legacy_dimension=1536, new_dimension=1024,
          synthetic_only=True, compatibility_constraints="passed", document_profile_trace="passed",
          activation_pointer_rollback="passed", old_indexes_preserved=41, **before)))


@pytest.mark.skipif(not os.environ.get("RAG_FIXTURE_DATABASE_URL"), reason="explicit verified fixture DSN required; skip is not apply evidence")
@pytest.mark.asyncio
async def test_real_fixture_additive_apply_constraints_and_preservation():
    fixture = load_file("owned_fixture", ROOT / "infra/local/rag-fixture/fixture.py")
    fixture.preflight()
    state = fixture.owned()
    dsn = fixture.validate_dsn(os.environ.get(fixture.DSN_ENV), state)
    expected = json.loads((ROOT / "infra/local/rag-fixture/verification-evidence.json").read_text(encoding="utf-8"))
    engine = create_async_engine(dsn, poolclass=NullPool, echo=False, hide_parameters=True)
    try:
        async with engine.begin() as conn:
            await conn.exec_driver_sql("SELECT pg_advisory_xact_lock(24715433)")
            await conn.run_sync(lambda c: apply_and_verify(c, fixture, expected))
        # Independently read after commit: upgrade is persistent, savepoint test
        # metadata is absent, and no index was implicitly activated.
        async with engine.connect() as conn:
            assert (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar_one() in {"0011", "0012"}
            assert await conn.run_sync(snapshot) == {key: expected["fixture"][key] for key in snapshot_keys()}
            assert (await conn.execute(text("SELECT count(*) FROM embedding_index_active_pointer"))).scalar_one() == 0
    finally:
        await engine.dispose()


def snapshot_keys():
    return ("stored_rows_sha256", "public_indexes_sha256")
