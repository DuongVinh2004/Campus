"""Bounded public HTTPS intake with DNS pinned at the socket boundary.

This fetcher retrieves one administrator-provided document; it does not crawl,
send credentials, adopt cookies, follow attachments, or establish source authority.
"""
from __future__ import annotations

import asyncio
import ipaddress
import socket
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urljoin, urlsplit

import httpcore
import httpx

from campus247.application.knowledge.platform_models import MAX_UPLOAD, PlatformError, digest
from campus247.infrastructure.knowledge.storage import StoredArtifact


from campus247.application.knowledge.values import public_document_url  # noqa: E402,F401 -- re-exported


async def public_addresses(host: str) -> tuple[str, ...]:
    rows = await asyncio.get_running_loop().getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    addresses = tuple(sorted({row[4][0] for row in rows}))
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise PlatformError(422, "URL_ADDRESS_DENIED", "Địa chỉ nguồn không thuộc mạng công khai được phép.")
    return addresses


class PublicPinnedBackend(httpcore.AsyncNetworkBackend):
    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        public_document_url("https://" + host + "/")
        if port != 443 or local_address is not None:
            raise PlatformError(422, "URL_ADDRESS_DENIED", "Cổng nguồn không được phép.")
        addresses = await public_addresses(host)
        # The connection uses this validated IP. TLS still receives the original
        # origin hostname from httpcore, so certificate/SNI validation remains on.
        return await httpcore.AnyIOBackend().connect_tcp(addresses[0], port, timeout=timeout, socket_options=socket_options)


class ResponseUpload:
    def __init__(self, stream):
        self.stream, self.pending, self.ended = stream.__aiter__(), bytearray(), False

    async def read(self, size):
        while len(self.pending) < size and not self.ended:
            try:
                block = await self.stream.__anext__()
                self.pending.extend(block)
                if len(self.pending) > MAX_UPLOAD + 65536:
                    raise PlatformError(413, "UPLOAD_TOO_LARGE", "Nguồn URL vượt 50 MB.")
            except StopAsyncIteration:
                self.ended = True
        result = bytes(self.pending[:size])
        del self.pending[:size]
        return result


class PublicDocumentFetcher:
    async def fetch(self, url, storage, *, previous_artifact=None, previous_acquisition=None):
        try:
            return await self._fetch(url, storage, previous_artifact=previous_artifact, previous_acquisition=previous_acquisition)
        except httpcore.ConnectError as error:
            if "CERTIFICATE_VERIFY_FAILED" in str(error):
                raise PlatformError(422, "SOURCE_TLS_UNVERIFIED", "Không xác minh được chuỗi chứng chỉ TLS của nguồn; giữ kiểm chứng chỉ và đối chiếu nguồn khác.") from None
            raise PlatformError(503, "SOURCE_FETCH_UNAVAILABLE", "Chưa kết nối được nguồn; chưa có căn cứ thay đổi hiệu lực hoặc thu hồi.") from None
        except (httpcore.NetworkError, httpcore.TimeoutException, TimeoutError):
            raise PlatformError(503, "SOURCE_FETCH_UNAVAILABLE", "Nguồn tạm chưa truy cập được; giữ tài liệu và lịch sử đang có.") from None

    async def _fetch(self, url, storage, *, previous_artifact=None, previous_acquisition=None):
        current = public_document_url(url)
        conditional = {}
        if previous_artifact is not None or previous_acquisition is not None:
            if (previous_artifact is None or not isinstance(previous_acquisition, dict)
                or previous_acquisition.get("requested_url") != url
                or previous_acquisition.get("fetch_policy") != "public-huce-https-pinned-dns-v1"):
                raise PlatformError(409, "SOURCE_FETCH_BINDING", "Cần checkpoint nguồn và acquisition đúng URL trước khi tải có điều kiện.")
            public_document_url(previous_acquisition["final_url"])
            storage.read(previous_artifact)
            for field, header in (("etag", "If-None-Match"), ("last_modified", "If-Modified-Since")):
                value = previous_acquisition.get(field)
                if value is not None:
                    if not isinstance(value, str) or not 0 < len(value) <= 1024 or any(ord(c) < 32 or ord(c) > 126 for c in value):
                        raise PlatformError(409, "SOURCE_FETCH_BINDING", "Validator HTTP không hợp lệ; giữ checkpoint để đối chiếu.")
                    conditional[header] = value
        hops = []
        timeout = {k: 18.0 for k in ("connect", "read", "write", "pool")}
        async with asyncio.timeout(90):
            # Match the application's existing HTTPX trust store and strict TLS
            # policy. No environment proxy/CA override or certificate bypass.
            async with httpcore.AsyncConnectionPool(ssl_context=httpx.create_ssl_context(verify=True, trust_env=False),
                max_connections=1, max_keepalive_connections=0, retries=0, network_backend=PublicPinnedBackend()) as pool:
                for _ in range(5):
                    public_document_url(current)
                    # Validators belong to the exact final resource, never an
                    # origin or a different redirect destination.
                    validators = conditional if previous_acquisition and current == previous_acquisition["final_url"] else {}
                    async with pool.stream("GET", current, headers={"User-Agent": "Campus247-PublicDocumentIntake/1.0", "Accept-Encoding": "identity", **validators},
                                           extensions={"timeout": timeout}) as response:
                        headers = {key.decode("ascii").lower(): value.decode("latin-1") for key, value in response.headers}
                        hops.append({"url": current, "http_status": response.status})
                        if response.status in {301, 302, 303, 307, 308}:
                            current = public_document_url(urljoin(current, headers.get("location", "")))
                            continue
                        if response.status in {401, 403}:
                            raise PlatformError(422, "URL_CREDENTIALS_REQUIRED", "Nguồn yêu cầu quyền truy cập; hệ thống không dùng thông tin đăng nhập để tải.")
                        if response.status == 304:
                            if not validators or previous_artifact is None:
                                raise PlatformError(409, "SOURCE_304_WITHOUT_BINDING", "Phản hồi không đổi chưa có binding của đúng nguồn.")
                            storage.read(previous_artifact)  # Recheck after the network wait.
                            artifact = StoredArtifact(**{name: str(previous_artifact[name]) if name == "id" else previous_artifact[name]
                                for name in StoredArtifact.__dataclass_fields__})
                            return artifact, {**previous_acquisition, "hops": hops, "observed_at": datetime.now(UTC).isoformat(),
                                "not_modified": True, "reused_original_sha256": artifact.sha256,
                                "previous_acquisition_sha256": digest(previous_acquisition), "source_verified": False,
                                "issued_at": None, "valid_from": None}
                        if response.status != 200:
                            raise PlatformError(503, "SOURCE_FETCH_UNAVAILABLE", "Chưa tải được nguồn; lỗi truy cập không phải căn cứ thu hồi tài liệu.")
                        if headers.get("content-encoding", "identity").lower() != "identity":
                            raise PlatformError(422, "URL_ENCODING_REQUIRES_REVIEW", "Nguồn trả dạng nén cần adapter kiểm chứng riêng.")
                        try:
                            if int(headers.get("content-length", "0")) > MAX_UPLOAD:
                                raise PlatformError(413, "UPLOAD_TOO_LARGE", "Nguồn URL vượt 50 MB.")
                        except ValueError:
                            raise PlatformError(422, "URL_RESPONSE_INVALID", "Kích thước phản hồi không hợp lệ.") from None
                        media = headers.get("content-type", "application/octet-stream").split(";", 1)[0].strip().lower()
                        artifact = await storage.receive(ResponseUpload(response.aiter_stream()), media)
                        return artifact, {"requested_url": url, "final_url": current, "hops": hops,
                            "not_modified": False,
                            "observed_at": datetime.now(UTC).isoformat(), "etag": headers.get("etag"),
                            "last_modified": headers.get("last-modified"), "media_type": media,
                            "source_verified": False, "issued_at": None, "valid_from": None,
                            "fetch_policy": "public-huce-https-pinned-dns-v1"}
        raise PlatformError(422, "URL_REDIRECT_LIMIT", "Nguồn chuyển hướng quá giới hạn; cần đối chiếu URL.")
