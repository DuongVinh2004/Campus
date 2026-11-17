"""Operational numbers for the admin dashboard and the alert rules: counts per minute, latency histograms, and a way to
add up the several API worker processes without a database.

Only counts and fixed labels are stored: no question text, no user or conversation identifiers, no exception strings.
Each worker keeps a ring of the last hour in memory and writes it every few seconds to `worker-<pid>.json`; the reader
adds up the files that are still fresh. A worker that died stops updating its file and drops out of the sum on its own.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

# Upper bounds in seconds; a value above the last bound lands in one extra overflow bucket.
LATENCY_BUCKETS_S = (0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0, 30.0)
WINDOW_MINUTES = 60
SNAPSHOT_PREFIX = "worker-"
WRITE_EVERY_S = 15.0
FRESH_FOR_S = 60.0
DELETE_AFTER_S = 600.0

OUTCOMES = ("ok", "abstained", "error")
ROUTE_GROUPS = ("chat", "auth", "knowledge", "learning", "other")
_ERROR_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


def _bucket_index(seconds: float) -> int:
    for index, bound in enumerate(LATENCY_BUCKETS_S):
        if seconds <= bound:
            return index
    return len(LATENCY_BUCKETS_S)


def _empty_minute(minute: int) -> dict[str, Any]:
    size = len(LATENCY_BUCKETS_S) + 1
    return {"minute": minute, "turns": 0, "ok": 0, "abstained": 0, "errors": {}, "first_token": [0] * size,
            "total": [0] * size, "admission_rejected": 0, "rate_limited": {}, "loop_blocked": 0, "loop_blocked_max_ms": 0}


def merge_minute(into: dict[str, Any], other: dict[str, Any]) -> dict[str, Any]:
    """Add `other` into `into` (same minute). Counters add, the longest block is the maximum."""
    for key in ("turns", "ok", "abstained", "admission_rejected", "loop_blocked"):
        into[key] += other.get(key, 0)
    for key in ("errors", "rate_limited"):
        for name, count in other.get(key, {}).items():
            into[key][name] = into[key].get(name, 0) + count
    for key in ("first_token", "total"):
        for index, count in enumerate(other.get(key, ())):
            into[key][index] += count
    into["loop_blocked_max_ms"] = max(into["loop_blocked_max_ms"], other.get("loop_blocked_max_ms", 0))
    return into


class OpsMetrics:
    """Per-process counters. Thread-safe: the chat route runs on the event loop, the loop watchdog on its own thread."""

    def __init__(self, clock: Callable[[], float] = time.time, window_minutes: int = WINDOW_MINUTES) -> None:
        self._clock, self._window = clock, window_minutes
        self._lock = threading.Lock()
        self._minutes: dict[int, dict[str, Any]] = {}
        self.gauges: dict[str, int] = {"in_flight": 0, "waiting": 0, "limit": 0}
        self.started_at = clock()

    def _bucket(self) -> dict[str, Any]:
        minute = int(self._clock() // 60)
        bucket = self._minutes.get(minute)
        if bucket is None:
            bucket = self._minutes[minute] = _empty_minute(minute)
            for old in [m for m in self._minutes if m <= minute - self._window]:
                del self._minutes[old]
        return bucket

    def record_turn(self, *, outcome: str, error_code: str | None = None, first_token_s: float | None = None,
                    total_s: float = 0.0) -> None:
        if outcome not in OUTCOMES:
            raise ValueError(f"outcome must be one of {OUTCOMES}")
        with self._lock:
            bucket = self._bucket()
            bucket["turns"] += 1
            if outcome == "error":
                code = error_code if error_code and _ERROR_CODE.match(error_code) else "OTHER"
                bucket["errors"][code] = bucket["errors"].get(code, 0) + 1
            else:
                bucket[outcome] += 1
            if first_token_s is not None:
                bucket["first_token"][_bucket_index(max(0.0, first_token_s))] += 1
            bucket["total"][_bucket_index(max(0.0, total_s))] += 1

    def record_admission_rejected(self) -> None:
        with self._lock:
            self._bucket()["admission_rejected"] += 1

    def record_rate_limited(self, route_group: str) -> None:
        group = route_group if route_group in ROUTE_GROUPS else "other"
        with self._lock:
            limited = self._bucket()["rate_limited"]
            limited[group] = limited.get(group, 0) + 1

    def record_loop_blocked(self, milliseconds: int) -> None:
        with self._lock:
            bucket = self._bucket()
            bucket["loop_blocked"] += 1
            bucket["loop_blocked_max_ms"] = max(bucket["loop_blocked_max_ms"], int(milliseconds))

    def set_gauges(self, *, in_flight: int, waiting: int, limit: int) -> None:
        with self._lock:
            self.gauges = {"in_flight": int(in_flight), "waiting": int(waiting), "limit": int(limit)}

    def snapshot(self, retrieval: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            now = self._clock()
            cutoff = int(now // 60) - self._window
            minutes = [json.loads(json.dumps(b)) for m, b in sorted(self._minutes.items()) if m > cutoff]
            return {"version": 1, "pid": os.getpid(), "started_at": self.started_at, "written_at": now,
                    "gauges": dict(self.gauges), "retrieval": dict(retrieval or {}), "minutes": minutes}


# ----------------------------------------------------------------------------------------- sharing between workers

def write_snapshot(directory: Path, snapshot: dict[str, Any]) -> Path:
    """Write this worker's file atomically: a reader never sees half a file."""
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{SNAPSHOT_PREFIX}{snapshot['pid']}.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(snapshot, separators=(",", ":")), encoding="utf-8")
    os.replace(temporary, target)
    return target


def prune_snapshots(directory: Path, *, now: float | None = None, older_than_s: float = DELETE_AFTER_S) -> int:
    """Delete worker snapshot files that stopped updating long ago. Touches only files this module wrote."""
    now = time.time() if now is None else now
    removed = 0
    for path in directory.glob(f"{SNAPSHOT_PREFIX}*.json"):
        try:
            if now - json.loads(path.read_text(encoding="utf-8")).get("written_at", 0) > older_than_s:
                path.unlink()
                removed += 1
        except (OSError, ValueError):
            continue
    return removed


def aggregate(directory: Path, *, now: float | None = None, fresh_for_s: float = FRESH_FOR_S) -> dict[str, Any]:
    """Add up the fresh worker files: minutes merge, gauges and retrieval counters add, `workers_reporting` counts files."""
    now = time.time() if now is None else now
    minutes: dict[int, dict[str, Any]] = {}
    gauges = {"in_flight": 0, "waiting": 0, "limit": 0}
    retrieval = {"retrievals": 0, "failed": 0, "timeouts": 0, "vector_ms_max": 0}
    workers = 0
    for path in sorted(directory.glob(f"{SNAPSHOT_PREFIX}*.json")) if directory.is_dir() else []:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue  # being replaced or damaged; the next read sees it whole
        if not isinstance(data, dict) or now - data.get("written_at", 0) > fresh_for_s:
            continue
        workers += 1
        for key in gauges:
            gauges[key] += int(data.get("gauges", {}).get(key, 0))
        for key in ("retrievals", "failed", "timeouts"):
            retrieval[key] += int(data.get("retrieval", {}).get(key, 0))
        retrieval["vector_ms_max"] = max(retrieval["vector_ms_max"], int(data.get("retrieval", {}).get("vector_ms_max", 0)))
        for item in data.get("minutes", []):
            merge_minute(minutes.setdefault(item["minute"], _empty_minute(item["minute"])), item)
    retrieval["failed_rate"] = retrieval["failed"] / retrieval["retrievals"] if retrieval["retrievals"] else 0.0
    return {"workers_reporting": workers, "now": now, "gauges": gauges, "retrieval": retrieval,
            "minutes": [minutes[m] for m in sorted(minutes)]}


async def run_writer(metrics: OpsMetrics, directory: Path, *, retrieval: Callable[[], dict[str, Any]] | None = None,
                     every_s: float = WRITE_EVERY_S) -> None:
    """Background task for each API worker. A failed write is skipped; the next one tries again."""
    while True:
        try:
            write_snapshot(directory, metrics.snapshot(retrieval() if retrieval else None))
            prune_snapshots(directory)
        except OSError:
            pass
        await asyncio.sleep(every_s)


# ----------------------------------------------------------------------------------------- reading a window

def percentile_upper_bound(histogram: list[int], quantile: float) -> float | None:
    """Smallest bucket bound that holds `quantile` of the samples; inf for the overflow bucket; None without samples."""
    total = sum(histogram)
    if total == 0:
        return None
    needed, seen = quantile * total, 0
    for index, count in enumerate(histogram):
        seen += count
        if seen >= needed:
            return LATENCY_BUCKETS_S[index] if index < len(LATENCY_BUCKETS_S) else float("inf")
    return float("inf")


def summarize_window(aggregated: dict[str, Any], *, minutes: int) -> dict[str, Any]:
    """Totals over the last `minutes` complete-or-current minutes ending at `aggregated["now"]`."""
    last = int(aggregated["now"] // 60)
    chosen = [m for m in aggregated["minutes"] if last - minutes < m["minute"] <= last]
    total = _empty_minute(last)
    for item in chosen:
        merge_minute(total, item)
    errors = sum(total["errors"].values())
    turns = total["turns"]
    return {"minutes": minutes, "turns": turns, "ok": total["ok"], "abstained": total["abstained"], "errors": dict(total["errors"]),
            "error_rate": errors / turns if turns else 0.0,
            "p50_s_le": percentile_upper_bound(total["total"], 0.50), "p95_s_le": percentile_upper_bound(total["total"], 0.95),
            "first_token_p95_s_le": percentile_upper_bound(total["first_token"], 0.95),
            "admission_rejected": total["admission_rejected"],
            "admission_rejected_rate": total["admission_rejected"] / (turns + total["admission_rejected"]) if turns + total["admission_rejected"] else 0.0,
            "rate_limited": dict(total["rate_limited"]), "loop_blocked": total["loop_blocked"],
            "loop_blocked_max_ms": total["loop_blocked_max_ms"]}
