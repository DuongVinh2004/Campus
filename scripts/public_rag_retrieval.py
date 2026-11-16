"""Shared, bounded BGE wiring for both local HUCE public chat entrypoints.

Construction only reads sources/indexes. It never starts a model service, builds
an index, opens the paid gateway or substitutes lexical/fake model results.
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx
from campus247.infrastructure.retrieval.public_hybrid import (
    PublicHybridKnowledgeStore,
    PublicRetrievalPolicy,
)
from campus247.infrastructure.retrieval.tei import (
    TEIEmbeddingAdapter,
    TEIRerankerAdapter,
)
from campus247.ports.embedding import EmbeddingProfile, validate_embedding_inputs
from campus247.ports.reranker import RerankerProfile

ROOT = Path(__file__).resolve().parents[1]
INDEX_DIRECTORY = ROOT / "infra/local/rag-advanced-20261013"
EMBED_SHA = "1eebfb28493f67bba03ce0ef64bfdc7fc5a3bd9d7493f818bb1d78cd798416b4"


def create_public_hybrid_store(directory: Path, *, tenant_id: str, campus_id: str,
                               faq_directory: Path | None = None, policy: PublicRetrievalPolicy | None = None,
                               include_reviewed_expansion: bool = True,
                               include_reviewed_services: bool = True,
                               include_reviewed_course_review: bool = True,
                               include_reviewed_withdrawal: bool = True,
                               include_reviewed_batch3_verified: bool = True,
                               include_reviewed_services_02: bool = True,
                               **kwargs) -> PublicHybridKnowledgeStore:
    embedding_profile = EmbeddingProfile(
        "BAAI/bge-m3", "5617a9f61b028005a4858fdac845db406aefb181", 1024,
        batch_limit=1, timeout_ms=5000,
    )
    embedding = TEIEmbeddingAdapter(embedding_profile, lambda: httpx.AsyncClient(
        base_url="http://127.0.0.1:18081", trust_env=False, follow_redirects=False,
    ))

    async def embed(text):
        inputs = validate_embedding_inputs((text,), embedding_profile)
        return (await embedding._embed(inputs)).vectors[0]

    reranker = TEIRerankerAdapter(RerankerProfile(
        "BAAI/bge-reranker-v2-m3", "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e", 20, 10000,
    ), lambda: httpx.AsyncClient(
        base_url="http://127.0.0.1:18082", trust_env=False, follow_redirects=False,
    ))

    def observe(row):
        print(json.dumps({"retrieval": row}), flush=True)

    return PublicHybridKnowledgeStore(
        directory, tenant_id=tenant_id, campus_id=campus_id, faq_directory=faq_directory,
        include_reviewed_expansion=include_reviewed_expansion,
        include_reviewed_services=include_reviewed_services,
        include_reviewed_course_review=include_reviewed_course_review,
        include_reviewed_withdrawal=include_reviewed_withdrawal,
        include_reviewed_batch3_verified=include_reviewed_batch3_verified,
        include_reviewed_services_02=include_reviewed_services_02,
        **kwargs,
        embed_query=embed, embedding_profile=embedding_profile,
        embedding_artifact_sha256=EMBED_SHA, reranker=reranker,
        # Six pairs in total, shared across at most three subqueries. Retain the
        # existing CPU envelope: 10s reranker, 12s retrieval including queueing.
        policy=policy or PublicRetrievalPolicy(fusion_k=6), diagnostics=observe,
    )


def public_hybrid_index_path(corpus: PublicHybridKnowledgeStore,
                             directory: Path = INDEX_DIRECTORY) -> Path:
    path = directory / f"index-{corpus.fingerprint}.json"
    resolved = path.resolve()
    if resolved == ROOT or not resolved.is_relative_to(ROOT):
        raise ValueError("index outside workspace")
    for parent in (path, *path.parents):
        if parent.exists() and (parent.is_symlink() or parent.is_junction()
                                or getattr(parent.stat(), "st_file_attributes", 0) & 0x400):
            raise ValueError("reparse index path denied")
        if parent == ROOT:
            break
    return resolved


def load_public_hybrid_store(directory: Path, *, tenant_id: str, campus_id: str,
                             faq_directory: Path | None = None, policy: PublicRetrievalPolicy | None = None) -> PublicHybridKnowledgeStore:
    corpus = create_public_hybrid_store(
        directory, tenant_id=tenant_id, campus_id=campus_id, faq_directory=faq_directory, policy=policy,
    )
    manifest = json.loads(public_hybrid_index_path(corpus).read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("source_text_unchanged") is not True:
        raise ValueError("unchanged source index required")
    corpus.load_vectors(manifest)
    return corpus
