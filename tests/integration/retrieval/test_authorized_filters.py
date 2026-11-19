"""Live eligibility semantics on the guarded synthetic fixture, all probes rollback."""
from dataclasses import replace
from datetime import datetime, timezone
import importlib.util
import os
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from campus247.application.retrieval.filters import RetrievalFilterCompiler, RetrievalFilterError
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy

ROOT = Path(__file__).resolve().parents[3]
HERE = ROOT / "infra/local/rag-fixture"
AT = datetime(2026, 10, 3, tzinfo=timezone.utc)


def fixture_tool():
    spec = importlib.util.spec_from_file_location("filter_compiler_fixture", HERE / "fixture.py")
    f = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(f)
    f.check_runtime()
    f.preflight()
    f.owned()
    return f


def context(**changes):
    scope = AuthorizedScope("tenant-huce", "HUCE", "synthetic-actor", frozenset({"STUDENT"}),
                            frozenset({"STUDENT"}), frozenset({"FIT"}), frozenset({"SYN-CS"}))
    return RetrievalContext(replace(scope, **changes), "vi", AT, SimulationPolicy.ALLOW_LABELED,
                            "123456789abcdef0123456789abcdef0")


def make_eligible(c, f):
    c.execute(text("UPDATE knowledge_source SET campus_scope='HUCE',faculty_scope=ARRAY['FIT'],"
                   "program_scope=ARRAY['SYN-CS'],audiences=ARRAY['STUDENT'] WHERE id=:id"), {"id": f.SOURCE_ID})
    c.execute(text("UPDATE document_version SET effective_from='2026-10-02',"
                   "effective_until='2026-10-04' WHERE id=:id"), {"id": f.DOCUMENT_ID})


def compiler_probes(c, f):
    _, _, head, tables = f.chain()
    assert head == "0012"
    f.guard_database(c, tables)
    f.inspect_seed(c, f.dimension(c), complete=True)
    compiler = RetrievalFilterCompiler(tenant_id="tenant-huce", campus_id="HUCE", profile_allows_simulation=True)

    def query(value, selected=compiler):
        predicate = selected.compile(value)
        statement = "SELECT k.id FROM knowledge_chunk k JOIN document_version v ON v.id=k.document_version_id " \
                    "JOIN knowledge_source s ON s.id=v.knowledge_source_id WHERE " + predicate.named_sql + " ORDER BY k.id LIMIT :limit"
        return c.execute(text(statement), dict(predicate.parameters) | {"limit": 1}).scalars().all()

    assert query(context()) == []  # Unknown legacy scope/date must not authorize.
    savepoint = c.begin_nested()
    try:
        make_eligible(c, f)
        assert len(query(context())) == 1
        assert len(query(replace(context(), effective_at=datetime(2026, 10, 2, tzinfo=timezone.utc)))) == 1
        for value in [replace(context(), effective_at=datetime(2026, 10, 1, tzinfo=timezone.utc)),
                      replace(context(), effective_at=datetime(2026, 10, 4, tzinfo=timezone.utc)),
                      context(faculty_codes=frozenset({"OTHER"})), context(program_codes=frozenset({"OTHER"})),
                      context(audiences=frozenset({"SUPPORT_OFFICER"})),
                      context(program_codes=frozenset({"SYN-CS'); SELECT 'probe'; --"})),
                      replace(context(), simulation_policy=SimulationPolicy.DENY)]:
            assert query(value) == []
        assert query(context(), RetrievalFilterCompiler(tenant_id="tenant-huce", campus_id="HUCE")) == []
        for changes in [{"tenant_id": "OTHER"}, {"campus_id": "OTHER"}, {"roles": frozenset({"OTHER"})}]:
            with pytest.raises(RetrievalFilterError):
                query(context(**changes))
        c.execute(text("UPDATE document_version SET effective_until=NULL WHERE id=:id"), {"id": f.DOCUMENT_ID})
        assert query(context()) == []
        c.execute(text("UPDATE document_version SET applicability_reviewed_at=:at WHERE id=:id"), {"at": AT, "id": f.DOCUMENT_ID})
        assert len(query(context())) == 1
        for state in ("DRAFT", "SUPERSEDED", "ARCHIVED"):
            c.execute(text("UPDATE document_version SET status=:state WHERE id=:id"), {"state": state, "id": f.DOCUMENT_ID})
            assert query(context()) == []
        c.execute(text("UPDATE document_version SET status='PUBLISHED' WHERE id=:id"), {"id": f.DOCUMENT_ID})
        for approval in ("DRAFT", "REJECTED"):
            c.execute(text("UPDATE knowledge_source SET approval_status=:approval WHERE id=:id"), {"approval": approval, "id": f.SOURCE_ID})
            assert query(context()) == []
    finally:
        savepoint.rollback()
    f.verify(c, tables, head)


@pytest.mark.skipif(not os.environ.get("RAG_FIXTURE_DATABASE_URL"), reason="explicit owned fixture required; skip is not evidence")
@pytest.mark.asyncio
async def test_compiler_actual_postgres_scope_dates_approval_state_and_simulation():
    f = fixture_tool()
    dsn = f.validate_dsn(os.environ.get(f.DSN_ENV), f.receipt())
    engine = create_async_engine(dsn, poolclass=NullPool, echo=False, hide_parameters=True)
    try:
        async with engine.begin() as conn:
            await conn.exec_driver_sql("SELECT pg_advisory_xact_lock(24715433)")
            await conn.run_sync(lambda c: compiler_probes(c, f))
    finally:
        await engine.dispose()
