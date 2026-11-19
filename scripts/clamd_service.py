"""Supervised ClamAV daemon for the Windows runtime: start clamd, keep the signatures fresh, reload after updates.

  python scripts/clamd_service.py serve            # long-running: clamd + freshclam every 2 h (what the launcher starts)
  python scripts/clamd_service.py update           # one signed update now, then RELOAD if clamd is running
  python scripts/clamd_service.py status           # JSON: up / database age / stale
  python scripts/clamd_service.py prepare          # create the state directory and configs only

State lives in a new directory (infra/local/clamav-service); the retained database from the 2026-11-04 acquisition is
copied once and never modified. The daemon listens on 127.0.0.1 only. Both executables are pinned by sha256 and the
signature updates are verified by freshclam against the bundled ClamAV certificates, so a tampered download is refused.
When this supervisor is killed, Windows closes its job object and the daemon dies with it (no orphan holding the port).
On Linux the packaged clamav-daemon and clamav-freshclam units do this job (see infra/cloud).
"""
from __future__ import annotations

import argparse
import asyncio
import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services/api/src")]

PORTABLE = ROOT / ".tooling/learning-clamav-20261104-01/portable/clamav-1.5.4.win.x64"
SEED_DATABASE = ROOT / ".tooling/learning-clamav-20261104-01/database"
SERVICE = ROOT / "infra/local/clamav-service"
PORT = 33100
PINS = {"clamd.exe": "d052be9cb42b3798e7a7a65c48a51a4253d8685d7720679b4279007fd6a1aa3f",
        "freshclam.exe": "4032fdd45184333d7c963eec87664a8339c6f31dc5ae94bb5008fe5e88feaf1f"}
HIDDEN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
UPDATE_INTERVAL_SECONDS = 2 * 3600
STARTUP_UPDATE_IF_OLDER_HOURS = 24

CLAMD_CONF = """DatabaseDirectory {database}
TemporaryDirectory {tmp}
TCPSocket {port}
TCPAddr 127.0.0.1
Foreground yes
LogFile {log}
LogTime yes
LogFileMaxSize 10M
MaxThreads 8
MaxScanSize 200M
MaxFileSize 100M
StreamMaxLength 105M
MaxFiles 10000
MaxRecursion 16
AlertExceedsMax yes
ConcurrentDatabaseReload no
SelfCheck 600
"""
FRESHCLAM_CONF = """DatabaseDirectory {database}
CVDCertsDirectory {certs}
DatabaseMirror database.clamav.net
DNSDatabaseInfo current.cvd.clamav.net
UpdateLogFile {log}
LogTime yes
LogFileMaxSize 10M
Foreground yes
ConnectTimeout 30
ReceiveTimeout 120
MaxAttempts 3
"""


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_binaries() -> None:
    for name, expected in PINS.items():
        if sha256(PORTABLE / name) != expected:
            raise RuntimeError(f"{name} does not match its pinned checksum; refusing to run it")


def prepare(service: Path = SERVICE) -> dict:
    """Create the state directory once. The retained database is copied, never modified."""
    (service / "tmp").mkdir(parents=True, exist_ok=True)
    (service / "logs").mkdir(exist_ok=True)
    database = service / "database"
    if not database.exists():
        shutil.copytree(SEED_DATABASE, database)
    paths = {"database": database.as_posix(), "tmp": (service / "tmp").as_posix(), "certs": (PORTABLE / "certs").as_posix()}
    (service / "clamd.conf").write_text(CLAMD_CONF.format(**paths, port=PORT, log=(service / "logs/clamd.log").as_posix()), encoding="ascii")
    (service / "freshclam.conf").write_text(FRESHCLAM_CONF.format(**paths, log=(service / "logs/freshclam.log").as_posix()), encoding="ascii")
    return {"service": str(service), "database": str(database)}


def scanner():
    from campus247.infrastructure.scanning.clamd import ClamdScanner
    return ClamdScanner(host="127.0.0.1", port=PORT, connect_timeout=2.0)


def status() -> dict:
    return asyncio.run(scanner().health())


def reload_daemon() -> bool:
    async def go():
        client = scanner()
        return await client._command(b"zRELOAD")
    try:
        return asyncio.run(go()) == "RELOADING"
    except Exception:  # the daemon is not running: nothing to reload
        return False


def update(service: Path = SERVICE) -> dict:
    """One signed update. freshclam verifies every database against the bundled certificates."""
    verify_binaries()
    prepare(service)
    started = time.time()
    result = subprocess.run([str(PORTABLE / "freshclam.exe"), f"--config-file={service / 'freshclam.conf'}"],
                            capture_output=True, text=True, timeout=900, creationflags=HIDDEN, cwd=str(PORTABLE))
    record = {"at": datetime.now(UTC).isoformat(), "exit_code": result.returncode, "seconds": round(time.time() - started, 1),
              "tail": (result.stdout + result.stderr).strip().splitlines()[-6:]}
    if result.returncode == 0:
        record["reloaded"] = reload_daemon()
    (service / "update-state.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


class Job:
    """A Windows job object that kills its processes when the last handle closes (this supervisor dying)."""

    def __init__(self):
        self.handle = None
        if os.name != "nt":
            return
        from ctypes import wintypes

        class Basic(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]

        class Io(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in ("a", "b", "c", "d", "e", "f")]

        class Extended(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", Io), ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        self.kernel = kernel
        self.handle = kernel.CreateJobObjectW(None, None)
        info = Extended()
        info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
            raise OSError("Could not configure the job object")

    def add(self, process: subprocess.Popen) -> None:
        if self.handle is not None and not self.kernel.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise OSError("Could not attach clamd to the job object")


def serve(service: Path = SERVICE) -> None:
    verify_binaries()
    prepare(service)
    job = Job()
    daemon = None
    next_update = time.monotonic() + UPDATE_INTERVAL_SECONDS
    health = {}
    try:
        health = status()
    except Exception:
        health = {}
    # A database already past the freshness limit would block every upload, so try to update before the first scan.
    database = service / "database"
    newest = max((path.stat().st_mtime for path in database.glob("*.c[lv]d")), default=0)
    if (time.time() - newest) / 3600 > STARTUP_UPDATE_IF_OLDER_HOURS:
        print(json.dumps({"startup_update": update(service)}), flush=True)
    failures = 0
    while True:
        if daemon is None or daemon.poll() is not None:
            if daemon is not None:
                failures += 1
                print(json.dumps({"clamd_exited": daemon.returncode, "restarts": failures}), flush=True)
                time.sleep(min(60, 2 * failures))
            daemon = subprocess.Popen([str(PORTABLE / "clamd.exe"), "-c", str(service / "clamd.conf")], cwd=str(PORTABLE),
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=HIDDEN)
            job.add(daemon)
        if time.monotonic() >= next_update:
            print(json.dumps({"update": update(service)}), flush=True)
            next_update = time.monotonic() + UPDATE_INTERVAL_SECONDS
        time.sleep(2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("serve", "update", "status", "prepare"))
    args = parser.parse_args()
    if args.command == "serve":
        serve()
    elif args.command == "update":
        print(json.dumps(update(), indent=2))
    elif args.command == "status":
        print(json.dumps(status(), indent=2))
    else:
        print(json.dumps(prepare(), indent=2))


if __name__ == "__main__":
    main()
