"""Operations status for administrators: one JSON document for the page and a text exposition for a local scraper.

`/metrics` is meant for a process on the same machine. A reverse proxy also connects from 127.0.0.1, so the loopback
test alone would let the internet in; any forwarding header therefore refuses the request.
"""
from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from campus247.application.campus_ops.service import ADMIN_ROLES
from campus247.observability.ops_status import OpsConfig, ProbeCache, build_status
from campus247.presentation.identity import get_current_identity

NO_STORE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
LOOPBACK = {"127.0.0.1", "::1"}
FORWARDING_HEADERS = ("x-forwarded-for", "x-forwarded-host", "x-forwarded-proto", "forwarded", "x-real-ip")


def _line(name: str, value: Any, labels: dict[str, str] | None = None) -> str | None:
    if value is None:
        return None
    suffix = "{" + ",".join(f'{key}="{val}"' for key, val in sorted((labels or {}).items())) + "}" if labels else ""
    return f"{name}{suffix} {float(value):g}"


def render_prometheus(status: dict[str, Any]) -> str:
    """Prometheus text format (gauges only) from the status document. Missing values are left out, never written as 0."""
    five, hour = status["turns"]["last_5m"], status["turns"]["last_60m"]
    lines: list[str | None] = [
        _line("campus247_workers_reporting", status["workers_reporting"]),
        _line("campus247_turns_5m", five["turns"]), _line("campus247_turns_60m", hour["turns"]),
        _line("campus247_turn_errors_5m", sum(five["errors"].values())),
        _line("campus247_turn_abstained_5m", five["abstained"]),
        _line("campus247_admission_rejected_5m", five["admission_rejected"]),
        _line("campus247_turn_p95_seconds_le_5m", five["p95_s_le"]),
        _line("campus247_loop_blocked_5m", five["loop_blocked"]),
        _line("campus247_in_flight", status["load"]["in_flight"]), _line("campus247_waiting", status["load"]["waiting"]),
        _line("campus247_in_flight_limit", status["load"]["limit"]),
        _line("campus247_vector_failed_rate", status["retrieval"]["failed_rate"]),
        _line("campus247_data_free_percent", status["storage"]["data_free_pct"]),
    ]
    for group, count in sorted(five["rate_limited"].items()):
        lines.append(_line("campus247_rate_limited_5m", count, {"group": group}))
    for model, state in sorted(status["models"].items()):
        lines.append(_line("campus247_model_up", 1 if state == "up" else 0, {"model": model}))
    gateway = status["gateway"]
    if gateway.get("reachable") is not None:
        lines.append(_line("campus247_gateway_up", 1 if gateway["reachable"] else 0))
    today = gateway.get("today") or {}
    lines += [_line("campus247_gateway_calls_today", today.get("calls")),
              _line("campus247_gateway_usd_today", today.get("usd")),
              _line("campus247_gateway_cap_reached", None if "cap_reached" not in today else int(today["cap_reached"]))]
    return "\n".join(line for line in lines if line) + "\n"


def create_admin_ops_router(config: OpsConfig, *, client: httpx.AsyncClient | None = None,
                            cache: ProbeCache | None = None) -> APIRouter:
    router = APIRouter(tags=["Operations"])
    shared_cache = cache or ProbeCache()
    owned_client = client

    def http() -> httpx.AsyncClient:
        nonlocal owned_client
        if owned_client is None:
            owned_client = httpx.AsyncClient(trust_env=False)
        return owned_client

    @router.get("/v1/admin/operations/status")
    async def status(request: Request):
        identity = get_current_identity(request)
        if not ADMIN_ROLES.intersection(identity.roles):
            return JSONResponse({"status": 403, "code": "FORBIDDEN", "detail": "Chỉ quản trị viên mới xem được trang này."},
                                status_code=403, headers=NO_STORE)
        return JSONResponse(await build_status(config, client=http(), cache=shared_cache), headers=NO_STORE)

    @router.get("/metrics", include_in_schema=False)
    async def metrics(request: Request):
        local = request.client is not None and request.client.host in LOOPBACK
        if not local or any(header in request.headers for header in FORWARDING_HEADERS):
            return PlainTextResponse("forbidden\n", status_code=403, headers=NO_STORE)
        return PlainTextResponse(render_prometheus(await build_status(config, client=http(), cache=shared_cache)),
                                 media_type="text/plain; version=0.0.4", headers=NO_STORE)

    return router
