import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from campus247.application.knowledge.platform_models import PlatformError, MAX_UPLOAD
from campus247.infrastructure.knowledge import fetch
from campus247.infrastructure.knowledge.storage import FileKnowledgeStorage
from .conftest import ROOT


@pytest.mark.parametrize("url", ["http://huce.edu.vn/a.pdf", "https://huce.edu.vn.evil.test/a.pdf", "https://127.0.0.1/a.pdf",
    "https://huce.edu.vn:444/a.pdf", "https://user:secret@huce.edu.vn/a.pdf", "https://huce.edu.vn/a.pdf?access_token=hidden",
    "https://other.test/a.pdf", "https://huce.edu.vn/a.pdf#fragment", "https://huce.edu.vn/\\evil"])
def test_url_policy_denies_untrusted_or_credentialed_sources(url):
    with pytest.raises(PlatformError, match="URL_SOURCE_REVIEW_REQUIRED"):
        fetch.public_document_url(url)


def test_dns_is_validated_and_actual_connection_uses_the_validated_ip(monkeypatch):
    async def run():
        connections = []
        async def addresses(host):
            assert host == "huce.edu.vn"
            return ("8.8.8.8",)
        class Network:
            async def connect_tcp(self, host, port, **kwargs):
                connections.append((host, port)); return "stream"
        monkeypatch.setattr(fetch, "public_addresses", addresses)
        monkeypatch.setattr(fetch.httpcore, "AnyIOBackend", Network)
        assert await fetch.PublicPinnedBackend().connect_tcp("huce.edu.vn", 443) == "stream"
        assert connections == [("8.8.8.8", 443)]
    asyncio.run(run())


@pytest.mark.parametrize("addresses", [("127.0.0.1",), ("8.8.8.8", "10.0.0.1"), ("::1",), ("169.254.169.254",), ()])
def test_dns_private_or_mixed_answers_fail_closed(monkeypatch, addresses):
    async def run():
        async def resolve(*args, **kwargs):
            return [(None, None, None, None, (address, 443)) for address in addresses]
        monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolve)
        with pytest.raises(PlatformError, match="URL_ADDRESS_DENIED"):
            await fetch.public_addresses("huce.edu.vn")
    asyncio.run(run())


def fake_pool(monkeypatch, responses):
    calls = []
    class Response:
        def __init__(self, status, headers, raw):
            self.status, self.headers, self.raw = status, [(k.encode(), v.encode()) for k, v in headers.items()], raw
        async def aiter_stream(self):
            yield self.raw
    class Pool:
        def __init__(self, **kwargs):
            assert kwargs["ssl_context"].check_hostname
            assert kwargs["ssl_context"].verify_mode == 2
            assert isinstance(kwargs["network_backend"], fetch.PublicPinnedBackend)
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        @asynccontextmanager
        async def stream(self, method, url, **kwargs):
            calls.append((method, url, kwargs["headers"]))
            yield Response(*responses.pop(0))
    monkeypatch.setattr(fetch.httpcore, "AsyncConnectionPool", Pool)
    return calls


def test_streamed_fetch_retains_hash_and_observation_without_effective_date(monkeypatch, retained_directory):
    calls = fake_pool(monkeypatch, [(200, {"content-type": "text/plain", "last-modified": "Mon, 26 Oct 2026 01:00:00 GMT"}, b"A new independent document fetched from a public URL.")])
    storage = FileKnowledgeStorage(ROOT, retained_directory / "artifacts")
    artifact, receipt = asyncio.run(fetch.PublicDocumentFetcher().fetch("https://huce.edu.vn/new.txt", storage))
    assert storage.read(artifact.__dict__).startswith(b"A new independent")
    assert receipt["issued_at"] is None and receipt["valid_from"] is None
    assert receipt["source_verified"] is False and receipt["last_modified"]
    assert set(calls[0][2]) == {"User-Agent", "Accept-Encoding"}


def test_redirect_is_revalidated_before_any_second_request(monkeypatch, retained_directory):
    calls = fake_pool(monkeypatch, [(302, {"location": "https://127.0.0.1/secret"}, b"")])
    with pytest.raises(PlatformError, match="URL_SOURCE_REVIEW_REQUIRED"):
        asyncio.run(fetch.PublicDocumentFetcher().fetch("https://huce.edu.vn/a", FileKnowledgeStorage(ROOT, retained_directory / "artifacts")))
    assert len(calls) == 1


@pytest.mark.parametrize("status,headers,raw,reason", [
    (403, {}, b"", "URL_CREDENTIALS_REQUIRED"),
    (503, {}, b"", "SOURCE_FETCH_UNAVAILABLE"),
    (200, {"content-length": str(MAX_UPLOAD+1)}, b"", "UPLOAD_TOO_LARGE"),
    (200, {"content-encoding": "gzip"}, b"", "URL_ENCODING_REQUIRES_REVIEW"),
])
def test_fetch_errors_do_not_create_withdrawal_or_publish(monkeypatch, retained_directory, status, headers, raw, reason):
    fake_pool(monkeypatch, [(status, headers, raw)])
    with pytest.raises(PlatformError, match=reason):
        asyncio.run(fetch.PublicDocumentFetcher().fetch("https://huce.edu.vn/a", FileKnowledgeStorage(ROOT, retained_directory / "artifacts")))


def test_conditional_304_reuses_only_the_exact_hash_bound_resource(monkeypatch, retained_directory):
    async def run():
        storage = FileKnowledgeStorage(ROOT, retained_directory / "artifacts")
        calls = fake_pool(monkeypatch, [(200, {"content-type": "text/plain", "etag": '"v1"'}, b"Retained original URL document without effective-date assertions.")])
        artifact, acquisition = await fetch.PublicDocumentFetcher().fetch("https://huce.edu.vn/a", storage)
        before = list(storage.root.iterdir())
        calls = fake_pool(monkeypatch, [(304, {}, b"")])
        reused, receipt = await fetch.PublicDocumentFetcher().fetch("https://huce.edu.vn/a", storage,
            previous_artifact=artifact.__dict__, previous_acquisition=acquisition)
        assert calls[0][2]["If-None-Match"] == '"v1"' and reused == artifact
        assert receipt["not_modified"] and not receipt["source_verified"]
        assert receipt["issued_at"] is None and receipt["valid_from"] is None
        assert list(storage.root.iterdir()) == before
        with pytest.raises(PlatformError, match="SOURCE_FETCH_BINDING"):
            await fetch.PublicDocumentFetcher().fetch("https://huce.edu.vn/different", storage,
                previous_artifact=artifact.__dict__, previous_acquisition=acquisition)
    asyncio.run(run())


def test_redirect_does_not_forward_other_resources_validators(monkeypatch, retained_directory):
    async def run():
        storage = FileKnowledgeStorage(ROOT, retained_directory / "artifacts")
        fake_pool(monkeypatch, [(200, {"content-type": "text/plain", "etag": '"v1"'}, b"Old original source; the final resource can later redirect.")])
        artifact, acquisition = await fetch.PublicDocumentFetcher().fetch("https://huce.edu.vn/a", storage)
        calls = fake_pool(monkeypatch, [(302, {"location": "https://fit.huce.edu.vn/b"}, b""),
            (200, {"content-type": "text/plain", "etag": '"v2"'}, b"New original from a different resource, retained separately.")])
        new, receipt = await fetch.PublicDocumentFetcher().fetch("https://huce.edu.vn/a", storage,
            previous_artifact=artifact.__dict__, previous_acquisition=acquisition)
        assert calls[0][2]["If-None-Match"] == '"v1"' and "If-None-Match" not in calls[1][2]
        assert new.id != artifact.id and not receipt["not_modified"]
        assert storage.read(artifact.__dict__).startswith(b"Old original")
    asyncio.run(run())


def test_unsolicited_304_and_injected_validator_are_rejected(monkeypatch, retained_directory):
    async def run():
        storage = FileKnowledgeStorage(ROOT, retained_directory / "artifacts")
        fake_pool(monkeypatch, [(304, {}, b"")])
        with pytest.raises(PlatformError, match="SOURCE_304_WITHOUT_BINDING"):
            await fetch.PublicDocumentFetcher().fetch("https://huce.edu.vn/a", storage)
        artifact = storage.write_bytes(b"Preserved original source.", "original", "text/plain")
        acquisition = {"requested_url": "https://huce.edu.vn/a", "final_url": "https://huce.edu.vn/a",
            "fetch_policy": "public-huce-https-pinned-dns-v1", "etag": '"v1"\r\nAuthorization: injected'}
        with pytest.raises(PlatformError, match="SOURCE_FETCH_BINDING"):
            await fetch.PublicDocumentFetcher().fetch("https://huce.edu.vn/a", storage, previous_artifact=artifact.__dict__, previous_acquisition=acquisition)
    asyncio.run(run())
