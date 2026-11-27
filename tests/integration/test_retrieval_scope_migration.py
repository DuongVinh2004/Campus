"""FILTER-001 apply/preservation checks on the explicitly owned synthetic DB.

No default DSN, app settings, reset or downgrade. Probe rows/updates roll back.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest
from alembic.runtime.environment import EnvironmentContext
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "infra/local/rag-fixture"
MIGRATION = ROOT / "services/api/migrations/versions/0012_retrieval_scope.py"
SCOPE = ("campus_scope", "faculty_scope", "program_scope", "audiences")
NEW_INDEXES = {"ix_source_retrieval_state", "ix_source_faculty_scope", "ix_source_program_scope",
               "ix_source_audiences", "ix_document_retrieval_effective"}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def baseline():
    return json.loads((HERE / "filter-001-baseline.json").read_text(encoding="utf-8"))


def snapshot(c):
    rows = {t: [json.loads(r) for r in c.execute(text("SELECT to_jsonb(t)::text FROM public." + t + " t ORDER BY id")).scalars()]
            for t in ("knowledge_source", "document_version", "knowledge_chunk")}
    indexes = [list(r) for r in c.execute(text("SELECT tablename,indexname,indexdef FROM pg_indexes "
                   "WHERE schemaname='public' ORDER BY tablename,indexname"))]
    constraints = [list(r) for r in c.execute(text("SELECT c.relname,k.conname,pg_get_constraintdef(k.oid) "
        "FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' ORDER BY c.relname,k.conname"))]
    columns = [list(r) for r in c.execute(text("SELECT table_name,column_name,data_type,udt_name,is_nullable,column_default "
                   "FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name,ordinal_position"))]
    return dict(rows=rows, indexes=indexes, constraints=constraints, columns=columns)


def preserve(c):
    before, now = baseline(), snapshot(c)
    for table, expected in before["rows"].items():
        excluded = SCOPE if table == "knowledge_source" else (("applicability_reviewed_at",) if table == "document_version" else ())
        assert [{k: v for k, v in row.items() if k not in excluded} for row in now["rows"][table]] == [json.loads(r) for r in expected]
    for key in ("indexes", "constraints", "columns"):
        assert {tuple(r) for r in before[key]} <= {tuple(r) for r in now[key]}
    return now


def test_reviewed_ancestry_and_forward_only_recovery():
    f = load("filter_fixture", HERE / "fixture.py")
    _, script, head, _ = f.chain()
    # Later reviewed additive revisions (0014-0033) extend the same linear chain. 0033 (learning concepts, mastery, tutor:
    # four new learning.* tables, forward-only, nothing existing altered) approved by the owner on 2026-11-27.
    assert head == "0033"
    chain = [(r.revision, r.down_revision) for r in script.iterate_revisions(head, "0010")]
    assert chain[-3:] == [("0013", "0012"), ("0012", "0011"), ("0011", "0010")]
    assert [down for _, down in chain][:-1] == [revision for revision, _ in chain][1:]
    for name, expected in baseline()["migration_hashes"].items():
        assert hashlib.sha256((MIGRATION.parent / name).read_bytes()).hexdigest() == expected
    with pytest.raises(RuntimeError, match="forward-only"):
        load("scope_migration", MIGRATION).downgrade()


def reject(c, stmt, params=None):
    with pytest.raises(DBAPIError) as error:
        with c.begin_nested():
            c.execute(text(stmt), params or {})
    assert getattr(error.value.orig, "sqlstate", None) in {"23514", "23502", "2202E"}


def verify_scope(c, f):
    assert c.execute(text("SELECT campus_scope,faculty_scope,program_scope,audiences FROM knowledge_source")).all() == [(None, None, None, None)]
    assert c.execute(text("SELECT applicability_reviewed_at FROM document_version")).all() == [(None,)]
    # CHECK storage is separate from knowledge-owner authorization/audit. No
    # existing row is enriched permanently by these transactional probes.
    insert = """INSERT INTO knowledge_source
        (id,source_type,canonical_uri,title,owner_unit,authority_level,approval_status,is_synthetic,
         campus_scope,faculty_scope,program_scope,audiences)
        VALUES ('019a0000-0000-7000-8000-000000000012','SYNTHETIC_DOCUMENT',
                'synthetic://filter-probe','Synthetic scope probe','RAG Fixture',1,'DRAFT',true,
                :campus,CAST(:faculty AS varchar[]),CAST(:program AS varchar[]),CAST(:audience AS varchar[]))"""
    good = dict(campus="HUCE", faculty=["FIT"], program=["SYN-CS"], audience=["STUDENT"])
    reject(c, insert, dict.fromkeys(good))
    for field in good:
        reject(c, insert, good | {field: None})
    for changes in (dict(campus="OTHER"), dict(faculty=[]), dict(faculty=["OTHER"]),
                    dict(faculty=[None]), dict(audience=[]), dict(audience=["ALL"]),
                    dict(audience=[None]), dict(program=[None]), dict(program=[""])):
        reject(c, insert, good | changes)
    savepoint = c.begin_nested()
    try:
        # Empty programs are valid storage and authorize no program in SQL.
        c.execute(text(insert), good | dict(program=[]))
        assert c.execute(text("SELECT count(*) FROM knowledge_source WHERE canonical_uri='synthetic://filter-probe' "
            "AND program_scope && CAST(:program AS varchar[])"), dict(program=["SYN-CS"])).scalar_one() == 0
        reject(c, "UPDATE knowledge_source SET campus_scope=NULL,faculty_scope=NULL,program_scope=NULL,audiences=NULL "
                  "WHERE canonical_uri='synthetic://filter-probe'")
        c.execute(text("UPDATE knowledge_source SET title=title WHERE id=:id"), dict(id=f.SOURCE_ID))
        reject(c, "UPDATE knowledge_source SET campus_scope='HUCE' WHERE id=:id", dict(id=f.SOURCE_ID))
        reject(c, "UPDATE knowledge_source SET id='019a0000-0000-7000-8000-000000000013' WHERE id=:id", dict(id=f.SOURCE_ID))
        c.execute(text("UPDATE knowledge_source SET campus_scope=:campus,faculty_scope=CAST(:faculty AS varchar[]),"
                       "program_scope=CAST(:program AS varchar[]),audiences=CAST(:audience AS varchar[]) WHERE id=:id"),
                  good | dict(id=f.SOURCE_ID))
        reject(c, "UPDATE knowledge_source SET campus_scope=NULL,faculty_scope=NULL,program_scope=NULL,audiences=NULL WHERE id=:id", dict(id=f.SOURCE_ID))
        reject(c, "UPDATE document_version SET effective_from='2026-10-03',effective_until='2026-10-03' WHERE id=:id", dict(id=f.DOCUMENT_ID))
        # Existing lifecycle states stay unchanged. SUPERSEDED is retained for
        # audit but the SQL candidate relation only accepts PUBLISHED.
        c.execute(text("UPDATE document_version SET status='SUPERSEDED' WHERE id=:id"), dict(id=f.DOCUMENT_ID))
        assert c.execute(text("SELECT count(*) FROM document_version WHERE id=:id AND status='PUBLISHED'"), dict(id=f.DOCUMENT_ID)).scalar_one() == 0
    finally:
        savepoint.rollback()
    predicate = """s.approval_status='APPROVED' AND d.status='PUBLISHED'
        AND d.effective_from <= :at AND (d.effective_until > :at
            OR (d.effective_until IS NULL AND d.applicability_reviewed_at IS NOT NULL))
        AND s.campus_scope=:campus AND s.faculty_scope && CAST(:faculty AS varchar[])
        AND s.program_scope && CAST(:program AS varchar[]) AND s.audiences && CAST(:audience AS varchar[])
        AND (:simulation AND s.is_synthetic OR NOT s.is_synthetic)"""
    from datetime import datetime, timezone
    params = good | dict(at=datetime(2026, 10, 3, tzinfo=timezone.utc), simulation=True)
    sql = "SELECT k.id FROM knowledge_chunk k JOIN document_version d ON d.id=k.document_version_id " \
          "JOIN knowledge_source s ON s.id=d.knowledge_source_id WHERE " + predicate + " ORDER BY k.id LIMIT 30"
    assert c.execute(text(sql), params).all() == []
    probe = c.begin_nested()
    try:
        c.execute(text("UPDATE document_version SET effective_from='2026-10-02',effective_until='2026-10-04' WHERE id=:id"), dict(id=f.DOCUMENT_ID))
        # Isolate unknown scope: dates/publication/approval are now eligible.
        assert c.execute(text(sql), params).all() == []
        c.execute(text("UPDATE knowledge_source SET campus_scope=:campus,faculty_scope=CAST(:faculty AS varchar[]),"
                       "program_scope=CAST(:program AS varchar[]),audiences=CAST(:audience AS varchar[]) WHERE id=:id"),
                  good | dict(id=f.SOURCE_ID))
        assert tuple(str(r[0]) for r in c.execute(text(sql), params)) == f.CHUNK_IDS
        for changes in (dict(campus="OTHER"), dict(faculty=[]), dict(program=[]),
                        dict(audience=[]), dict(simulation=False),
                        dict(at=datetime(2026, 10, 1, tzinfo=timezone.utc)),
                        dict(at=datetime(2026, 10, 4, tzinfo=timezone.utc))):
            assert c.execute(text(sql), params | changes).all() == []
        c.execute(text("UPDATE document_version SET effective_until=NULL WHERE id=:id"), dict(id=f.DOCUMENT_ID))
        assert c.execute(text(sql), params).all() == []
        c.execute(text("UPDATE document_version SET applicability_reviewed_at=:at WHERE id=:id"), params | dict(id=f.DOCUMENT_ID))
        assert len(c.execute(text(sql), params).all()) == 3
        for state in ("DRAFT", "SUPERSEDED", "ARCHIVED"):
            c.execute(text("UPDATE document_version SET status=:state WHERE id=:id"), dict(state=state, id=f.DOCUMENT_ID))
            assert c.execute(text(sql), params).all() == []
    finally:
        probe.rollback()
    plans = {}
    # A three-row fixture cannot establish performance. Disable seqscan only
    # within the transaction to demonstrate index eligibility, not speed.
    c.execute(text("SET LOCAL enable_seqscan=off"))
    probes = {
        "state": ("SELECT id FROM knowledge_source WHERE campus_scope=:campus AND approval_status='APPROVED' AND is_synthetic=true", good),
        "faculty": ("SELECT id FROM knowledge_source WHERE faculty_scope && CAST(:faculty AS varchar[])", good),
        "program": ("SELECT id FROM knowledge_source WHERE program_scope && CAST(:program AS varchar[])", good),
        "audience": ("SELECT id FROM knowledge_source WHERE audiences && CAST(:audience AS varchar[])", good),
        "effective": ("SELECT id FROM document_version WHERE knowledge_source_id=:id AND status='PUBLISHED' AND effective_from<=:at", params | dict(id=f.SOURCE_ID)),
    }
    for name, (query, values) in probes.items():
        plan = c.execute(text("EXPLAIN (FORMAT JSON) " + query), values).scalar_one()
        assert any(index in json.dumps(plan) for index in NEW_INDEXES)
        plans[name] = plan
    c.execute(text("SET LOCAL enable_seqscan=on"))
    assert c.execute(text("SELECT count(*) FROM embedding_index_active_pointer")).scalar_one() == 0
    return plans


def apply_and_verify(c, f):
    config, script, head, tables = f.chain()
    f.guard_database(c, tables)
    f.inspect_seed(c, f.dimension(c), complete=True)
    assert f.dimension(c) == 1536
    assert c.execute(text("SELECT version_num FROM alembic_version")).scalar_one() in {"0011", "0012"}
    preserve(c)
    if c.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0011":
        with EnvironmentContext(config, script, fn=lambda rev, ctx: script._upgrade_revs(head, rev)) as context:
            context.configure(connection=c, transactional_ddl=True)
            with context.begin_transaction():
                context.run_migrations()
    assert c.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0012"
    plans = verify_scope(c, f)
    now = preserve(c)
    assert len(now["indexes"]) == len(baseline()["indexes"]) + 5
    assert len(now["constraints"]) == len(baseline()["constraints"]) + 2
    assert len(now["columns"]) == len(baseline()["columns"]) + 5
    f.verify(c, tables, head)
    print("FILTER001_EVIDENCE=" + json.dumps(dict(head=head, legacy_rows_vectors_columns="preserved",
        historical_indexes=46, historical_constraints=167, new_indexes=5, new_constraints=2,
        partial_null_and_new_unknown="rejected", reviewed_scope_reversion="rejected",
        legacy_candidate_count=0, empty_program_candidate_count=0, active_pointer_count=0,
        isolated_scope_temporal_state_and_simulation_predicates="passed", positive_sql_candidate_count=3,
        plans=plans, schema=now)))


@pytest.mark.skipif(not os.environ.get("RAG_FIXTURE_DATABASE_URL"), reason="explicit owned fixture required; skip is not apply evidence")
@pytest.mark.asyncio
async def test_owned_fixture_scope_apply_and_preservation():
    f = load("filter_fixture_live", HERE / "fixture.py")
    f.preflight()
    state = f.owned()
    dsn = f.validate_dsn(os.environ.get(f.DSN_ENV), state)
    engine = create_async_engine(dsn, poolclass=NullPool, echo=False, hide_parameters=True)
    try:
        async with engine.begin() as conn:
            await conn.exec_driver_sql("SELECT pg_advisory_xact_lock(24715433)")
            await conn.run_sync(lambda c: apply_and_verify(c, f))
        async with engine.connect() as conn:
            await conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            assert (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar_one() == "0012"
            await conn.run_sync(preserve)
    finally:
        await engine.dispose()
