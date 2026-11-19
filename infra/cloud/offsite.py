"""Copy backups off the server with restic (encrypted on this machine before anything is sent).

  python infra/cloud/offsite.py init   --backups DIR
  python infra/cloud/offsite.py push   --backups DIR            # newest backup, only if its LAST_BACKUP.json says ok
  python infra/cloud/offsite.py forget --backups DIR            # keep 14 daily, 8 weekly, 6 monthly snapshots
  python infra/cloud/offsite.py check  --backups DIR            # restic check, reading a 5 % sample of the data

Configuration (never on the command line, so it cannot show up in `ps` or logs):
  CAMPUS247_RESTIC_REPOSITORY   restic repository URL, for example sftp:user@host:/srv/campus247 or s3:s3.example.com/bucket
  RESTIC_PASSWORD_FILE          file with the repository password, readable by the owner only
  CAMPUS247_RESTIC_BIN          restic binary (default: restic from PATH)
Other restic variables (AWS_ACCESS_KEY_ID ...) pass through untouched. The password is also the key to every copy: keep one
more copy of it offline, because without it the off-site backups cannot be read by anyone.

`push` writes <backups>/OFFSITE.json and `check` writes OFFSITE_CHECK.json (ok, time, snapshot, error type) for the operations
page and the alert rules.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

STATUS_FILES = {"push": "OFFSITE.json", "check": "OFFSITE_CHECK.json"}
KEEP = ("--keep-daily", "14", "--keep-weekly", "8", "--keep-monthly", "6")
TIMEOUT_S = {"init": 300, "backup": 6 * 3600, "forget": 3600, "check": 6 * 3600}  # keyed by the restic subcommand

Runner = Callable[[list[str], dict[str, str], int], subprocess.CompletedProcess]


class OffsiteError(Exception):
    pass


def default_runner(args: list[str], env: dict[str, str], timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(args, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False)


def configuration(environ: dict[str, str]) -> tuple[str, str, str]:
    """(repository, password file, restic binary). Refuses a missing setting and a password file others can read."""
    repository = environ.get("CAMPUS247_RESTIC_REPOSITORY", "").strip()
    password_file = environ.get("RESTIC_PASSWORD_FILE", "").strip()
    if not repository:
        raise OffsiteError("CAMPUS247_RESTIC_REPOSITORY is not set")
    if not password_file or not Path(password_file).is_file():
        raise OffsiteError("RESTIC_PASSWORD_FILE is not set or does not exist")
    if os.name == "posix" and Path(password_file).stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise OffsiteError("RESTIC_PASSWORD_FILE must be readable by its owner only (chmod 600)")
    return repository, password_file, environ.get("CAMPUS247_RESTIC_BIN", "restic")


def newest_good_backup(backups: Path) -> Path:
    try:
        last = json.loads((backups / "LAST_BACKUP.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise OffsiteError("no LAST_BACKUP.json: nothing has been backed up yet") from None
    if not last.get("ok"):
        raise OffsiteError("the last backup failed; not copying it off the server")
    folder = backups / str(last.get("folder", ""))
    if not folder.is_dir() or (folder / "MANIFEST.json").is_file() is False:
        raise OffsiteError("the backup named in LAST_BACKUP.json is not complete")
    return folder


def run_restic(command: str, extra: list[str], environ: dict[str, str], runner: Runner) -> subprocess.CompletedProcess:
    repository, password_file, binary = configuration(environ)
    env = dict(environ, RESTIC_REPOSITORY=repository, RESTIC_PASSWORD_FILE=password_file)
    env.pop("RESTIC_PASSWORD", None)  # only the file is used
    result = runner([binary, command, *extra], env, TIMEOUT_S.get(command, 3600))
    if result.returncode != 0:
        raise OffsiteError(f"restic {command} exited with {result.returncode}")
    return result


def summary_of(stdout: str) -> dict:
    """The `summary` message restic prints at the end of `backup --json`."""
    for line in reversed(stdout.splitlines()):
        try:
            message = json.loads(line)
        except ValueError:
            continue
        if isinstance(message, dict) and message.get("message_type") == "summary":
            return message
    return {}


def write_status(backups: Path, filename: str, record: dict) -> None:
    target = backups / filename
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(record, indent=1), encoding="utf-8")
    os.replace(temporary, target)


def execute(command: str, backups: Path, environ: dict[str, str], runner: Runner = default_runner) -> dict:
    record: dict = {"command": command, "ok": False, "at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
    try:
        if command == "init":
            run_restic("init", [], environ, runner)
        elif command == "push":
            folder = newest_good_backup(backups)
            result = run_restic("backup", [str(folder), "--tag", "daily", "--host", "campus247", "--json"], environ, runner)
            summary = summary_of(result.stdout)
            record |= {"folder": folder.name, "snapshot": summary.get("snapshot_id"), "bytes_added": summary.get("data_added")}
        elif command == "forget":
            run_restic("forget", [*KEEP, "--prune"], environ, runner)
        elif command == "check":
            run_restic("check", ["--read-data-subset", "5%"], environ, runner)
        else:
            raise OffsiteError(f"unknown command {command}")
        record["ok"] = True
    except (OffsiteError, subprocess.TimeoutExpired, OSError) as error:
        record["error"] = type(error).__name__
        record["detail"] = str(error) if isinstance(error, OffsiteError) else None
    if command in STATUS_FILES:  # push says whether the off-site copy is current, check whether it can be read back
        write_status(backups, STATUS_FILES[command], record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("init", "push", "forget", "check"))
    parser.add_argument("--backups", type=Path, required=True)
    args = parser.parse_args()
    record = execute(args.command, args.backups, dict(os.environ))
    print(json.dumps(record))
    return 0 if record["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
