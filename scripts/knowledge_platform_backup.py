"""Verify a snapshot backup in a newly created database. No overwrite/clean/drop.

The original cluster, database, files, backups and all previous evidence remain.
This local command includes artifacts referenced by the main runtime tenant.
"""
import asyncio
import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime

import asyncpg

from knowledge_platform import ROOT,STATE,PGROOT,TENANT,connection,checked_path,retain

TABLES=("knowledge_source","document_version","knowledge_chunk","knowledge_chunk_input","embedding_index_manifest",
    "knowledge_artifact","knowledge_ingest_version","knowledge_ingestion_job","knowledge_job_step","knowledge_review",
    "knowledge_release","knowledge_release_member","knowledge_release_pointer","knowledge_runtime_ack","audit_event","outbox_event")


async def fingerprints(conn):
    result={}
    for table in TABLES:
        # Identifiers are the fixed tuple above. No user text becomes SQL.
        value=await conn.fetchval(f"SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),'[]'::jsonb)::text FROM {table} t")
        result[table]={"rows":len(json.loads(value)),"sha256":hashlib.sha256(value.encode()).hexdigest()}
    return result


async def main():
    parameters=connection()
    stamp=datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    restore_name="campus247_knowledge_restore_"+stamp
    target=checked_path(STATE / ("backup-restore-"+stamp),ROOT)
    target.mkdir()
    report={"source_database":parameters["database"],"restore_database":restore_name,"at":datetime.now(UTC).isoformat(),
            "destructive":False,"artifact_scope":TENANT,"all_existing_state_retained":True}
    origin=await asyncpg.connect(**parameters)
    try:
        async with origin.transaction(isolation="repeatable_read",readonly=True):
            snapshot=await origin.fetchval("SELECT pg_export_snapshot()")
            expected=await fingerprints(origin)
            artifacts=await origin.fetch("SELECT * FROM knowledge_artifact WHERE tenant_id=$1 ORDER BY id",TENANT)
            environment={k:v for k,v in os.environ.items() if k.upper() in {"PATH","SYSTEMROOT","WINDIR"}}
            environment.update(PGPASSWORD=parameters["password"],PGHOST=parameters["host"],PGPORT=str(parameters["port"]),PGUSER=parameters["user"])
            dump=checked_path(target / "metadata.dump",ROOT)
            with dump.open("xb") as output:
                process=subprocess.run([str(PGROOT / "bin/pg_dump.exe"),"-Fc","--snapshot="+snapshot,parameters["database"]],
                    stdout=output,stderr=subprocess.PIPE,env=environment,creationflags=0x08000000,check=False)
            if process.returncode:
                raise RuntimeError("PG_DUMP_FAILED")
            report["dump_sha256"]=hashlib.sha256(dump.read_bytes()).hexdigest()
            files=checked_path(target / "artifacts",ROOT)
            files.mkdir()
            artifact_receipts=[]
            for row in artifacts:
                source=checked_path(STATE / "artifacts" / row["object_key"],ROOT)
                raw=source.read_bytes()
                if len(raw)!=row["byte_size"] or hashlib.sha256(raw).hexdigest()!=row["sha256"]:
                    raise RuntimeError("ARTIFACT_BACKUP_INTEGRITY")
                destination=checked_path(files / row["object_key"],ROOT)
                with destination.open("xb") as output:
                    output.write(raw)
                artifact_receipts.append({"id":str(row["id"]),"sha256":row["sha256"],"bytes":len(raw)})
        if await origin.fetchval("SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname=$1)",restore_name):
            raise RuntimeError("RESTORE_DESTINATION_EXISTS")
        # The identifier consists solely of a constant prefix and decimal timestamp.
        if not restore_name.removeprefix("campus247_knowledge_restore_").isdigit():
            raise ValueError("Invalid restore database identifier")
        await origin.execute('CREATE DATABASE "'+restore_name+'"')
        process=subprocess.run([str(PGROOT / "bin/pg_restore.exe"),"--exit-on-error","--no-owner","--no-privileges",
            "--dbname="+restore_name,str(dump)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=environment,
            creationflags=0x08000000,check=False)
        if process.returncode:
            raise RuntimeError("PG_RESTORE_FAILED")
        recovered=await asyncpg.connect(**{**parameters,"database":restore_name})
        try:
            actual=await fingerprints(recovered)
            assert actual==expected,"RESTORED_METADATA_MISMATCH"
            for receipt in artifact_receipts:
                raw=(files / receipt["id"]).read_bytes()
                assert hashlib.sha256(raw).hexdigest()==receipt["sha256"],"RESTORED_ARTIFACT_MISMATCH"
            report.update(passed=True,tables=actual,artifact_count=len(artifact_receipts),artifact_manifest=artifact_receipts)
        finally:
            await recovered.close()
    except Exception as error:
        report.update(passed=False,error_code=type(error).__name__,failure=str(error)[:300])
        raise
    finally:
        await origin.close()
        retain(target / "verification.json",report)
        print(json.dumps({"report":str(target / "verification.json"),"passed":report.get("passed"),"restored_database":restore_name,
                          "artifact_count":report.get("artifact_count")}),flush=True)


if __name__=="__main__":
    asyncio.run(main())
