"""Production lexical query/fallback on PostgreSQL, with rollback-only synthetic probes."""
from dataclasses import replace
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from campus247.application.retrieval.filters import RetrievalFilterCompiler, RetrievalFilterError
from campus247.domain.retrieval import SimulationPolicy
from campus247.infrastructure.retrieval.lexical import LexicalSearchAdapter
from tests.integration.retrieval.test_authorized_filters import context, fixture_tool, make_eligible


class RecordingConnection:
    def __init__(self, driver):
        self.driver = driver
        self.calls = []

    async def fetch(self, sql, *args):
        self.calls.append((sql, args))
        return await self.driver.fetch(sql, *args)


def adapter(simulation=True):
    return LexicalSearchAdapter(filter_compiler=RetrievalFilterCompiler(
        tenant_id="tenant-huce", campus_id="HUCE", profile_allows_simulation=simulation))


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [None, {}, {"roles": ["SYSTEM_ADMIN"]}])
async def test_missing_or_untyped_context_is_rejected_before_database_access(value):
    class MustNotQuery:
        async def fetch(self, *args):
            pytest.fail("untrusted context reached SQL")
    with pytest.raises(RetrievalFilterError, match="typed trusted"):
        await adapter().search("fixture", context=value, conn=MustNotQuery())


@pytest.mark.asyncio
async def test_missing_compiler_or_binding_and_invalid_limit_fail_closed():
    with pytest.raises(RetrievalFilterError, match="compiler"):
        await LexicalSearchAdapter().search("fixture", context=context())
    with pytest.raises(RetrievalFilterError, match="database binding"):
        await adapter().search("fixture", context=context())
    for limit in (0, -1, 31, True, "1"):
        with pytest.raises(RetrievalFilterError, match="limit"):
            await adapter().search("fixture", context=context(), top_k=limit)


@pytest.mark.skipif(not os.environ.get("RAG_FIXTURE_DATABASE_URL"), reason="explicit owned fixture required; skip is not evidence")
@pytest.mark.asyncio
async def test_primary_and_fallback_sql_filter_before_rank_limit_and_zero_leakage():
    f = fixture_tool()
    dsn = f.validate_dsn(os.environ.get(f.DSN_ENV), f.receipt())
    engine = create_async_engine(dsn, poolclass=NullPool, echo=False, hide_parameters=True)
    plans = {}
    try:
        async with engine.begin() as conn:
            await conn.exec_driver_sql("SELECT pg_advisory_xact_lock(24715433)")
            _, _, head, tables = f.chain()
            await conn.run_sync(lambda c: f.guard_database(c, tables))
            raw = await conn.get_raw_connection()
            recorded = RecordingConnection(raw.driver_connection)
            service = adapter()
            assert await service.search("fixture", context=context(), conn=recorded) == []
            probe = await conn.begin_nested()
            try:
                await conn.run_sync(lambda c: make_eligible(c, f))
                # Retained seed deliberately has NULL lexical vectors. Populate
                # only inside this savepoint so real FTS has a positive control.
                await conn.execute(text("UPDATE knowledge_chunk SET content_tsv=to_tsvector('simple',content_text) "
                                        "WHERE document_version_id=:id"), {"id": f.DOCUMENT_ID})
                # An unauthorized matching chunk has substantially higher lexical
                # rank. At LIMIT 1 it must neither hide nor replace an eligible hit.
                await conn.execute(text("INSERT INTO knowledge_source (id,source_type,canonical_uri,title,owner_unit,"
                    "authority_level,approval_status,is_synthetic,campus_scope,faculty_scope,program_scope,audiences) "
                    "VALUES ('019a0000-0000-7000-8000-000000000101','SYNTHETIC_DOCUMENT','synthetic://lexical-denied',"
                    "'Synthetic denied source','RAG Fixture',1,'APPROVED',true,'HUCE',ARRAY['FIT'],ARRAY['OTHER'],ARRAY['SUPPORT_OFFICER'])"))
                await conn.execute(text("INSERT INTO document_version (id,knowledge_source_id,version_label,content_checksum,"
                    "status,storage_object_key,effective_from,effective_until,published_at) VALUES "
                    "('019a0000-0000-7000-8000-000000000102','019a0000-0000-7000-8000-000000000101','synthetic-denied',"
                    ":checksum,'PUBLISHED','synthetic/lexical-denied','2026-10-02','2026-10-04',:at)"), {"checksum": "a" * 64, "at": context().effective_at})
                content = "fixture " * 100
                await conn.execute(text("INSERT INTO knowledge_chunk (id,document_version_id,ordinal,section_path,content_text,content_checksum,content_tsv) "
                    "VALUES ('019a0000-0000-7000-8000-000000000103','019a0000-0000-7000-8000-000000000102',1,'Synthetic denied',:content,:checksum,to_tsvector('simple',:content))"),
                    {"content": content, "checksum": hashlib.sha256(content.encode()).hexdigest()})
                strongest = await recorded.driver.fetchval("SELECT id FROM knowledge_chunk "
                    "ORDER BY ts_rank_cd(content_tsv,plainto_tsquery('simple',$1)) DESC NULLS LAST LIMIT 1", "fixture")
                assert str(strongest) == "019a0000-0000-7000-8000-000000000103"
                for query, calls in [("fixture", 1), ("fixture unreachabletoken", 2)]:
                    recorded.calls.clear()
                    result = await service.search(query, top_k=1, context=context(), conn=recorded)
                    assert len(result) == 1 and result[0].chunk_id in f.CHUNK_IDS
                    assert len(recorded.calls) == calls
                    for number, (statement, values) in enumerate(recorded.calls):
                        predicate = service._filter_compiler.compile(context())
                        assert predicate.asyncpg_sql in statement
                        assert statement.index(predicate.asyncpg_sql) < statement.index("ORDER BY") < statement.index("LIMIT")
                        assert values[2:] == predicate.values
                        await conn.exec_driver_sql("SET LOCAL enable_seqscan=off")
                        plan = await recorded.driver.fetchval("EXPLAIN (FORMAT JSON) " + statement, *values)
                        parsed = json.loads(plan) if isinstance(plan, str) else plan
                        # FILTER-003 requires an appropriate predicate index,
                        # not a particular planner choice on four synthetic rows.
                        assert "ix_document_retrieval_effective" in json.dumps(parsed)
                        plans[f"{query}:{number}"] = parsed
                        await conn.exec_driver_sql("SET LOCAL enable_seqscan=on")
                    for value in [context(faculty_codes=frozenset({"OTHER"})), context(program_codes=frozenset({"EMPTY"})),
                                  context(audiences=frozenset({"SYSTEM_ADMIN"})),
                                  replace(context(), effective_at=context().effective_at - timedelta(days=2)),
                                  replace(context(), effective_at=context().effective_at + timedelta(days=1)),
                                  replace(context(), simulation_policy=SimulationPolicy.DENY)]:
                        assert await service.search(query, context=value, conn=recorded) == []
                    for state in ("DRAFT", "SUPERSEDED", "ARCHIVED"):
                        await conn.execute(text("UPDATE document_version SET status=:state WHERE id=:id"), {"state": state, "id": f.DOCUMENT_ID})
                        assert await service.search(query, context=context(), conn=recorded) == []
                    await conn.execute(text("UPDATE document_version SET status='PUBLISHED' WHERE id=:id"), {"id": f.DOCUMENT_ID})
                    for approval in ("DRAFT", "REJECTED"):
                        await conn.execute(text("UPDATE knowledge_source SET approval_status=:approval WHERE id=:id"), {"approval": approval, "id": f.SOURCE_ID})
                        assert await service.search(query, context=context(), conn=recorded) == []
                    await conn.execute(text("UPDATE knowledge_source SET approval_status='APPROVED' WHERE id=:id"), {"id": f.SOURCE_ID})
                await conn.exec_driver_sql("SET LOCAL enable_seqscan=off")
                gin_plan = await recorded.driver.fetchval("EXPLAIN (FORMAT JSON) SELECT id FROM knowledge_chunk "
                    "WHERE content_tsv @@ plainto_tsquery('simple',$1)", "fixture")
                gin_plan = json.loads(gin_plan) if isinstance(gin_plan, str) else gin_plan
                assert "ix_knowledge_chunk_tsv" in json.dumps(gin_plan)
                plans["gin_text_eligibility_only"] = gin_plan
                await conn.exec_driver_sql("SET LOCAL enable_seqscan=on")
                plans["index_evidence"] = "eligibility with enable_seqscan=off; not benchmark"
            finally:
                await probe.rollback()
            await conn.run_sync(lambda c: f.verify(c, tables, head))
        # Plans contain only synthetic query/relations. Retain with pytest artifacts.
        directory = Path(os.environ["RAG_EXECUTION_EVIDENCE_DIR"])
        assert directory.resolve(strict=True).is_relative_to(f.ROOT) and not directory.is_symlink() and not directory.is_junction()
        output = directory / "lexical-filter-explain.json"
        with output.open("x", encoding="utf-8") as file:
            json.dump(plans, file, sort_keys=True, indent=2)
    finally:
        await engine.dispose()
