"""Hot reload of the RAG v2 index: swap is atomic, running turns are unaffected, failure keeps the old node. No DB, no models."""
import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from campus247.bootstrap import rag_v2 as module
from campus247.bootstrap.rag_v2 import RagV2IndexReloader, SwappableRagNode

POINTER = {"release_id": "r2", "generation": 28, "policy_generation": 3}


class FakeNode:
    def __init__(self, name, release, generation, gate=None):
        self.name, self.gate = name, gate
        self.rag_v2_status = SimpleNamespace(manifest={"release_id": release, "generation": generation, "policy_generation": 3}, warm="ready")

    async def __call__(self, state, *, context=None):
        if self.gate is not None:
            await self.gate.wait()
        return self.name


class FakeStore:
    def __init__(self, ready):
        self.ready, self.acks = ready, []

    async def ensure(self):
        pass

    async def registry_for(self, conn, release_id, generation, policy_generation):
        return self.ready

    async def ack_instance(self, conn, instance_id, registry_id, path):
        self.acks.append((instance_id, registry_id, path))


class FakeConnection:
    pass


class FakePool:
    @asynccontextmanager
    async def acquire(self):
        yield FakeConnection()


def reloader(proxy, store, pointer=POINTER):
    class Repo:
        pool = FakePool()
        async def pointer(self, conn):
            return dict(pointer)
    runtime = SimpleNamespace(repo=Repo())
    settings = SimpleNamespace(rag_v2_index_dir="data/rag_v2_index/embedded2", model_copy=lambda update: SimpleNamespace(**update))
    return RagV2IndexReloader(proxy, settings=settings, gateway=None, knowledge_runtime=runtime, inventory_reader=None,
                              context_factory=None, store=store, instance_id="api-1", poll_seconds=0.01)


def patch_loader(monkeypatch, nodes, warm_state="ready"):
    seen = []
    def load(settings, **kwargs):
        seen.append(str(settings.rag_v2_index_dir))
        return nodes.pop(0)
    def warm(node, runtime, factory):
        async def run():
            node.rag_v2_status.warm = warm_state
        return asyncio.ensure_future(run())
    monkeypatch.setattr(module, "load_rag_v2", load)
    monkeypatch.setattr(module, "start_rag_v2_warmup", warm)
    return seen


def test_swaps_to_the_index_built_for_the_serving_release_and_acknowledges_it(monkeypatch):
    async def main():
        old, new = FakeNode("old", "r1", 27), FakeNode("new", "r2", 28)
        proxy = SwappableRagNode(old)
        store = FakeStore({"id": "reg-2", "path": "data/rag_v2_index/embedded-x"})
        seen = patch_loader(monkeypatch, [new])
        loader = reloader(proxy, store)
        assert await proxy(None) == "old"
        await loader.step()
        assert await proxy(None) == "new" and seen[0].endswith("embedded-x")
        assert store.acks[-1][1] == "reg-2" and proxy.refreshing is False
    asyncio.run(main())


def test_a_turn_in_flight_finishes_on_the_old_node(monkeypatch):
    async def main():
        gate = asyncio.Event()
        old, new = FakeNode("old", "r1", 27, gate=gate), FakeNode("new", "r2", 28)
        proxy = SwappableRagNode(old)
        patch_loader(monkeypatch, [new])
        running = asyncio.create_task(proxy(None))   # started before the swap
        await asyncio.sleep(0)
        await reloader(proxy, FakeStore({"id": "reg-2", "path": "p"})).step()
        assert await proxy(None) == "new"            # new turns use the new index at once
        gate.set()
        assert await running == "old"                # the running turn is not disturbed
    asyncio.run(main())


def test_failed_warmup_keeps_the_serving_node_and_does_not_acknowledge_the_new_index(monkeypatch):
    async def main():
        old, new = FakeNode("old", "r1", 27), FakeNode("new", "r2", 28)
        proxy = SwappableRagNode(old)
        store = FakeStore({"id": "reg-2", "path": "p"})
        patch_loader(monkeypatch, [new], warm_state="failed")
        loader = reloader(proxy, store)
        await loader.step()
        assert await proxy(None) == "old" and store.acks[-1][1] is None
        assert proxy.refreshing is True               # still catching up: readiness stays up for a bounded time
        await loader.step()                           # a failed registry entry is not retried in a tight loop
        assert len(store.acks) == 2
    asyncio.run(main())


def test_no_swap_without_a_matching_registry_entry_and_nothing_to_do_when_already_current(monkeypatch):
    async def main():
        proxy = SwappableRagNode(FakeNode("old", "r1", 27))
        patch_loader(monkeypatch, [])
        loader = reloader(proxy, FakeStore(None))
        await loader.step()
        assert await proxy(None) == "old" and proxy.refreshing is True
        current = SwappableRagNode(FakeNode("cur", "r2", 28))
        store = FakeStore({"id": "reg-2", "path": "p"})
        await reloader(current, store).step()        # already serving the right release: no load, ack of the registry entry
        assert await current(None) == "cur" and store.acks[-1][1] == "reg-2" and current.refreshing is False
    asyncio.run(main())


def test_refresh_window_is_bounded(monkeypatch):
    async def main():
        proxy = SwappableRagNode(FakeNode("old", "r1", 27))
        patch_loader(monkeypatch, [])
        loader = reloader(proxy, FakeStore(None))
        await loader.step()
        assert proxy.refreshing is True
        loader._stale_since -= RagV2IndexReloader.REFRESH_WINDOW_S + 1   # never indexed: readiness must turn degraded again
        await loader.step()
        assert proxy.refreshing is False
    asyncio.run(main())


def test_proxy_forwards_everything_the_graph_and_health_use():
    node = FakeNode("n", "r", 1)
    node.prefetch = lambda state: "prefetched"
    proxy = SwappableRagNode(node)
    assert proxy.prefetch(None) == "prefetched" and proxy.rag_v2_status.warm == "ready" and hasattr(proxy, "prefetch")
    with pytest.raises(AttributeError):
        SwappableRagNode.__new__(SwappableRagNode).missing
