"""Explicit managed candidate boundary; never promotes a production profile.

provider-version:N binds the public Models metadata for this session. It is NOT
an immutable weight/artifact revision. A composition root must authorize egress
and minimize inputs before supplying the client factory. No .env/default key/URL
discovery, logging, retries, fallback, truncation or background threads here.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
import json

import httpx

from campus247.ports.embedding import (
    EmbeddingBatch, EmbeddingContractError, EmbeddingProfile, EmbeddingTimeoutError,
    EmbeddingVector, validate_embedding_inputs, validate_embedding_vector,
)

_ORIGIN = "https://generativelanguage.googleapis.com"
_MODEL = "gemini-embedding-2"
_PATH = "/v1beta/models/" + _MODEL
_RESPONSE_LIMIT = 256 * 1024


class GeminiEmbeddingAdapter:
    """One-loop, bounded session with reusable connection and serialized requests.

    Enter opens the client but does not contact the provider. initialize() checks
    public metadata under its own explicit startup deadline. Measurement callers
    must include this startup time in cold results. Each embedding operation has
    the profile deadline, including lock wait, complete response and validation.
    Cancelled/failed attempts consume call/byte budgets; no automatic retry.
    """

    def __init__(self, profile: EmbeddingProfile, client_factory: Callable[[], httpx.AsyncClient],
                 *, max_calls: int, max_total_input_bytes: int, max_input_bytes: int = 4096,
                 startup_timeout_ms: int = 700) -> None:
        if (not isinstance(profile, EmbeddingProfile) or profile.model_id != _MODEL
                or not profile.model_revision.startswith("provider-version:")
                or not profile.model_revision.removeprefix("provider-version:").isdigit()
                or profile.dimension not in (768, 1536, 3072) or not callable(client_factory)):
            raise EmbeddingContractError("explicit managed candidate binding required")
        if any(type(n) is not int or n <= 0 for n in (
                max_calls, max_total_input_bytes, max_input_bytes, startup_timeout_ms)):
            raise EmbeddingContractError("positive explicit session limits required")
        self._profile, self._factory = profile, client_factory
        self._max_calls, self._max_bytes = max_calls, max_total_input_bytes
        self._input_limit, self._startup_ms = max_input_bytes, startup_timeout_ms
        self._client = None
        self._lock = None
        self._initialized = False
        self._used = False
        self._calls = self._bytes = 0

    @property
    def profile(self) -> EmbeddingProfile:
        return self._profile

    @property
    def attempted_calls(self) -> int:
        return self._calls

    @property
    def attempted_input_bytes(self) -> int:
        return self._bytes

    async def __aenter__(self):
        if self._used:
            raise EmbeddingContractError("embedding session cannot be reentered")
        self._used = True
        self._client = self._factory()
        self._lock = asyncio.Lock()
        try:
            client = self._client
            if (str(client.base_url).rstrip("/") != _ORIGIN or client.follow_redirects
                    or client.trust_env or client.params):
                raise EmbeddingContractError("approved fixed provider client required")
            await client.__aenter__()
        except BaseException:
            await self.aclose()
            raise
        return self

    async def aclose(self) -> None:
        self._initialized = False
        if self._client is not None:
            await self._client.aclose()

    async def __aexit__(self, *args):
        await self.aclose()

    def _require_open(self):
        if self._client is None or self._client.is_closed or self._lock is None:
            raise EmbeddingContractError("open embedding session required")

    async def _json(self, method: str, path: str, body=None):
        assert path in {_PATH, _PATH + ":embedContent"}
        async with self._client.stream(method, path, json=body, follow_redirects=False) as response:
            if response.status_code != 200:
                raise EmbeddingContractError("embedding provider returned non-success status")
            payload = bytearray()
            async for part in response.aiter_bytes():
                if len(payload) + len(part) > _RESPONSE_LIMIT:
                    raise EmbeddingContractError("embedding response exceeds limit")
                payload.extend(part)
            return json.loads(payload)

    async def initialize(self) -> None:
        self._require_open()
        self._initialized = False
        try:
            async with asyncio.timeout(self._startup_ms / 1000), self._lock:
                info = await self._json("GET", _PATH)
                expected = self.profile.model_revision.removeprefix("provider-version:")
                if (not isinstance(info, dict) or info.get("name") != "models/" + _MODEL
                        or info.get("version") != expected
                        or "embedContent" not in info.get("supportedGenerationMethods", ())):
                    raise EmbeddingContractError("embedding provider metadata binding rejected")
                self._initialized = True
        except (TimeoutError, httpx.TimeoutException):
            self._initialized = False
            raise EmbeddingTimeoutError("embedding startup deadline exceeded") from None
        except (ValueError, TypeError, httpx.HTTPError):
            self._initialized = False
            raise EmbeddingContractError("embedding provider metadata rejected") from None

    async def aembed_documents(self, texts: Sequence[str]) -> EmbeddingBatch:
        inputs = validate_embedding_inputs(texts, self.profile)
        # One request per document: Embedding 2 aggregates multipart content.
        return await self._embed(tuple("title: none | text: " + text for text in inputs))

    async def aembed_query(self, text: str) -> EmbeddingVector:
        inputs = validate_embedding_inputs((text,), self.profile)
        return (await self._embed(("task: search result | query: " + inputs[0],))).vectors[0]

    async def _embed(self, inputs: tuple[str, ...]) -> EmbeddingBatch:
        self._require_open()
        if not self._initialized:
            raise EmbeddingContractError("verified provider metadata required before content egress")
        sizes = tuple(len(text.encode("utf-8")) for text in inputs)
        if any(size > self._input_limit for size in sizes):
            raise EmbeddingContractError("embedding input exceeds byte limit")
        try:
            async with asyncio.timeout(self.profile.timeout_ms / 1000), self._lock:
                if (self._calls + len(inputs) > self._max_calls
                        or self._bytes + sum(sizes) > self._max_bytes):
                    raise EmbeddingContractError("embedding session budget exhausted")
                vectors = []
                for text, size in zip(inputs, sizes, strict=True):
                    self._calls += 1
                    self._bytes += size
                    data = await self._json("POST", _PATH + ":embedContent", {
                        "model": "models/" + _MODEL,
                        "content": {"parts": [{"text": text}]},
                        "embedContentConfig": {"outputDimensionality": self.profile.dimension,
                                               "autoTruncate": False},
                    })
                    row = data["embedding"]["values"]
                    if not isinstance(row, list) or any(type(v) not in (int, float) for v in row):
                        raise EmbeddingContractError("embedding numeric output rejected")
                    vectors.append(validate_embedding_vector(row, self.profile))
                return EmbeddingBatch(tuple(vectors), self.profile.model_id, self.profile.model_revision,
                                      self.profile.dimension, self.profile.normalization)
        except (TimeoutError, httpx.TimeoutException):
            raise EmbeddingTimeoutError("embedding operation deadline exceeded") from None
        except (KeyError, ValueError, TypeError, OverflowError, httpx.HTTPError):
            raise EmbeddingContractError("embedding provider response rejected") from None

    def embed_documents(self, texts: Sequence[str]) -> EmbeddingBatch:
        # Sync port is a worker boundary. A reusable session belongs to one loop.
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise EmbeddingContractError("synchronous embedding requires a worker context")
        validate_embedding_inputs(texts, self.profile)
        async def run():
            async with self:
                await self.initialize()
                return await self.aembed_documents(texts)
        return asyncio.run(run())

    def embed_query(self, text: str) -> EmbeddingVector:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise EmbeddingContractError("synchronous embedding requires a worker context")
        validate_embedding_inputs((text,), self.profile)
        async def run():
            async with self:
                await self.initialize()
                return await self.aembed_query(text)
        return asyncio.run(run())
