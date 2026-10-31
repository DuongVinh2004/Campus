"""Index contracts, including on-disk format via virtual file handles (no cleanup)."""
import io
import json
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path

import numpy as np
import pytest
from campus247.rag_v2.adapters.memory_index import MemoryIndex
from campus247.rag_v2.retrieval.bm25 import BM25
from campus247.rag_v2.retrieval.hybrid import retrieve
from campus247.rag_v2.types import Scope, Unit
from campus247.rag_v2.understanding.analyze import analyze


def make_unit(uid, text, scope=None):
    return Unit(uid, ("chunk-" + uid,), "doc-" + uid, "v1", "Tài liệu", "quy_che", "article",
                "Điều 1", 2, text, scope=scope or Scope())


@pytest.mark.parametrize("query", ["học phí tín chỉ", "hoc phi tin chi", "HỌC PHÍ TÍN CHỈ"])
def test_bm25_accented_and_unaccented(query):
    index = BM25([("fee", "Học phí tín chỉ"), ("library", "Thủ tục mượn sách thư viện")])
    assert index.search(query, 10)[0][0] == "fee"
    assert index.search(query, 10, allowed=set()) == []
    assert index.search(query, 0) == []


def test_bigram_prefers_phrase_over_reordered_tokens():
    index = BM25([("wrong", "phí học chỉ tín"), ("right", "học phí tín chỉ")])
    assert index.search("hoc phi tin chi", 1)[0][0] == "right"


@pytest.mark.asyncio
async def test_vector_uses_injected_embedding_and_filters_before_limit():
    calls = []
    async def embed(query):
        calls.append(query)
        return [10, 0]
    units = [make_unit("a", "Học phí tín chỉ"), make_unit("b", "Điều kiện bảo lưu"), make_unit("c", "Thư viện")]
    matrix = np.array([[10, 0], [0, 2], [3, 4]], dtype=np.float32)
    original = matrix.copy()
    index = MemoryIndex.from_units(units, matrix, embed)
    assert (await index.vector("query", 3))[0] == ("a", 1.0)
    assert (await index.vector("query", 1, allowed={"b", "c"}))[0][0] == "c"
    assert calls == ["query", "query"]
    assert np.array_equal(matrix, original)
    assert index.all_ids() == ("a", "b", "c")
    assert index.get("missing") is None and index.get("a") == units[0]
    assert (await index.vector("query", 1, allowed=set())) == []


def virtual_directory(monkeypatch, *, manifest=None, matrix=None):
    units = [make_unit("a", "Học phí K64", Scope(cohorts=("K64",))), make_unit("b", "Thư viện")]
    matrix = np.eye(2, dtype=np.float32) if matrix is None else matrix
    npy = io.BytesIO()
    np.save(npy, matrix, allow_pickle=False)
    unit_bytes = ("\n".join(json.dumps(asdict(u), ensure_ascii=False) for u in units) + "\n").encode("utf-8")
    metadata = {"unit_count": 2, "embedding_dimension": 2, "embedding_status": "complete", "files_sha256": {
        "units.jsonl": sha256(unit_bytes).hexdigest(), "embeddings.npy": sha256(npy.getvalue()).hexdigest()}}
    metadata.update(manifest or {})
    files = {"manifest.json": json.dumps(metadata).encode(), "units.jsonl": unit_bytes, "embeddings.npy": npy.getvalue()}
    original_open = Path.open
    def open_file(path, mode="r", *args, **kwargs):
        if path.parent == Path("virtual-index") and path.name in files:
            data = files[path.name]
            return io.BytesIO(data) if "b" in mode else io.StringIO(data.decode("utf-8"))
        return original_open(path, mode, *args, **kwargs)
    monkeypatch.setattr(Path, "open", open_file)
    async def embed(query):
        return [1, 0]
    return units, embed


@pytest.mark.asyncio
async def test_directory_load_matches_t3_serialization_and_hashes(monkeypatch):
    units, embed = virtual_directory(monkeypatch)
    index = MemoryIndex("virtual-index", embed)
    assert index.get("a") == units[0]
    assert index.lexical("hoc phi", 1)[0][0] == "a"
    assert await index.vector("học phí", 1) == [("a", 1.0)]


@pytest.mark.asyncio
async def test_explicit_pending_t3_index_can_search_lexically_without_fabricated_vectors(monkeypatch):
    _, embed = virtual_directory(monkeypatch, matrix=np.empty((2, 0), dtype=np.float32),
                                 manifest={"embedding_dimension": 0, "embedding_status": "pending"})
    index = MemoryIndex("virtual-index", embed)
    assert index.lexical("hoc phi", 1)[0][0] == "a"
    with pytest.raises(ValueError, match="pending"):
        await index.vector("hoc phi", 1)


@pytest.mark.parametrize("manifest", [
    {"unit_count": 3}, {"embedding_dimension": 3}, {"unit_ids": ["b", "a"]}, {"embedding_status": "pending"},
    {"files_sha256": {"units.jsonl": "incorrect"}},
])
def test_manifest_corruption_rejected(monkeypatch, manifest):
    _, embed = virtual_directory(monkeypatch, manifest=manifest)
    with pytest.raises(ValueError):
        MemoryIndex("virtual-index", embed)


@pytest.mark.parametrize("matrix", [[[0, 0]], [[float("nan"), 1]], [[1, 2], [3, 4]], [1, 2], [[]]])
def test_invalid_unit_vectors_rejected(matrix):
    async def embed(query):
        return [1, 0]
    with pytest.raises(ValueError):
        MemoryIndex.from_units([make_unit("a", "text")], matrix, embed)


@pytest.mark.asyncio
@pytest.mark.parametrize("values", [[0, 0], [1], [float("nan"), 1], [float("inf"), 0]])
async def test_invalid_query_vectors_rejected(values):
    async def embed(query):
        return values
    index = MemoryIndex.from_units([make_unit("a", "text")], [[1, 0]], embed)
    with pytest.raises(ValueError):
        await index.vector("query", 1)


@pytest.mark.asyncio
async def test_end_to_end_memory_index_to_hybrid_retains_relevant_sources():
    units = [make_unit(str(i), f"Điều kiện bảo lưu và nghỉ học tạm thời. Mục {i}.") for i in range(15)]
    async def embed(query):
        return [1, 0]
    class Fail:
        async def rerank(self, query, texts, *, deadline_s):
            raise TimeoutError
    index = MemoryIndex.from_units(units, [[1, 0]] * 15, embed)
    result = await retrieve(analyze("Điều kiện bảo lưu?", ()), index, Fail(), rerank_deadline_s=0.1)
    assert result.trace["preselected"] == 10 and result.trace["documents"] == 10
    assert result.fallback_used and len(result.candidates) == 8
    assert all(index.get(c.unit_id).text.startswith("Điều kiện bảo lưu") for c in result.candidates)


def test_anchored_search_stays_inside_units_naming_the_identifier():
    documents = [("noise", "tổng tín chỉ loại trừ tổng tín chỉ loại trừ"),
                 ("target", "K71QD Tổng 181TC không tính giáo dục thể chất"),
                 ("other", "K71QD Học phần 430103 giáo dục thể chất")]
    index = BM25(documents)
    assert index.search("K71QD tổng tín chỉ loại trừ", 1)[0][0] == "noise"
    assert [uid for uid, _ in index.anchored("K71QD tổng tín chỉ loại trừ", 5)] == ["target", "other"]
    assert index.anchored("tổng tín chỉ", 5) == []
    assert index.anchored("K71QD tổng", 5, allowed={"other"}) == [("other", pytest.approx(index.anchored("K71QD tổng", 5, allowed={"other"})[0][1]))]
    assert index.anchored("K71QD", 5, max_document_frequency=1) == []
