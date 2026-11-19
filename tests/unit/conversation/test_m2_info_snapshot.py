"""Local fixture metadata snapshots never replace actual inference calls."""
import importlib.util
from pathlib import Path

import httpx
import pytest
from campus247.infrastructure.retrieval.tei import _identity, _json

PATH = Path(__file__).resolve().parents[3] / "infra/local/rag-fixture/m2_info_cache_20261012_71.py"
SPEC = importlib.util.spec_from_file_location("m2_info_snapshot_test", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.mark.asyncio
async def test_only_first_identity_GET_cached_across_client_lifetimes():
    requests, receipts, snapshots = [], [], {}
    info = {"model_id": "owned", "model_sha": "frozen", "model_type": {"embedding": {}}, "auto_truncate": False}

    def handle(request):
        requests.append((request.method, request.url.path))
        return httpx.Response(200, json=info if request.url.path == "/info" else [[0.1]])

    for _ in range(3):
        async with MODULE.InfoSnapshotClient(snapshots=snapshots, receipt=lambda name, value: receipts.append(value),
            base_url="http://127.0.0.1:18081", transport=httpx.MockTransport(handle)) as client:
            actual_info = await _json(client, "GET", "/info", 1)
            _identity(actual_info, "owned", "frozen", "embedding")
            assert await _json(client, "POST", "/embed", 1, {"inputs": ["question"]}) == [[0.1]]
    assert requests == [("GET", "/info"), ("POST", "/embed"), ("POST", "/embed"), ("POST", "/embed")]
    assert [r["actual_HTTP"] for r in receipts] == [True, False, False]
    with pytest.raises(ValueError):
        _identity(actual_info, "another-model", "frozen", "embedding")


@pytest.mark.asyncio
async def test_unsuccessful_info_is_not_cached():
    snapshots = {}
    async with MODULE.InfoSnapshotClient(snapshots=snapshots, receipt=lambda *args: None,
        base_url="http://127.0.0.1:18082", transport=httpx.MockTransport(lambda request: httpx.Response(503))) as client:
        with pytest.raises(ValueError):
            await _json(client, "GET", "/info", 1)
    assert snapshots == {}
