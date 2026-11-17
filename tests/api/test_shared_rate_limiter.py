"""Postgres-backed abuse limiter: exact limits across independent pools, fail closed, same middleware contract.

Runs against the retained local Postgres but only touches a throw-away table with a random name, dropped at the end.
Skipped (with the reason) when that database is not running.
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from campus247.infrastructure.rate_limit.postgres_store import PostgresRateLimiterStore  # noqa: E402
from campus247.presentation.middleware.abuse_limits import AbuseLimiterMiddleware, RateLimitRule  # noqa: E402


async def open_pool():
    """A small pool (the local server allows 20 connections in total and the running runtime already holds some)."""
    import asyncpg
    try:
        import knowledge_platform as platform
        value = platform.connection()
        pool = await asyncpg.create_pool(**value, min_size=1, max_size=2, command_timeout=10)
    except Exception as error:  # noqa: BLE001
        pytest.skip(f"retained local Postgres not available or out of free connections: {type(error).__name__}")
    return pool


@pytest.fixture
def table():
    return "rl_test_" + uuid.uuid4().hex[:12]


def drop(pool, table):
    async def run():
        async with pool.acquire() as conn:
            await conn.execute(f"DROP TABLE IF EXISTS {table}")
    return run()


@pytest.mark.asyncio
async def test_limit_counts_down_then_rejects_with_retry_after(table):
    pool = await open_pool()
    try:
        store = PostgresRateLimiterStore(lambda: pool, table=table)
        results = [await store.check_and_increment("usr:a:/v1/x", 5, 60) for _ in range(7)]
        assert [r[0] for r in results] == [True] * 5 + [False] * 2
        assert [r[1] for r in results[:5]] == [4, 3, 2, 1, 0]
        assert all(1 <= r[2] <= 60 for r in results[5:])
        assert (await store.check_and_increment("usr:b:/v1/x", 5, 60))[0] is True  # another key is independent
    finally:
        await drop(pool, table)
        await pool.close()


@pytest.mark.asyncio
async def test_several_processes_together_allow_exactly_the_limit(table):
    """Three independent pools and store instances stand in for three API processes, racing on one key."""
    pools = [await open_pool() for _ in range(3)]
    try:
        stores = [PostgresRateLimiterStore(lambda p=p: p, table=table) for p in pools]
        outcomes = await asyncio.gather(*[stores[i % 3].check_and_increment("usr:race:/v1/conversations", 30, 60)
                                          for i in range(90)])
        assert sum(1 for allowed, _, _ in outcomes if allowed) == 30
        assert sum(1 for allowed, _, _ in outcomes if not allowed) == 60
    finally:
        await drop(pools[0], table)
        for pool in pools:
            await pool.close()


@pytest.mark.asyncio
async def test_window_expires(table):
    pool = await open_pool()
    try:
        store = PostgresRateLimiterStore(lambda: pool, table=table)
        assert (await store.check_and_increment("k", 1, 1))[0] is True
        assert (await store.check_and_increment("k", 1, 1))[0] is False
        await asyncio.sleep(1.2)
        assert (await store.check_and_increment("k", 1, 1))[0] is True
    finally:
        await drop(pool, table)
        await pool.close()


@pytest.mark.parametrize("name", ["", "Bad-Name", "a;drop table x", "1abc", "x" * 64])
def test_table_name_must_be_a_plain_identifier(name):
    with pytest.raises(ValueError):
        PostgresRateLimiterStore(lambda: None, table=name)


# ---- through the middleware: same contract, fail closed ---------------------------------------------------------

def app_with(store, *, fail_closed=True):
    app = FastAPI()

    @app.get("/v1/x")
    async def route():
        return {"ok": True}

    app.add_middleware(AbuseLimiterMiddleware, store=store,
                       rules=[RateLimitRule("/v1/x", max_requests=2, window_seconds=60, fail_closed=fail_closed)])
    return app


class Broken:
    async def check_and_increment(self, key, max_requests, window_seconds):
        raise ConnectionError("database down")


def test_middleware_fails_closed_when_the_shared_store_is_down():
    client = TestClient(app_with(Broken()))
    reply = client.get("/v1/x")
    assert reply.status_code == 503 and reply.headers["retry-after"] == "30"


def test_missing_pool_fails_closed():
    client = TestClient(app_with(PostgresRateLimiterStore(lambda: None)))
    assert client.get("/v1/x").status_code == 503


def test_fail_open_rule_still_serves_when_the_store_is_down():
    assert TestClient(app_with(Broken(), fail_closed=False)).get("/v1/x").status_code == 200


def test_middleware_awaits_an_async_store_and_returns_429_with_headers():
    class Counting:
        def __init__(self):
            self.n = 0

        async def check_and_increment(self, key, max_requests, window_seconds):
            self.n += 1
            return (True, max_requests - self.n, 0) if self.n <= max_requests else (False, 0, 17)

    client = TestClient(app_with(Counting()))
    assert [client.get("/v1/x").status_code for _ in range(3)] == [200, 200, 429]
    denied = client.get("/v1/x")
    assert denied.headers["retry-after"] == "17" and denied.headers["x-ratelimit-remaining"] == "0"
