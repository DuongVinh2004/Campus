"""Internal ASGI transport with streaming backpressure and joined cancellation."""
import asyncio
from contextlib import suppress

import httpx


class StreamingASGITransport(httpx.AsyncBaseTransport):
    def __init__(self, app):
        self.app = app

    async def handle_async_request(self, request):
        scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": request.method, "headers": [(key.lower(), value) for key, value in request.headers.raw],
            "scheme": request.url.scheme, "path": request.url.path,
            "raw_path": request.url.raw_path.split(b"?")[0], "query_string": request.url.query,
            "server": (request.url.host, request.url.port), "client": ("127.0.0.1", 123), "root_path": ""}
        chunks = request.stream.__aiter__()
        complete, closed, started = asyncio.Event(), asyncio.Event(), asyncio.Event()
        queue = asyncio.Queue(maxsize=1)
        status, headers, error = None, [], None
        request_complete = False

        async def receive():
            nonlocal request_complete
            if request_complete:
                await closed.wait()
                return {"type": "http.disconnect"}
            try:
                return {"type": "http.request", "body": await chunks.__anext__(), "more_body": True}
            except StopAsyncIteration:
                request_complete = True
                return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            nonlocal status, headers
            if message["type"] == "http.response.start":
                status, headers = message["status"], message.get("headers", [])
                started.set()
            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                if body and request.method != "HEAD":
                    await queue.put(body)
                if not message.get("more_body", False):
                    complete.set()
                    await queue.put(None)

        async def invoke():
            nonlocal error
            try:
                await self.app(scope, receive, send)
            except asyncio.CancelledError:
                raise
            except Exception as failure:
                error = failure
                started.set()
                await queue.put(failure)

        job = asyncio.create_task(invoke())

        class ResponseStream(httpx.AsyncByteStream):
            async def __aiter__(self):
                try:
                    while True:
                        item = await queue.get()
                        if item is None:
                            return
                        if isinstance(item, BaseException):
                            raise item
                        yield item
                finally:
                    await self.aclose()

            async def aclose(self):
                closed.set()
                if not complete.is_set() and not job.done():
                    job.cancel()
                with suppress(asyncio.CancelledError):
                    try:
                        await asyncio.wait_for(job, 1)
                    except TimeoutError:
                        job.cancel()
                        with suppress(asyncio.CancelledError):
                            await job

        stream = ResponseStream()
        try:
            await asyncio.wait_for(started.wait(), 40)
            if status is None:
                raise error or RuntimeError("ASGI response unavailable")
            return httpx.Response(status, headers=headers, stream=stream)
        except BaseException:
            await stream.aclose()
            raise
