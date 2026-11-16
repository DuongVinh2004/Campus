"""Preserve Next's navigation protocol through the loopback entry point."""
import httpx
from fastapi import HTTPException, Request, Response

REQUEST_HEADERS = frozenset({
    "rsc", "next-router-state-tree", "next-router-prefetch", "next-router-segment-prefetch", "next-url",
})
RESPONSE_HEADERS = frozenset({
    "content-type", "vary", "cache-control", "location", "x-nextjs-stale-time",
    "x-nextjs-prerender", "x-nextjs-postponed", "x-nextjs-rewritten-path", "x-nextjs-rewritten-query",
})


async def proxy_frontend(page_path: str, request: Request, frontend_port: int) -> Response:
    # Route/path authorization remains with the caller. Never forward auth,
    # cookies, host overrides or arbitrary upstream response headers to Next.
    headers = {key: value for key, value in request.headers.items() if key in REQUEST_HEADERS}
    async with httpx.AsyncClient(trust_env=False, timeout=15) as client:
        response = await client.get(f"http://127.0.0.1:{frontend_port}/" + page_path,
            params=request.query_params, headers=headers)
    if len(response.content) > 10 * 1024**2:
        raise HTTPException(502)
    return Response(response.content, status_code=response.status_code,
        headers={key: value for key, value in response.headers.items() if key in RESPONSE_HEADERS})
