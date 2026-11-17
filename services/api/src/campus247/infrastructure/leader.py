"""One process out of several runs the background jobs: leader election with a Postgres advisory lock.

Every API process starts this coroutine. Exactly one of them holds the session-level advisory lock and runs the jobs
(scheduler, learning worker, OCR); the others stay on standby and keep trying. The lock belongs to the database
session, so it is released by the database itself when the leader's process dies or its connection drops, and a
standby takes over within `poll_s`. The leader checks its own session every `check_s` and stops its jobs at once
when the session is lost, so two processes never run the jobs for longer than one check interval after a loss.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

LOG = logging.getLogger("campus247.leader")
BACKGROUND_JOBS_LOCK_ID = 727_002


class BackgroundLeader:
    def __init__(self, pool_provider: Callable[[], Any], *, lock_id: int = BACKGROUND_JOBS_LOCK_ID,
                 poll_s: float = 5.0, check_s: float = 2.0, name: str = "background-jobs") -> None:
        self._pool_provider, self.lock_id, self.poll_s, self.check_s, self.name = pool_provider, lock_id, poll_s, check_s, name
        self.is_leader = False
        self.takeovers = 0  # how many times this process became leader

    async def run(self, start_jobs: Callable[[], Awaitable[list[asyncio.Task]]],
                  on_standby: Callable[[], None] | None = None) -> None:
        """Run until cancelled. `start_jobs` creates the job tasks once this process is leader."""
        while True:
            try:
                await self._lead_once(start_jobs, on_standby)
            except asyncio.CancelledError:
                raise
            except Exception as error:  # noqa: BLE001 -- the database may be briefly down; try again, never crash the API
                LOG.warning("leader_election_error name=%s kind=%s", self.name, type(error).__name__)
            await asyncio.sleep(self.poll_s)

    async def _lead_once(self, start_jobs, on_standby) -> None:
        pool = self._pool_provider()
        if pool is None:
            raise RuntimeError("pool unavailable")
        connection = await pool.acquire(timeout=self.poll_s * 2)
        tasks: list[asyncio.Task] = []
        try:
            if not await connection.fetchval("SELECT pg_try_advisory_lock($1)", self.lock_id, timeout=self.poll_s * 2):
                if on_standby is not None:
                    on_standby()
                return
            self.is_leader = True
            self.takeovers += 1
            LOG.warning("leader_acquired name=%s", self.name)
            # The previous holder can only have lost the lock by losing its session, and it notices that at its next
            # check (at most `check_s` later) and stops its jobs. Waiting a little longer than that before starting ours
            # means the two never run together; a short delay in starting the jobs is the price.
            await asyncio.sleep(self.check_s * 1.5)
            tasks = await start_jobs()
            while True:
                await asyncio.sleep(self.check_s)
                # Raises when the session is gone: the database has then already released the lock.
                await connection.fetchval("SELECT 1", timeout=self.check_s * 2)
                dead = [task for task in tasks if task.done() and not task.cancelled() and task.exception() is not None]
                if dead:
                    raise RuntimeError("a background job stopped unexpectedly")
        finally:
            self.is_leader = False
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            try:
                await connection.execute("SELECT pg_advisory_unlock($1)", self.lock_id, timeout=2)
            except Exception:  # noqa: BLE001 -- a dead session has no lock left to release
                pass
            try:
                await pool.release(connection)
            except Exception:  # noqa: BLE001
                pass
            if tasks:
                LOG.warning("leader_released name=%s", self.name)
