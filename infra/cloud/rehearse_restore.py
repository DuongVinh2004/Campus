"""Restore drill: prove the newest backup can really be restored, without touching the running system.

  python infra/cloud/rehearse_restore.py --root /opt/campus247 --backups /var/backups/campus247 [--pg-bin DIR] [--admin-prefix "runuser -u postgres --"]

What it does, in order, recording each step in <backups>/REHEARSAL.json:
  1. pick the newest backup folder and verify every checksum;
  2. restore it into a NEW empty root and a NEW database named campus247_rehearsal_<stamp> (never the live ones);
  3. compare: same set of tables as the live database, and every restored SQLite store passes its integrity check;
  4. delete only what this run created (that database and that root), also when a step failed.

It refuses to run when the new database name or the new root would be anything but its own. Row counts are reported but are
not a pass criterion: the live database keeps changing after the backup was taken.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

HERE = Path(__file__).resolve().parent
DATABASE_PREFIX = "campus247_rehearsal_"
ROOT_PREFIX = "campus247-rehearsal-"
STATUS_FILE = "REHEARSAL.json"


class RehearsalError(Exception):
    pass


@dataclass
class Steps:
    """Everything that touches the outside world, so the order and the cleanup can be tested without a database."""
    verify: Callable[[Path], dict]
    create_database: Callable[[str], None]
    restore: Callable[[Path, Path, str], dict]  # folder, new root, database name
    live_tables: Callable[[], dict]
    restored_tables: Callable[[Path, str], dict]
    sqlite_check: Callable[[Path], dict]
    drop_database: Callable[[str], None]


def newest_backup(backups: Path) -> Path:
    folders = sorted(p for p in backups.glob("campus247-backup-*") if (p / "MANIFEST.json").is_file())
    if not folders:
        raise RehearsalError("no backup folder with a MANIFEST.json")
    return folders[-1]


def rehearse(*, backups: Path, work_dir: Path, steps: Steps, now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> dict:
    started = time.time()
    stamp = now().strftime("%Y%m%d%H%M%S")
    database = f"{DATABASE_PREFIX}{stamp}"
    record: dict = {"ok": False, "at": now().isoformat().replace("+00:00", "Z"), "database": database, "steps": []}
    work_dir.mkdir(parents=True, exist_ok=True)
    work_dir = work_dir.resolve()  # mkdtemp returns an absolute path; a relative --work-dir must still compare equal
    new_root = Path(tempfile.mkdtemp(prefix=ROOT_PREFIX, dir=work_dir))
    created_database = False

    def step(name: str, action):
        begun = time.time()
        try:
            result = action()
        except BaseException as error:  # noqa: BLE001 -- recorded, then the drill stops and cleans up
            record["steps"].append({"name": name, "ok": False, "seconds": round(time.time() - begun, 1), "error": type(error).__name__})
            raise
        record["steps"].append({"name": name, "ok": True, "seconds": round(time.time() - begun, 1)})
        return result

    try:
        assert database.startswith(DATABASE_PREFIX) and new_root.name.startswith(ROOT_PREFIX) and new_root.parent == work_dir
        folder = step("pick", lambda: newest_backup(backups))
        record["backup"] = folder.name
        step("verify", lambda: steps.verify(folder))
        step("create_database", lambda: steps.create_database(database))
        created_database = True
        step("restore", lambda: steps.restore(folder, new_root, database))
        live = step("live_tables", steps.live_tables)
        restored = step("restored_tables", lambda: steps.restored_tables(new_root, database))
        missing, extra = sorted(set(live) - set(restored)), sorted(set(restored) - set(live))
        record["row_counts"] = {"live": live, "restored": restored}
        if missing or extra:
            record["steps"].append({"name": "compare_tables", "ok": False, "missing": missing, "extra": extra})
            raise RehearsalError("table sets differ")
        record["steps"].append({"name": "compare_tables", "ok": True, "tables": len(live)})
        stores = step("sqlite_integrity", lambda: steps.sqlite_check(new_root))
        bad = sorted(name for name, result in stores.items() if result != "ok")
        if bad:
            record["steps"].append({"name": "sqlite_result", "ok": False, "stores": bad})
            raise RehearsalError("sqlite integrity check failed")
        record["ok"] = True
    except BaseException as error:  # noqa: BLE001
        record["error"] = type(error).__name__
    finally:
        cleanup = []
        if created_database:
            try:
                assert database.startswith(DATABASE_PREFIX)
                steps.drop_database(database)
                cleanup.append("database_dropped")
            except BaseException as error:  # noqa: BLE001
                cleanup.append("database_drop_failed:" + type(error).__name__)
                record["ok"] = False
        if new_root.exists() and new_root.name.startswith(ROOT_PREFIX) and new_root.parent == work_dir:
            shutil.rmtree(new_root)
            cleanup.append("root_removed")
        record["cleanup"] = cleanup
        record["seconds"] = round(time.time() - started, 1)
        target = backups / STATUS_FILE
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(record, indent=1), encoding="utf-8")
        os.replace(temporary, target)
    return record


# ---------------------------------------------------------------------------------------------- the real steps

def real_steps(root: Path, pg_bin: str | None, admin: list[str] | None) -> Steps:
    sys.path.insert(0, str(HERE))
    import backup as backup_tool
    import compare_restore

    live_connection = backup_tool.connection(root)

    def create_database(name: str) -> None:
        if admin:  # restore_database_as_admin creates the database itself
            return
        backup_tool.run_pg(backup_tool.pg_tool("createdb", pg_bin), [name], live_connection)

    def restore(folder: Path, new_root: Path, database: str) -> dict:
        state = new_root / backup_tool.STATE_REL
        state.mkdir(parents=True)
        # local-connection.json is machine-specific and never inside a backup: point the new root at the new database only.
        (state / "local-connection.json").write_text(json.dumps(live_connection | {"database": database}), encoding="utf-8")
        return backup_tool.restore(folder, new_root, pg_bin, force=False, admin=admin)

    def restored_tables(new_root: Path, database: str) -> dict:
        return compare_restore.pg_counts(live_connection | {"database": database})

    def sqlite_check(new_root: Path) -> dict:
        results = {}
        for store in backup_tool.SQLITE_STORES:
            path = new_root / backup_tool.STATE_REL / store
            if path.exists():
                with closing(sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)) as db:
                    results[store] = str(db.execute("PRAGMA integrity_check").fetchone()[0])
        return results

    def drop_database(name: str) -> None:
        if not name.startswith(DATABASE_PREFIX):
            raise RehearsalError("refusing to drop a database that is not a rehearsal database")
        if admin:
            backup_tool.admin_sql(admin, pg_bin, live_connection["port"], f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")
        else:
            backup_tool.run_pg(backup_tool.pg_tool("dropdb", pg_bin), ["--if-exists", name], live_connection)

    return Steps(verify=backup_tool.verify, create_database=create_database, restore=restore,
                 live_tables=lambda: compare_restore.pg_counts(live_connection), restored_tables=restored_tables,
                 sqlite_check=sqlite_check, drop_database=drop_database)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=HERE.parents[1])
    parser.add_argument("--backups", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, help="where the temporary root is created (default: next to the backups)")
    parser.add_argument("--pg-bin")
    parser.add_argument("--admin-prefix", default="")
    args = parser.parse_args()
    record = rehearse(backups=args.backups, work_dir=args.work_dir or args.backups / "rehearsal-work",
                      steps=real_steps(args.root, args.pg_bin, args.admin_prefix.split() or None))
    print(json.dumps({key: record[key] for key in ("ok", "backup", "database", "cleanup", "seconds") if key in record}))
    return 0 if record["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
