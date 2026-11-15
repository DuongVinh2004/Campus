from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import inspect
import threading
from typing import Any
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response


@dataclass(frozen=True)
class RateLimitRule:
    path_prefix: str
    max_requests: int
    window_seconds: int
    fail_closed: bool = True


class InMemoryRateLimiterStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, list[float]] = {}
        self._injected_error: Exception | None = None

    def inject_error(self, error: Exception | None) -> None:
        self._injected_error = error

    def check_and_increment(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, int, int]:
        if self._injected_error is not None:
            raise self._injected_error

        now = datetime.now(timezone.utc).timestamp()
        cutoff = now - window_seconds

        with self._lock:
            history = self._hits.get(key, [])
            # Filter timestamps within current window
            valid_hits = [t for t in history if t > cutoff]

            if len(valid_hits) >= max_requests:
                earliest = valid_hits[0]
                retry_after = max(1, int(window_seconds - (now - earliest)))
                self._hits[key] = valid_hits
                return False, 0, retry_after

            valid_hits.append(now)
            self._hits[key] = valid_hits
            remaining = max(0, max_requests - len(valid_hits))
            return True, remaining, 0


class AbuseLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: Any,
        store: Any | None = None,  # InMemoryRateLimiterStore, or any store with (async) check_and_increment
        rules: list[RateLimitRule] | None = None,
        trusted_proxies: set[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._store = store or InMemoryRateLimiterStore()
        self._rules = rules or []
        self._trusted_proxies = trusted_proxies or set()

    def _match_rule(self, path: str) -> RateLimitRule | None:
        for rule in self._rules:
            if path.startswith(rule.path_prefix):
                return rule
        return None

    def _resolve_limiter_key(self, request: Request, rule: RateLimitRule) -> str:
        # 1. Principal-aware isolation: if authenticated, key by subject_id
        identity = getattr(request.state, "identity", None)
        if identity and getattr(identity, "subject_id", None):
            return f"usr:{identity.subject_id}:{rule.path_prefix}"

        # 2. Network-aware isolation: derive network IP strictly from socket connection
        # AC-TASK-API-ABUSE-001-02: Client-controlled forwarding headers cannot bypass or poison limiter key
        peer_ip = request.client.host if request.client else "unknown"
        return f"net:{peer_ip}:{rule.path_prefix}"

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        rule = self._match_rule(request.url.path)
        if not rule:
            return await call_next(request)

        key = self._resolve_limiter_key(request, rule)

        try:
            outcome = self._store.check_and_increment(
                key=key,
                max_requests=rule.max_requests,
                window_seconds=rule.window_seconds,
            )
            if inspect.isawaitable(outcome):  # a shared (database) store is a coroutine
                outcome = await outcome
            allowed, remaining, retry_after = outcome
        except Exception:
            # AC-TASK-API-ABUSE-001-03: Fail-closed on expensive endpoints, bounded-safe otherwise
            if rule.fail_closed:
                return JSONResponse(
                    status_code=503,
                    content={
                        "type": "urn:problem-type:service-unavailable",
                        "title": "Service Unavailable",
                        "status": 503,
                        "detail": "Rate limiter backend unavailable; request rejected to protect resources.",
                    },
                    headers={"Retry-After": "30"},
                )
            return await call_next(request)

        if not allowed:
            # AC-TASK-API-ABUSE-001-01: Excess requests rejected before expensive work
            return JSONResponse(
                status_code=429,
                content={
                    "type": "urn:problem-type:rate-limit-exceeded",
                    "title": "Too Many Requests",
                    "status": 429,
                    "detail": f"Rate limit exceeded. Maximum {rule.max_requests} requests per {rule.window_seconds}s.",
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(rule.max_requests),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(rule.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
