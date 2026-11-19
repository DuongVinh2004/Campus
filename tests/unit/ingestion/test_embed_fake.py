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

with patch.dict("os.environ", {"ENVIRONMENT": "test"}):
    from campus247_worker.ingestion.embed_fake import DeterministicEmbeddingAdapter


@pytest.fixture(autouse=True)
def explicit_test_profile(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")


def test_embed_text_deterministic_and_normalized() -> None:
    adapter = DeterministicEmbeddingAdapter(dimension=384)
    text = "Trường Đại học Xây dựng Hà Nội"

    vec1 = adapter.embed_text(text)
    vec2 = adapter.embed_text(text)

    assert len(vec1) == 384
    assert vec1 == vec2

    # L2 norm must be approximately 1.0
    norm = math.sqrt(sum(x * x for x in vec1))
    assert pytest.approx(norm, 1e-4) == 1.0


def test_embed_different_texts_produce_different_vectors() -> None:
    adapter = DeterministicEmbeddingAdapter(dimension=384)
    vec_a = adapter.embed_text("Học phí kỳ 1")
    vec_b = adapter.embed_text("Mượn phòng học H1")

    assert vec_a != vec_b


def test_embed_batch() -> None:
    adapter = DeterministicEmbeddingAdapter(dimension=384)
    texts = ["Văn bản 1", "Văn bản 2", "Văn bản 3"]
    vecs = adapter.embed_batch(texts)

    assert len(vecs) == 3
    assert len(vecs[0]) == 384


def test_embed_empty_fails() -> None:
    adapter = DeterministicEmbeddingAdapter(dimension=384)
    with pytest.raises(ValueError, match="Cannot embed empty text"):
        adapter.embed_text("")
