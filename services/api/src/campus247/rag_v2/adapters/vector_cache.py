"""Query-vector cache with in-flight sharing, for the embedding calls of retrieval.

Embedding a question is a pure function of its text and the (fixed) model, so the same text always gives the same
vector: a cached or shared result is identical to a fresh call. This only removes repeated work:

- the same question asked again (or by two students at once) is embedded once;
- an embedding started early (see `prefetch` in the RAG node) is the one retrieval later waits for.

Failures are never cached and a caller that gives up (retrieval waits at most 1 s for the vector branch) does not
cancel the shared call, so the result is still there for the next caller. No text leaves memory and nothing is logged.
"""
from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from typing import Any


class QueryVectorCache:
    def __init__(self, embed: Callable[[str], Awaitable[Any]], *, max_entries: int = 2048, ttl_s: float = 3600.0) -> None:
        if max_entries < 1 or ttl_s <= 0:
            raise ValueError("cache bounds must be positive")
        self._embed, self._max, self._ttl = embed, max_entries, ttl_s
        self._entries: OrderedDict[str, tuple[float, asyncio.Future]] = OrderedDict()
        self.hits = self.misses = 0

    async def __call__(self, query: str):
        now = time.monotonic()
        entry = self._entries.get(query)
        if entry is not None and (now - entry[0] > self._ttl or (entry[1].done() and (
                entry[1].cancelled() or entry[1].exception() is not None))):
            self._entries.pop(query, None)
            entry = None
        if entry is None:
            self.misses += 1
            future = asyncio.ensure_future(self._embed(query))
            future.add_done_callback(lambda done: done.cancelled() or done.exception())  # never "exception never retrieved"
            entry = self._entries[query] = (now, future)
            while len(self._entries) > self._max:
                self._entries.popitem(last=False)
        else:
            self.hits += 1
            self._entries.move_to_end(query)
        try:
            return await asyncio.shield(entry[1])
        except BaseException:
            if entry[1].done() and (entry[1].cancelled() or entry[1].exception() is not None):
                if self._entries.get(query) is entry:
                    self._entries.pop(query, None)  # a failed call is not kept
            raise

    def prefetch(self, query: str) -> None:
        """Start embedding `query` now without waiting; errors stay inside the shared future."""
        if query in self._entries:
            return
        task = asyncio.ensure_future(self(query))
        task.add_done_callback(lambda done: done.cancelled() or done.exception())
