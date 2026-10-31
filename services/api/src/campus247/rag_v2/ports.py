"""Ports the v2 core depends on. Implemented by infrastructure adapters and by fakes in tests."""
from __future__ import annotations

from typing import Protocol, Sequence

from campus247.rag_v2.types import Unit


class UnitIndex(Protocol):
    def get(self, unit_id: str) -> Unit | None: ...
    def lexical(self, query: str, limit: int, *, allowed: set[str] | None = None) -> list[tuple[str, float]]: ...
    async def vector(self, query: str, limit: int, *, allowed: set[str] | None = None) -> list[tuple[str, float]]: ...
    def all_ids(self) -> Sequence[str]: ...


class Reranker(Protocol):
    async def rerank(self, query: str, texts: Sequence[str], *, deadline_s: float) -> list[float]:
        """Return one logit per text, same order. Raise TimeoutError on deadline; caller falls back."""
