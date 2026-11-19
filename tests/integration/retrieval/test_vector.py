from __future__ import annotations

from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[3]
API_SRC = ROOT / "services" / "api" / "src"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))

from campus247.infrastructure.retrieval.vector import VectorIndexEntry, VectorSearchAdapter


def test_vector_search_cosine_similarity() -> None:
    adapter = VectorSearchAdapter(environment="test", dimension=3)

    # Seed 3 vectors
    adapter.add_entry(
        VectorIndexEntry(
            chunk_id="chunk_1",
            document_version_id="ver_1",
            section_path="Sec 1",
            content_text="Quy dinh hoc phi",
            embedding=[1.0, 0.0, 0.0],
        )
    )
    adapter.add_entry(
        VectorIndexEntry(
            chunk_id="chunk_2",
            document_version_id="ver_1",
            section_path="Sec 2",
            content_text="Muon phong hoc",
            embedding=[0.0, 1.0, 0.0],
        )
    )
    adapter.add_entry(
        VectorIndexEntry(
            chunk_id="chunk_3",
            document_version_id="ver_1",
            section_path="Sec 3",
            content_text="Thu tuc giay to",
            embedding=[0.707, 0.707, 0.0],
        )
    )

    query_vec = [1.0, 0.0, 0.0]
    results = adapter.search(query_vector=query_vec, limit=2)

    assert len(results) == 2
    assert results[0].chunk_id == "chunk_1"
    assert pytest.approx(results[0].similarity, 1e-3) == 1.0
    assert results[1].chunk_id == "chunk_3"
    assert pytest.approx(results[1].similarity, 1e-3) == 0.7071


def test_vector_search_empty_query_fails() -> None:
    adapter = VectorSearchAdapter(environment="test", dimension=3)
    with pytest.raises(ValueError, match="Query vector cannot be empty"):
        adapter.search(query_vector=[], limit=5)
