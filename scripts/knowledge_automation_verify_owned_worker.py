"""Suspend/resume one exactly identified idle prototype worker around tests.

Keep the same process, loaded code, attempts and leases. Never touches the main
worker/API, terminates a process, resets a queue, or edits any stored result.
"""
import asyncio
import ctypes
from datetime import UTC, datetime
import json
import subprocess
import sys

import asyncpg

from knowledge_platform import ROOT, checked_path, rehearsal_connection, retain

MANIFEST = "infra/local/knowledge-automation-20261026/schema-rehearsal-restored-20261026T101117685822.json"


async def assert_idle():
    conn = await asyncpg.connect(**rehearsal_connection(ROOT / MANIFEST))
    try:
        async with conn.transaction(readonly=True):
            if await conn.fetchval("SELECT EXISTS(SELECT 1 FROM knowledge_ingestion_job WHERE state='RUNNING' AND lease_until>clock_timestamp())"):
                raise RuntimeError("Prototype has an owned live job; no suspension")
            if await conn.fetchval("SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND state='idle in transaction' AND pid<>pg_backend_pid())"):
                raise RuntimeError("Prototype has an open transaction; resume before verification")
    finally:
        await conn.close()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--local-ocr", action="store_true")
    args = parser.parse_args()
    if args.pid <= 0:
        raise ValueError("Exact existing prototype PID required")
    probe = subprocess.run(["powershell", "-NoProfile", "-Command",
        f'(Get-CimInstance Win32_Process -Filter "ProcessId={args.pid}").CommandLine'], capture_output=True, text=True, check=True)
    commandline = probe.stdout.strip()
    if not commandline.endswith("scripts/knowledge_platform.py worker --rehearsal "+MANIFEST):
        raise RuntimeError("Worker process identity changed")
    asyncio.run(assert_idle())
    kernel, native = ctypes.WinDLL("kernel32", use_last_error=True), ctypes.WinDLL("ntdll")
    kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    for method in (native.NtSuspendProcess, native.NtResumeProcess):
        method.argtypes, method.restype = [ctypes.c_void_p], ctypes.c_long
    handle = kernel.OpenProcess(0x0800|0x1000, False, args.pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    report = {"started_at": datetime.now(UTC), "worker_pid": args.pid, "exact_commandline": commandline, "main_process_action": False}
    suspended = False
    try:
        if native.NtSuspendProcess(handle) != 0:
            raise RuntimeError("Could not suspend exact prototype worker")
        suspended = True
        report["suspended"] = True
        print(json.dumps({"suspended_exact_prototype_worker": args.pid}), flush=True)
        asyncio.run(assert_idle())
        arguments = [sys.executable, "-B", "-X", "utf8", "scripts/knowledge_automation_verify.py"]
        if args.local_ocr:
            arguments.append("--local-ocr")
        report["local_ocr_smoke"] = args.local_ocr
        result = subprocess.run(arguments, cwd=ROOT, check=False)
        report["verification_exit_code"] = result.returncode
    finally:
        if suspended:
            report["resumed_same_process"] = native.NtResumeProcess(handle) == 0
            print(json.dumps({"resumed_same_prototype_process": args.pid, "success": report["resumed_same_process"]}), flush=True)
        kernel.CloseHandle(handle)
        report["finished_at"] = datetime.now(UTC)
        path = checked_path(ROOT / "infra/local/knowledge-automation-20261026" /
            ("worker-pause-resume-"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")+".json"), ROOT)
        retain(path, report)
        print(json.dumps({"process_receipt": str(path)}), flush=True)
    if report.get("verification_exit_code") or report.get("resumed_same_process") is not True:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
