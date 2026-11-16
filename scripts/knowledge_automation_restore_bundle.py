"""Restore a retained PG/artifact/SQLite bundle into new local targets only.

SQLite read transactions span the exported PostgreSQL snapshot. The bundle is
called a coherent business cut only if each source SQLite data_version remains
unchanged across that interval. Live runtime acks must be renewed after restore.
"""
import asyncio
import hashlib
import json
import shutil
import sqlite3
from datetime import UTC, datetime

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import URL

from knowledge_platform import ROOT, STATE, DB_PORT, TENANT, checked_path, retain
from knowledge_automation_restore import capture
from campus247.infrastructure.knowledge.storage import FileKnowledgeStorage

SQLITE_FILES = ("actor-state.sqlite3", "action-idempotency.sqlite3", "conversations.sqlite3")


def sqlite_fingerprint(conn):
    schema = conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name").fetchall()
    tables = {}
    for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        quoted = '"'+name.replace('"','""')+'"'
        hashes = []
        for row in conn.execute("SELECT * FROM "+quoted):
            encoded = json.dumps([{"bytes":v.hex()} if isinstance(v,bytes) else v for v in row], ensure_ascii=False, separators=(",",":"))
            hashes.append(hashlib.sha256(encoded.encode()).hexdigest())
        tables[name] = {"rows":len(hashes),"rows_sha256":hashlib.sha256("".join(sorted(hashes)).encode()).hexdigest()}
    return {"schema_sha256":hashlib.sha256(json.dumps(schema,ensure_ascii=False).encode()).hexdigest(),"tables":tables}


def new_database(path):
    checked_path(path, ROOT)
    with path.open("xb"):
        pass
    return sqlite3.connect(path.as_uri()+"?mode=rw",uri=True)


async def build(scope, report):
    sources = {}
    try:
        for name in SQLITE_FILES:
            path = checked_path(STATE / name, ROOT)
            if not path.is_file(): raise RuntimeError("Required source SQLite store is missing")
            conn = sqlite3.connect(path.as_uri()+"?mode=ro",uri=True,timeout=2)
            conn.execute("PRAGMA query_only=ON")
            before = conn.execute("PRAGMA data_version").fetchone()[0]
            conn.execute("BEGIN")
            fingerprint = sqlite_fingerprint(conn)  # Pins this read snapshot.
            sources[name] = (conn,before,fingerprint)
        report["sqlite_read_interval_started_at"] = datetime.now(UTC).isoformat()
        backup_artifacts = checked_path(scope / "artifact-backup", ROOT)
        restored_artifacts = checked_path(scope / "artifact-restored", ROOT)
        backup_artifacts.mkdir(); restored_artifacts.mkdir()
        report["sqlite"] = {}
        async def snapshot(conn):
            report["postgres_snapshot_observed_at"] = str(await conn.fetchval("SELECT clock_timestamp()"))
            # The operational store is tenant-bound. Retained test tenants use
            # different artifact roots; their PG rows remain in the full dump,
            # but never look them up in this tenant's physical namespace.
            rows = await conn.fetch("SELECT * FROM knowledge_artifact WHERE tenant_id=$1 ORDER BY id",TENANT)
            report["artifact_scope_tenant"] = TENANT
            report["other_tenant_artifact_rows_outside_storage_scope"] = await conn.fetchval("SELECT count(*) FROM knowledge_artifact WHERE tenant_id<>$1",TENANT)
            size = sum(row["byte_size"] for row in rows)
            if shutil.disk_usage(ROOT).free < 2*size + 512*1024**2:
                raise RuntimeError("Insufficient workspace disk headroom for two retained artifact copies")
            original_storage = FileKnowledgeStorage(ROOT, STATE / "artifacts")
            artifact_manifest = []
            for row in rows:
                raw = original_storage.read(row)
                target = checked_path(backup_artifacts / row["object_key"], ROOT)
                if target.parent != backup_artifacts: raise RuntimeError("Artifact destination outside exact new namespace")
                with target.open("xb") as stream: stream.write(raw)
                artifact_manifest.append({key:str(row[key]) if key=="id" else row[key] for key in ("id","object_key","sha256","byte_size","media_type","kind")})
            report["artifact_count"],report["artifact_bytes"] = len(rows),size
            retain(scope / "artifact-manifest.json",artifact_manifest)
            for name,(source,_,fingerprint) in sources.items():
                backup = checked_path(scope / ("backup-"+name),ROOT)
                destination = new_database(backup)
                try:
                    source.backup(destination)
                    if sqlite_fingerprint(destination) != fingerprint:
                        raise RuntimeError("SQLite snapshot fingerprint mismatch")
                finally:
                    destination.close()
                report["sqlite"][name] = {"source_fingerprint":fingerprint,"backup_path":str(backup),
                    "backup_sha256":hashlib.sha256(backup.read_bytes()).hexdigest()}
            report["artifact_manifest_sha256"] = hashlib.sha256((scope / "artifact-manifest.json").read_bytes()).hexdigest()
        target, parameters = await capture(scope,report,during_snapshot=snapshot)
        stable = True
        for name,(source,before,_) in sources.items():
            source.rollback()  # End only our read transaction, never user work.
            after = source.execute("PRAGMA data_version").fetchone()[0]
            report["sqlite"][name].update(data_version_before=before,data_version_after=after,source_unchanged=before==after)
            stable &= before==after
        report["sqlite_read_interval_finished_at"] = datetime.now(UTC).isoformat()
        report["cross_store_capture_verified"] = stable
        report["cross_store_basis"] = "SQLite read snapshots span exported PG snapshot; no SQLite commit observed via persistent-connection data_version" if stable else "SQLite changed during PG snapshot interval; preserve independent restores, no coherent-cut claim"
        for name,item in report["sqlite"].items():
            backup = checked_path(__import__("pathlib").Path(item["backup_path"]),ROOT)
            restored = checked_path(scope / ("restored-"+name),ROOT)
            source = sqlite3.connect(backup.as_uri()+"?mode=ro",uri=True)
            destination = new_database(restored)
            try:
                source.backup(destination)
                item["integrity_check"] = destination.execute("PRAGMA integrity_check").fetchall()
                item["foreign_key_violation_count"] = len(destination.execute("PRAGMA foreign_key_check").fetchall())
                item["restored_fingerprint"] = sqlite_fingerprint(destination)
                item["fingerprints_equal"] = item["restored_fingerprint"] == item["source_fingerprint"]
                if item["integrity_check"] != [("ok",)] or not item["fingerprints_equal"]:
                    raise RuntimeError("Restored SQLite integrity/fingerprint verification failed")
            finally:
                destination.close(); source.close()
            item["restored_path"] = str(restored)
        backup_storage = FileKnowledgeStorage(ROOT, backup_artifacts)
        restored_storage = FileKnowledgeStorage(ROOT, restored_artifacts)
        manifest = json.loads((scope / "artifact-manifest.json").read_text(encoding="utf-8"))
        for row in manifest:
            raw = backup_storage.read(row)
            target_file = restored_storage.path(row["object_key"])
            with target_file.open("xb") as stream: stream.write(raw)
            restored_storage.read(row)
        report["restored_artifact_store"] = str(restored_artifacts)
        report["restored_sqlite"] = {name:item["restored_path"] for name,item in report["sqlite"].items()}
        report["restored_operational_artifacts_hash_checked"] = True
        if not stable:
            raise RuntimeError("Cross-store capture changed; bundle retained without activation")
        return target,parameters
    finally:
        for source,_,_ in sources.values(): source.close()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", choices=("0021", "0022"), default="0021")
    revision = parser.parse_args().revision
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
    scope = checked_path(ROOT / "infra/local/knowledge-automation-20261026" / ("restore-bundle-"+stamp),ROOT)
    scope.mkdir()
    manifest = checked_path(scope.parent / ("schema-rehearsal-bundle-"+stamp+".json"),ROOT)
    report = {"started_at":datetime.now(UTC).isoformat(),"status":"started","host":"127.0.0.1","port":DB_PORT,
        "serving_database_modified":False,"new_database_retained":True,"backup_directory":str(scope),
        "runtime_ack_reusable":False,"cross_store_capture_verified":False}
    try:
        target,parameters = asyncio.run(build(scope,report))
        if report["source_schema"] == "0022" and revision != "0022":
            raise ValueError("A0022 backup must remain at0022; no downgrade is permitted")
        config = Config(str(ROOT / "services/api/alembic.ini"))
        url = URL.create("postgresql+asyncpg",username=parameters["user"],password=parameters["password"],host=parameters["host"],port=parameters["port"],database=target)
        config.set_main_option("sqlalchemy.url",url.render_as_string(hide_password=False).replace("%","%%"))
        command.upgrade(config,revision)
        command.upgrade(config,revision)
        report.update(status="passed",revision=revision,replay="passed",postgres_fingerprints_equal=True)
    except Exception as error:
        report.update(status="failed",error_type=type(error).__name__)
        raise
    finally:
        report["finished_at"] = datetime.now(UTC).isoformat()
        retain(manifest,report)
        print(json.dumps({"manifest":str(manifest),"status":report["status"],"database":report.get("database"),
            "cross_store_capture_verified":report["cross_store_capture_verified"],"artifact_count":report.get("artifact_count")}))


if __name__ == "__main__":
    main()
