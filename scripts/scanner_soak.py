"""Soak test for the ClamAV daemon through the client the API uses: steady scans, repeated signature reloads, memory trend.

  python scripts/scanner_soak.py --minutes 30 --reload-every 5            # accelerated: many reload cycles in half an hour
  python scripts/scanner_soak.py --hours 72 --reload-every 120 --out soak-72h.jsonl   # the real multi-day run

Works against a daemon on loopback TCP (the Windows service, --port) or a Unix socket (the Linux VM, --socket). It uses the
product settings (30 s timeout, 75 s retry window). One JSON line per interval is appended to --out (a new file under
.tooling by default) and a summary is printed at the end and written next to it. PASS means: no scan failed, every
interval's scans were answered, the database never went stale and the daemon's resident memory did not grow by more than
`--max-growth-percent` (default 10) between the first and last reading. Nothing here changes the daemon or its database
except sending RELOAD, which re-reads the database that is already on disk.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import time
from datetime import UTC, datetime
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


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--minutes", type=float, default=0.0)
    parser.add_argument("--hours", type=float, default=0.0)
    parser.add_argument("--reload-every", type=float, default=5.0, help="minutes between RELOAD commands (0 = never)")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--size-kb", type=int, default=512)
    parser.add_argument("--interval", type=float, default=30.0, help="seconds between report lines")
    parser.add_argument("--port", type=int, default=33100)
    parser.add_argument("--socket", default=None, help="Unix socket path (Linux); overrides --port")
    parser.add_argument("--max-growth-percent", type=float, default=10.0)
    parser.add_argument("--max-database-age-hours", type=int, default=72)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    duration = args.hours * 3600 + args.minutes * 60
    if duration <= 0:
        parser.error("give --minutes or --hours")
    out = args.out or ROOT / ".tooling" / f"scanner-soak-{datetime.now():%Y%m%d-%H%M%S}.jsonl"
    if out.exists():
        parser.error(f"{out} exists; soak reports are never overwritten")
    out.parent.mkdir(parents=True, exist_ok=True)
    work = out.with_suffix(".files")
    work.mkdir()
    from datetime import timedelta
    scanner = ClamdScanner(host=None if args.socket else "127.0.0.1", port=None if args.socket else args.port,
                           socket_path=args.socket, scan_timeout=30, retry_window=75,
                           max_database_age=timedelta(hours=args.max_database_age_hours))
    files = []
    for index in range(args.concurrency):
        path = work / f"f{index}.pdf"
        path.write_bytes(b"%PDF-1.7\n" + os.urandom(args.size_kb * 1024))
        files.append(path)
    began = time.monotonic()
    deadline = began + duration
    window = {"ok": 0, "errors": {}, "latencies": []}
    totals = {"ok": 0, "errors": {}, "reloads": 0, "stale_seen": 0}
    stop = asyncio.Event()

    async def worker(index: int) -> None:
        while not stop.is_set():
            started = time.perf_counter()
            try:
                await scanner.scan(files[index])
            except (ScanRejected, ScannerUnavailable) as failure:
                for bucket in (window["errors"], totals["errors"]):
                    bucket[failure.code] = bucket.get(failure.code, 0) + 1
            else:
                window["ok"] += 1
                totals["ok"] += 1
                window["latencies"].append((time.perf_counter() - started) * 1000)
            await asyncio.sleep(0.2)

    async def reloader() -> None:
        while not stop.is_set() and args.reload_every > 0:
            await asyncio.sleep(args.reload_every * 60)
            if stop.is_set():
                return
            reply = await scanner._command(b"zRELOAD")
            totals["reloads"] += 1
            window["reload"] = reply

    readings = []
    with out.open("x", encoding="utf-8") as report:
        tasks = [asyncio.create_task(worker(i)) for i in range(args.concurrency)] + [asyncio.create_task(reloader())]
        try:
            while time.monotonic() < deadline:
                await asyncio.sleep(min(args.interval, max(0.0, deadline - time.monotonic())))
                health = await scanner.health()
                latencies = sorted(window["latencies"])
                rss = daemon_rss_mb()
                if rss is not None:
                    readings.append(rss)
                if health.get("stale"):
                    totals["stale_seen"] += 1
                line = {"t_min": round((time.monotonic() - began) / 60, 1), "ok": window["ok"], "errors": window["errors"],
                        "p95_ms": round(latencies[int(0.95 * (len(latencies) - 1))]) if latencies else None,
                        "max_ms": round(latencies[-1]) if latencies else None, "rss_mb": rss, "up": health.get("up"),
                        "database_age_hours": health.get("database_age_hours"), "reload": window.get("reload")}
                report.write(json.dumps(line) + "\n")
                report.flush()
                window.update(ok=0, errors={}, latencies=[])
                window.pop("reload", None)
        finally:
            stop.set()
            await asyncio.gather(*tasks, return_exceptions=True)
            shutil.rmtree(work, ignore_errors=True)
    growth = None
    if len(readings) >= 2 and readings[0]:
        growth = round(100 * (readings[-1] - readings[0]) / readings[0], 1)
    failures = sum(totals["errors"].values())
    verdict = failures == 0 and totals["stale_seen"] == 0 and (growth is None or growth <= args.max_growth_percent)
    summary = {"minutes": round(duration / 60, 1), "scans_ok": totals["ok"], "scan_errors": totals["errors"], "reloads": totals["reloads"],
               "stale_intervals": totals["stale_seen"], "rss_first_mb": readings[0] if readings else None,
               "rss_last_mb": readings[-1] if readings else None, "rss_max_mb": max(readings) if readings else None,
               "rss_growth_percent": growth, "verdict": "PASS" if verdict else "FAIL", "report": str(out)}
    out.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if verdict else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
