"""One startup binding of the v2 snapshot, existing gateway and loopback models."""
from __future__ import annotations

from pathlib import Path

from campus247.agent.nodes.rag_v2 import RagV2Node
from campus247.rag_v2.adapters.http_reranker import HTTPReranker
from campus247.rag_v2.adapters.index_store import ROOT, read_index
from campus247.rag_v2.adapters.memory_index import MemoryIndex
from campus247.rag_v2.service import RagV2Service


def load_rag_v2(settings, *, gateway, knowledge_runtime):
    directory = Path(settings.rag_v2_index_dir)
    if not directory.is_absolute():
        directory = ROOT / directory
    if not directory.is_dir():
        raise ValueError("RAG_V2_INDEX_MISSING: configure CAMPUS247_RAG_V2_INDEX")
    snapshot = read_index(directory)
    if knowledge_runtime is None:
        raise ValueError("RAG_V2_AUTHORIZATION_REQUIRED: release-bound source reader required")

    async def embed(query):
        batch = await knowledge_runtime.embedding._embed((query,))
        return batch.vectors[0].values

    # Reuse the validated 18081 embedding adapter and gateway, including their
    # original endpoint identity, egress, accounting and writer-lease controls.
    index = MemoryIndex.__new__(MemoryIndex)
    index.manifest = snapshot.manifest
    index._initialize(snapshot.units, snapshot.embeddings, embed)
    service = RagV2Service(snapshot.facts)
    return RagV2Node(service=service, index=index,
        reranker=HTTPReranker(batch_size=10), embed=embed, gateway=gateway,
        authorize_sources=lambda query, context: knowledge_runtime.rag_v2_sources(
            query, context, tuple(dict.fromkeys(chunk for unit in snapshot.units for chunk in unit.chunk_ids))),
        revalidate=knowledge_runtime.rag_v2_revalidate)
