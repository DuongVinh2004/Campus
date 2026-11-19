"""Load check for the ClamAV daemon through the same client the API uses.

  python scripts/scanner_load_test.py --concurrency 20 --scans 200 --size-mb 5
  python scripts/scanner_load_test.py --concurrency 20 --scans 40 --size-mb 50
  python scripts/scanner_load_test.py --concurrency 20 --duration 60 --size-mb 5 --reload-at 15   # RELOAD under load

Files are random bytes behind a PDF header (the scanner reads bytes, not structure) written to a new directory under
.tooling and removed afterwards. Prints p50/p95/max wall time per scan, errors and the daemon's resident memory.
Nothing here changes the daemon or its database.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services/api/src")]

from campus247.infrastructure.scanning.clamd import ClamdScanner  # noqa: E402
from campus247.ports.file_scanner import ScanRejected, ScannerUnavailable  # noqa: E402


def daemon_rss_mb() -> int | None:
    try:
        import psutil
    except ImportError:
        return None
    sizes = [p.memory_info().rss for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower().startswith("clamd")]
    return max(sizes) // 2**20 if sizes else None


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--scans", type=int, default=200)
    parser.add_argument("--size-mb", type=float, default=5.0)
    parser.add_argument("--port", type=int, default=33100)
    parser.add_argument("--scan-timeout", type=float, default=120.0, help="per-scan timeout; the API uses 30")
    parser.add_argument("--retry-window", type=float, default=0.0, help="seconds an unavailable daemon is retried; the API uses 75")
    parser.add_argument("--duration", type=float, default=0.0, help="keep scanning for this many seconds instead of a fixed count")
    parser.add_argument("--reload-at", type=float, default=-1.0, help="seconds after the start at which RELOAD is sent to the daemon")
    args = parser.parse_args()
    work = ROOT / ".tooling" / f"scanner-load-{int(time.time())}"
    work.mkdir()
    try:
        files = []
        for index in range(min(args.concurrency, args.scans)):
            path = work / f"f{index}.pdf"
            path.write_bytes(b"%PDF-1.7\n" + os.urandom(int(args.size_mb * 1024 * 1024)))
            files.append(path)
        scanner = ClamdScanner(host="127.0.0.1", port=args.port, scan_timeout=args.scan_timeout, retry_window=args.retry_window, max_bytes=max(100 * 1024**2, int(args.size_mb * 2**20) + 1024))
        before = daemon_rss_mb()
        health = await scanner.health()
        gate = asyncio.Semaphore(args.concurrency)
        times, errors = [], {}

        async def one(index: int) -> None:
            async with gate:
                started = time.perf_counter()
                try:
                    await scanner.scan(files[index % len(files)])
                except (ScanRejected, ScannerUnavailable) as failure:
                    errors[failure.code] = errors.get(failure.code, 0) + 1
                else:
                    times.append(time.perf_counter() - started)

        began = time.perf_counter()
        reloaded = {}

        async def reload_later():
            await asyncio.sleep(args.reload_at)
            reloaded["sent_at"] = round(time.perf_counter() - began, 1)
            reloaded["reply"] = await scanner._command(b"zRELOAD")
            for _ in range(240):  # until the daemon answers a VERSION again
                await asyncio.sleep(0.5)
                try:
                    await scanner.database(refresh=True)
                    break
                except ScannerUnavailable:
                    continue
            reloaded["answering_again_at"] = round(time.perf_counter() - began, 1)

        async def steady():
            index = 0
            deadline = began + args.duration
            async def worker():
                nonlocal index
                while time.perf_counter() < deadline:
                    index += 1
                    await one(index)
            await asyncio.gather(*(worker() for _ in range(args.concurrency)))

        extra = [asyncio.create_task(reload_later())] if args.reload_at >= 0 else []
        if args.duration > 0:
            await steady()
        else:
            await asyncio.gather(*(one(i) for i in range(args.scans)))
        if extra:
            await asyncio.gather(*extra)
        elapsed = time.perf_counter() - began
        args.scans = len(times) + sum(errors.values())
        times.sort()
        pick = lambda q: round(times[min(len(times) - 1, int(q * len(times)))] * 1000) if times else None
        print(json.dumps({"scans": args.scans, "concurrency": args.concurrency, "size_mb": args.size_mb,
                          "ok": len(times), "errors": errors, "p50_ms": pick(0.50), "p95_ms": pick(0.95), "max_ms": pick(0.999),
                          "throughput_per_s": round(args.scans / elapsed, 1), "database": health.get("database_version"),
                          "daemon_rss_mb_before": before, "daemon_rss_mb_after": daemon_rss_mb(),
                          **({"reload": reloaded, "slowest_ms": round(times[-1] * 1000) if times else None} if extra else {})}, indent=2))
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
