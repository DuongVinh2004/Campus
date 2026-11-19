from __future__ import annotations

import hashlib
import math
import os
import random
from typing import Sequence

from campus247.ports.embedding import (
    EmbeddingBatch,
    EmbeddingProfile,
    EmbeddingVector,
    EmptyEmbeddingInputError,
    validate_embedding_inputs,
    validate_embedding_vector,
)


def _require_test_profile() -> None:
    if os.getenv("ENVIRONMENT", "development").strip().lower() != "test":
        raise RuntimeError("fake embedding requires the explicit test profile")


_require_test_profile()


class DeterministicEmbeddingAdapter:
    """Test fixture only; its output is never semantic quality/release evidence."""

    def __init__(self, dimension: int = 1536, batch_limit: int = 64) -> None:
        _require_test_profile()
        self.dimension = dimension
        self._profile = EmbeddingProfile(
            model_id="test-only/deterministic-fake",
            model_revision="sha256-seeded-v1",
            dimension=dimension,
            batch_limit=batch_limit,
        )

    @property
    def profile(self) -> EmbeddingProfile:
        return self._profile

    def embed_text(self, text: str) -> list[float]:
        _require_test_profile()
        if not text or not text.strip():
            raise EmptyEmbeddingInputError("Cannot embed empty text")
        cleaned = validate_embedding_inputs((text,), self._profile)[0]

        # Derive 64-bit integer seed from sha256 of text
        digest = hashlib.sha256(cleaned.encode("utf-8")).digest()
        seed = int.from_bytes(digest[:8], byteorder="big")

        rng = random.Random(seed)
        # Generate pseudo-random vector with standard normal distribution
        raw_vec = [rng.gauss(0.0, 1.0) for _ in range(self.dimension)]

        # L2-normalize
        norm = math.sqrt(sum(x * x for x in raw_vec))
        if norm == 0.0:
            return [0.0] * self.dimension

        return [round(x / norm, 6) for x in raw_vec]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        _require_test_profile()
        cleaned = validate_embedding_inputs(texts, self._profile)
        return [self.embed_text(text) for text in cleaned]

    def embed_query(self, text: str) -> EmbeddingVector:
        return validate_embedding_vector(self.embed_text(text), self._profile)

    def embed_documents(self, texts: Sequence[str]) -> EmbeddingBatch:
        _require_test_profile()
        cleaned = validate_embedding_inputs(texts, self._profile)
        vectors = tuple(
            validate_embedding_vector(self.embed_text(text), self._profile)
            for text in cleaned
        )
        return EmbeddingBatch(
            vectors=vectors,
            model_id=self._profile.model_id,
            model_revision=self._profile.model_revision,
            dimension=self._profile.dimension,
            normalization=self._profile.normalization,
        )
