"""The retrieval check after a release change: once per burst of changes, never during busy times, never on start-up."""
import asyncio
import logging

import pytest

from campus247.application.knowledge.release_check import ReleaseWatch, run_release_watch


class Env:
    def __init__(self):
        self.release, self.is_busy, self.started = "r1", False, 0

    async def start(self):
        self.started += 1


@pytest.fixture
def env():
    return Env()


def watch(env, **kw):
    return ReleaseWatch(lambda: env.release, env.start, lambda: env.is_busy, debounce_s=600, retry_s=900, max_tries=3, **kw)


@pytest.mark.asyncio
async def test_the_release_found_at_start_up_is_not_a_change(env):
    w = watch(env)
    assert [await w.tick(t) for t in (0, 60, 5000)] == ["idle", "idle", "idle"] and env.started == 0


@pytest.mark.asyncio
async def test_a_change_waits_out_the_debounce_then_starts_one_check(env):
    w = watch(env)
    await w.tick(0)
    env.release = "r2"
    assert await w.tick(100) == "waiting"
    assert await w.tick(699) == "waiting" and env.started == 0
    assert await w.tick(700) == "started" and env.started == 1
    assert await w.tick(800) == "idle" and env.started == 1


@pytest.mark.asyncio
async def test_several_quick_changes_make_one_check_after_the_last_one(env):
    w = watch(env)
    await w.tick(0)
    env.release = "r2"
    await w.tick(100)
    env.release = "r3"
    assert await w.tick(500) == "waiting"  # restarts the wait
    assert await w.tick(1000) == "waiting" and env.started == 0
    assert await w.tick(1100) == "started" and env.started == 1


@pytest.mark.asyncio
async def test_a_busy_system_is_asked_again_later_and_the_check_is_dropped_after_three_tries(env):
    w = watch(env)
    await w.tick(0)
    env.release, env.is_busy = "r2", True
    await w.tick(10)
    assert await w.tick(700) == "busy"
    assert await w.tick(1000) == "waiting"  # the retry is 15 minutes later
    assert await w.tick(1600) == "busy"
    assert await w.tick(2500) == "dropped" and env.started == 0
    env.is_busy = False
    assert await w.tick(9000) == "idle" and env.started == 0


@pytest.mark.asyncio
async def test_it_starts_when_the_system_calms_down_before_the_tries_run_out(env):
    w = watch(env)
    await w.tick(0)
    env.release, env.is_busy = "r2", True
    await w.tick(10)
    assert await w.tick(700) == "busy"
    env.is_busy = False
    assert await w.tick(1600) == "started" and env.started == 1


@pytest.mark.asyncio
async def test_a_withdrawn_release_cancels_a_pending_check(env):
    w = watch(env)
    await w.tick(0)
    env.release = "r2"
    await w.tick(10)
    env.release = None
    assert await w.tick(20) == "idle"
    env.release = "r3"
    await w.tick(30)
    assert await w.tick(629) == "waiting" and env.started == 0  # the withdrawn release left nothing pending; only r3's own wait counts
    assert await w.tick(630) == "started" and env.started == 1


@pytest.mark.asyncio
async def test_the_loop_survives_a_failing_check_and_can_be_cancelled(env, caplog):
    async def failing():
        raise RuntimeError("cannot start")

    w = ReleaseWatch(lambda: env.release, failing, lambda: False, debounce_s=0, retry_s=1, max_tries=3)
    clock = iter(range(0, 1000, 10)).__next__
    with caplog.at_level(logging.WARNING, logger="campus247.release_check"):
        env.release = "r1"
        await run_release_watch(w, every_s=0, clock=clock, passes=1)
        env.release = "r2"
        await run_release_watch(w, every_s=0, clock=clock, passes=3)
    assert "release_check_failed kind=RuntimeError" in caplog.text and "cannot start" not in caplog.text
    task = asyncio.create_task(run_release_watch(w, every_s=3600))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
