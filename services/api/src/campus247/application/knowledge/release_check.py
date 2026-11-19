"""Run the retrieval check once after a new knowledge release goes live, without getting in the way of people using the chat.

The watcher only looks at the id of the live release. When it changes it waits (so several quick activations make one check),
then starts the check unless the system is busy; a busy system is asked again later, a few times, and then the check is dropped (the
nightly run still happens). Starting a check is injected, so this module knows nothing about processes or models.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

LOG = logging.getLogger("campus247.release_check")


class ReleaseWatch:
    def __init__(self, release_id: Callable[[], str | None], start_check: Callable[[], Awaitable[None]], busy: Callable[[], bool], *,
                 debounce_s: float = 600.0, retry_s: float = 900.0, max_tries: int = 3) -> None:
        self._release_id, self._start_check, self._busy = release_id, start_check, busy
        self.debounce_s, self.retry_s, self.max_tries = debounce_s, retry_s, max_tries
        self._seen: str | None = None
        self._first = True
        self._changed_at: float | None = None
        self._due_at: float | None = None
        self._tries = 0

    async def tick(self, now: float) -> str:
        """One look. Returns what happened: idle, waiting, started, busy, dropped."""
        current = self._release_id()
        if self._first:  # the release found at start-up is not a change
            self._first, self._seen = False, current
            return "idle"
        if current != self._seen:
            self._seen = current
            if current:  # a release was withdrawn when it became None: nothing to check
                self._changed_at, self._due_at, self._tries = now, now + self.debounce_s, 0
            else:
                self._changed_at = self._due_at = None
        if self._due_at is None:
            return "idle"
        if now < self._due_at:
            return "waiting"
        if self._busy():
            self._tries += 1
            if self._tries >= self.max_tries:
                LOG.info("release_check_dropped reason=busy tries=%d", self._tries)
                self._due_at = None
                return "dropped"
            self._due_at = now + self.retry_s
            return "busy"
        self._due_at = None
        await self._start_check()
        return "started"


async def run_release_watch(watch: ReleaseWatch, *, every_s: float = 60.0, clock: Callable[[], float] = time.monotonic, passes: int | None = None) -> None:
    done = 0
    while passes is None or done < passes:
        try:
            outcome = await watch.tick(clock())
            if outcome in {"started", "dropped"}:
                LOG.info("release_check outcome=%s", outcome)
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001 -- keep watching; the nightly run is the safety net
            LOG.warning("release_check_failed kind=%s", type(error).__name__)
        done += 1
        if passes is None or done < passes:
            await asyncio.sleep(every_s)
