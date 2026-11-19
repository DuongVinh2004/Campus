"""Per-turn integrity work is kept briefly, and a release or policy change drops it at once."""
import asyncio
import contextlib
from types import SimpleNamespace

import pytest

from campus247.infrastructure.knowledge import runtime as runtime_module
from campus247.infrastructure.knowledge.runtime import KnowledgeReleaseRuntime


def build():
    runtime = object.__new__(KnowledgeReleaseRuntime)
    calls = SimpleNamespace(version=0)

    async def version(conn, version_id):
        calls.version += 1
        return {"id": version_id, "n": calls.version}

    runtime.repo = SimpleNamespace(version=version)
    return runtime, calls


@contextlib.contextmanager
def turn(release="r1", generation=1, policy=1):
    token = runtime_module._TURN.set({"release_id": release, "generation": generation, "policy_generation": policy})
    try:
        yield
    finally:
        runtime_module._TURN.reset(token)


@pytest.mark.asyncio
async def test_a_version_is_read_once_while_the_generation_is_unchanged():
    runtime, calls = build()
    with turn():
        first = await runtime._version_cached(None, "v1")
        second = await runtime._version_cached(None, "v1")
    assert first is second and calls.version == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("change", [{"generation": 2}, {"policy": 2}, {"release": "r2"}])
async def test_a_release_or_policy_change_drops_the_kept_read(change):
    runtime, calls = build()
    with turn():
        await runtime._version_cached(None, "v1")
    with turn(**change):
        await runtime._version_cached(None, "v1")
    assert calls.version == 2


@pytest.mark.asyncio
async def test_a_kept_read_expires(monkeypatch):
    runtime, calls = build()
    clock = [1000.0]
    monkeypatch.setattr(runtime_module.time, "monotonic", lambda: clock[0])
    with turn():
        await runtime._version_cached(None, "v1")
        clock[0] += runtime.VERSION_TTL_S + 1
        await runtime._version_cached(None, "v1")
    assert calls.version == 2


@pytest.mark.asyncio
async def test_snapshot_key_follows_the_content_hashes_of_the_version():
    runtime, _ = build()
    runtime.platform = object()
    reads = []

    async def fake_read(platform, conn, version):
        reads.append(version["rendition_sha256"])
        return {"kind": "X", "sha": version["rendition_sha256"]}

    import campus247.application.knowledge.source_snapshot as snapshot_module
    original = snapshot_module.read_snapshot
    snapshot_module.read_snapshot = fake_read
    try:
        base = {"rendition_id": "a", "rendition_sha256": "h1", "original_sha256": "o", "effective_from": "2026-01-01"}
        with turn():
            await runtime._snapshot_cached(None, "v1", base)
            await runtime._snapshot_cached(None, "v1", base)
            await runtime._snapshot_cached(None, "v1", {**base, "rendition_sha256": "h2"})
    finally:
        snapshot_module.read_snapshot = original
    assert reads == ["h1", "h2"]
