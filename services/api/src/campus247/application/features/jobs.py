"""Run a background job only while its feature is on (F0.5): stop it when the flag turns off, start it again when it turns on."""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

LOG = logging.getLogger("campus247.features")


async def run_gated(enabled: Callable[[], bool], make_job: Callable[[], Awaitable[None]], *, name: str = "job", poll_s: float = 2.0) -> None:
    task: asyncio.Task | None = None
    try:
        while True:
            try:
                on = bool(enabled())
            except Exception:  # noqa: BLE001 -- a failing flag lookup keeps the previous state
                on = task is not None
            if on and task is None:
                task = asyncio.create_task(make_job())
            elif not on and task is not None:
                await _stop(task)
                task = None
                LOG.info("feature_job_stopped job=%s", name)
            elif task is not None and task.done():
                error = None if task.cancelled() else task.exception()
                if error is not None:
                    LOG.warning("feature_job_failed job=%s kind=%s", name, type(error).__name__)
                task = None  # a job that ended on its own is started again on the next pass
            await asyncio.sleep(poll_s)
    finally:
        if task is not None:
            await _stop(task)


async def _stop(task: asyncio.Task) -> None:
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception:  # noqa: BLE001
        pass
