"""P00 read-only runtime/schema/source inventory; only the new receipt is written."""
from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
from collections import Counter
from datetime import UTC, datetime

import asyncpg
import httpx

from knowledge_platform import ROOT, STATE, TENANT, checked_path, connection, model_budget, retain
from knowledge_platform_runtime import api_state, frontend_ready, matching_processes, process_inventory


async def inspect():
    started = datetime.now(UTC)
    conn = await asyncpg.connect(**connection(), timeout=10)
    try:
        async with conn.transaction(readonly=True, isolation="repeatable_read"):
            database = await conn.fetchval("SELECT current_database()")
            schema = await conn.fetchval("SELECT version_num FROM alembic_version")
            pointer = dict(await conn.fetchrow("SELECT * FROM knowledge_release_pointer WHERE tenant_id=$1 AND campus_id='HUCE'", TENANT))
            acks = [dict(r) for r in await conn.fetch("""SELECT instance_id,boot_id,release_id,generation,
                policy_generation,valid_until,error_code,valid_until>clock_timestamp() AS live
                FROM knowledge_runtime_ack WHERE tenant_id=$1""", TENANT)]
            sources = {str(r["source_id"]) for r in await conn.fetch("SELECT source_id FROM knowledge_source_scope WHERE tenant_id=$1", TENANT)}
            counts = dict(await conn.fetchrow("""SELECT count(*) AS versions,
                count(*) FILTER(WHERE review_state='NEEDS_REVIEW') AS needs_review
                FROM knowledge_ingest_version WHERE tenant_id=$1""", TENANT))
            members = await conn.fetch("SELECT * FROM knowledge_release_member WHERE release_id=$1 ORDER BY version_id", pointer["release_id"])
            columns = [dict(r) for r in await conn.fetch("""SELECT table_name,column_name,data_type,is_nullable
                FROM information_schema.columns WHERE table_schema='public' AND
                (table_name LIKE 'knowledge_%' OR table_name IN ('document_version','embedding_index_manifest'))
                ORDER BY table_name,ordinal_position""")]
            jobs = [dict(r) for r in await conn.fetch("SELECT state,stage,count(*) AS count FROM knowledge_ingestion_job WHERE tenant_id=$1 GROUP BY state,stage", TENANT)]
            # Trace one existing serving chunk to its immutable original without a model call.
            citation = await conn.fetchrow("""SELECT m.source_id,m.version_id,c.id AS chunk_id,c.content_checksum,
                c.content_text,c.page_start,c.page_end,c.section_path,a.object_key,a.sha256,a.byte_size
                FROM knowledge_release_member m JOIN knowledge_chunk c ON c.document_version_id=m.version_id
                JOIN knowledge_ingest_version x ON x.version_id=m.version_id
                JOIN knowledge_artifact a ON a.id=x.original_id AND a.tenant_id=x.tenant_id
                WHERE m.release_id=$1 AND x.tenant_id=$2 ORDER BY m.version_id,c.id LIMIT 1""", pointer["release_id"], TENANT)
            trace = None
            if citation:
                # The storage root comes from the serving composition, never a guessed original path.
                from knowledge_platform import components
                pool, _, platform, _ = await components()
                try:
                    raw = platform.storage.read(citation)
                    trace = {k: citation[k] for k in ("source_id", "version_id", "chunk_id", "page_start", "page_end", "section_path", "sha256")}
                    trace.update(original_verified=hashlib.sha256(raw).hexdigest() == citation["sha256"],
                        chunk_verified=hashlib.sha256(citation["content_text"].encode()).hexdigest() == citation["content_checksum"])
                finally:
                    await pool.close()
    finally:
        await conn.close()
    priority_file = checked_path(ROOT / "infra/local/huce-completion-20261025-02/source-execution-priorities-01.json", ROOT)
    priority = json.loads(priority_file.read_text(encoding="utf-8"))
    groups = Counter(r["group"] for r in priority["sources"] if r["source_id"] in sources)
    models = []
    for port in (18081, 18082):
        response = httpx.get(f"http://127.0.0.1:{port}/info", trust_env=False, timeout=10)
        response.raise_for_status()
        info = response.json()
        models.append({"port": port, **{k: info.get(k) for k in ("model_id", "model_sha", "model_dtype")}})
    from multi_agent_live_resources import latest_paid_snapshot
    paid = latest_paid_snapshot()
    status = subprocess.run(["git", "status", "--porcelain=v1", "-uall"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    tracked = [line for line in status.stdout.splitlines() if not line.startswith("??")]
    migrations = sorted((ROOT / "services/api/migrations/versions").glob("*.py"))
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    config = Config(str(ROOT / "services/api/alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "services/api/migrations"))
    rows = process_inventory()
    result = {"started_at": started, "finished_at": datetime.now(UTC), "workspace": str(ROOT.resolve()),
        "git_head": head, "tracked_changes": tracked, "tracked_change_count": len(tracked),
        "untracked_file_count": sum(line.startswith("??") for line in status.stdout.splitlines()),
        "git_warnings": status.stderr, "database": database, "schema": schema,
        "migration_heads": ScriptDirectory.from_config(config).get_heads(),
        "migration_hashes": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in migrations},
        "pointer": pointer, "acks": acks, "source_count": len(sources), "version_counts": counts,
        "serving_members": len(members), "priority_counts_existing_sources": dict(groups),
        "priority_ids_missing_from_database": sorted({r["source_id"] for r in priority["sources"]} - sources),
        "sources_without_priority": sorted(sources - {r["source_id"] for r in priority["sources"]}),
        "schema_columns": columns, "jobs": jobs, "citation_trace": trace,
        "runtime": api_state(), "frontend": frontend_ready(),
        "processes": {kind: matching_processes(rows, kind) for kind in ("api", "worker", "frontend")},
        "models": models, "native_ledger": model_budget(),
        "paid_ledger": {k: paid[k] for k in ("calls", "input_tokens_charged", "output_tokens_charged", "conservative_charged_usd", "unsettled_attempts_retained")},
        "agent_quota": "not available from runtime ledger", "model_calls_by_this_inventory": 0,
        "mutation": "new receipt only; no schema/source/release/process/budget change"}
    output = checked_path(ROOT / "infra/local/knowledge-automation-20261026" / ("baseline-" + started.strftime("%Y%m%dT%H%M%S%f") + ".json"), ROOT)
    retain(output, result)
    print(json.dumps({"receipt": str(output), "schema": schema, "source_count": len(sources),
        "serving_members": len(members), "priority_counts": dict(groups), "trace": trace is not None,
        "tracked_change_count": len(tracked)}, default=str))


if __name__ == "__main__":
    asyncio.run(inspect())
