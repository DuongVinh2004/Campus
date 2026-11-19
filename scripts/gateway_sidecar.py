"""Gateway sidecar: the one process that owns the paid provider, the paid ledger and the spend cap.

API processes (any number) call it on loopback with an internal token (campus247.infrastructure.llm.remote_gateway).
It reuses the retained in-process Gateway unchanged, so the ledger lease, budget reservation and settlement, egress
policy and the operation bounds (28,000 bytes, 1000 output tokens, 5000 ms per call) are exactly as before; it adds a
daily spend and call cap and an internal token. Run it with infra/local/rag-fixture/.venv/Scripts/python.exe -B.

  python scripts/gateway_sidecar.py serve --port 8025 [--concurrency 16] [--daily-usd-cap 5.00] [--daily-call-cap 2000]

A cap of 0 means "no daily cap" (the retained accounting-only mode). A request that would start after the cap is
reached is refused with 429 before any provider call; calls already running may finish, so the overshoot is bounded
by the provider concurrency times the cost reserved for one call.
"""
from __future__ import annotations

import argparse
import hmac
import json
import logging
import os
import secrets
import sys
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts"), str(ROOT / "services/api/src"), str(ROOT / "packages/synthetic/src"),
                str(ROOT / "infra/local/rag-fixture")]

from fastapi import FastAPI, Request  # noqa: E402  (module level: FastAPI resolves the Request annotation by name)
from fastapi.responses import JSONResponse  # noqa: E402

from campus247.infrastructure.llm.gateway_wire import (  # noqa: E402
    MAX_BODY_BYTES, WireError, request_from_json, response_to_json)

STATE = ROOT / "infra/local/public-rag-20261013"
TOKEN_FILE = STATE / "gateway-sidecar.token"
CAP_FILE = STATE / "gateway-daily-cap.json"
ICT = timezone(timedelta(hours=7))
LOG = logging.getLogger("campus247.gateway")


class CapReached(Exception):
    pass


class DailySpendCap:
    """Counts the day's spend and calls as the change in the retained budget snapshot since the day began (ICT)."""

    def __init__(self, path: Path, snapshot, *, usd_cap: Decimal, call_cap: int, now=lambda: datetime.now(ICT)):
        self._path, self._snapshot, self.usd_cap, self.call_cap, self._now = path, snapshot, usd_cap, call_cap, now

    def _baseline(self, snap) -> dict:
        day = self._now().date().isoformat()
        try:
            value = json.loads(self._path.read_text(encoding="utf-8"))
            if value.get("day") == day:
                return value
        except (OSError, ValueError):
            pass
        value = {"day": day, "usd0": str(snap["conservative_charged_usd"]), "calls0": int(snap["calls"])}
        self._path.write_text(json.dumps(value), encoding="utf-8")
        return value

    def today(self) -> tuple[Decimal, int]:
        snap = self._snapshot()
        base = self._baseline(snap)
        return Decimal(str(snap["conservative_charged_usd"])) - Decimal(base["usd0"]), int(snap["calls"]) - base["calls0"]

    def check(self) -> None:
        if not self.usd_cap and not self.call_cap:
            return
        spent, calls = self.today()
        if self.usd_cap and spent >= self.usd_cap or self.call_cap and calls >= self.call_cap:
            raise CapReached


def load_or_create_token(path: Path = TOKEN_FILE) -> str:
    if path.exists():
        return path.read_text(encoding="ascii").strip()
    token = secrets.token_hex(32)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="ascii") as stream:
        stream.write(token)
    return token


def create_sidecar_app(gateway, token: str, cap: DailySpendCap | None = None):
    """The HTTP surface; `gateway` is the retained Gateway (or a test double with the same generate/capabilities)."""
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    counters = {"ok": 0, "refused": 0, "failed": 0, "in_flight": 0}
    app.state.counters = counters

    def authorized(request: Request) -> bool:
        return hmac.compare_digest(request.headers.get("x-gateway-token", "").encode(), token.encode())

    @app.get("/health")
    async def health():
        return {"status": "ok", **counters}

    @app.get("/v1/status")
    async def status(request: Request):
        """Counters and today's spend against the daily cap, for the operations page and the alert rules. Read only."""
        if not authorized(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        today = None
        if cap is not None:
            spent, calls = cap.today()
            reached = bool(cap.usd_cap and spent >= cap.usd_cap or cap.call_cap and calls >= cap.call_cap)
            today = {"usd": str(spent), "calls": calls, "usd_cap": str(cap.usd_cap), "call_cap": cap.call_cap,
                     "cap_enabled": bool(cap.usd_cap or cap.call_cap), "cap_reached": reached}
        return {"counters": dict(counters), "today": today}

    @app.get("/v1/capabilities")
    async def capabilities(request: Request):
        if not authorized(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        value = gateway.capabilities("deepseek", "deepseek-flash")
        return {key: getattr(value, key) for key in value.__dataclass_fields__}

    @app.post("/v1/generate")
    async def generate(request: Request):
        if not authorized(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        raw = await request.body()
        if len(raw) > MAX_BODY_BYTES:
            return JSONResponse({"error": "body too large"}, status_code=413)
        try:
            llm_request = request_from_json(json.loads(raw))
        except (ValueError, WireError):
            return JSONResponse({"error": "invalid request"}, status_code=400)
        if cap is not None:
            try:
                cap.check()
            except CapReached:
                counters["refused"] += 1
                LOG.warning("gateway_call refused reason=daily_cap")
                return JSONResponse({"error": "daily cap reached"}, status_code=429)
        counters["in_flight"] += 1
        started = time.monotonic()
        try:
            response = await gateway.generate(llm_request)
        except ValueError as error:
            if "operation bound" in str(error):
                counters["refused"] += 1
                return JSONResponse({"error": "operation bound"}, status_code=400)
            counters["failed"] += 1
            LOG.warning("gateway_call failed kind=%s ms=%d", type(error).__name__, (time.monotonic() - started) * 1000)
            return JSONResponse({"error_type": type(error).__name__}, status_code=502)
        except Exception as error:  # noqa: BLE001 -- the provider side failed; the retained gateway already settled the ledger
            counters["failed"] += 1
            LOG.warning("gateway_call failed kind=%s ms=%d", type(error).__name__, (time.monotonic() - started) * 1000)
            return JSONResponse({"error_type": type(error).__name__}, status_code=502)
        finally:
            counters["in_flight"] -= 1
        counters["ok"] += 1
        return response_to_json(response)

    return app


def build_gateway(concurrency: int):
    import run_public_rag
    from multi_agent_live_resources import restore_paid
    run_public_rag.PROVIDER_CONCURRENCY_LIMIT = concurrency

    class RetainedGateway(run_public_rag.Gateway):
        json_mode = True

        def _restore_budget(self, snapshot, pending):
            return restore_paid(snapshot, pending)

    return RetainedGateway()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("serve",))
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--concurrency", type=int, default=16)
    parser.add_argument("--daily-usd-cap", default="0", help="0 = no daily cap")
    parser.add_argument("--daily-call-cap", type=int, default=0, help="0 = no daily cap")
    args = parser.parse_args()
    if not 1 <= args.concurrency <= 200 or args.daily_call_cap < 0 or Decimal(args.daily_usd_cap) < 0:
        raise SystemExit("invalid limits")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    import uvicorn
    gateway = build_gateway(args.concurrency)  # takes the ledger lease first: a second sidecar fails closed here
    try:
        token = load_or_create_token()
        cap = DailySpendCap(CAP_FILE, gateway.budget.snapshot, usd_cap=Decimal(args.daily_usd_cap), call_cap=args.daily_call_cap)
        LOG.warning("gateway_sidecar_started port=%d concurrency=%d daily_usd_cap=%s daily_call_cap=%d", args.port,
                    args.concurrency, args.daily_usd_cap, args.daily_call_cap)
        uvicorn.run(create_sidecar_app(gateway, token, cap), host="127.0.0.1", port=args.port, log_level="warning")
    finally:
        gateway.close()


if __name__ == "__main__":
    main()
