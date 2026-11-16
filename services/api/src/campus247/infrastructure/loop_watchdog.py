"""Detects an event loop that is blocked by synchronous work and records where (function names and lines only).

A blocked loop cannot cancel anything: a request timeout fires late, so a turn can fail at its 30 s budget although the
provider answered at once. The watchdog runs in its own thread, sees the loop's heartbeat go stale and logs the loop
thread's innermost frames, once per second while the block lasts and once more with the total when it ends.
"""
from __future__ import annotations

import asyncio
import logging
import sys
import threading
import time
import traceback

LOG = logging.getLogger("campus247.loop")


class LoopWatchdog:
    def __init__(self, loop: asyncio.AbstractEventLoop, *, threshold_s: float = 1.0, beat_s: float = 0.2,
                 name: str = "api") -> None:
        self._loop, self.threshold_s, self.beat_s, self.name = loop, threshold_s, beat_s, name
        self._last = time.monotonic()
        self._stop = threading.Event()
        self._thread_id: int | None = None
        self._handle: asyncio.TimerHandle | None = None
        self._watcher = threading.Thread(target=self._watch, name="loop-watchdog", daemon=True)
        self.longest_s = 0.0

    def start(self) -> "LoopWatchdog":
        self._thread_id = threading.get_ident()
        self._last = time.monotonic()
        self._beat()
        self._watcher.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._handle is not None:
            self._handle.cancel()

    def _beat(self) -> None:
        self._last = time.monotonic()
        self._handle = self._loop.call_later(self.beat_s, self._beat)

    def _where(self) -> str:
        frame = sys._current_frames().get(self._thread_id)
        if frame is None:
            return "?"
        stack = traceback.extract_stack(frame)[-6:]
        return " < ".join(f"{item.filename.replace(chr(92), '/').rsplit('/', 1)[-1]}.{item.name}:{item.lineno}"
                          for item in reversed(stack))

    def _watch(self) -> None:
        blocked_since = None
        last_report = 0.0
        while not self._stop.wait(0.25):
            stale = time.monotonic() - self._last
            if stale >= self.threshold_s:
                blocked_since = blocked_since or (time.monotonic() - stale)
                if time.monotonic() - last_report >= 1.0:
                    last_report = time.monotonic()
                    LOG.warning("loop_blocked name=%s ms=%d at %s", self.name, stale * 1000, self._where())
            elif blocked_since is not None:
                total = time.monotonic() - blocked_since
                self.longest_s = max(self.longest_s, total)
                LOG.warning("loop_unblocked name=%s total_ms=%d", self.name, total * 1000)
                blocked_since = None
