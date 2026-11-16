"""Retain a consistent PostgreSQL snapshot and restore only into a new local DB.

No --clean/drop/reset, no source writes, no SQLite atomicity claim. Source
artifacts stay immutable in their existing workspace store and are hash-checked.
"""
import asyncio
import hashlib
import json
import os
import re
import subprocess
from datetime import UTC, datetime
from uuid import uuid4

import asyncpg
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import URL

from knowledge_platform import ROOT, STATE, PGROOT, DB_NAME, DB_PORT, TENANT, checked_path, connection, retain


async def fingerprint(conn):
    counts = {}
    for table in ("knowledge_source", "document_version", "knowledge_ingest_version", "knowledge_artifact", "knowledge_chunk",
                  "knowledge_chunk_input", "knowledge_review", "knowledge_release", "knowledge_release_member", "audit_event", "outbox_event"):
        counts[table] = await conn.fetchval("SELECT count(*) FROM " + table)
    vectors = await conn.fetchval("""SELECT md5(string_agg(id::text || ':' || COALESCE(md5(embedding_rag_v1::text),'NULL'),
        ',' ORDER BY id)) FROM knowledge_chunk""")
    artifacts = await conn.fetchval("SELECT md5(string_agg(id::text || ':' || sha256 || ':' || byte_size::text,',' ORDER BY id)) FROM knowledge_artifact")
    members = await conn.fetchval("SELECT md5(string_agg(release_id::text || ':' || version_id::text || ':' || rendition_sha256 || ':' || metadata_sha256,',' ORDER BY release_id,version_id)) FROM knowledge_release_member")
    return {"counts": counts, "vectors_fingerprint": vectors, "artifacts_fingerprint": artifacts, "release_members_fingerprint": members}


def child(command_args, parameters):
    environment = {key: value for key, value in os.environ.items() if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR"}}
    environment["PGPASSWORD"] = parameters["password"]
    return subprocess.run(command_args, cwd=ROOT, env=environment, capture_output=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False)


async def capture(scope, report, during_snapshot=None):
    parameters = connection()  # Exact verified local cluster, not an application default.
    source = await asyncpg.connect(**parameters)
    backup = checked_path(scope / "postgres.dump", ROOT)
    if backup.exists(): raise ValueError("New backup required")
    try:
        async with source.transaction(readonly=True, isolation="repeatable_read"):
            if await source.fetchval("SELECT current_database()") != DB_NAME:
                raise RuntimeError("Source DB identity mismatch")
            report["source_schema"] = await source.fetchval("SELECT version_num FROM alembic_version")
            if report["source_schema"] not in {"0018", "0022"}:
                raise RuntimeError("Only the reviewed retained 0018/0022 source schemas are accepted")
            report["source_fingerprint"] = await fingerprint(source)
            report["source_pointer"] = dict(await source.fetchrow("SELECT * FROM knowledge_release_pointer WHERE tenant_id=$1 AND campus_id='HUCE'", TENANT))
            snapshot = await source.fetchval("SELECT pg_export_snapshot()")
            arguments = [str(checked_path(PGROOT / "bin/pg_dump.exe", ROOT)), "-h", "127.0.0.1", "-p", str(DB_PORT),
                "-U", parameters["user"], "--format=custom", "--snapshot", snapshot, "--file", str(backup), DB_NAME]
            result = await asyncio.to_thread(child, arguments, parameters)
            report["dump_exit_code"] = result.returncode
            with (scope / "dump.stderr.log").open("xb") as stream: stream.write(result.stderr)
            if result.returncode: raise RuntimeError("Retained PostgreSQL dump failed")
            report["snapshot_exported"] = True
            if during_snapshot is not None:
                await during_snapshot(source)
    finally:
        await source.close()
    report["backup_sha256"] = hashlib.sha256(backup.read_bytes()).hexdigest()
    report["backup_bytes"] = backup.stat().st_size
    listing = await asyncio.to_thread(child, [str(PGROOT / "bin/pg_restore.exe"), "--list", str(backup)], parameters)
    with (scope / "restore-toc.txt").open("xb") as stream: stream.write(listing.stdout)
    if listing.returncode or any(re.search(r"\b(?:DATABASE|DATABASE PROPERTIES|EVENT TRIGGER)\b", line)
        for line in listing.stdout.decode("utf-8").splitlines() if not line.startswith(";")):
        raise RuntimeError("Archive contains a database/global operation outside the new target")
    target = "campus247_automation_20261026_" + uuid4().hex[:12]
    if not re.fullmatch(r"campus247_automation_20261026_[0-9a-f]{12}", target): raise ValueError("Invalid restore target")
    admin = await asyncpg.connect(**(parameters | {"database": "postgres"}))
    try:
        if await admin.fetchval("SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname=$1)", target):
            raise RuntimeError("Restore target already exists; it is preserved")
        await admin.execute('CREATE DATABASE "' + target + '"')
    finally:
        await admin.close()
    report["database"] = target
    conn = await asyncpg.connect(**(parameters | {"database": target}))
    try:
        if await conn.fetchval("SELECT current_database()") != target or await conn.fetchval("SELECT to_regclass('knowledge_source') IS NOT NULL"):
            raise RuntimeError("Restore target is not the new empty task DB")
    finally:
        await conn.close()
    arguments = [str(PGROOT / "bin/pg_restore.exe"), "-h", "127.0.0.1", "-p", str(DB_PORT), "-U", parameters["user"],
        "--exit-on-error", "--dbname", target, str(backup)]
    result = await asyncio.to_thread(child, arguments, parameters)
    report["restore_exit_code"] = result.returncode
    with (scope / "restore.stderr.log").open("xb") as stream: stream.write(result.stderr)
    if result.returncode: raise RuntimeError("Restore failed; new target and backup retained")
    restored = await asyncpg.connect(**(parameters | {"database": target}))
    try:
        async with restored.transaction(readonly=True):
            report["restored_fingerprint"] = await fingerprint(restored)
            if report["restored_fingerprint"] != report["source_fingerprint"]:
                raise RuntimeError("Restore fingerprints differ")
    finally:
        await restored.close()
    return target, parameters


def main():
    at = datetime.now(UTC)
    scope = checked_path(ROOT / "infra/local/knowledge-automation-20261026" / ("restore-"+at.strftime("%Y%m%dT%H%M%S%f")), ROOT)
    scope.mkdir(exist_ok=False)
    manifest = checked_path(scope.parent / ("schema-rehearsal-restored-"+at.strftime("%Y%m%dT%H%M%S%f")+".json"), ROOT)
    report = {"started_at": at.isoformat(), "host": "127.0.0.1", "port": DB_PORT, "status": "started",
        "serving_database_modified": False, "new_database_retained": True, "backup_directory": str(scope),
        "sqlite_restored": False, "cross_store_atomicity_verified": False, "source_artifact_store": str(STATE / "artifacts")}
    try:
        target, parameters = asyncio.run(capture(scope, report))
        config = Config(str(ROOT / "services/api/alembic.ini"))
        url = URL.create("postgresql+asyncpg", username=parameters["user"], password=parameters["password"],
            host=parameters["host"], port=parameters["port"], database=target)
        config.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False).replace("%", "%%"))
        revision = "0022" if report["source_schema"] == "0022" else "0020"
        command.upgrade(config, revision)
        report.update(status="passed", revision=revision, postgres_fingerprints_equal=True)
    except Exception as error:
        report.update(status="failed", error_type=type(error).__name__)
        raise
    finally:
        report["finished_at"] = datetime.now(UTC).isoformat()
        retain(manifest, report)
        print(json.dumps({"manifest": str(manifest), "status": report["status"], "database": report.get("database"),
            "backup_bytes": report.get("backup_bytes"), "postgres_fingerprints_equal": report.get("postgres_fingerprints_equal", False)}))


if __name__ == "__main__":
    main()
