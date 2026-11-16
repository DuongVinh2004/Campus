"""Logical SQL/API backup + restore without invoking native backup executables.

Creates a fresh database, applies the unchanged additive migrations, then inserts
records through the normal constraints/triggers. No guard is disabled, no target
is overwritten, and every backup/failed restore remains retained.
"""
import asyncio
import hashlib
import json
import re
import sqlite3
from datetime import UTC,datetime

import asyncpg

from knowledge_platform import ROOT,STATE,TENANT,connection,checked_path,retain
from knowledge_platform_backup import fingerprints

ORDER=("retrieval_profile","embedding_index_manifest","knowledge_source","knowledge_source_scope","knowledge_artifact",
    "document_version","knowledge_ingest_version","knowledge_chunk","knowledge_chunk_input","knowledge_ingestion_job",
    "knowledge_job_step","knowledge_review","knowledge_release","knowledge_release_member","knowledge_release_seal",
    "knowledge_release_pointer","knowledge_runtime_ack","knowledge_platform_request","knowledge_release_preview","audit_event","outbox_event")


def sqlite_fingerprints(conn):
    result={}
    for name, in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        if not re.fullmatch(r"[a-z_][a-z0-9_]*",name):
            raise ValueError("Unsupported runtime-store table")
        records=sorted(json.dumps(list(row),ensure_ascii=False,default=str) for row in conn.execute('SELECT * FROM "'+name+'"'))
        result[name]={"rows":len(records),"sha256":hashlib.sha256("\n".join(records).encode()).hexdigest()}
    return result


def runtime_store_backups(target):
    folder=checked_path(target / "runtime-stores",ROOT)
    folder.mkdir()
    result={}
    for name in ("conversations.sqlite3","actor-state.sqlite3","action-idempotency.sqlite3"):
        source=checked_path(STATE / name,ROOT)
        if not source.is_file():
            continue
        destination=checked_path(folder / name,ROOT)
        with destination.open("xb"):
            pass
        with sqlite3.connect(source.as_uri()+"?mode=ro",uri=True) as original:
            original.execute("BEGIN")
            expected=sqlite_fingerprints(original)
            with sqlite3.connect(destination) as recovered:
                original.backup(recovered)
                if sqlite_fingerprints(recovered)!=expected or recovered.execute("PRAGMA quick_check").fetchone()!=("ok",):
                    raise RuntimeError("RUNTIME_STORE_RESTORE_MISMATCH")
            original.rollback()
        result[name]={"tables":expected,"file_sha256":hashlib.sha256(destination.read_bytes()).hexdigest()}
    return result


def migrate_destination(parameters):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy.engine import URL
    config=Config(str(ROOT / "services/api/alembic.ini"))
    url=URL.create("postgresql+asyncpg",username=parameters["user"],password=parameters["password"],
        host=parameters["host"],port=parameters["port"],database=parameters["database"])
    config.set_main_option("sqlalchemy.url",url.render_as_string(hide_password=False).replace("%","%%"))
    command.upgrade(config,"0017")


async def main():
    parameters=connection()
    stamp=datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    target=checked_path(STATE / ("logical-backup-"+stamp),ROOT)
    target.mkdir()
    restored_name="campus247_knowledge_logical_"+stamp
    origin=await asyncpg.connect(**parameters)
    report={"source_database":parameters["database"],"restore_database":restored_name,"artifact_scope":TENANT,
            "method":"SQL API export; constraints and immutable triggers remain enabled", "destructive":False}
    try:
        async with origin.transaction(isolation="repeatable_read",readonly=True):
            expected=await fingerprints(origin)
            # Fail closed rather than silently omit a populated application table.
            tables=await origin.fetch("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            for row in tables:
                name=row["tablename"]
                if not re.fullmatch(r"[a-z_][a-z0-9_]*",name):
                    raise ValueError("Unsupported table identifier")
                if name not in {*ORDER,"alembic_version"} and await origin.fetchval(f'SELECT EXISTS(SELECT 1 FROM "{name}")'):
                    raise RuntimeError("ADDITIONAL_TABLE_REQUIRES_BACKUP_MAPPING")
            receipts=[]
            for table in ORDER:
                columns=await origin.fetch("""SELECT a.attname AS name,format_type(a.atttypid,a.atttypmod) AS type
                    FROM pg_attribute a WHERE a.attrelid=$1::regclass AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum""",table)
                if any(not re.fullmatch(r"[a-z_][a-z0-9_]*",c["name"]) for c in columns):
                    raise ValueError("Unsupported column identifier")
                projection=",".join('"'+c["name"]+'"::text' for c in columns)
                order=" ORDER BY created_at,id" if table=="knowledge_release" else ""
                records=await origin.fetch('SELECT '+projection+' FROM "'+table+'"'+order)
                payload={"table":table,"columns":[dict(c) for c in columns],"rows":[list(r) for r in records]}
                raw=json.dumps(payload,ensure_ascii=False,separators=(",",":")).encode()
                with checked_path(target / (table+".json"),ROOT).open("xb") as stream:
                    stream.write(raw)
                receipts.append({"table":table,"sha256":hashlib.sha256(raw).hexdigest(),"rows":len(records)})
            artifacts=await origin.fetch("SELECT object_key,sha256,byte_size FROM knowledge_artifact WHERE tenant_id=$1",TENANT)
            folder=checked_path(target / "artifacts",ROOT)
            folder.mkdir()
            for item in artifacts:
                source=checked_path(STATE / "artifacts" / item["object_key"],ROOT)
                raw=source.read_bytes()
                if hashlib.sha256(raw).hexdigest()!=item["sha256"] or len(raw)!=item["byte_size"]:
                    raise RuntimeError("ARTIFACT_BACKUP_CHECKSUM")
                with checked_path(folder / item["object_key"],ROOT).open("xb") as stream:
                    stream.write(raw)
        if await origin.fetchval("SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname=$1)",restored_name):
            raise RuntimeError("FRESH_RESTORE_DESTINATION_REQUIRED")
        if not restored_name.removeprefix("campus247_knowledge_logical_").isdigit():
            raise ValueError("Invalid restore identifier")
        await origin.execute('CREATE DATABASE "'+restored_name+'"')
        destination={**parameters,"database":restored_name}
        recovered=await asyncpg.connect(**destination)
        try:
            await recovered.execute("CREATE EXTENSION vector")
            await recovered.execute("CREATE EXTENSION btree_gist")
        finally:
            await recovered.close()
        await asyncio.to_thread(migrate_destination,destination)
        recovered=await asyncpg.connect(**destination)
        try:
            async with recovered.transaction():
                for receipt in receipts:
                    raw=(target / (receipt["table"]+".json")).read_bytes()
                    if hashlib.sha256(raw).hexdigest()!=receipt["sha256"]:
                        raise RuntimeError("BACKUP_METADATA_CHECKSUM")
                    payload=json.loads(raw)
                    columns=payload["columns"]
                    # Types are the original server catalog format_type output.
                    # Restore only a fixed table and its already migrated columns.
                    actual=await recovered.fetch("""SELECT a.attname AS name,format_type(a.atttypid,a.atttypmod) AS type
                        FROM pg_attribute a WHERE a.attrelid=$1::regclass AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum""",receipt["table"])
                    if [dict(c) for c in actual]!=columns:
                        raise RuntimeError("RESTORE_SCHEMA_MISMATCH")
                    sql='INSERT INTO "'+receipt["table"]+'" ('+",".join('"'+c["name"]+'"' for c in columns)+') VALUES ('
                    sql+=",".join(f'${i+1}::text::{c["type"]}' for i,c in enumerate(columns))+")"
                    await recovered.executemany(sql,payload["rows"])
            actual=await fingerprints(recovered)
            if actual!=expected:
                raise RuntimeError("RESTORED_FINGERPRINT_MISMATCH")
            for item in artifacts:
                raw=(folder / item["object_key"]).read_bytes()
                if hashlib.sha256(raw).hexdigest()!=item["sha256"]:
                    raise RuntimeError("RESTORED_ARTIFACT_CHECKSUM")
            report.update(passed=True,tables=actual,metadata_files=receipts,artifact_count=len(artifacts))
            report["runtime_stores"]=runtime_store_backups(target)
            report["cross_store_snapshot"]="individually consistent snapshots; not a distributed transaction"
        finally:
            await recovered.close()
    except Exception as error:
        report.update(passed=False,error_code=type(error).__name__,failure=str(error)[:300])
        raise
    finally:
        await origin.close()
        retain(target / "verification.json",report)
        print(json.dumps({"report":str(target / "verification.json"),"passed":report.get("passed"),"artifact_count":report.get("artifact_count")}),flush=True)


if __name__=="__main__":
    asyncio.run(main())
