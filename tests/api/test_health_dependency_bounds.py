"""Readiness must not fabricate connectivity or leave acquisition unbounded."""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from campus247.presentation import health


def request_for(engine):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(db_engine=engine)))


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["connect", "query"])
async def test_database_probe_deadline_covers_connection_and_query(monkeypatch, phase):
    cancelled = asyncio.Event()
    entered = asyncio.Event()
    exited = asyncio.Event()

    async def stall():
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    class Connection:
        async def execute(self, query):
            assert str(query) == "SELECT 1"
            if phase == "query":
                await stall()

    class Acquisition:
        async def __aenter__(self):
            if phase == "connect":
                await stall()
            return Connection()

        async def __aexit__(self, *args):
            exited.set()

    engine = SimpleNamespace(connect=lambda: Acquisition())
    real_wait_for = asyncio.wait_for
    observed_budgets = []

    async def short_budget(awaitable, timeout):
        observed_budgets.append(timeout)
        return await real_wait_for(awaitable, timeout=0.01)

    monkeypatch.setattr(health.asyncio, "wait_for", short_budget)
    assert await real_wait_for(health.check_database_connectivity(request_for(engine)), timeout=1) == "unavailable"
    assert observed_budgets == [2.0]
    assert entered.is_set() and cancelled.is_set()
    assert exited.is_set() == (phase == "query")


@pytest.mark.asyncio
async def test_database_probe_propagates_request_cancellation():
    entered = asyncio.Event()
    closed = asyncio.Event()

    class Acquisition:
        async def __aenter__(self):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                closed.set()

        async def __aexit__(self, *args):
            pass

    task = asyncio.create_task(health.check_database_connectivity(request_for(SimpleNamespace(connect=lambda: Acquisition()))))
    await asyncio.wait_for(entered.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=1)
    assert closed.is_set()


@pytest.mark.asyncio
async def test_database_probe_reports_ready_only_after_success_and_closure():
    events = []

    class Connection:
        async def execute(self, query):
            events.append(str(query))

    class Acquisition:
        async def __aenter__(self):
            events.append("connected")
            return Connection()

        async def __aexit__(self, *args):
            events.append("closed")

    assert await health.check_database_connectivity(request_for(SimpleNamespace(connect=lambda: Acquisition()))) == "ready"
    assert events == ["connected", "SELECT 1", "closed"]


def test_unbound_redis_is_disabled_not_ready():
    app = FastAPI()
    app.include_router(health.router)
    response = TestClient(app).get("/health/ready")
    assert response.status_code == 200
    body = health.ReadinessStatus.model_validate(response.json())
    assert {d.name: d.status for d in body.dependencies} == {"database": "disabled", "redis": "disabled"}


def test_failed_database_initialization_cannot_be_reported_as_disabled(monkeypatch):
    from campus247.bootstrap import app as bootstrap

    def fail_initialization(_url):
        raise RuntimeError("synthetic-sensitive-database-detail")

    monkeypatch.setattr(bootstrap, "get_engine", fail_initialization)
    app = bootstrap.create_app()
    with TestClient(app) as client:
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["code"] == "DEPENDENCY_UNAVAILABLE"
        assert response.json()["retryable"] is True
        assert "synthetic-sensitive-database-detail" not in response.text
        assert client.get("/health/live").json() == {"status": "alive"}


def test_successful_database_lifecycle_checks_connectivity_and_disposes(monkeypatch):
    from campus247.bootstrap import app as bootstrap
    events = []

    class Connection:
        async def execute(self, query):
            events.append(str(query))

    class Acquisition:
        async def __aenter__(self):
            events.append("connected")
            return Connection()

        async def __aexit__(self, *args):
            events.append("closed")

    class Engine:
        def connect(self):
            return Acquisition()

        async def dispose(self):
            events.append("disposed")

    monkeypatch.setattr(bootstrap, "get_engine", lambda _url: Engine())
    app = bootstrap.create_app()
    with TestClient(app) as client:
        response = client.get("/health/ready")
        assert response.status_code == 200
        statuses = {d["name"]: d["status"] for d in response.json()["dependencies"]}
        assert statuses == {"database": "ready", "redis": "disabled"}
    assert events == ["connected", "SELECT 1", "closed", "disposed"]
