import importlib.util
import io
import json
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import httpx
import numpy as np
import pytest
from campus247.rag_v2.adapters.index_store import (
    normalize_embeddings,
    read_index,
    write_index,
)
from campus247.rag_v2.ingest.units import build_units
from campus247.rag_v2.types import Fact

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("t3_build_index", ROOT / "scripts/rag_v2_build_index.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def sample():
    return build_units([{"chunk_id": "c", "document_id": "d", "version_id": "v", "doc_title": "Thông báo", "doc_family": "thong_bao", "text": "Hạn nộp: 20/10/2026."}])[0]


@pytest.fixture
def memory_disk(monkeypatch):
    """Exercise real serialization/checksums without disposable filesystem files."""
    files = {}
    directory = ROOT / "data/rag_v2_index_test_memory"
    original_exists = Path.exists

    def local(path):
        return path == directory or directory in path.parents

    @contextmanager
    def opened(path, mode="r", **kwargs):
        assert local(path)
        if "x" in mode and path in files:
            raise FileExistsError(path)
        writing = "x" in mode or "w" in mode
        data = files.get(path, b"")
        stream = io.BytesIO(data) if "b" in mode else io.StringIO(data.decode("utf8"))
        yield stream
        if writing:
            value = stream.getvalue()
            files[path] = value if isinstance(value, bytes) else value.encode("utf8")
        stream.close()

    monkeypatch.setattr(Path, "open", opened)
    monkeypatch.setattr(Path, "exists", lambda p: p in files if local(p) else original_exists(p))
    monkeypatch.setattr(Path, "mkdir", lambda p, **kwargs: None)
    monkeypatch.setattr(Path, "read_bytes", lambda p: files[p])
    monkeypatch.setattr(Path, "read_text", lambda p, **kwargs: files[p].decode("utf8"))
    return directory, files


def test_snapshot_roundtrip_and_no_replacement(memory_disk):
    path, files = memory_disk
    unit = sample()
    fact = Fact("f", "deadline", "hạn nộp", "20/10/2026", unit.unit_id, "Hạn nộp: 20/10/2026.")
    matrix = normalize_embeddings([[3, 4]], 1)
    write_index(path, [unit], [fact], matrix, {"corpus_sha256": "hash", "release_id": "r", "generation": 27})
    loaded = read_index(path)
    assert loaded.units == (unit,)
    assert loaded.facts == (fact,)
    np.testing.assert_allclose(loaded.embeddings, [[.6, .8]])
    assert loaded.manifest["embedding_status"] == "complete"
    before = dict(files)
    with pytest.raises(FileExistsError):
        write_index(path, [unit], [fact], matrix, {})
    assert before == files
    files[path / "facts.jsonl"] += b" "
    with pytest.raises(ValueError, match="CHECKSUM"):
        read_index(path)


def test_pending_snapshot_explicitly_has_no_vectors(memory_disk):
    path, _ = memory_disk
    write_index(path, [sample()], [], np.empty((1, 0), dtype=np.float32), {})
    snapshot = read_index(path)
    assert snapshot.embeddings.shape == (1, 0)
    assert snapshot.manifest["embedding_status"] == "pending"


@pytest.mark.parametrize("values,count", [([[0, 0]], 1), ([[float('nan'), 1]], 1), ([[1, 2]], 2), ([1, 2], 1)])
def test_reject_invalid_embedding_matrix(values, count):
    with pytest.raises(ValueError):
        normalize_embeddings(values, count)


def test_invalid_fact_rejected_before_any_file(memory_disk):
    path, files = memory_disk
    fact = Fact("f", "deadline", "hạn", "invented", sample().unit_id, "invented")
    with pytest.raises(ValueError, match="PROVENANCE"):
        write_index(path, [sample()], [fact], normalize_embeddings([[1, 0]], 1), {})
    assert files == {}


def test_context_is_not_quotable_fact_evidence(memory_disk):
    path, files = memory_disk
    unit = sample()
    fact = Fact("f", "contact", "đơn vị", "Thông báo", unit.unit_id, "Thông báo")
    assert fact.quote in unit.text
    with pytest.raises(ValueError, match="PROVENANCE"):
        write_index(path, [unit], [fact], normalize_embeddings([[1, 0]], 1), {})
    assert not files


def test_reject_destination_outside_workspace():
    with pytest.raises(ValueError, match="OUTSIDE"):
        write_index(ROOT.parent / "outside", [], [], np.empty((0, 0), dtype=np.float32), {})


def test_real_protocol_bounded_batches_and_l2():
    batches = []

    def handler(request):
        if request.url.path == "/info":
            return httpx.Response(200, json={"model_id": "BAAI/bge-m3", "model_sha": "revision", "model_type": {"embedding": {}}, "auto_truncate": False})
        assert request.url.path == "/embed"
        payload = json.loads(request.content)
        assert payload["normalize"] is True and payload["truncate"] is False
        batches.append(payload["inputs"])
        return httpx.Response(200, json=[[3., 4.] for _ in payload["inputs"]])

    units = [replace(sample(), unit_id=str(i)) for i in range(45)]
    with httpx.Client(transport=httpx.MockTransport(handler), base_url="http://127.0.0.1:18081") as client:
        vectors, metadata = builder.embed_units(units, client=client)
    assert [len(b) for b in batches] == [20, 20, 5]
    np.testing.assert_allclose(np.linalg.norm(vectors, axis=1), 1)
    assert vectors.dtype == np.float32
    assert metadata["embedding_model"] == "BAAI/bge-m3"


def test_runtime_unavailable_is_not_replaced_by_fake_vectors():
    def handler(request):
        if request.url.path == "/info":
            return httpx.Response(200, json={"model_id": "BAAI/bge-m3", "model_type": {"embedding": {}}, "auto_truncate": False})
        return httpx.Response(503, json={"error": "MODEL_RUNTIME_UNAVAILABLE"})

    with httpx.Client(transport=httpx.MockTransport(handler), base_url="http://127.0.0.1:18081") as client, pytest.raises(httpx.HTTPStatusError):
        builder.embed_units([sample()], client=client)


@pytest.mark.parametrize("rows", [[], [[0, 0]], [[True, 1]], [[1, float('inf')]]])
def test_reject_bad_server_output(rows):
    def handler(request):
        if request.url.path == "/info":
            return httpx.Response(200, json={"model_id": "BAAI/bge-m3", "model_type": {"embedding": {}}, "auto_truncate": False})
        # JSON does not represent Infinity; emit it as a corrupt raw response.
        return httpx.Response(200, content=json.dumps(rows).encode())

    with httpx.Client(transport=httpx.MockTransport(handler), base_url="http://127.0.0.1:18081") as client, pytest.raises(ValueError):
        builder.embed_units([sample()], client=client)


def test_oversized_npy_header_is_rejected_before_allocation(tmp_path):
    import numpy as np
    import pytest
    from campus247.rag_v2.adapters.npy import load_matrix
    good = tmp_path / "good.npy"
    np.save(good, np.ones((2, 3), dtype=np.float32))
    assert load_matrix(good).shape == (2, 3)
    bomb = tmp_path / "bomb.npy"
    header = b"{'descr': '<f4', 'fortran_order': False, 'shape': (1, 1099511627776), }"
    header += b" " * (64 - (10 + len(header) + 1) % 64) + b"\n"
    bomb.write_bytes(b"\x93NUMPY\x01\x00" + len(header).to_bytes(2, "little") + header + b"\0" * 16)
    with pytest.raises(ValueError, match="INDEX_NPY_SIZE"):
        load_matrix(bomb)
