"""Backup and restore of one Campus 24/7 runtime (Windows or Linux): database, SQLite stores, state files, ledger.

  python infra/cloud/backup.py backup  --root /opt/campus247 --out /var/backups/campus247 [--keep 14]
  python infra/cloud/backup.py verify  --backup /var/backups/campus247/campus247-backup-<stamp>
  python infra/cloud/backup.py restore --backup <dir> --root /opt/campus247 [--pg-bin DIR]

What is saved (all inside one folder with MANIFEST.json holding a SHA-256 of every part):
  postgres.dump          pg_dump custom format of the knowledge database
  sqlite/*.sqlite3       each SQLite store through the SQLite backup API (consistent even while the API writes)
  state.tar.gz           identity files, signing keys, tokens, artifacts, authorizations (not logs, screenshots or builds)
  ledger.tar.gz          the paid-ledger records that decide the restart snapshot: everything except provider-*.json,
                         plus the newest LEDGER_KEEP provider records (the gateway reads only the newest 2000 on start)
Secrets are inside the backup, so the folder is created mode 0700 and must be stored like the server itself.
Nothing is deleted from the source; restore refuses to overwrite a non-empty database or existing state files unless --force.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path

STATE_REL = Path("infra/local/knowledge-platform-20261023")
LEDGER_REL = Path("infra/local/public-rag-20261013")
# Other directories the running system reads, saved with their paths relative to the workspace root: the human authorizations
# (spend and call limits, accounting-only mode) the paid gateway replays at start, the native model accounting, and the
# learning-materials workspace.
EXTRA_DIRS = (Path("infra/local/multi-agent-integrated-20261013-01"), Path("infra/local/rag-advanced-models-20261013-18"),
              Path("infra/local/learning-materials-20261104-01"))
EXTRA_MAX_BYTES = 5_000_000
SQLITE_STORES = ("conversations.sqlite3", "actor-state.sqlite3", "campus-ops.sqlite3", "action-idempotency.sqlite3",
                 "write-previews.sqlite3", "source-reviews.sqlite3", "oidc.sqlite3", "answer-quality.sqlite3")
LEDGER_KEEP = 3000
LEDGER_SKIP = ("gateway-sidecar.token",)
SKIP_SUFFIXES = (".png", ".log", ".sqlite3", ".sqlite3-wal", ".sqlite3-shm")
SKIP_DIRS = ("frontend-", "resume-", "rehearsals", "backup-restore-", "ops-metrics", "ops-alerts")
STATUS_FILE = "LAST_BACKUP.json"
# Plaintext passwords kept next to the hashed identity files on the development machine. A server only needs the hashes,
# so these are left out unless --with-credentials is given (for example to rehearse logins with synthetic test accounts).
CREDENTIAL_NAMES = ("bootstrap-password.txt",)
# Different on every machine: the database connection (host, port, password) is created by install.sh on the server.
ENVIRONMENT_SPECIFIC = ("local-connection.json",)
CREDENTIAL_SUFFIX = "-credentials.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def connection(root: Path) -> dict:
    return json.loads((root / STATE_REL / "local-connection.json").read_text(encoding="utf-8"))


def pg_tool(name: str, pg_bin: str | None) -> str:
    exe = name + (".exe" if os.name == "nt" else "")
    return str(Path(pg_bin) / exe) if pg_bin else exe


def run_pg(tool: str, args: list[str], conn: dict) -> None:
    env = {**os.environ, "PGPASSWORD": conn["password"]}
    subprocess.run([tool, "-h", conn["host"], "-p", str(conn["port"]), "-U", conn["user"], *args], check=True, env=env)


def state_files(root: Path, with_credentials: bool = False):
    base = root / STATE_REL
    for path in sorted(base.rglob("*")):
        relative = path.relative_to(base)
        if not path.is_file() or path.suffix in SKIP_SUFFIXES or path.name.endswith(".sqlite3-journal"):
            continue
        if not with_credentials and (path.name in CREDENTIAL_NAMES or path.name.endswith(CREDENTIAL_SUFFIX)):
            continue
        if path.name in ENVIRONMENT_SPECIFIC:
            continue
        if any(part.startswith(SKIP_DIRS) for part in relative.parts):
            continue
        yield path, relative


def add_tar(archive: Path, base: Path, files) -> int:
    count = 0
    with tarfile.open(archive, "w:gz") as tar:
        for path, relative in files:
            tar.add(path, arcname=relative.as_posix(), recursive=False)
            count += 1
    return count


def ledger_files(root: Path):
    base = root / LEDGER_REL
    if not base.is_dir():
        return
    providers = []
    for path in base.iterdir():
        if not path.is_file():
            continue
        if path.name.startswith(LEDGER_SKIP) or path.suffix == ".lock":
            continue  # the writer lease is a byte-range lock held by the running gateway; the token is created per server
        if path.name.startswith("provider-"):
            providers.append(path)
        else:
            yield path, path.relative_to(base)
    providers.sort(key=lambda p: p.name)
    newest = providers[-LEDGER_KEEP:]
    for path in newest:
        yield path, path.relative_to(base)
    # Attempts that were reserved but never settled stay in the budget snapshot; the gateway reloads each of their
    # reservation records when it starts, wherever they sit in the ledger. Keep those records too.
    kept = {p.name for p in newest}
    for ordinal in unsettled_ordinals(newest):
        for kind in ("reservation", "result"):
            candidate = base / f"provider-{ordinal:05d}-{kind}.json"
            if candidate.is_file() and candidate.name not in kept:
                kept.add(candidate.name)
                yield candidate, candidate.relative_to(base)


def unsettled_ordinals(newest: list[Path]) -> list[int]:
    """Same choice as the gateway's restart: the newest 2000 records, the one with the most calls and fewest pending."""
    best, best_key = None, None
    for path in newest[-2000:]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            snapshot = value["snapshot"]
            key = (snapshot["calls"], -len(snapshot["unsettled_attempts_retained"]), value.get("stage") == "result")
        except (OSError, ValueError, KeyError):
            continue
        if best_key is None or key > best_key:
            best, best_key = snapshot, key
    return [int(o) for o in (best or {}).get("unsettled_attempts_retained", [])]


def extra_files(root: Path, scratch: Path, with_credentials: bool = False):
    """(path to read, name inside the archive). SQLite files go through the backup API so they are consistent."""
    for relative_dir in EXTRA_DIRS:
        base = root / relative_dir
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if (not path.is_file() or path.stat().st_size > EXTRA_MAX_BYTES or path.suffix in (".png", ".log", ".lock")
                    or path.name.endswith(("-wal", "-shm", "-journal"))):
                continue
            if not with_credentials and (path.name in CREDENTIAL_NAMES or path.name.endswith(CREDENTIAL_SUFFIX)
                                         or path.name == "credentials.json"):
                continue
            arcname = (relative_dir / path.relative_to(base)).as_posix()
            if path.suffix == ".sqlite3":
                copy_path = scratch / arcname.replace("/", "__")
                with contextlib.closing(sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=30)) as origin,                         contextlib.closing(sqlite3.connect(copy_path)) as copy:
                    origin.backup(copy)
                yield copy_path, Path(arcname)
            else:
                yield path, Path(arcname)


def backup(root: Path, out: Path, pg_bin: str | None, keep: int, with_credentials: bool = False) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = out / f"campus247-backup-{stamp}"
    target.mkdir(parents=True, mode=0o700)
    (target / "sqlite").mkdir()
    parts: dict[str, str] = {}
    conn = connection(root)
    run_pg(pg_tool("pg_dump", pg_bin), ["-Fc", "-f", str(target / "postgres.dump"), conn["database"]], conn)
    parts["postgres.dump"] = sha256(target / "postgres.dump")
    for name in SQLITE_STORES:
        source = root / STATE_REL / name
        if not source.exists():
            continue
        destination = target / "sqlite" / name
        with contextlib.closing(sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True, timeout=30)) as origin,                 contextlib.closing(sqlite3.connect(destination)) as copy:
            origin.backup(copy)
        parts[f"sqlite/{name}"] = sha256(destination)
    state_count = add_tar(target / "state.tar.gz", root / STATE_REL, state_files(root, with_credentials))
    parts["state.tar.gz"] = sha256(target / "state.tar.gz")
    ledger_count = add_tar(target / "ledger.tar.gz", root / LEDGER_REL, ledger_files(root))
    parts["ledger.tar.gz"] = sha256(target / "ledger.tar.gz")
    scratch = target / "scratch"
    scratch.mkdir()
    extra_count = add_tar(target / "extra.tar.gz", root, extra_files(root, scratch, with_credentials))
    shutil.rmtree(scratch)
    parts["extra.tar.gz"] = sha256(target / "extra.tar.gz")
    manifest = {"schema": "campus247-backup-v1", "created_utc": stamp, "database": conn["database"], "parts": parts,
                "state_files": state_count, "ledger_files": ledger_count, "extra_files": extra_count, "with_credentials": with_credentials,
                "python": sys.version.split()[0]}
    (target / "MANIFEST.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    if keep:
        old = sorted(p for p in out.glob("campus247-backup-*") if p.is_dir())[:-keep]
        for folder in old:
            shutil.rmtree(folder)  # only this tool's own earlier backups, oldest first, beyond the retention count
    return target


def write_status(out: Path, *, ok: bool, started: float, folder: Path | None = None, error: str | None = None) -> dict:
    """Record the outcome of the last backup attempt in `<out>/LAST_BACKUP.json` for the operations page and the alerts.

    Atomic (temporary file, then replace). Holds no secret: only times, sizes, a checksum and the error's type name.
    """
    record: dict = {"ok": ok, "verified": ok, "finished_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "duration_s": round(time.time() - started, 1)}
    if folder is not None and (folder / "MANIFEST.json").exists():
        record["folder"] = folder.name
        record["bytes"] = sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())
        record["manifest_sha256"] = sha256(folder / "MANIFEST.json")
    if error:
        record["error"] = error
    out.mkdir(parents=True, exist_ok=True)
    target = out / STATUS_FILE
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(record, indent=1), encoding="utf-8")
    os.replace(temporary, target)
    return record


def verify(folder: Path) -> dict:
    manifest = json.loads((folder / "MANIFEST.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != "campus247-backup-v1":
        raise SystemExit("not a Campus 24/7 backup")
    for name, expected in manifest["parts"].items():
        if sha256(folder / name) != expected:
            raise SystemExit(f"checksum mismatch: {name}")
    return manifest


def safe_extract(archive: Path, destination: Path, force: bool) -> int:
    count = 0
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            target = (destination / member.name).resolve()
            if not member.isfile() or not target.is_relative_to(destination.resolve()):
                raise SystemExit(f"unsafe archive member: {member.name}")
            if target.exists() and not force:
                raise SystemExit(f"refusing to overwrite {target} (use --force)")
            target.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(member) as source, target.open("wb") as sink:
                shutil.copyfileobj(source, sink)
            count += 1
    return count


def admin_sql(admin: list[str], pg_bin: str | None, port: int, sql: str, database: str = "postgres") -> str:
    out = subprocess.run([*admin, pg_tool("psql", pg_bin), "-p", str(port), "-d", database, "-At", "-v", "ON_ERROR_STOP=1", "-c", sql],
                         check=True, capture_output=True, text=True)
    return out.stdout.strip()


def restore_database_as_admin(folder: Path, conn: dict, pg_bin: str | None, admin: list[str], force: bool) -> None:
    """Restore as the database superuser (peer authentication): the dump creates its extensions (vector, btree_gist),
    which the application role may not. An existing database with tables is only replaced with --force."""
    port, database, owner = conn["port"], conn["database"], conn["user"]
    exists = admin_sql(admin, pg_bin, port, f"SELECT 1 FROM pg_database WHERE datname = '{database}'")
    if exists:
        tables = int(admin_sql(admin, pg_bin, port, "SELECT count(*) FROM pg_tables WHERE schemaname = 'public'", database) or 0)
        if tables and not force:
            raise SystemExit(f"refusing to replace database {database} that already has {tables} tables (use --force)")
        admin_sql(admin, pg_bin, port, f"DROP DATABASE {database} WITH (FORCE)")
    admin_sql(admin, pg_bin, port, f"CREATE DATABASE {database} OWNER {owner}")
    subprocess.run([*admin, pg_tool("pg_restore", pg_bin), "-p", str(port), "-d", database, "--exit-on-error", str(folder / "postgres.dump")],
                   check=True)


def restore(folder: Path, root: Path, pg_bin: str | None, force: bool, admin: list[str] | None = None) -> dict:
    manifest = verify(folder)
    result = {"state_files": safe_extract(folder / "state.tar.gz", root / STATE_REL, force),
              "ledger_files": safe_extract(folder / "ledger.tar.gz", root / LEDGER_REL, force)}
    if (folder / "extra.tar.gz").exists():
        result["extra_files"] = safe_extract(folder / "extra.tar.gz", root, force)
    for name in SQLITE_STORES:
        source = folder / "sqlite" / name
        if source.exists():
            destination = root / STATE_REL / name
            if destination.exists() and not force:
                raise SystemExit(f"refusing to overwrite {destination} (use --force)")
            # The backup folder may be read-only and its SQLite files in WAL mode: open them immutable (no -shm needed).
            with contextlib.closing(sqlite3.connect(f"file:{source.as_posix()}?mode=ro&immutable=1", uri=True)) as origin,                     contextlib.closing(sqlite3.connect(destination)) as copy:
                origin.backup(copy)
    conn = connection(root)
    if admin:
        restore_database_as_admin(folder, conn, pg_bin, admin, force)
    else:
        args = ["--no-owner", "--exit-on-error", "-d", conn["database"]]
        if force:
            args = ["--clean", "--if-exists", *args]
        run_pg(pg_tool("pg_restore", pg_bin), [*args, str(folder / "postgres.dump")], conn)
    result["database"] = manifest["database"]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("backup", "verify", "restore", "status"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--out", type=Path)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--pg-bin")
    parser.add_argument("--keep", type=int, default=14)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--with-credentials", action="store_true", help="also save the plaintext *-credentials.json files")
    parser.add_argument("--admin-prefix", default="", help='restore: run Postgres tools as the superuser, e.g. "runuser -u postgres --"')
    args = parser.parse_args()
    started = time.time()
    if args.command == "backup":
        if not args.out:
            parser.error("--out is required")
        args.out.mkdir(parents=True, exist_ok=True)
        folder = None
        try:
            folder = backup(args.root, args.out, args.pg_bin, args.keep, args.with_credentials)
            parts = verify(folder)["parts"]
        except BaseException as error:  # noqa: BLE001 -- record the failure for the alerts, then let it propagate unchanged
            write_status(args.out, ok=False, started=started, folder=folder, error=type(error).__name__)
            raise
        write_status(args.out, ok=True, started=started, folder=folder)
        print(json.dumps({"backup": str(folder), "seconds": round(time.time() - started, 1), **parts}))
    elif args.command == "status":
        if not args.out:
            parser.error("--out is required")
        try:
            print((args.out / STATUS_FILE).read_text(encoding="utf-8"))
        except OSError:
            raise SystemExit(f"no {STATUS_FILE} in {args.out}: no backup has run yet") from None
    elif args.command == "verify":
        print(json.dumps({"ok": True, **verify(args.backup)}))
    else:
        print(json.dumps(restore(args.backup, args.root, args.pg_bin, args.force, args.admin_prefix.split() or None)))


if __name__ == "__main__":
    main()
