"""Exact legacy proxy transport/auth behavior in the unified composition."""
import httpx
from fastapi.testclient import TestClient

from campus247.bootstrap.unified_demo import create_unified_demo_app

ID = "019a0000-0000-7000-8000-000000000001"


def login(c, account="SV001"):
    r = c.post("/v1/auth/demo-login",json={"account":account})
    assert r.status_code == 200
    return {"Authorization":"Bearer "+r.json()["token"]}


def test_stream_bytes_and_current_actor_are_forwarded_without_new_writer(tmp_path):
    frames = b'event: message.delta\ndata: {"delta":"synthetic"}\n\nevent: message.completed\ndata: {"finish_status":"answered","phase":"completed"}\n\n'
    observed = []
    def upstream(request):
        observed.append({"port":request.url.port,"host":request.url.host,"path":request.url.path,
                         "method":request.method,"has_signed_auth":request.headers.get("authorization","").startswith("Bearer "),
                         "body":request.content})
        return httpx.Response(200,content=frames,headers={"Content-Type":"text/event-stream; charset=utf-8"})
    app = create_unified_demo_app(tmp_path / "proxy.sqlite3",rag_transport=httpx.MockTransport(upstream))
    with TestClient(app) as c:
        response = c.post(f"/v1/conversations/{ID}/messages:stream",headers=login(c),json={"content":"Synthetic question"})
        assert response.status_code == 200 and response.content == frames
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["cache-control"] == "no-store"
    assert observed[0]["port"] == 8003 and observed[0]["host"] == "127.0.0.1"
    assert observed[0]["has_signed_auth"] and observed[0]["path"].endswith("/messages:stream")
    assert app.state.owns_paid_ledger is False


def test_staff_cannot_expand_chat_authority_through_unified_proxy(tmp_path):
    calls=[]
    def upstream(request):
        calls.append(request.url.path)
        return httpx.Response(200,json={})
    with TestClient(create_unified_demo_app(tmp_path / "staff.sqlite3",rag_transport=httpx.MockTransport(upstream))) as c:
        response = c.post("/v1/conversations",headers=login(c,"OF002"),json={})
        assert response.status_code == 403
    assert calls == []


def test_history_cursor_and_upstream_failure_are_not_rewritten(tmp_path):
    calls=[]
    def upstream(request):
        calls.append(str(request.url.query))
        if request.method == "GET":
            return httpx.Response(200,json={"messages":[],"page":{"next_cursor":None,"has_more":False}})
        return httpx.Response(503,json={"code":"UPSTREAM_UNAVAILABLE","detail":"synthetic upstream failure"})
    with TestClient(create_unified_demo_app(tmp_path / "read.sqlite3",rag_transport=httpx.MockTransport(upstream))) as c:
        h = login(c)
        response = c.get(f"/v1/conversations/{ID}/messages?cursor=known-cursor&limit=25",headers=h)
        assert response.status_code == 200 and response.json()["page"]["has_more"] is False
        response = c.post("/v1/conversations",headers=h,json={})
        assert response.status_code == 503 and response.json()["code"] == "UPSTREAM_UNAVAILABLE"
    assert "cursor=known-cursor&limit=25" in calls[0]


def test_oversized_turn_is_rejected_before_proxy_dispatch(tmp_path):
    calls=[]
    def upstream(request):
        calls.append(request.url.path)
        return httpx.Response(200,json={})
    with TestClient(create_unified_demo_app(tmp_path / "bound.sqlite3",rag_transport=httpx.MockTransport(upstream))) as c:
        response = c.post(f"/v1/conversations/{ID}/messages:stream",headers=login(c),content="x"*20001)
        assert response.status_code == 413
    assert calls == []
