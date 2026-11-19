"""One bounded public HTTPS GET for the crawler, with the same network guards as the document fetcher.

Reuses the pinned-DNS backend and the HUCE-only URL rule: the connection goes to a validated public address, TLS keeps
certificate and hostname checks, no credentials, no cookies, no environment proxy, at most five validated redirects.
The body is returned in memory (it is not stored); the crawler stores what it decides to ingest.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from urllib.parse import urljoin

import httpcore
import httpx

from campus247.application.knowledge.crawl.rules import USER_AGENT
from campus247.application.knowledge.platform_models import PlatformError
from campus247.application.knowledge.values import public_document_url
from campus247.infrastructure.knowledge.fetch import PublicPinnedBackend

MAX_PAGE_BYTES = 5 * 1024 * 1024


@dataclass
class FetchedResource:
    status: int
    final_url: str
    media: str = ""
    body: bytes = b""
    headers: dict = field(default_factory=dict)


class PublicPageFetcher:
    async def get(self, url: str, *, max_bytes: int = MAX_PAGE_BYTES, validators: dict | None = None, accept: str = "*/*") -> FetchedResource:
        try:
            return await self._get(url, max_bytes, validators or {}, accept)
        except httpcore.ConnectError as error:
            if "CERTIFICATE_VERIFY_FAILED" in str(error):
                raise PlatformError(422, "SOURCE_TLS_UNVERIFIED", "Không xác minh được chứng chỉ TLS của nguồn.") from None
            raise PlatformError(503, "SOURCE_FETCH_UNAVAILABLE", "Chưa kết nối được nguồn.") from None
        except (httpcore.NetworkError, httpcore.TimeoutException, TimeoutError):
            raise PlatformError(503, "SOURCE_FETCH_UNAVAILABLE", "Nguồn tạm chưa truy cập được.") from None

    async def _get(self, url, max_bytes, validators, accept):
        current = public_document_url(url)
        timeout = {k: 18.0 for k in ("connect", "read", "write", "pool")}
        async with asyncio.timeout(90):
            async with httpcore.AsyncConnectionPool(ssl_context=httpx.create_ssl_context(verify=True, trust_env=False), max_connections=1,
                                                    max_keepalive_connections=0, retries=0, network_backend=PublicPinnedBackend()) as pool:
                for _ in range(6):
                    public_document_url(current)
                    headers = {"User-Agent": USER_AGENT, "Accept": accept, "Accept-Encoding": "identity", **validators}
                    async with pool.stream("GET", current, headers=headers, extensions={"timeout": timeout}) as response:
                        received = {key.decode("ascii").lower(): value.decode("latin-1") for key, value in response.headers}
                        if response.status in {301, 302, 303, 307, 308}:
                            current = public_document_url(urljoin(current, received.get("location", "")))
                            continue
                        if response.status != 200:
                            return FetchedResource(response.status, current, headers=received)
                        if received.get("content-encoding", "identity").lower() != "identity":
                            raise PlatformError(422, "URL_ENCODING_REQUIRES_REVIEW", "Nguồn trả dạng nén chưa được hỗ trợ.")
                        try:
                            if int(received.get("content-length", "0")) > max_bytes:
                                raise PlatformError(413, "RESOURCE_TOO_LARGE", "Tài nguyên vượt giới hạn kích thước.")
                        except ValueError:
                            raise PlatformError(422, "URL_RESPONSE_INVALID", "Kích thước phản hồi không hợp lệ.") from None
                        body = bytearray()
                        async for chunk in response.aiter_stream():
                            body.extend(chunk)
                            if len(body) > max_bytes:
                                raise PlatformError(413, "RESOURCE_TOO_LARGE", "Tài nguyên vượt giới hạn kích thước.")
                        media = received.get("content-type", "application/octet-stream").split(";", 1)[0].strip().lower()
                        return FetchedResource(200, current, media, bytes(body), received)
        raise PlatformError(422, "URL_REDIRECT_LIMIT", "Nguồn chuyển hướng quá giới hạn.")
