"""Real asynchronous stream boundary, without provider/native calls."""
import asyncio

import httpx
import pytest

from campus247.infrastructure.streaming_asgi import StreamingASGITransport


@pytest.mark.asyncio
async def test_first_progress_arrives_while_application_is_still_running():
    release, exited = asyncio.Event(), asyncio.Event()
    async def app(scope, receive, send):
        assert scope["headers"] and scope["path"] == "/v1/conversations/test/messages:stream"
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/event-stream")]})
        try:
            await send({"type": "http.response.body", "body": b"event: agent.status\n\n", "more_body": True})
            await release.wait()
            await send({"type": "http.response.body", "body": b"event: message.completed\n\n", "more_body": False})
        finally:
            exited.set()
    async with httpx.AsyncClient(transport=StreamingASGITransport(app), base_url="http://loopback") as client:
        async with asyncio.timeout(1):
            async with client.stream("POST", "/v1/conversations/test/messages:stream", json={"content": "test"}) as response:
                iterator = response.aiter_bytes()
                assert await iterator.__anext__() == b"event: agent.status\n\n"
                assert not exited.is_set()
                release.set()
                assert await iterator.__anext__() == b"event: message.completed\n\n"
                with pytest.raises(StopAsyncIteration):
                    await iterator.__anext__()
        assert exited.is_set()


@pytest.mark.asyncio
async def test_disconnect_cancels_and_joins_app_without_orphan():
    exited = asyncio.Event()
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200})
        try:
            await send({"type": "http.response.body", "body": b"progress", "more_body": True})
            await asyncio.Event().wait()
        finally:
            exited.set()
    async with httpx.AsyncClient(transport=StreamingASGITransport(app), base_url="http://loopback") as client:
        async with client.stream("POST", "/v1/conversations/test/messages:stream") as response:
            assert await response.aiter_bytes().__anext__() == b"progress"
        assert exited.is_set()
