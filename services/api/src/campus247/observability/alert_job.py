"""The loop that evaluates the alert rules once a minute. Started only in the API process that holds the background-jobs lock, so
there is one evaluator however many workers run."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from campus247.observability.alerts import AlertManager

LOG = logging.getLogger("campus247.alerts")


async def run_alerts(manager: AlertManager, build_status: Callable[[], Awaitable[dict[str, Any]]], *, every_s: float = 60.0,
                     clock: Callable[[], datetime] = lambda: datetime.now(UTC), passes: int | None = None) -> None:
    """Evaluate every `every_s` seconds until cancelled (or `passes` times, for tests). A pass that fails is logged and retried."""
    done = 0
    while passes is None or done < passes:
        try:
            manager.evaluate(await build_status(), now=clock())
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001 -- the monitor must outlive a bad pass
            LOG.warning("alert_pass_failed kind=%s", type(error).__name__)
        done += 1
        if passes is None or done < passes:
            await asyncio.sleep(every_s)
