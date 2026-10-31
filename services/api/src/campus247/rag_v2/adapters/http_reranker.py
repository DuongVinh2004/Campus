"""Deadline-bound TEI reranker on the explicitly authorized loopback endpoint."""
from __future__ import annotations

import asyncio
import json
import math
from collections.abc import Callable, Sequence
from time import monotonic

import httpx

_URL = "http://127.0.0.1:18082"


class HTTPReranker:
    def __init__(self, *, batch_size: int = 12, concurrency: int = 1,
                 client_factory: Callable[[], httpx.AsyncClient] | None = None):
        if any(type(n) is not int or n < 1 for n in (batch_size, concurrency)):
            raise ValueError("positive integer batch and concurrency limits required")
        self.batch_size, self.concurrency = batch_size, concurrency
        self._client_factory = client_factory or (lambda: httpx.AsyncClient(
            base_url=_URL, trust_env=False, follow_redirects=False))

    async def rerank(self, query: str, texts: Sequence[str], *, deadline_s: float) -> list[float]:
        if not texts:
            return []
        if not math.isfinite(deadline_s) or deadline_s <= 0:
            raise TimeoutError("reranker deadline exceeded")
        end = monotonic() + deadline_s

        async def request(client, method, path, payload=None):
            remaining = end - monotonic()
            if remaining <= 0:
                raise TimeoutError("reranker deadline exceeded")
            async with client.stream(method, _URL + path, json=payload, timeout=remaining,
                                     follow_redirects=False) as response:
                if response.status_code != 200:
                    raise ValueError("reranker runtime returned a non-success status")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(body) + len(chunk) > 1024 * 1024:
                        raise ValueError("reranker response exceeds limit")
                    body.extend(chunk)
                return json.loads(body)

        try:
            async with asyncio.timeout(deadline_s):
                async with self._client_factory() as client:
                    info = await request(client, "GET", "/info")
                    if not isinstance(info, dict):
                        raise TypeError("invalid reranker capabilities")
                    model_type = info.get("model_type")
                    if model_type is not None and (not isinstance(model_type, dict) or "reranker" not in model_type):
                        raise ValueError("runtime is not a reranker")
                    def bound(key, default):
                        value = info.get(key, default)
                        return value if type(value) is int and value > 0 else default
                    batch_size = min(self.batch_size, bound("max_client_batch_size", self.batch_size))
                    # Parallel batches require an explicit server capability.
                    parallel = min(self.concurrency, bound("max_concurrent_requests", 1))
                    semaphore = asyncio.Semaphore(parallel)

                    async def batch(start):
                        passages = list(texts[start:start + batch_size])
                        async with semaphore:
                            rows = await request(client, "POST", "/rerank", {
                                "query": query, "texts": passages, "raw_scores": True,
                                "return_text": False, "truncate": False,
                            })
                        if not isinstance(rows, list) or len(rows) != len(passages):
                            raise ValueError("reranker must return every input")
                        scores, seen = [0.0] * len(passages), set()
                        for row in rows:
                            if not isinstance(row, dict) or set(row) != {"index", "score"}:
                                raise ValueError("invalid ranking row")
                            i, score = row["index"], row["score"]
                            if type(i) is not int or not 0 <= i < len(passages) or i in seen:
                                raise ValueError("duplicate or foreign ranking index")
                            if type(score) not in (int, float) or not math.isfinite(score):
                                raise ValueError("invalid ranking score")
                            scores[i] = float(score)
                            seen.add(i)
                        return scores

                    tasks = [asyncio.create_task(batch(i)) for i in range(0, len(texts), batch_size)]
                    try:
                        batches = await asyncio.gather(*tasks)
                    finally:
                        for task in tasks:
                            if not task.done():
                                task.cancel()
                        await asyncio.gather(*tasks, return_exceptions=True)
                    return [score for scores in batches for score in scores]
        except httpx.TimeoutException:
            raise TimeoutError("reranker deadline exceeded") from None


HttpReranker = HTTPReranker
