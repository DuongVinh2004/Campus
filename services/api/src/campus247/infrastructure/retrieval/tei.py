"""TEI HTTP boundaries for existing ports; construction never activates a runtime.

The composition root supplies a fresh client factory after endpoint, artifact and
runtime clearance. /info validates served identity, not publisher provenance.
No credentials, endpoints, retries, model loads or authorization grants default here.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Sequence
from contextlib import asynccontextmanager, contextmanager
from functools import wraps
from time import monotonic, perf_counter_ns

import httpx

from campus247.application.retrieval.rerank import StrictRerankOutputValidator
from campus247.ports.embedding import (
    EmbeddingBatch,
    EmbeddingContractError,
    EmbeddingProfile,
    EmbeddingTimeoutError,
    EmbeddingVector,
    validate_embedding_inputs,
    validate_embedding_vector,
)
from campus247.ports.reranker import (
    RerankerContractError,
    RerankerProfile,
    RerankerTimeoutError,
    RerankRequest,
    RerankResult,
    RerankScore,
)

ClientFactory = Callable[[], httpx.AsyncClient]
DiagnosticSink = Callable[[dict], None]
_MAX_RESPONSE_BYTES = 4 * 1024 * 1024


def _emit(sink, phase, started, outcome):
    if sink is not None:
        # Enum phases and timing only. Observers cannot change port results or
        # expose request/response/header/exception content through this surface.
        try:
            sink({"phase": phase, "elapsed_ns": max(0, perf_counter_ns() - started),
                  "outcome": outcome, "clock": "perf_counter_ns"})
        except Exception:  # noqa: BLE001 -- observer failures must not change port results
            return


@contextmanager
def _phase(sink, name):
    started = perf_counter_ns() if sink is not None else 0
    outcome = "completed"
    try:
        yield
    except BaseException as error:
        outcome = "cancelled" if isinstance(error, asyncio.CancelledError) else "failed"
        raise
    finally:
        _emit(sink, name, started, outcome)


def _diagnosed(method):
    @wraps(method)
    async def observed(self, *args, **kwargs):
        with _phase(self._diagnostics, "adapter_total"):
            return await method(self, *args, **kwargs)
    return observed


IDENTITY_TTL_S = 30.0


@asynccontextmanager
async def _client(factory, sink):
    with _phase(sink, "client_construct"):
        client = factory()
    opened = perf_counter_ns() if sink is not None else 0
    entered = False
    close_started = None
    try:
        async with client as active:
            entered = True
            _emit(sink, "client_open", opened, "completed")
            try:
                yield active
            finally:
                close_started = perf_counter_ns() if sink is not None else 0
    finally:
        if entered:
            _emit(sink, "client_close", close_started, "completed" if client.is_closed else "failed")
        else:
            _emit(sink, "client_open", opened, "failed")


async def _json(client: httpx.AsyncClient, method: str, path: str, timeout: float,
                payload: dict | None = None, *, diagnostics=None):
    # Bound decoded response bytes too: a small compressed response can expand.
    with _phase(diagnostics, "identity_http" if method == "GET" else "inference_http"):
        async with client.stream(method, path, json=payload, timeout=timeout,
                                 follow_redirects=False) as response:
            if response.status_code != 200:
                raise ValueError("runtime returned a non-success status")
            body = bytearray()
            async for chunk in response.aiter_bytes():
                if len(body) + len(chunk) > _MAX_RESPONSE_BYTES:
                    raise ValueError("runtime response exceeds limit")
                body.extend(chunk)
            with _phase(diagnostics, "response_decode"):
                return json.loads(body.decode("utf-8"))


def _identity(info, model_id: str, revision: str, kind: str) -> None:
    if not isinstance(info, dict) or info.get("model_id") != model_id or info.get("model_sha") != revision:
        raise ValueError("served model does not match the exact profile")
    model_type = info.get("model_type")
    if not isinstance(model_type, dict) or set(model_type) != {kind}:
        raise ValueError("served model type does not match the port")
    if info.get("auto_truncate") is not False:
        raise ValueError("automatic truncation must be disabled")


class TEIEmbeddingAdapter:
    def __init__(self, profile: EmbeddingProfile, client_factory: ClientFactory, *,
                 diagnostics: DiagnosticSink | None = None) -> None:
        if not isinstance(profile, EmbeddingProfile) or not callable(client_factory):
            raise EmbeddingContractError("typed profile and approved client factory are required")
        if diagnostics is not None and not callable(diagnostics):
            raise EmbeddingContractError("diagnostics must be callable")
        self._profile, self._client_factory = profile, client_factory
        self._diagnostics = diagnostics
        self._identity_valid_until = 0.0

    @property
    def profile(self) -> EmbeddingProfile:
        return self._profile

    def embed_documents(self, texts: Sequence[str]) -> EmbeddingBatch:
        inputs = validate_embedding_inputs(texts, self.profile)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._embed(inputs))
        # The existing sync port must be called in a worker; never nest event loops
        # or silently create unbounded background threads from an async API route.
        raise EmbeddingContractError("synchronous embedding requires a worker context")

    def embed_query(self, text: str) -> EmbeddingVector:
        return self.embed_documents((text,)).vectors[0]

    @_diagnosed
    async def _embed(self, inputs: tuple[str, ...]) -> EmbeddingBatch:
        seconds = self.profile.timeout_ms / 1000
        try:
            async with asyncio.timeout(seconds):
                async with _client(self._client_factory, self._diagnostics) as client:
                    # The served model's identity is verified on the first call, every IDENTITY_TTL_S after that, and
                    # again after any failure. Every call used to pay a second request (and a second lock turn in the
                    # model server) for a fact that does not change between two questions.
                    if monotonic() >= self._identity_valid_until:
                        info = await _json(client, "GET", "/info", seconds, diagnostics=self._diagnostics)
                        with _phase(self._diagnostics, "identity_validation"):
                            _identity(info, self.profile.model_id, self.profile.model_revision, "embedding")
                        self._identity_valid_until = monotonic() + IDENTITY_TTL_S
                    rows = await _json(client, "POST", "/embed", seconds,
                                       {"inputs": list(inputs), "normalize": True, "truncate": False},
                                       diagnostics=self._diagnostics)
                    with _phase(self._diagnostics, "output_validation"):
                        if not isinstance(rows, list) or len(rows) != len(inputs):
                            raise ValueError("embedding output count does not match input")
                        vectors = []
                        for row in rows:
                            if not isinstance(row, list) or any(type(v) not in (int, float) for v in row):
                                raise ValueError("embedding values must be numbers")
                            vectors.append(validate_embedding_vector(row, self.profile))
                        return EmbeddingBatch(tuple(vectors), self.profile.model_id,
                            self.profile.model_revision, self.profile.dimension, self.profile.normalization)
        except (TimeoutError, httpx.TimeoutException):
            self._identity_valid_until = 0.0
            raise EmbeddingTimeoutError("embedding runtime deadline exceeded") from None
        except (ValueError, TypeError, OverflowError, httpx.HTTPError):
            self._identity_valid_until = 0.0
            raise EmbeddingContractError("embedding runtime response rejected") from None


class TEIRerankerAdapter:
    def __init__(self, profile: RerankerProfile, client_factory: ClientFactory, *,
                 diagnostics: DiagnosticSink | None = None) -> None:
        if not isinstance(profile, RerankerProfile) or not callable(client_factory):
            raise RerankerContractError("typed profile and approved client factory are required")
        if diagnostics is not None and not callable(diagnostics):
            raise RerankerContractError("diagnostics must be callable")
        self._profile, self._client_factory = profile, client_factory
        self._diagnostics = diagnostics

    @property
    def profile(self) -> RerankerProfile:
        return self._profile

    @_diagnosed
    async def rerank(self, request: RerankRequest) -> RerankResult:
        if not isinstance(request, RerankRequest) or request.profile != self.profile:
            raise RerankerContractError("request profile does not match adapter")
        if not request.candidates:
            return RerankResult((), self.profile.model_id, self.profile.model_revision, 0)
        started = monotonic()
        seconds = self.profile.timeout_ms / 1000
        try:
            async with asyncio.timeout(seconds):
                async with _client(self._client_factory, self._diagnostics) as client:
                    info = await _json(client, "GET", "/info", seconds, diagnostics=self._diagnostics)
                    with _phase(self._diagnostics, "identity_validation"):
                        _identity(info, self.profile.model_id, self.profile.model_revision, "reranker")
                    rows = await _json(client, "POST", "/rerank", seconds, {
                        "query": request.query.text,
                        "texts": [c.content_text for c in request.candidates],
                        "raw_scores": True, "return_text": False, "truncate": False,
                    }, diagnostics=self._diagnostics)
                    with _phase(self._diagnostics, "output_validation"):
                        if not isinstance(rows, list) or len(rows) != len(request.candidates):
                            raise ValueError("reranker must return every supplied candidate")
                        ranked, seen = [], set()
                        for row in rows:
                            if not isinstance(row, dict) or set(row) != {"index", "score"}:
                                raise ValueError("invalid ranking shape")
                            index = row["index"]
                            if type(index) is not int or not 0 <= index < len(request.candidates) or index in seen:
                                raise ValueError("duplicate or foreign ranking index")
                            seen.add(index)
                            ranked.append(RerankScore(request.candidates[index].chunk_id, row["score"]))
                        result = RerankResult(tuple(ranked), self.profile.model_id, self.profile.model_revision,
                                              int((monotonic() - started) * 1000))
                        return StrictRerankOutputValidator().validate(request, result)
        except (TimeoutError, httpx.TimeoutException):
            raise RerankerTimeoutError("reranker runtime deadline exceeded") from None
        except (ValueError, TypeError, OverflowError, httpx.HTTPError):
            raise RerankerContractError("reranker runtime response rejected") from None
