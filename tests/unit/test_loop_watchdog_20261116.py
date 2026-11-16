"""The watchdog names the function that blocks the event loop and stays quiet otherwise."""
import asyncio
import logging
import time

import pytest
from campus247.infrastructure.loop_watchdog import LoopWatchdog


def blocking_work():
    time.sleep(1.6)


@pytest.mark.asyncio
async def test_blocked_loop_is_reported_with_the_blocking_function(caplog):
    caplog.set_level(logging.WARNING, logger="campus247.loop")
    watchdog = LoopWatchdog(asyncio.get_running_loop(), threshold_s=0.5).start()
    try:
        await asyncio.sleep(0.3)
        blocking_work()
        await asyncio.sleep(0.6)
    finally:
        watchdog.stop()
    assert "loop_blocked" in caplog.text and "blocking_work" in caplog.text
    assert "loop_unblocked" in caplog.text and watchdog.longest_s >= 1.0


@pytest.mark.asyncio
async def test_free_loop_logs_nothing(caplog):
    caplog.set_level(logging.WARNING, logger="campus247.loop")
    watchdog = LoopWatchdog(asyncio.get_running_loop(), threshold_s=0.5).start()
    try:
        for _ in range(5):
            await asyncio.sleep(0.2)
    finally:
        watchdog.stop()
    assert "loop_blocked" not in caplog.text
