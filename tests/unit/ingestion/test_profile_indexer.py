import hashlib
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "services/worker/src"))
from campus247_worker.ingestion.index import ChunkIndexPayload, KnowledgeIndexer, ProfileChunkIndexPayload
from campus247.ports.embedding import EmbeddingProfile, validate_embedding_vector


def fixture():
    profile = EmbeddingProfile("BAAI/bge-m3", "5617a9f61b028005a4858fdac845db406aefb181", 1024)
    content = "Synthetic source section."
    chunk = ChunkIndexPayload("chunk", "document", 0, "Section 1", content, hashlib.sha256(content.encode()).hexdigest())
    payload = ProfileChunkIndexPayload(chunk, validate_embedding_vector([1] + [0] * 1023, profile),
                                       datetime(2026, 10, 6, tzinfo=timezone.utc))
    calls = []
    class Result:
        def first(self): return ("document",)
    class DB:
        def in_transaction(self): return True
        def execute(self, sql, params):
            calls.append((str(sql), params))
            return Result()
        def commit(self): raise AssertionError("caller must own transaction")
    return profile, payload, DB(), calls


def test_bound_embeddings_persist_with_metadata_and_without_legacy_write_or_commit():
    profile, payload, db, calls = fixture()
    assert KnowledgeIndexer().persist_profile_chunks(db, [payload], profile=profile, index_version="new-index") == 1
    assert len(calls) == 2
    assert "FOR SHARE OF v, m" in calls[0][0] and "BUILDING" in calls[0][0] and "DRAFT" in calls[0][0]
    sql, rows = calls[1]
    assert "embedding_rag_v1" in sql and "CAST(:embedding AS vector(1024))" in sql
    assert "UPDATE" not in sql and "ON CONFLICT" not in sql
    assert rows[0]["model_version"] == profile.model_id + "@" + profile.model_revision
    assert rows[0]["dimension"] == 1024 and rows[0]["embedded_at"] == payload.embedded_at


@pytest.mark.parametrize("change", ["checksum", "model", "dimension", "timestamp", "locator", "duplicate"])
def test_invalid_batch_never_calls_database(change):
    profile, payload, db, calls = fixture()
    if change == "checksum": payload = replace(payload, chunk=replace(payload.chunk, content_checksum="a" * 64))
    elif change == "model": payload = replace(payload, embedding=replace(payload.embedding, model_id="other-model"))
    elif change == "dimension": payload = replace(payload, embedding=replace(payload.embedding, dimension=1536))
    elif change == "timestamp": payload = replace(payload, embedded_at=payload.embedded_at.replace(tzinfo=None))
    elif change == "locator": payload = replace(payload, chunk=replace(payload.chunk, section_path=None))
    batch = [payload, payload] if change == "duplicate" else [payload]
    with pytest.raises(ValueError):
        KnowledgeIndexer().persist_profile_chunks(db, batch, profile=profile, index_version="new-index")
    assert not calls


def test_unbound_embedding_cannot_be_silently_discarded():
    _, payload, db, calls = fixture()
    with pytest.raises(ValueError, match="unbound embedding"):
        KnowledgeIndexer().persist_chunks(db, [replace(payload.chunk, embedding_vector=[1, 0])])
    assert not calls


def test_missing_outer_transaction_rejects_before_db():
    profile, payload, db, calls = fixture()
    db.in_transaction = lambda: False
    with pytest.raises(ValueError, match="caller-owned"):
        KnowledgeIndexer().persist_profile_chunks(db, [payload], profile=profile, index_version="new-index")
    assert not calls


def test_physical_norm_tolerance_rejects_before_db():
    profile, payload, db, calls = fixture()
    # The general port tolerates 1e-3; 0013 storage explicitly requires 1e-4.
    payload = replace(payload, embedding=replace(payload.embedding, values=(1.0002,) + (0.0,) * 1023))
    with pytest.raises(ValueError, match="physical storage"):
        KnowledgeIndexer().persist_profile_chunks(db, [payload], profile=profile, index_version="new-index")
    assert not calls
