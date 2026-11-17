"""Read-only P15 mapping of the exact 46 focused sources; no admission/backfill.

Originals, renditions, chunk inputs and review bindings are checked in the live
release, without OCR, embedding, model calls, schema writes, or source updates.
Legacy technical reuse never manufactures a verified business edition.
"""
import asyncio
from collections import Counter
from datetime import UTC, datetime
import json

from knowledge_platform import ROOT, TENANT, checked_path, components, retain
from campus247.application.knowledge.platform_models import PlatformError, digest
from campus247.infrastructure.knowledge.repository import json_value


async def main():
    priority_path = checked_path(ROOT / "infra/local/huce-completion-20261025-02/source-execution-priorities-01.json", ROOT)
    raw_priority = priority_path.read_bytes()
    priority = json.loads(raw_priority)
    counts = Counter(row["group"] for row in priority["sources"])
    if counts != {"CNTT": 24, "DUNG_CHUNG": 22, "DE_SAU": 71}:
        raise ValueError("Exact human-selected focus set required")
    focused = [row for row in priority["sources"] if row["group"] in {"CNTT", "DUNG_CHUNG"}]
    deferred = {row["source_id"] for row in priority["sources"] if row["group"] == "DE_SAU"}
    pool, _, platform, _ = await components()
    report = {"started_at": datetime.now(UTC), "mode": "READ_ONLY_SHADOW_MAP", "priority_sha256": digest(raw_priority),
        "model_calls": 0, "source_updates": 0, "schema_updates": 0, "release_changed": False, "sources": []}
    try:
        async with pool.acquire() as conn:
            async with conn.transaction(readonly=True, isolation="repeatable_read"):
                if await conn.fetchval("SELECT current_database()") != "campus247_knowledge_local_20261023":
                    raise ValueError("Only the exact original local database may be inspected")
                report["schema"] = await conn.fetchval("SELECT version_num FROM alembic_version")
                report["pointer"] = await platform.repo.pointer(conn)
                release_id = report["pointer"]["release_id"]
                members = [dict(row) for row in await conn.fetch("SELECT * FROM knowledge_release_member WHERE release_id=$1 ORDER BY source_id", release_id)]
                report["serving_member_count"] = len(members)
                report["membership_sha256"] = digest(members)
                report["deferred_serving_binding_sha256"] = digest([row for row in members if str(row["source_id"]) in deferred])
                report["deferred_priority_count"] = len(deferred)
                report["source_count"] = await conn.fetchval("SELECT count(*) FROM knowledge_source_scope WHERE tenant_id=$1", TENANT)
                report["version_count"] = await conn.fetchval("SELECT count(*) FROM knowledge_ingest_version WHERE tenant_id=$1", TENANT)
                member_by_source = {str(row["source_id"]): row for row in members}
                for expected in focused:
                    source_id = expected["source_id"]
                    versions = await conn.fetch("""SELECT x.version_id,a.sha256 AS original_sha256 FROM knowledge_ingest_version x
                        JOIN document_version v ON v.id=x.version_id
                        JOIN knowledge_source_scope scope ON scope.source_id=v.knowledge_source_id AND scope.tenant_id=x.tenant_id
                        JOIN knowledge_artifact a ON a.id=x.original_id AND a.tenant_id=x.tenant_id
                        WHERE v.knowledge_source_id=$1 AND x.tenant_id=$2 ORDER BY v.created_at,x.version_id""", source_id, TENANT)
                    row = {"source_id": source_id, "group": expected["group"], "title": expected["title"],
                        "legacy_evidence_category": expected["evidence_category_unchanged"], "version_count": len(versions),
                        "priority_original_sha256": expected["original_sha256"],
                        "priority_original_retained": any(item["original_sha256"] == expected["original_sha256"] for item in versions),
                        "business_edition": "UNKNOWN_NOT_BACKFILLED", "admission_granted": False,
                        "remaining": ["source-based edition/time/scope mapping", "occurrence/dependency review under the new schema"]}
                    member = member_by_source.get(source_id)
                    if member:
                        try:
                            version = await platform._eligible(conn, member["version_id"])
                            for field in ("original_id", "rendition_id"):
                                artifact = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", version[field], TENANT)
                                platform.storage.read(artifact)
                            chunks = await conn.fetch("""SELECT c.id,c.content_text,c.content_checksum,ci.index_text,ci.input_sha256,
                                c.embedding_model_version,c.embedding_dimension,c.embedding_rag_v1 IS NOT NULL AS embedded
                                FROM knowledge_chunk c LEFT JOIN knowledge_chunk_input ci ON ci.chunk_id=c.id
                                WHERE c.document_version_id=$1 ORDER BY c.ordinal,c.id""", version["version_id"])
                            if not chunks or any(digest(c["content_text"].encode()) != c["content_checksum"] or not c["index_text"]
                                or digest(c["index_text"].encode()) != c["input_sha256"] or not c["embedded"] or c["embedding_dimension"] != 1024 for c in chunks):
                                raise PlatformError(409, "LEGACY_CHUNK_BINDING", "Chunk/input/profile binding needs investigation")
                            row.update(category="REUSABLE_EXISTING_RELEASE_BINDING", version_id=str(version["version_id"]),
                                original_sha256=version["original_sha256"], rendition_sha256=version["rendition_sha256"],
                                metadata_sha256=version["metadata_sha256"], processor_profile=version["processor_profile"],
                                index_version=version["index_version"], chunk_count=len(chunks),
                                chunk_binding_sha256=digest([{key: c[key] for key in ("id", "content_checksum", "input_sha256", "embedding_model_version")} for c in chunks]),
                                original_and_rendition_hash_checked=True, new_processing_required_now=False)
                        except PlatformError as error:
                            row.update(category="BINDING_REQUIRES_INVESTIGATION", reason=error.code, new_processing_required_now="UNKNOWN")
                    else:
                        row.update(category="NOT_IN_CURRENT_RELEASE", new_processing_required_now="UNKNOWN")
                    report["sources"].append(row)
                report["mapped_focus_count"] = len(report["sources"])
                report["categories"] = dict(Counter(row["category"] for row in report["sources"]))
                report["all_priority_originals_retained"] = all(row["priority_original_retained"] for row in report["sources"])
                report["mapping_only"] = True
    finally:
        await pool.close()
    report["finished_at"] = datetime.now(UTC)
    path = checked_path(ROOT / "infra/local/knowledge-automation-20261026" / ("shadow-map-"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")+".json"), ROOT)
    retain(path, report)
    print(json.dumps({"receipt": str(path), "focus": report["mapped_focus_count"], "categories": report["categories"],
        "all_priority_originals_retained": report["all_priority_originals_retained"], "new_model_calls": 0}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
