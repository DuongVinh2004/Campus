from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[6]

import asyncpg

from campus247.ports.retrieval import ChunkResult
from campus247.domain.retrieval import RetrievalContext
from campus247.infrastructure.retrieval.postgres_vector import PostgresVectorSearchAdapter


def load_database_url() -> str:
    """Load DATABASE_URL from .env file or environment."""
    env_file = ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("DATABASE_URL="):
                val = line.split("=", 1)[1].strip()
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                return val
    return os.getenv("DATABASE_URL", "postgresql://campus247:campus247_local_dev@localhost:5433/campus247_local")


def normalize_asyncpg_url(url: str) -> str:
    """Convert SQLAlchemy async URL to standard asyncpg connection URL."""
    prefix = "postgresql+asyncpg://"
    if url.startswith(prefix):
        return "postgresql://" + url[len(prefix):]
    return url


@dataclass(frozen=True)
class VectorIndexEntry:
    chunk_id: str
    document_version_id: str
    section_path: str | None
    content_text: str
    embedding: list[float]


@dataclass(frozen=True)
class VectorCandidate:
    chunk_id: str
    document_version_id: str
    section_path: str | None
    content_text: str
    similarity: float


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    if len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class AwaitableList(list):
    """List that can also be awaited in async contexts."""

    def __await__(self):
        async def _coro():
            return self

        return _coro().__await__()


class VectorSearchAdapter:
    """Explicit test vectors only until approved adapter/manifest wiring is verified."""

    def __init__(
        self,
        db_pool: asyncpg.Pool | asyncpg.Connection | None = None,
        database_url: str | None = None,
        dimension: int = 1536,
        *,
        environment: str | None = None,
        verified_backend: PostgresVectorSearchAdapter | None = None,
    ) -> None:
        if verified_backend is not None and (
            not isinstance(verified_backend, PostgresVectorSearchAdapter)
            or db_pool is not None or database_url is not None
        ):
            raise ValueError("one explicit verified vector database binding required")
        self._verified_backend = verified_backend
        self._db_pool = db_pool
        self._database_url = database_url
        self._dimension = dimension
        self._environment = (
            environment if environment is not None else os.getenv("ENVIRONMENT", "development")
        ).strip().lower()
        self._entries: list[VectorIndexEntry] = []

    def _require_test_fixture(self) -> None:
        if self._environment != "test":
            raise RuntimeError("in-memory vector fixtures require the explicit test profile")
        if self._db_pool is not None or self._database_url is not None:
            raise RuntimeError("in-memory vector fixtures cannot access a database")

    def add_entry(self, entry: VectorIndexEntry) -> None:
        self._require_test_fixture()
        self._entries.append(entry)

    def search(
        self,
        query_text: str = "",
        top_k: int = 30,
        *,
        query_vector: list[float] | None = None,
        limit: int | None = None,
        conn: asyncpg.Connection | None = None,
        context: RetrievalContext | None = None,
    ) -> Any:
        # In-memory sync search backward compatibility
        if query_vector is not None or (not query_text and self._entries):
            self._require_test_fixture()
            if conn is not None:
                raise RuntimeError("in-memory vector fixtures cannot access a database")
            effective_limit = limit if limit is not None else top_k
            q_vec = query_vector if query_vector is not None else []
            if not q_vec:
                raise ValueError("Query vector cannot be empty")
            scored: list[VectorCandidate] = []
            for entry in self._entries:
                sim = _cosine_similarity(q_vec, entry.embedding)
                scored.append(
                    VectorCandidate(
                        chunk_id=entry.chunk_id,
                        document_version_id=entry.document_version_id,
                        section_path=entry.section_path,
                        content_text=entry.content_text,
                        similarity=round(sim, 4),
                    )
                )
            scored.sort(key=lambda c: c.similarity, reverse=True)
            return AwaitableList(scored[:effective_limit])

        # Async pgvector search
        effective_k = limit if limit is not None else top_k
        return self._search_async(query_text, effective_k, conn=conn, context=context)

    async def _search_async(
        self,
        query_text: str,
        top_k: int = 30,
        conn: asyncpg.Connection | None = None,
        *, context: RetrievalContext | None = None,
    ) -> list[ChunkResult]:
        if self._verified_backend is not None:
            if conn is not None:
                raise ValueError("verified vector database binding cannot be overridden")
            return await self._verified_backend.search(query_text, top_k, context=context)
        # Missing verified dependencies still fail before configuration/provider/DB.
        raise RuntimeError("vector search requires an approved embedding adapter and verified active manifest")
