import asyncio
from pathlib import Path
import sys

import httpx
import pytest
from starlette.requests import Request

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import knowledge_frontend_proxy as proxy


def request(headers=()):
    return Request({"type": "http", "method": "GET", "path": "/services", "query_string": b"_rsc=fixture",
        "headers": list(headers), "scheme": "http", "server": ("127.0.0.1", 8015)})


def upstream(monkeypatch, handler):
    client = httpx.AsyncClient
    monkeypatch.setattr(proxy.httpx, "AsyncClient", lambda **kwargs: client(transport=httpx.MockTransport(handler), **kwargs))


def test_navigation_protocol_and_response_metadata_survive_without_forwarding_credentials(monkeypatch):
    def handler(incoming):
        assert str(incoming.url) == "http://127.0.0.1:3015/services?_rsc=fixture"
        assert incoming.headers["rsc"] == "1"
        assert incoming.headers["next-router-state-tree"] == "%5B%22%22%5D"
        assert incoming.headers["next-url"] == "/chat"
        assert "authorization" not in incoming.headers and "cookie" not in incoming.headers
        assert "x-forwarded-host" not in incoming.headers
        return httpx.Response(200, content=b'0:["fixture"]\n', headers={
            "Content-Type": "text/x-component", "Vary": "RSC, Next-Router-State-Tree", "Cache-Control": "no-store",
            "x-nextjs-stale-time": "300", "Set-Cookie": "unrelated=blocked", "X-Private": "blocked"})
    upstream(monkeypatch, handler)
    response = asyncio.run(proxy.proxy_frontend("services", request([
        (b"rsc", b"1"), (b"next-router-state-tree", b"%5B%22%22%5D"), (b"next-url", b"/chat"),
        (b"cookie", b"synthetic-private"), (b"authorization", b"synthetic-private"),
        (b"x-forwarded-host", b"unrelated.invalid")]), 3015))
    assert response.body == b'0:["fixture"]\n'
    assert response.headers["content-type"].startswith("text/x-component")
    assert response.headers["vary"] == "RSC, Next-Router-State-Tree"
    assert response.headers["x-nextjs-stale-time"] == "300"
    assert "set-cookie" not in response.headers and "x-private" not in response.headers


@pytest.mark.parametrize("status,content,headers", [
    (307, b"", {"Location": "/chat", "Cache-Control": "no-store"}),
    (200, b"\x89PNG\x00\xff", {"Content-Type": "image/png"}),
])
def test_redirects_and_binary_assets_remain_intact(monkeypatch, status, content, headers):
    upstream(monkeypatch, lambda incoming: httpx.Response(status, content=content, headers=headers))
    response = asyncio.run(proxy.proxy_frontend("services", request(), 3015))
    assert response.status_code == status and response.body == content
    for key, value in headers.items():
        assert response.headers[key].startswith(value)


def test_existing_response_size_limit_is_preserved(monkeypatch):
    upstream(monkeypatch, lambda incoming: httpx.Response(200, content=b"x" * (10 * 1024**2 + 1)))
    with pytest.raises(proxy.HTTPException) as error:
        asyncio.run(proxy.proxy_frontend("services", request(), 3015))
    assert error.value.status_code == 502
