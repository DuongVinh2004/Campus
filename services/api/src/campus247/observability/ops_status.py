"""The operations status document: metrics of the last hour plus live probes of the services around the API.

Everything is read only and bounded: probes time out after one second and are cached for ten, so the page cannot pile
requests onto a struggling model server. A probe that fails is reported as "down" or "unreachable", never as an error of
the page itself.
"""
from __future__ import annotations

import json
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from campus247.observability.ops_metrics import LATENCY_BUCKETS_S, WINDOW_MINUTES, aggregate, percentile_upper_bound, summarize_window

PROBE_TIMEOUT_S = 1.0
PROBE_CACHE_S = 10.0
BACKUP_FILES = {"last": "LAST_BACKUP.json", "offsite": "OFFSITE.json", "rehearsal": "REHEARSAL.json"}


@dataclass
class OpsConfig:
    metrics_dir: Path
    data_dir: Path
    backup_dir: Path | None = None
    model_urls: dict[str, str] = field(default_factory=dict)  # name -> URL answered with 2xx when the model server is up
    gateway_url: str | None = None
    gateway_token: str | None = None
    background: Callable[[], dict[str, Any]] | None = None  # {"leader": bool, "learning_worker": str}
    features: Callable[[], dict[str, Any]] | None = None  # {"off": n, "overrides": n, "restart_required": n, "store_error": bool}
    quality_dir: Path | None = None  # where evals/runners/nightly_retrieval.py writes LATEST.json


class ProbeCache:
    """Remembers a probe result for a few seconds. One cache per process."""

    def __init__(self, clock: Callable[[], float] = time.monotonic, ttl_s: float = PROBE_CACHE_S) -> None:
        self._clock, self._ttl, self._items = clock, ttl_s, {}

    async def get(self, key: str, fetch):
        stored = self._items.get(key)
        if stored is not None and self._clock() - stored[0] < self._ttl:
            return stored[1]
        value = await fetch()
        self._items[key] = (self._clock(), value)
        return value


def _free_pct(path: Path | None) -> float | None:
    if path is None:
        return None
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return None
    return round(100.0 * usage.free / usage.total, 1) if usage.total else None


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def backup_state(directory: Path | None, *, now: datetime) -> dict[str, Any]:
    """What the backup scripts last wrote: when, whether it verified, and how old it is."""
    if directory is None:
        return {"configured": False}
    state: dict[str, Any] = {"configured": True}
    for name, filename in BACKUP_FILES.items():
        record = _read_json(directory / filename)
        if record is None:
            state[name] = None
            continue
        at = record.get("finished_at") or record.get("at")
        age = None
        try:
            age = round((now - datetime.fromisoformat(str(at).replace("Z", "+00:00"))).total_seconds() / 3600, 1)
        except (TypeError, ValueError):
            pass
        state[name] = {"at": at, "ok": bool(record.get("ok", record.get("verified", False))), "age_hours": age}
    return state


def quality_state(directory: Path | None, *, now: datetime) -> dict[str, Any]:
    """The newest nightly retrieval check: its numbers, how old it is, and what fell against the baseline. Read only."""
    if directory is None:
        return {"configured": False}
    record = _read_json(directory / "LATEST.json")
    if record is None:
        return {"configured": True, "ran": False}
    age = None
    try:
        age = round((now - datetime.fromisoformat(str(record.get("at")).replace("Z", "+00:00"))).total_seconds() / 3600, 1)
    except (TypeError, ValueError):
        pass
    metrics = record.get("metrics") if isinstance(record.get("metrics"), dict) else None
    return {"configured": True, "ran": True, "at": record.get("at"), "age_hours": age, "ok": bool(record.get("ok")), "skipped": record.get("skipped"),
            "regressions": list(record.get("regressions") or []), "has_baseline": bool(record.get("baseline")),
            "metrics": {key: metrics[key] for key in ("cases", "any", "fused_top8", "survive") if key in metrics} if metrics else None}


async def _probe_model(client: httpx.AsyncClient, url: str) -> str:
    try:
        response = await client.get(url, timeout=PROBE_TIMEOUT_S)
        return "up" if response.status_code < 300 else "down"
    except (httpx.HTTPError, OSError):
        return "down"


async def _probe_gateway(client: httpx.AsyncClient, url: str, token: str) -> dict[str, Any]:
    try:
        response = await client.get(url.rstrip("/") + "/v1/status", headers={"X-Gateway-Token": token}, timeout=PROBE_TIMEOUT_S)
        if response.status_code != 200:
            return {"reachable": False, "reason": f"HTTP {response.status_code}"}
        body = response.json()
        return {"reachable": True, "counters": body.get("counters", {}), "today": body.get("today")}
    except (httpx.HTTPError, OSError, ValueError):
        return {"reachable": False, "reason": "unreachable"}


def _series(aggregated: dict[str, Any]) -> dict[str, list]:
    last = int(aggregated["now"] // 60)
    by_minute = {m["minute"]: m for m in aggregated["minutes"]}
    series: dict[str, list] = {"minute": [], "turns": [], "errors": [], "p95_s_le": []}
    for minute in range(last - WINDOW_MINUTES + 1, last + 1):
        item = by_minute.get(minute)
        bound = percentile_upper_bound(item["total"], 0.95) if item else None
        series["minute"].append(minute * 60)
        series["turns"].append(item["turns"] if item else 0)
        series["errors"].append(sum(item["errors"].values()) if item else 0)
        series["p95_s_le"].append(None if bound is None else (bound if bound != float("inf") else LATENCY_BUCKETS_S[-1] + 1))
    return series


def _json_safe(summary: dict[str, Any]) -> dict[str, Any]:
    """Infinity is the overflow bucket; JSON has no infinity, so it is reported as null with an explicit flag."""
    safe = dict(summary)
    for key in ("p50_s_le", "p95_s_le", "first_token_p95_s_le"):
        if safe.get(key) == float("inf"):
            safe[key] = None
            safe[key + "_over"] = LATENCY_BUCKETS_S[-1]
    return safe


async def build_status(config: OpsConfig, *, client: httpx.AsyncClient, cache: ProbeCache,
                       now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    aggregated = aggregate(config.metrics_dir, now=now.timestamp())
    models = {}
    for name, url in config.model_urls.items():
        models[name] = await cache.get("model:" + name, lambda url=url: _probe_model(client, url))
    gateway = {"reachable": None, "reason": "not_configured"}
    if config.gateway_url and config.gateway_token:
        gateway = await cache.get("gateway", lambda: _probe_gateway(client, config.gateway_url, config.gateway_token))
    return {
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "workers_reporting": aggregated["workers_reporting"],
        "window_minutes": WINDOW_MINUTES,
        "turns": {"last_5m": _json_safe(summarize_window(aggregated, minutes=5)),
                  "last_10m": _json_safe(summarize_window(aggregated, minutes=10)),
                  "last_60m": _json_safe(summarize_window(aggregated, minutes=60))},
        "load": aggregated["gauges"],
        "retrieval": aggregated["retrieval"],
        "models": models,
        "gateway": gateway,
        "background": config.background() if config.background else {},
        "features": config.features() if config.features else {},
        "storage": {"data_free_pct": _free_pct(config.data_dir), "backup_free_pct": _free_pct(config.backup_dir)},
        "backup": backup_state(config.backup_dir, now=now),
        "quality": quality_state(config.quality_dir, now=now),
        "series": _series(aggregated),
    }
