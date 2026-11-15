"""Rate limiter store shared by every API process: sliding window kept in Postgres.

The in-memory store counts per process, so N API processes would allow N times the limit. This store keeps one row per
accepted request and decides under a per-key advisory lock, so concurrent processes see one consistent window.
Same contract as InMemoryRateLimiterStore.check_and_increment, but a coroutine.

Failures (pool missing, timeout, database error) raise: AbuseLimiterMiddleware turns that into 503 for fail-closed
rules, exactly as for the in-memory store. Nothing here allows a request when the store is unavailable.
Time comes from the database clock so all processes agree. Stored: the limiter key (pseudonymous subject id or peer
address plus path prefix) and a timestamp; rows leave the window after `window_seconds` and are pruned on the next hit.
"""
from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from typing import Any

DEFAULT_TABLE = "app_rate_limit_hit"
QUERY_TIMEOUT_S = 2.0  # a limiter that waits longer than this is as good as down: fail closed
_SCHEMA_LOCK_ID = 727_001
_NAME = re.compile(r"[a-z_][a-z0-9_]{0,62}")


class PostgresRateLimiterStore:
    def __init__(self, pool_provider: Callable[[], Any], *, table: str = DEFAULT_TABLE) -> None:
        if not _NAME.fullmatch(table):
            raise ValueError("plain table identifier required")
        self._pool_provider, self._table = pool_provider, table
        self._ready = False
        self._ready_lock: asyncio.Lock | None = None
        self._calls = 0

    async def _ensure_schema(self, pool) -> None:
        if self._ready:
            return
        if self._ready_lock is None:
            self._ready_lock = asyncio.Lock()
        async with self._ready_lock:
            if self._ready:
                return
            # Several processes may start together: serialise the DDL, which is not safe to race.
            async with pool.acquire(timeout=QUERY_TIMEOUT_S * 5) as conn:
                await conn.execute("SELECT pg_advisory_lock($1)", _SCHEMA_LOCK_ID, timeout=QUERY_TIMEOUT_S * 5)
                try:
                    await conn.execute(f"CREATE TABLE IF NOT EXISTS {self._table} "
                                       "(key text NOT NULL, hit_at double precision NOT NULL)")
                    await conn.execute(f"CREATE INDEX IF NOT EXISTS {self._table}_key_at ON {self._table} (key, hit_at)")
                finally:
                    await conn.execute("SELECT pg_advisory_unlock($1)", _SCHEMA_LOCK_ID)
            self._ready = True

    async def check_and_increment(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int, int]:
        pool = self._pool_provider()
        if pool is None:
            raise RuntimeError("rate limiter pool unavailable")
        await self._ensure_schema(pool)
        async with pool.acquire(timeout=QUERY_TIMEOUT_S) as conn:
            async with conn.transaction():
                await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", key, timeout=QUERY_TIMEOUT_S)
                row = await conn.fetchrow(
                    f"WITH pruned AS (DELETE FROM {self._table} WHERE key = $1 "
                    "AND hit_at <= (extract(epoch from clock_timestamp())::double precision) - $2 RETURNING 1) "
                    f"SELECT count(*) AS n, min(hit_at) AS earliest, (extract(epoch from clock_timestamp())::double precision) AS now "
                    f"FROM {self._table} WHERE key = $1 AND hit_at > (extract(epoch from clock_timestamp())::double precision) - $2",
                    key, float(window_seconds), timeout=QUERY_TIMEOUT_S)
                count, earliest, now = row["n"], row["earliest"], row["now"]
                if count >= max_requests:
                    return False, 0, max(1, int(window_seconds - (now - earliest)))
                await conn.execute(f"INSERT INTO {self._table} (key, hit_at) VALUES ($1, $2)", key, now,
                                   timeout=QUERY_TIMEOUT_S)
        self._calls += 1
        if self._calls % 500 == 0:
            await self._prune_stale(pool, window_seconds)
        return True, max(0, max_requests - count - 1), 0

    async def _prune_stale(self, pool, window_seconds: int) -> None:
        """Keys that stopped asking would otherwise stay forever; drop anything older than a day."""
        try:
            async with pool.acquire(timeout=QUERY_TIMEOUT_S) as conn:
                await conn.execute(f"DELETE FROM {self._table} WHERE hit_at < (extract(epoch from clock_timestamp())::double precision) - $1",
                                   float(max(86_400, window_seconds * 10)), timeout=QUERY_TIMEOUT_S)
        except Exception:  # noqa: BLE001 -- housekeeping must never fail a request
            pass
