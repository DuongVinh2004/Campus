"""Answers to repeated single-turn questions over the same authorized sources (lever L2).

The key binds everything the answer depends on: the fingerprint of the authorized rows (release, scope, validity and
content hashes), the resolved question, and the prompts' version. Only complete, cited answers are stored. A hit skips
retrieval, generation and the support check; the caller still runs the router/safety checks before it, and re-validates
the cited chunks and the output guard after it, exactly as for a fresh answer.
"""
from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict
from hashlib import sha256

from campus247.rag_v2.generation.prompt import GENERATION_PROMPT
from campus247.rag_v2.types import Outcome
from campus247.rag_v2.verification.semantic import SEMANTIC_PROMPT
from campus247.rag_v2.verification.verbatim import mode as verbatim_mode
from campus247.rag_v2.understanding.normalize import fold

PROMPT_VERSION = sha256((GENERATION_PROMPT + "\0" + SEMANTIC_PROMPT).encode()).hexdigest()[:16]


def enabled() -> bool:
    from campus247.features.runtime import value  # F0: the env variable is the flag's legacy source; an admin override wins
    return bool(value("chat.answer_cache", os.environ.get("CAMPUS247_RAG_ANSWER_CACHE", "off").strip().lower() in {"1", "on", "true", "yes"}))


class AnswerCache:
    def __init__(self, maxsize: int = 512, ttl_s: float = 6 * 3600, clock=time.monotonic):
        self.maxsize, self.ttl_s, self._clock = maxsize, ttl_s, clock
        self._items: OrderedDict[str, tuple[float, Outcome]] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = self.misses = 0

    @staticmethod
    def key(rows_fingerprint: str, question: str) -> str:
        text = " ".join(fold(question).split())
        return sha256("\0".join((rows_fingerprint, text, PROMPT_VERSION, verbatim_mode())).encode()).hexdigest()

    def get(self, key: str) -> Outcome | None:
        with self._lock:
            hit = self._items.get(key)
            if hit is not None and self._clock() - hit[0] <= self.ttl_s:
                self._items.move_to_end(key)
                self.hits += 1
                return hit[1]
            if hit is not None:
                del self._items[key]
            self.misses += 1
            return None

    def put(self, key: str, outcome: Outcome) -> None:
        if outcome.kind != "answer" or not outcome.citations or not outcome.statements:
            return
        with self._lock:
            self._items[key] = (self._clock(), outcome)
            self._items.move_to_end(key)
            while len(self._items) > self.maxsize:
                self._items.popitem(last=False)
