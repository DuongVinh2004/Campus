"""Background loop that sends the reminders. Runs in the one API process that holds the background-jobs lock."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime

from campus247.application.campus_ops.reminders import deliver, exam_candidates

LOG = logging.getLogger("campus247.reminders")


def run_once(store, resolver_factory: Callable[[], Callable[[str], str | None]], *, now: datetime) -> int:
    """One pass: find upcoming exams, notify what is due. SQLite work, so call it off the event loop."""
    return deliver(store, exam_candidates(store, resolver_factory(), now=now), now=now)


async def run_reminders(store, resolver_factory: Callable[[], Callable[[str], str | None]], *, every_s: float = 300.0,
                        clock: Callable[[], datetime] = lambda: datetime.now(UTC), passes: int | None = None) -> None:
    """Repeat `run_once` every `every_s` seconds until cancelled (or `passes` times, for tests). A failed pass is logged and retried."""
    done = 0
    while passes is None or done < passes:
        try:
            sent = await asyncio.to_thread(run_once, store, resolver_factory, now=clock())
            if sent:
                LOG.info("reminders_sent count=%d", sent)
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001 -- keep the loop alive; the next pass tries again
            LOG.warning("reminders_failed kind=%s", type(error).__name__)
        done += 1
        if passes is None or done < passes:
            await asyncio.sleep(every_s)
