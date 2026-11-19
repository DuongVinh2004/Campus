"""Worker liveness and reconnect behavior without resetting durable state."""
import asyncio
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from knowledge_worker_loop import serve_worker


def worker(callback):
    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield self
        async def fetchval(self, query):
            assert query == "SELECT current_database()"
            return "isolated-worker-loop"
    return SimpleNamespace(repo=SimpleNamespace(tenant="isolated-tenant", pool=Pool()),
        owner="isolated-owner", run_once=callback)


def pulse_path():
    path = ROOT / "infra/local/knowledge-automation-20261026" / ("worker-loop-test-"+uuid4().hex+".jsonl")
    assert path.resolve().is_relative_to(ROOT)
    return path


def test_long_job_has_database_verified_pulses_and_shutdown_is_never_reported_live():
    async def run():
        path = pulse_path()
        entered = asyncio.Event()
        async def process():
            entered.set()
            await asyncio.Event().wait()
        task = asyncio.create_task(serve_worker(worker(process), "isolated-worker-loop", path, pulse_interval=.005))
        await entered.wait()
        await asyncio.sleep(.025)
        during = [json.loads(line) for line in path.read_text().splitlines()]
        assert len(during) >= 2
        assert all(item["state"] == "PROCESSING" and item["database_verified"] for item in during)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        final = json.loads(path.read_text().splitlines()[-1])
        assert final["state"] == "STOPPED" and not final["database_verified"]
    asyncio.run(run())


def test_reconnect_retries_without_invoking_any_job_reset_or_losing_process():
    async def run():
        path = pulse_path()
        recovered = asyncio.Event()
        calls = []
        async def process():
            calls.append(True)
            if len(calls) == 1:
                raise ConnectionError("synthetic offline database")
            recovered.set()
            return "IDLE"
        task = asyncio.create_task(serve_worker(worker(process), "isolated-worker-loop", path,
            interval=.005, pulse_interval=.005))
        await asyncio.wait_for(recovered.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        records = [json.loads(line) for line in path.read_text().splitlines()]
        assert any(item["state"] == "DEPENDENCY_WAIT" and not item["database_verified"] for item in records)
        assert len(calls) >= 2
    asyncio.run(run())


def test_existing_pulse_evidence_is_never_overwritten():
    async def process():
        pytest.fail("An existing pulse log must fail before claiming work")
    path = pulse_path()
    with path.open("x") as stream:
        stream.write("retained evidence\n")
    with pytest.raises(FileExistsError):
        asyncio.run(serve_worker(worker(process), "isolated-worker-loop", path, once=True))
    assert path.read_text() == "retained evidence\n"
