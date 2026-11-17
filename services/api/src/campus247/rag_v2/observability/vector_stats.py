"""How often the vector branch of retrieval is lost, per process.

Hybrid retrieval gives the vector branch 1.0 s and, when it fails, silently continues with lexical results only.
Under load the embedding server queues and that branch can fail often without any error surfacing, so answer
quality drops with no signal. This counts every retrieval and every lost vector branch and logs both, so the
rate can be read from the log and watched on a dashboard. Counts only: no text, identifiers or exception strings.
"""
from __future__ import annotations

import logging
import threading

LOG = logging.getLogger("campus247.rag_v2")
ROLLUP_EVERY = 25  # retrievals between two summary lines


class VectorStats:
    def __init__(self, rollup_every: int = ROLLUP_EVERY) -> None:
        self._lock = threading.Lock()
        self._every = max(1, rollup_every)
        self.retrievals = 0
        self.failed = 0
        self.timeouts = 0
        self.slow_ms_max = 0.0

    def record(self, *, failed: bool, timeout: bool = False, seconds: float = 0.0) -> None:
        with self._lock:
            self.retrievals += 1
            self.failed += bool(failed)
            self.timeouts += bool(failed and timeout)
            self.slow_ms_max = max(self.slow_ms_max, seconds * 1000)
            rollup = self.retrievals % self._every == 0
            snapshot = self._snapshot()
        if failed:
            LOG.warning("rag_v2_vector_failed reason=%s ms=%d", "timeout" if timeout else "error", round(seconds * 1000))
        if rollup:
            LOG.warning("rag_v2_vector_stats retrievals=%(retrievals)d failed=%(failed)d timeouts=%(timeouts)d "
                        "failed_rate=%(failed_rate).3f vector_ms_max=%(vector_ms_max)d", snapshot)

    def _snapshot(self) -> dict:
        return {"retrievals": self.retrievals, "failed": self.failed, "timeouts": self.timeouts,
                "failed_rate": self.failed / self.retrievals if self.retrievals else 0.0,
                "vector_ms_max": round(self.slow_ms_max)}

    def snapshot(self) -> dict:
        with self._lock:
            return self._snapshot()


VECTOR_STATS = VectorStats()
