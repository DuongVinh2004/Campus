"""Keep the old public URL and certificate proxy on the sole integrated writer."""
import sys
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from starlette.responses import StreamingResponse

ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/health/live")
def health():
    return {"status": "ok", "mode": "integrated_loopback_proxy", "owns_paid_ledger": False}


@app.api_route("/{resource:path}", methods=["GET", "POST"])
async def forward(resource: str, request: Request):
    path = "/"+resource
    if ".." in path or "\\" in path or len(path) > 500 or len(request.url.query) > 1024:
        raise HTTPException(404)
    if not (path.startswith(("/v1/", "/_next/static/", "/images/")) or path in
            {"/", "/login", "/chat", "/tickets", "/staff", "/privacy"}):
        raise HTTPException(404)
    body = await request.body()
    if len(body) > 20000:
        raise HTTPException(413)
    headers = {name: request.headers[name] for name in ("authorization", "cookie", "content-type", "last-event-id") if name in request.headers}
    client = httpx.AsyncClient(base_url="http://127.0.0.1:8003", timeout=45,
                              trust_env=False, follow_redirects=False)
    try:
        upstream = await client.send(client.build_request(request.method, path,
            params=request.query_params, content=body, headers=headers), stream=True)
    except httpx.HTTPError:
        await client.aclose()
        raise HTTPException(503, "Integrated runtime unavailable") from None
    async def stream():
        try:
            async for part in upstream.aiter_bytes():
                yield part
        finally:
            await upstream.aclose()
            await client.aclose()
    response = StreamingResponse(stream(), status_code=upstream.status_code,
        headers={name: upstream.headers[name] for name in ("content-type", "cache-control") if name in upstream.headers})
    for cookie in upstream.headers.get_list("set-cookie"):
        response.raw_headers.append((b"set-cookie", cookie.encode("latin-1")))
    return response


if __name__ == "__main__":
    import uvicorn
    sys.stdout.reconfigure(encoding="utf-8")
    uvicorn.run(app, host="127.0.0.1", port=8000, access_log=False, log_level="warning")
