from __future__ import annotations

import math
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[3]
WORKER_SRC = ROOT / "services" / "worker" / "src"
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from campus247.ports.embedding import (
    EmbeddingBatchLimitError,
    EmbeddingDimensionMismatchError,
    EmbeddingModelMismatchError,
    EmbeddingPort,
    EmbeddingProfile,
    EmptyEmbeddingInputError,
    InvalidEmbeddingVectorError,
    validate_embedding_inputs,
    validate_embedding_vector,
)
with patch.dict("os.environ", {"ENVIRONMENT": "test"}):
    from campus247_worker.ingestion.embed_fake import DeterministicEmbeddingAdapter


def profile() -> EmbeddingProfile:
    return EmbeddingProfile(
        model_id="BAAI/bge-m3",
        model_revision="5617a9f61b028005a4858fdac845db406aefb181",
        dimension=3,
        batch_limit=2,
    )


def test_fake_adapter_satisfies_shared_port_for_query_and_documents(monkeypatch) -> None:
    # Contract evidence only, never a semantic quality or release evaluation.
    monkeypatch.setenv("ENVIRONMENT", "test")
    adapter: EmbeddingPort = DeterministicEmbeddingAdapter(dimension=8, batch_limit=2)

    query = adapter.embed_query("học phí")
    documents = adapter.embed_documents(("quy định học phí", "miễn giảm học phí"))

    assert query.dimension == adapter.profile.dimension == 8
    assert len(documents.vectors) == 2
    assert documents.model_revision == query.model_revision
    assert query.model_id == documents.model_id == "test-only/deterministic-fake"
    assert all(math.isclose(sum(x * x for x in item.values), 1.0, abs_tol=1e-3) for item in documents.vectors)


def test_empty_and_oversized_batches_fail_closed() -> None:
    with pytest.raises(EmptyEmbeddingInputError):
        validate_embedding_inputs((), profile())
    with pytest.raises(EmptyEmbeddingInputError):
        validate_embedding_inputs(("ok", "  "), profile())
    with pytest.raises(EmbeddingBatchLimitError):
        validate_embedding_inputs(("a", "b", "c"), profile())


def test_dimension_and_model_mismatch_are_rejected() -> None:
    with pytest.raises(EmbeddingDimensionMismatchError):
        validate_embedding_vector((1.0, 0.0), profile())
    with pytest.raises(EmbeddingModelMismatchError):
        validate_embedding_vector((1.0, 0.0, 0.0), profile(), model_id="other/model")
    with pytest.raises(EmbeddingModelMismatchError):
        validate_embedding_vector(
            (1.0, 0.0, 0.0),
            profile(),
            model_revision="mutable-main",
        )


@pytest.mark.parametrize("bad_value", [math.nan, math.inf, -math.inf])
def test_non_finite_vectors_are_rejected(bad_value: float) -> None:
    with pytest.raises(InvalidEmbeddingVectorError):
        validate_embedding_vector((bad_value, 0.0, 1.0), profile())


def test_zero_or_unnormalized_vectors_are_rejected() -> None:
    with pytest.raises(InvalidEmbeddingVectorError):
        validate_embedding_vector((0.0, 0.0, 0.0), profile())
    with pytest.raises(InvalidEmbeddingVectorError):
        validate_embedding_vector((1.0, 1.0, 0.0), profile())
