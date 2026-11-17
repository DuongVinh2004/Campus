"""Read-only v2 unit store; BM25 plus exact normalized dot-product retrieval."""
from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Sequence
from hashlib import sha256
from pathlib import Path

import numpy as np
from campus247.rag_v2.adapters.npy import load_matrix
from campus247.rag_v2.retrieval.bm25 import BM25
from campus247.rag_v2.types import Scope, Unit

EmbedQuery = Callable[[str], Awaitable[Sequence[float]]]


class MemoryIndex:
    def __init__(self, directory: str | Path, embed_query: EmbedQuery):
        directory = Path(directory)
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        for name in ("units.jsonl", "embeddings.npy"):
            expected = manifest.get("files_sha256", {}).get(name)
            if expected is not None and sha256((directory / name).read_bytes()).hexdigest() != expected:
                raise ValueError("index checksum differs from manifest")
        units = []
        with (directory / "units.jsonl").open(encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                row = json.loads(line)
                row["scope"] = Scope(**{key: tuple(value) for key, value in row.get("scope", {}).items()})
                row["chunk_ids"] = tuple(row["chunk_ids"])
                units.append(Unit(**row))
        vectors = load_matrix(directory / "embeddings.npy")
        if "unit_count" in manifest and manifest["unit_count"] != len(units):
            raise ValueError("manifest unit count differs from stored units")
        if "unit_ids" in manifest and manifest["unit_ids"] != [u.unit_id for u in units]:
            raise ValueError("manifest order differs from stored units")
        self.manifest = manifest
        self._initialize(units, vectors, embed_query)
        if "embedding_dimension" in manifest and manifest["embedding_dimension"] != self._vectors.shape[1]:
            raise ValueError("manifest embedding dimension differs from matrix")
        expected_status = "complete" if self._vectors.shape[1] else "pending"
        if "embedding_status" in manifest and manifest["embedding_status"] != expected_status:
            raise ValueError("manifest embedding status differs from matrix")

    @classmethod
    def from_units(cls, units: Sequence[Unit], embeddings, embed_query: EmbedQuery) -> MemoryIndex:
        """Build the same index from already loaded units (also useful for tests)."""
        instance = cls.__new__(cls)
        instance.manifest = {}
        instance._initialize(units, embeddings, embed_query)
        return instance

    def _initialize(self, units, embeddings, embed_query):
        if not callable(embed_query):
            raise TypeError("an asynchronous query embedding callable is required")
        self._ids = tuple(u.unit_id for u in units)
        self._units = {u.unit_id: u for u in units}
        if len(self._units) != len(self._ids):
            raise ValueError("duplicate unit ids")
        vectors = np.array(embeddings, dtype=np.float32, copy=True)
        if vectors.ndim != 2 or vectors.shape[0] != len(units):
            raise ValueError("embedding shape differs from stored units")
        if not vectors.shape[1]:
            if self.manifest.get("embedding_status") != "pending":
                raise ValueError("zero-dimensional embeddings require an explicit pending manifest")
            self._vectors = vectors
        else:
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            if not np.isfinite(vectors).all() or not np.isfinite(norms).all() or (norms == 0).any():
                raise ValueError("unit embeddings must be finite nonzero vectors")
            self._vectors = vectors / norms
        self._vectors.flags.writeable = False
        self._embed_query = embed_query
        self._bm25 = BM25((u.unit_id, f"{u.doc_title}\n{u.path}\n{u.text}") for u in units)

    def get(self, unit_id: str) -> Unit | None:
        return self._units.get(unit_id)

    def all_ids(self) -> Sequence[str]:
        return self._ids

    def lexical(self, query: str, limit: int, *, allowed: set[str] | None = None) -> list[tuple[str, float]]:
        return self._bm25.search(query, limit, allowed=allowed)

    def anchored(self, query: str, limit: int, *, allowed: set[str] | None = None) -> list[tuple[str, float]]:
        return self._bm25.anchored(query, limit, allowed=allowed)

    async def vector(self, query: str, limit: int, *, allowed: set[str] | None = None) -> list[tuple[str, float]]:
        if limit <= 0 or not self._ids or allowed == set():
            return []
        if not self._vectors.shape[1]:
            raise ValueError("document embeddings are pending")
        vector = np.asarray(await self._embed_query(query), dtype=np.float32)
        if vector.shape != (self._vectors.shape[1],) or not np.isfinite(vector).all():
            raise ValueError("query embedding has invalid shape or values")
        norm = np.linalg.norm(vector)
        if not np.isfinite(norm) or norm == 0:
            raise ValueError("query embedding must be nonzero and finite")
        scores = self._vectors @ (vector / norm)
        rows = ((uid, float(scores[i])) for i, uid in enumerate(self._ids) if allowed is None or uid in allowed)
        return sorted(rows, key=lambda item: (-item[1], item[0]))[:limit]


MemoryUnitIndex = MemoryIndex
