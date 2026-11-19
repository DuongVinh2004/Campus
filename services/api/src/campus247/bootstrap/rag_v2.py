"""One startup binding of the v2 snapshot, existing gateway and loopback models."""
from __future__ import annotations

import asyncio
import inspect
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from campus247.agent.nodes.rag_v2 import RagV2Node
from campus247.domain.shared.values import generate_uuid7
from campus247.ports.identity import IdentityContext, IdentityRole
from campus247.rag_v2.adapters.http_reranker import HTTPReranker
from campus247.rag_v2.adapters.index_store import ROOT, read_index

ROOT_DIR = ROOT
from campus247.rag_v2.adapters.memory_index import MemoryIndex
from campus247.rag_v2.service import RagV2Service
from campus247.rag_v2.vocabulary import Vocabulary


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

    async def embed_uncached(query):
        batch = await knowledge_runtime.embedding._embed((query,))
        return batch.vectors[0].values

    # The same text always gives the same vector: embed it once, share it between callers, and let the node start it early.
    from campus247.rag_v2.adapters.vector_cache import QueryVectorCache
    embed = QueryVectorCache(embed_uncached)

    # Reuse the validated 18081 embedding adapter and gateway, including their
    # original endpoint identity, egress, accounting and writer-lease controls.
    index = MemoryIndex.__new__(MemoryIndex)
    index.manifest = snapshot.manifest
    index._initialize(snapshot.units, snapshot.embeddings, embed)
    service = RagV2Service(snapshot.facts, Vocabulary.from_units(snapshot.units))
    node = RagV2Node(service=service, index=index,
        reranker=HTTPReranker(batch_size=10), embed=embed, gateway=gateway,
        authorize_sources=lambda query, context: knowledge_runtime.rag_v2_sources(
            query, context, tuple(dict.fromkeys(chunk for unit in snapshot.units for chunk in unit.chunk_ids))),
        revalidate=knowledge_runtime.rag_v2_revalidate)
    node.rag_v2_status = RagV2Status(manifest, knowledge_runtime, inventory_reader)
    node.start_injection_warmup()
    return node


class SwappableRagNode:
    """Holds the node that is serving; a newer index replaces it with a single attribute assignment.

    A turn already running keeps the node object it started with, so it finishes on the index it began on. Nothing
    of retrieval, ranking, thresholds or prompts lives here: every call is forwarded to the current RagV2Node.
    """
    def __init__(self, node):
        self.current = node
        self.refreshing = False   # a newer release is being indexed or loaded (readiness stays up while true)
        self.loaded_path = None   # index directory currently serving (set by the reloader)

    async def __call__(self, *args, **kwargs):
        return await self.current(*args, **kwargs)

    def __getattr__(self, name):
        if name == "current":  # not yet set (copy/unpickle): never recurse
            raise AttributeError(name)
        return getattr(self.current, name)


class RagV2IndexReloader:
    """Loads the index the ingestion worker built for the serving release, in the background, then swaps it in.

    Uses `load_rag_v2` and `start_rag_v2_warmup` unchanged (same checks, same warm-up of the source gate), so the new
    node is complete and warm before any question sees it. Failure leaves the serving node untouched.
    """
    REFRESH_WINDOW_S = 600.0

    def __init__(self, proxy, *, settings, gateway, knowledge_runtime, inventory_reader, context_factory, store,
                 instance_id, poll_seconds=5.0, warm_timeout_s=240.0):
        self.proxy, self.settings, self.gateway = proxy, settings, gateway
        self.runtime, self.inventory_reader, self.context_factory = knowledge_runtime, inventory_reader, context_factory
        self.store, self.instance_id, self.poll, self.warm_timeout = store, instance_id, poll_seconds, warm_timeout_s
        self.proxy.loaded_path = str(Path(settings.rag_v2_index_dir).resolve())
        self._stale_since = None
        self._failed = {}   # registry id -> monotonic time of the last failed attempt

    def _matches(self, pointer) -> bool:
        manifest = self.proxy.current.rag_v2_status.manifest
        return (pointer["release_id"] is not None and str(manifest.get("release_id")) == str(pointer["release_id"])
                and manifest.get("generation") == pointer["generation"]
                and manifest.get("policy_generation") == pointer["policy_generation"])

    async def run(self):
        import logging
        await self.store.ensure()
        while True:
            try:
                await self.step()
            except asyncio.CancelledError:
                raise
            except Exception as error:  # noqa: BLE001 -- serving continues on the current index; retried next poll
                logging.getLogger("campus247.rag_v2").warning("rag_v2_reload_step_failed kind=%s", type(error).__name__)
            await asyncio.sleep(self.poll)

    async def step(self):
        import time
        repo = self.runtime.repo
        async with repo.pool.acquire() as conn:
            pointer = await repo.pointer(conn)
            ready = (await self.store.registry_for(conn, pointer["release_id"], pointer["generation"], pointer["policy_generation"])
                     if pointer["release_id"] else None)
        matches = self._matches(pointer)
        if matches:
            self._stale_since = None
        else:
            self._stale_since = self._stale_since or time.monotonic()
        self.proxy.refreshing = (not matches) and time.monotonic() - self._stale_since < self.REFRESH_WINDOW_S
        if not matches and ready is not None and time.monotonic() - self._failed.get(str(ready["id"]), -1e9) > 60:
            try:
                await self.swap(ready)
                matches = self._matches(pointer)
                if matches:
                    self._stale_since, self.proxy.refreshing = None, False
            except asyncio.CancelledError:
                raise
            except Exception as error:  # noqa: BLE001
                import logging
                self._failed[str(ready["id"])] = time.monotonic()
                logging.getLogger("campus247.rag_v2").warning("rag_v2_reload_failed kind=%s", type(error).__name__)
        async with repo.pool.acquire() as conn:
            await self.store.ack_instance(conn, self.instance_id, ready["id"] if (matches and ready is not None) else None,
                                          self.proxy.loaded_path)

    async def swap(self, ready):
        path = Path(ready["path"])
        path = path if path.is_absolute() else ROOT_DIR / path
        settings = self.settings.model_copy(update={"rag_v2_index_dir": path})
        node = await asyncio.to_thread(load_rag_v2, settings, gateway=self.gateway, knowledge_runtime=self.runtime,
                                       inventory_reader=self.inventory_reader)
        warm = start_rag_v2_warmup(node, self.runtime, self.context_factory)
        try:
            await asyncio.wait_for(warm, self.warm_timeout)
        except BaseException:
            warm.cancel()
            raise
        if node.rag_v2_status.warm != "ready":
            raise RuntimeError("RAG_V2_RELOAD_WARMUP_FAILED")
        self.proxy.current = node          # the only moment the serving node changes
        self.proxy.loaded_path = str(path.resolve())


def start_rag_v2_warmup(node, runtime, context_factory):
    """Read the public student scope through the existing factory and source gate."""
    node.rag_v2_status.warm = "pending"

    async def warm():
        try:
            now = datetime.now(UTC)
            actor = IdentityContext(subject_id=generate_uuid7(), external_subject="rag-v2-warmup",
                issuer="internal:rag-v2-warmup", roles=(IdentityRole.STUDENT,), display_name="RAG warmup",
                auth_time=now, expires_at=now + timedelta(hours=1), tenant_id=runtime.repo.tenant,
                session_id=generate_uuid7(), is_synthetic=True, student_code="internal-rag-v2-warmup")
            context = context_factory.create(actor, effective_at=now, locale="vi-VN",
                trace_id=uuid4().hex, allow_simulation=False)
            scope = context.authorized_scope
            if scope.roles != frozenset({"STUDENT"}) or not scope.audiences <= {"PUBLIC", "STUDENT"}:
                raise ValueError("RAG_V2_WARMUP_SCOPE_INVALID")
            rows = await node.authorize_sources("", context)
            await asyncio.to_thread(node._prepare_index, rows)
            node.rag_v2_status.warm = "ready"
        except asyncio.CancelledError:
            node.rag_v2_status.warm = "failed"
            raise
        except Exception as exc:  # noqa: BLE001 -- optional warmup must not prevent startup
            node.rag_v2_status.warm = "failed"
            import logging
            logging.getLogger("campus247.rag_v2").warning("rag_v2_warmup_failed kind=%s", type(exc).__name__)

    return asyncio.create_task(warm(), name="rag-v2-warmup")
