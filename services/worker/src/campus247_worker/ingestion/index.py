from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import math
from typing import Any
from sqlalchemy import Connection, text

from campus247.ports.embedding import EmbeddingProfile, EmbeddingVector, validate_embedding_vector


@dataclass(frozen=True)
class ChunkIndexPayload:
    chunk_id: str
    document_version_id: str
    ordinal: int
    section_path: str | None
    content_text: str
    content_checksum: str
    page_start: int | None = None
    page_end: int | None = None
    embedding_vector: list[float] | None = None


@dataclass(frozen=True)
class ProfileChunkIndexPayload:
    chunk: ChunkIndexPayload
    embedding: EmbeddingVector
    embedded_at: datetime


class KnowledgeIndexer:
    """Persists version-bound knowledge chunk index records."""

    def persist_chunks(self, conn: Connection, chunks: list[ChunkIndexPayload]) -> int:
        if not chunks:
            return 0
        if any(c.embedding_vector is not None for c in chunks):
            raise ValueError("unbound embedding cannot be silently discarded; use profile persistence")

        stmt = text(
            """
            INSERT INTO knowledge_chunk (
                id,
                document_version_id,
                ordinal,
                section_path,
                page_start,
                page_end,
                content_text,
                content_checksum,
                version
            ) VALUES (
                :id,
                :document_version_id,
                :ordinal,
                :section_path,
                :page_start,
                :page_end,
                :content_text,
                :content_checksum,
                1
            )
            """
        )

        params = [
            {
                "id": c.chunk_id,
                "document_version_id": c.document_version_id,
                "ordinal": c.ordinal,
                "section_path": c.section_path,
                "page_start": c.page_start,
                "page_end": c.page_end,
                "content_text": c.content_text,
                "content_checksum": c.content_checksum,
            }
            for c in chunks
        ]

        conn.execute(stmt, params)
        conn.commit()
        return len(chunks)

    def persist_profile_chunks(self, conn: Connection, chunks: list[ProfileChunkIndexPayload],
                               *, profile: EmbeddingProfile, index_version: str) -> int:
        """INSERT exact bound vectors; caller owns transaction and publication.

        Requires a BUILDING manifest and DRAFT version already created by the
        authorized versioned job. Never updates old chunks, commits a partial
        index or infers a model from vector length. Legacy 1536 store is omitted.
        """
        if (not isinstance(profile, EmbeddingProfile) or
                (profile.model_id, profile.model_revision, profile.dimension, profile.normalization) !=
                ("BAAI/bge-m3", "5617a9f61b028005a4858fdac845db406aefb181", 1024, "l2")):
            raise ValueError("qualified physical profile mapping required")
        if not isinstance(index_version, str) or not index_version.strip() or index_version != index_version.strip():
            raise ValueError("explicit index version required")
        if not chunks:
            return 0
        if not conn.in_transaction():
            raise ValueError("caller-owned index transaction required")
        params = []
        seen = set()
        for item in chunks:
            if not isinstance(item, ProfileChunkIndexPayload) or not isinstance(item.embedding, EmbeddingVector):
                raise ValueError("typed chunk and embedding required")
            c, vector = item.chunk, item.embedding
            if (vector.dimension != profile.dimension or vector.normalization != profile.normalization):
                raise ValueError("embedding physical mapping mismatch")
            validate_embedding_vector(vector.values, profile, model_id=vector.model_id,
                                      model_revision=vector.model_revision)
            if abs(1 - math.fsum(v * v for v in vector.values)) > 1e-4:
                raise ValueError("embedding exceeds physical storage normalization tolerance")
            if (c.chunk_id in seen or c.embedding_vector is not None or not c.section_path
                    or not c.content_text.strip() or c.ordinal < 0
                    or c.content_checksum != hashlib.sha256(c.content_text.encode("utf-8")).hexdigest()
                    or not isinstance(item.embedded_at, datetime) or item.embedded_at.tzinfo is None):
                raise ValueError("chunk integrity/locator/embedding timestamp rejected")
            seen.add(c.chunk_id)
            params.append({"id": c.chunk_id, "document_version_id": c.document_version_id,
                "ordinal": c.ordinal, "section_path": c.section_path, "page_start": c.page_start,
                "page_end": c.page_end, "content_text": c.content_text, "content_checksum": c.content_checksum,
                "embedding": "[" + ",".join(str(v) for v in vector.values) + "]",
                "model_version": profile.model_id + "@" + profile.model_revision,
                "dimension": profile.dimension, "embedded_at": item.embedded_at})
        # Check every document/index before any INSERT. FOR SHARE prevents a
        # concurrent lifecycle change until the caller's transaction finishes.
        for document_id in sorted({c.chunk.document_version_id for c in chunks}):
            row = conn.execute(text("""
                SELECT v.id FROM document_version v
                JOIN embedding_index_manifest m ON m.index_version = v.index_version
                WHERE v.id = :document_id AND v.status = 'DRAFT'
                  AND m.index_version = :index_version AND m.build_status = 'BUILDING'
                  AND m.embedding_model_id = :model AND m.embedding_model_revision = :revision
                  AND m.dimension = :dimension AND m.normalization = 'l2' AND m.distance_metric = 'cosine'
                FOR SHARE OF v, m
            """), {"document_id": document_id, "index_version": index_version,
                "model": profile.model_id, "revision": profile.model_revision,
                "dimension": profile.dimension}).first()
            if row is None:
                raise ValueError("draft document/building manifest binding required")
        conn.execute(text("""
            INSERT INTO knowledge_chunk (id, document_version_id, ordinal, section_path,
                page_start, page_end, content_text, content_checksum, embedding_rag_v1,
                embedding_model_version, embedding_dimension, embedded_at, version)
            VALUES (:id, :document_version_id, :ordinal, :section_path, :page_start, :page_end,
                :content_text, :content_checksum, CAST(:embedding AS vector(1024)),
                :model_version, :dimension, :embedded_at, 1)
        """), params)
        return len(chunks)
