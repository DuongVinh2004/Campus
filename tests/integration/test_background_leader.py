"""Background jobs run in exactly one API process; another takes over when the leader's database session is lost.

Uses the retained local Postgres with a random advisory lock id per test (nothing is created or stored). Each
BackgroundLeader gets its own pool, which stands in for one API process. Skipped when that database is not running.
"""
from __future__ import annotations

import asyncio
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from campus247.infrastructure.leader import BackgroundLeader  # noqa: E402


async def open_pool():
    import asyncpg
    try:
        import knowledge_platform as platform
        return await asyncpg.create_pool(**platform.connection(), min_size=1, max_size=3, command_timeout=10)
    except Exception as error:  # noqa: BLE001
        pytest.skip(f"retained local Postgres not available: {type(error).__name__}")


class Cluster:
    """N fake API processes: each has a pool, a leader and the jobs it would run."""

    def __init__(self, count, lock_id, crash_first=0):
        self.lock_id, self.count = lock_id, count
        self.running = [0] * count      # jobs currently running per process
        self.started = [0] * count      # times each process started its jobs
        self.max_running_total = 0
        self.crash_first = crash_first
        self.pools, self.leaders, self.runs = [], [], []

    async def start(self):
        for i in range(self.count):
            pool = await open_pool()
            self.pools.append(pool)
            leader = BackgroundLeader(lambda p=pool: p, lock_id=self.lock_id, poll_s=0.15, check_s=0.1)
            self.leaders.append(leader)
            self.runs.append(asyncio.create_task(leader.run(lambda i=i: self.jobs(i))))
        return self

    async def jobs(self, index):
        self.started[index] += 1
        crash = self.crash_first > 0
        self.crash_first -= 1

        async def job():
            self.running[index] += 1
            self.max_running_total = max(self.max_running_total, sum(self.running))
            try:
                await asyncio.sleep(0.05 if crash else 3600)
                if crash:
                    raise RuntimeError("job failed")
            finally:
                self.running[index] -= 1
        return [asyncio.create_task(job()), asyncio.create_task(job())]

    def leaders_now(self):
        return [i for i, leader in enumerate(self.leaders) if leader.is_leader]

    async def wait_for_leader(self, exclude=(), timeout=5):
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            now = [i for i in self.leaders_now() if i not in exclude]
            if now and self.running[now[0]] == 2:
                return now[0]
            await asyncio.sleep(0.02)
        raise AssertionError(f"no leader within {timeout}s: {self.leaders_now()}")

    async def close(self):
        for run in self.runs:
            run.cancel()
        await asyncio.gather(*self.runs, return_exceptions=True)
        for pool in self.pools:
            try:
                await asyncio.wait_for(pool.close(), 5)
            except Exception:  # noqa: BLE001
                pool.terminate()


@pytest.fixture
def lock_id():
    return random.randint(10_000_000, 2_000_000_000)


@pytest.mark.asyncio
async def test_exactly_one_of_three_processes_runs_the_jobs(lock_id):
    cluster = await Cluster(3, lock_id).start()
    try:
        leader = await cluster.wait_for_leader()
        await asyncio.sleep(0.6)  # the others keep polling; none may take over while the leader is healthy
        assert cluster.leaders_now() == [leader]
        assert sum(cluster.started) == 1 and cluster.running[leader] == 2
        assert cluster.max_running_total == 2  # two jobs of one process, never a second process's
    finally:
        await cluster.close()


@pytest.mark.asyncio
async def test_a_standby_takes_over_when_the_leader_process_dies(lock_id):
    cluster = await Cluster(3, lock_id).start()
    try:
        first = await cluster.wait_for_leader()
        cluster.runs[first].cancel()          # the process goes away ...
        await asyncio.gather(cluster.runs[first], return_exceptions=True)
        cluster.pools[first].terminate()      # ... and its connections with it
        second = await cluster.wait_for_leader(exclude={first})
        assert second != first and cluster.running[first] == 0
        assert cluster.max_running_total == 2  # never two processes at once
    finally:
        await cluster.close()


@pytest.mark.asyncio
async def test_lost_database_session_stops_the_leader_and_another_takes_over(lock_id):
    cluster = await Cluster(3, lock_id).start()
    try:
        first = await cluster.wait_for_leader()
        async with cluster.pools[(first + 1) % 3].acquire() as admin:
            pid = await admin.fetchval("SELECT pid FROM pg_locks WHERE locktype='advisory' AND objid=$1 AND granted", lock_id)
            assert pid is not None
            await admin.execute("SELECT pg_terminate_backend($1)", pid)
        # Whoever leads next, there are never two leaders' jobs running together.
        for _ in range(60):
            await asyncio.sleep(0.05)
            assert sum(cluster.running) <= 2
        leader = await cluster.wait_for_leader()
        assert cluster.leaders_now() == [leader]
        assert cluster.max_running_total == 2
    finally:
        await cluster.close()


@pytest.mark.asyncio
async def test_a_crashed_job_makes_the_leader_restart_its_jobs(lock_id):
    cluster = await Cluster(1, lock_id, crash_first=1).start()
    try:
        deadline = asyncio.get_running_loop().time() + 5
        while cluster.started[0] < 2 and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.05)
        assert cluster.started[0] >= 2
        assert await cluster.wait_for_leader() == 0
    finally:
        await cluster.close()


@pytest.mark.asyncio
async def test_clean_shutdown_releases_the_lock_at_once(lock_id):
    cluster = await Cluster(1, lock_id).start()
    pool = await open_pool()
    try:
        await cluster.wait_for_leader()
        cluster.runs[0].cancel()
        await asyncio.gather(cluster.runs[0], return_exceptions=True)
        async with pool.acquire() as conn:
            assert await conn.fetchval("SELECT pg_try_advisory_lock($1)", lock_id) is True
            await conn.execute("SELECT pg_advisory_unlock($1)", lock_id)
        assert cluster.running[0] == 0
    finally:
        await pool.close()
        await cluster.close()
