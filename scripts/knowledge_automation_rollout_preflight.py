"""Read-only exact-main preflight; retain fingerprints before approved rollout."""
import asyncio
from datetime import UTC, datetime
import hashlib
import json
import shutil
import sqlite3

import asyncpg

from knowledge_platform import ROOT, STATE, checked_path, connection, rehearsal_bundle_paths, retain
from knowledge_automation_checkpoint_20261027 import database
from knowledge_automation_checkpoint_blocked import command
from knowledge_automation_live_eval import paid
from knowledge_automation_restore import fingerprint
from knowledge_automation_restore_bundle import sqlite_fingerprint, SQLITE_FILES


async def main():
    scope = ROOT / "infra/local/knowledge-automation-20261026"
    baseline = json.loads((scope / "checkpoint-ready-20261027T075315423548.json").read_bytes())
    main_db = await database(connection())
    if (main_db["schema"], main_db["source_count"], main_db["version_count"], main_db["serving_members"]) != ("0018",120,330,114):
        raise RuntimeError("Main identity/counts differ from approved package")
    for key in ("release_id", "generation", "policy_generation"):
        if str(main_db["pointer"][key]) != str(baseline["main"]["pointer"][key]):
            raise RuntimeError("Main pointer changed")
    if any(hashlib.sha256(checked_path(ROOT / name, ROOT).read_bytes()).hexdigest() != digest for name,digest in baseline["code_sha256"].items()):
        raise RuntimeError("Prepared code differs from approved checkpoint")
    conn = await asyncpg.connect(**connection())
    try:
        async with conn.transaction(readonly=True, isolation="repeatable_read"):
            before = await fingerprint(conn)
            jobs = [dict(row) for row in await conn.fetch("SELECT id,state,attempts,lease_owner,lease_until FROM knowledge_ingestion_job WHERE state IN ('QUEUED','RUNNING','RETRY_WAIT') ORDER BY id")]
            columns = {}
            table_hashes = {}
            # Preserve every column of the pre-existing content tables, even if
            # additive migrations add nullable fields. Only these exact columns
            # are compared immediately after migration and before runtime starts.
            for table in ("knowledge_source_scope","document_version","knowledge_ingest_version","knowledge_artifact",
                "knowledge_review","knowledge_release","knowledge_release_member","knowledge_release_pointer","knowledge_ingestion_job"):
                names = [row["column_name"] for row in await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=$1 ORDER BY ordinal_position",table)]
                columns[table] = names
                records = await conn.fetch('SELECT '+','.join('"'+name+'"' for name in names)+' FROM "'+table+'"')
                encoded = sorted(json.dumps(dict(row),ensure_ascii=False,sort_keys=True,default=str) for row in records)
                table_hashes[table] = {"count":len(records),"sha256":hashlib.sha256("\n".join(encoded).encode()).hexdigest()}
    finally:
        await conn.close()
    paths = rehearsal_bundle_paths(scope / "schema-rehearsal-bundle-20261026T174106266973.json")
    sqlite = {}
    for label, folder in (("main",STATE),("prototype",None)):
        sqlite[label] = {}
        for name in SQLITE_FILES:
            path = checked_path(folder / name if folder else paths[name],ROOT)
            db = sqlite3.connect(path.as_uri()+"?mode=ro",uri=True)
            try:
                item = {"fingerprint":sqlite_fingerprint(db)}
                if name == "conversations.sqlite3":
                    pending = [json.loads(row[0]) for row in db.execute("SELECT receipt FROM conversation_turn") if json.loads(row[0])["state"] == "pending"]
                    item["pending_turns"] = [{key:record[key] for key in ("client_id","committed_at")} for record in pending]
                sqlite[label][name] = item
            finally:
                db.close()
    listeners = json.loads(command(["powershell.exe","-NoProfile","-Command",
        "Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in 8015,3015,8017,8018,3018,55437,18081,18082 } | Select-Object LocalPort,OwningProcess | ConvertTo-Json -Compress"]))
    report = {"at":datetime.now(UTC),"authorization":"Direct user reply: Cho phép triển khai gói lên bản chính",
        "main":main_db,"database_fingerprint":before,"content_columns":columns,"content_hashes":table_hashes,
        "pending_jobs":jobs,"sqlite":sqlite,"listeners":listeners,"free_bytes":shutil.disk_usage(ROOT).free,
        "code_matches_approved_checkpoint":True,"paid_before":paid(),
        "tracked_changes":command(["git","status","--short","-uno"]).splitlines()}
    target = checked_path(scope / ("rollout-preflight-"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")+".json"),ROOT)
    retain(target,report)
    print(json.dumps({"receipt":str(target),"pending_jobs":jobs,"pending_turns":{label:row["conversations.sqlite3"]["pending_turns"] for label,row in sqlite.items()},"main_ports_absent":not any(row["LocalPort"] in {8015,3015} for row in listeners)},default=str))


if __name__ == "__main__":
    asyncio.run(main())
