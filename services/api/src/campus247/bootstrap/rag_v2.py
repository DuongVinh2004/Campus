"""One startup binding of the v2 snapshot, existing gateway and loopback models."""
from __future__ import annotations

from pathlib import Path
import inspect

from campus247.agent.nodes.rag_v2 import RagV2Node
from campus247.rag_v2.adapters.http_reranker import HTTPReranker
from campus247.rag_v2.adapters.index_store import ROOT, read_index
from campus247.rag_v2.adapters.memory_index import MemoryIndex
from campus247.rag_v2.service import RagV2Service


class RagV2Status:
    """Readiness only; never grants source access or restarts the runtime.

    inventory_reader returns release_id/generation/policy_generation and a
    chunk_inventory mapping from the same read-only release transaction.
    """
    def __init__(self, manifest, runtime, inventory_reader=None):
        self.manifest, self.runtime = manifest, runtime
        self.inventory_reader = inventory_reader
        self.warm = None

    async def refresh(self):
        manifest = self.manifest
        result = dict(enabled=True, snapshot_state="complete", stale=None,
            unit_count=manifest.get("unit_count", 0), release_id=manifest.get("release_id"),
            generation=manifest.get("generation"), policy_generation=manifest.get("policy_generation"),
            warm=self.warm, missing_chunks=None, extra_chunks=None, changed_chunks=None,
            inventory_checked=False)
        current = getattr(self.runtime, "current", None)
        if self.inventory_reader is not None:
            inventory = self.inventory_reader()
            current = await inventory if inspect.isawaitable(inventory) else inventory
            if not isinstance(current, dict) or not isinstance(current.get("chunk_inventory"), dict):
                raise ValueError("RAG_V2_INVENTORY_INVALID")
            expected, actual = manifest.get("chunk_inventory", {}), current["chunk_inventory"]
            missing, extra = set(actual) - set(expected), set(expected) - set(actual)
            changed = {k for k in set(expected) & set(actual) if expected[k] != actual[k]}
            result.update(missing_chunks=len(missing), extra_chunks=len(extra), changed_chunks=len(changed),
                          inventory_checked=True, stale=bool(missing or extra or changed))
        if current is not None:
            mismatch = any(manifest.get(k) is None or str(manifest[k]) != str(current.get(k))
                           for k in ("release_id", "generation", "policy_generation"))
            result["stale"] = bool(result["stale"] or mismatch) if result["inventory_checked"] or mismatch else None
        if result["stale"]:
            result["snapshot_state"] = "stale"
        elif result["stale"] is None:
            result["snapshot_state"] = "unverified"
        return result


def load_rag_v2(settings, *, gateway, knowledge_runtime, inventory_reader=None):
    directory = Path(settings.rag_v2_index_dir)
    if not directory.is_absolute():
        directory = ROOT / directory
    if not directory.is_dir():
        raise ValueError("RAG_V2_INDEX_MISSING: configure CAMPUS247_RAG_V2_INDEX")
    snapshot = read_index(directory)
    if knowledge_runtime is None:
        raise ValueError("RAG_V2_AUTHORIZATION_REQUIRED: release-bound source reader required")
    manifest = snapshot.manifest
    profile = getattr(knowledge_runtime.embedding, "profile", None)
    if (manifest.get("embedding_status") != "complete" or profile is None
            or not manifest.get("embedding_revision")
            or manifest.get("embedding_model") != profile.model_id
            or manifest.get("embedding_revision") != profile.model_revision
            or manifest.get("embedding_dimension") != profile.dimension
            or snapshot.embeddings.shape[1] != profile.dimension
            or manifest.get("embedding_pooling") != getattr(profile, "pooling", "cls")
            or str(manifest.get("normalization", "")).casefold() != profile.normalization):
        raise ValueError("RAG_V2_EMBEDDING_INCOMPATIBLE")

    async def embed(query):
        batch = await knowledge_runtime.embedding._embed((query,))
        return batch.vectors[0].values

    # Reuse the validated 18081 embedding adapter and gateway, including their
    # original endpoint identity, egress, accounting and writer-lease controls.
    index = MemoryIndex.__new__(MemoryIndex)
    index.manifest = snapshot.manifest
    index._initialize(snapshot.units, snapshot.embeddings, embed)
    service = RagV2Service(snapshot.facts)
    node = RagV2Node(service=service, index=index,
        reranker=HTTPReranker(batch_size=10), embed=embed, gateway=gateway,
        authorize_sources=lambda query, context: knowledge_runtime.rag_v2_sources(
            query, context, tuple(dict.fromkeys(chunk for unit in snapshot.units for chunk in unit.chunk_ids))),
        revalidate=knowledge_runtime.rag_v2_revalidate)
    node.rag_v2_status = RagV2Status(manifest, knowledge_runtime, inventory_reader)
    return node
