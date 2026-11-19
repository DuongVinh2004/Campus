"""Observable durable worker loop; pulses append to a new, exact local log."""
from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime

import asyncpg


async def serve_worker(worker, database, heartbeat_file=None, *, once=False, interval=2, pulse_interval=10, auto=None):
    # The caller resolves this exact destination within its workspace. Exclusive
    # creation preserves earlier worker evidence, including after PID reuse.
    stream = heartbeat_file.open("xb") if heartbeat_file else None
    state = {"state": "STARTING", "last_outcome": None, "dependency_error": None}

    def write(**extra):
        if stream:
            record = {"at": datetime.now(UTC).isoformat(), "pid": os.getpid(),
                "database": database, "tenant": worker.repo.tenant, "owner": worker.owner,
                **state, **extra}
            stream.write((json.dumps(record) + "\n").encode())
            stream.flush()

    async def pulse():
        while True:
            try:
                async with worker.repo.pool.acquire() as conn:
                    actual = await conn.fetchval("SELECT current_database()")
                if actual != database:
                    raise ValueError("Worker database identity changed")
                write(database_verified=True)
            except (asyncpg.PostgresConnectionError, asyncpg.InterfaceError, OSError, TimeoutError):
                write(database_verified=False)
            await asyncio.sleep(pulse_interval)

    monitor = asyncio.create_task(pulse()) if stream else None
    delay = interval
    try:
        while True:
            if monitor and monitor.done():
                monitor.result()  # A failed pulse must not leave an unobservable claim loop.
            state["state"] = "PROCESSING"
            try:
                outcome = await worker.run_once()
            except (asyncpg.PostgresConnectionError, asyncpg.InterfaceError, OSError, TimeoutError) as error:
                # No job, attempts, lease, checkpoint or ledger is reset. A job
                # already owned remains fenced until its normal lease expiry.
                state.update(state="DEPENDENCY_WAIT", dependency_error=type(error).__name__)
                write(database_verified=False)
                if once:
                    raise
                await asyncio.sleep(delay)
                delay = min(30, delay * 2)
                continue
            if auto is not None:
                try:
                    await auto.tick()  # documents move on by themselves: checks, release, index (see auto_publication.py)
                except Exception:  # noqa: BLE001 -- the ingestion loop must keep running; the next tick retries
                    pass
            state.update(state="RESOURCE_WAIT" if outcome == "RESOURCE_WAIT" else "IDLE",
                last_outcome=outcome, dependency_error=None)
            delay = interval
            if outcome != "IDLE":
                print(json.dumps({"worker": outcome}), flush=True)
            if once:
                return outcome
            await asyncio.sleep(interval)
    finally:
        if monitor:
            monitor.cancel()
            await asyncio.gather(monitor, return_exceptions=True)
        state["state"] = "STOPPED"
        write(database_verified=False)
        if stream:
            stream.close()
