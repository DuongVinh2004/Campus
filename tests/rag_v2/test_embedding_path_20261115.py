"""Step 1.9: the embedding path does less work without changing a single vector or check.

Query-vector cache (shared in-flight calls, failures not kept), the early prefetch from the RAG node, the per-row
digest of the authorized rows, and the model-identity check that is now repeated at most every 30 s.
"""
import asyncio
import time
from types import SimpleNamespace

import httpx
import pytest

from campus247.agent.nodes import rag_v2 as node_module
from campus247.infrastructure.retrieval import tei
from campus247.ports.embedding import EmbeddingProfile
from campus247.rag_v2.adapters.vector_cache import QueryVectorCache


# ---- cache ---------------------------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_same_text_is_embedded_once_and_concurrent_callers_share_the_call():
    calls = []

    async def embed(query):
        calls.append(query)
        await asyncio.sleep(0.05)
        return (len(query), 0.5)

    cache = QueryVectorCache(embed)
    results = await asyncio.gather(*[cache("học phí") for _ in range(5)], cache("điểm rèn luyện"))
    assert results[:5] == [(7, 0.5)] * 5 and results[5] == (14, 0.5)
    assert calls == ["học phí", "điểm rèn luyện"]
    assert await cache("học phí") == (7, 0.5) and len(calls) == 2
    assert (cache.hits, cache.misses) == (5, 2)


@pytest.mark.asyncio
async def test_a_caller_that_gives_up_does_not_cancel_the_shared_call():
    release = asyncio.Event()

    async def embed(query):
        await release.wait()
        return "vector"

    cache = QueryVectorCache(embed)
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.05):
            await cache("q")
    release.set()
    assert await cache("q") == "vector"          # the call kept running and is reused


@pytest.mark.asyncio
async def test_failures_are_never_cached():
    attempts = []

    async def embed(query):
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("model busy")
        return "ok"

    cache = QueryVectorCache(embed)
    with pytest.raises(RuntimeError):
        await cache("q")
    assert await cache("q") == "ok" and len(attempts) == 2


@pytest.mark.asyncio
async def test_entries_expire_and_the_cache_is_bounded():
    async def embed(query):
        return query

    cache = QueryVectorCache(embed, max_entries=3, ttl_s=0.05)
    for i in range(6):
        await cache(f"q{i}")
    assert len(cache._entries) == 3
    await asyncio.sleep(0.08)
    before = cache.misses
    await cache("q5")
    assert cache.misses == before + 1             # expired, embedded again
    with pytest.raises(ValueError):
        QueryVectorCache(embed, max_entries=0)


@pytest.mark.asyncio
async def test_prefetch_starts_the_call_without_waiting_and_swallows_errors():
    started = asyncio.Event()

    async def embed(query):
        started.set()
        raise RuntimeError("boom")

    cache = QueryVectorCache(embed)
    cache.prefetch("q")                          # returns at once, no exception
    await asyncio.wait_for(started.wait(), 1)
    await asyncio.sleep(0.01)                    # the failure stays inside the future; nothing is raised here
    cache.prefetch("q")                          # idempotent while an entry exists, harmless after failure


# ---- node prefetch ---------------------------------------------------------------------------------------------

class Recorder:
    def __init__(self):
        self.queries = []

    def prefetch(self, query):
        self.queries.append(query)


def make_node(embed):
    node = node_module.RagV2Node.__new__(node_module.RagV2Node)
    node.embed = embed
    return node


def turn(query, history=False):
    turns = (SimpleNamespace(role="user", content="trước đó"),) if history else ()
    return SimpleNamespace(request=SimpleNamespace(query=query, history=SimpleNamespace(turns=turns) if history else None))


def test_prefetch_embeds_the_search_query_of_a_plain_question():
    recorder = Recorder()
    make_node(recorder).prefetch(turn("Học phí học kỳ này là bao nhiêu?"))
    assert len(recorder.queries) == 1 and recorder.queries[0]


@pytest.mark.parametrize("state", [turn("Học phí là bao nhiêu?", history=True), turn("?"), turn("thời tiết hôm nay thế nào")])
def test_prefetch_skips_follow_ups_and_questions_that_will_not_be_searched(state):
    recorder = Recorder()
    make_node(recorder).prefetch(state)
    assert recorder.queries == []


def test_prefetch_never_breaks_the_turn():
    make_node(lambda query: None).prefetch(turn("Học phí?"))     # no .prefetch on the embed callable
    make_node(SimpleNamespace(prefetch=lambda q: 1 / 0)).prefetch(turn("Học phí là bao nhiêu?"))
    make_node(Recorder()).prefetch(SimpleNamespace())             # malformed state


# ---- per-row digest ---------------------------------------------------------------------------------------------

def rows():
    return {f"c{i}": {"chunk_id": f"c{i}", "evidence_sha256": "h", "source_id": "s", "document_version_id": "v",
                      "title": "t", "section_path": "p", "effective_from": None, "effective_until": None,
                      "content_text": f"nội dung {i}"} for i in range(50)}


def test_fingerprint_is_stable_and_reuses_row_digests():
    data = rows()
    first = node_module._rows_fingerprint(data)
    entries = {chunk: node_module._ROW_DIGESTS[(id(row["content_text"]), chunk)] for chunk, row in data.items()}
    assert node_module._rows_fingerprint(data) == first
    # a per-turn copy of each row (new dict, same text object) finds the remembered digest instead of hashing again
    copies = {chunk: dict(row) for chunk, row in data.items()}
    assert node_module._rows_fingerprint(copies) == first
    assert all(node_module._ROW_DIGESTS[(id(row["content_text"]), chunk)] is entries[chunk] for chunk, row in copies.items())


def test_any_change_to_a_row_changes_the_fingerprint():
    data = rows()
    base = node_module._rows_fingerprint(data)
    for field, value in (("title", "khác"), ("evidence_sha256", "x"), ("effective_until", "2027-01-01"), ("content_text", "đã sửa")):
        changed = rows()
        node_module._rows_fingerprint(changed)             # remember the original digests first
        changed["c7"][field] = value
        assert node_module._rows_fingerprint(changed) != base, field
    extra = rows()
    extra["c999"] = dict(extra["c1"], chunk_id="c999")
    assert node_module._rows_fingerprint(extra) != base
    assert node_module._rows_fingerprint({k: v for k, v in rows().items() if k != "c3"}) != base


def test_a_replaced_text_object_with_equal_content_hashes_to_the_same_value():
    data = rows()
    base = node_module._rows_fingerprint(data)
    data["c5"]["content_text"] = "".join(["nội dung ", "5"])      # a new str object, same content
    assert node_module._rows_fingerprint(data) == base


# ---- model identity check -----------------------------------------------------------------------------------------

def adapter_with(handler):
    profile = EmbeddingProfile("m", "rev", 4, batch_limit=1, timeout_ms=2000)
    factory = lambda: httpx.AsyncClient(base_url="http://x", transport=httpx.MockTransport(handler))  # noqa: E731
    return tei.TEIEmbeddingAdapter(profile, factory)


@pytest.mark.asyncio
async def test_identity_is_checked_once_then_every_ttl_and_after_a_failure(monkeypatch):
    paths = []
    state = {"fail": False}

    def handler(request):
        paths.append((request.method, request.url.path))
        if request.url.path == "/info":
            return httpx.Response(200, json={"model_id": "m", "model_sha": "rev", "model_type": {"embedding": {}},
                                             "auto_truncate": False})
        if state["fail"]:
            return httpx.Response(503, json={"error": "x"})
        return httpx.Response(200, json=[[0.5, 0.5, 0.5, 0.5]])

    adapter = adapter_with(handler)
    for _ in range(3):
        await adapter._embed(("q",))
    assert paths.count(("GET", "/info")) == 1 and paths.count(("POST", "/embed")) == 3
    state["fail"] = True
    with pytest.raises(Exception):
        await adapter._embed(("q",))
    state["fail"] = False
    await adapter._embed(("q",))
    assert paths.count(("GET", "/info")) == 2          # re-verified after the failure
    monkeypatch.setattr(tei, "IDENTITY_TTL_S", 0.0)
    adapter._identity_valid_until = 0.0
    await adapter._embed(("q",))
    await adapter._embed(("q",))
    assert paths.count(("GET", "/info")) == 4          # with a zero TTL every call checks again


@pytest.mark.asyncio
async def test_a_wrong_model_is_still_refused():
    def handler(request):
        if request.url.path == "/info":
            return httpx.Response(200, json={"model_id": "other", "model_sha": "rev", "model_type": {"embedding": {}},
                                             "auto_truncate": False})
        return httpx.Response(200, json=[[0.5, 0.5, 0.5, 0.5]])

    with pytest.raises(Exception):
        await adapter_with(handler)._embed(("q",))
