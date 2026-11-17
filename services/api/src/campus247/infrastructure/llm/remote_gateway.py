"""LlmGateway client for the gateway sidecar: the only way an API process reaches the paid provider.

The API process holds no provider credential, no ledger lease and no HTTP route to the provider. Every call goes to
the sidecar on loopback with an internal token; the sidecar owns the ledger, the budget, the spend cap and the
provider concurrency. When the sidecar is down or slow this client raises a clear error: there is no fallback and
nothing here can call the provider directly.
"""
from __future__ import annotations

from pathlib import Path

import httpx

from campus247.infrastructure.llm.gateway_wire import (
    MAX_BODY_BYTES, WireError, request_to_json, response_from_json)
from campus247.ports.llm import LlmRequest, LlmResponse, ModelCapabilities

QUEUE_ALLOWANCE_S = 5.0  # the sidecar's provider deadline starts after its own queue; this bounds that wait for the API


class GatewayError(RuntimeError):
    """Base class: the gateway did not produce a response. Messages never contain request content."""


class GatewayUnavailable(GatewayError):
    """The sidecar could not be reached or did not answer in time. No provider call was made by this process."""


class GatewayRefused(GatewayError):
    """The sidecar refused the call on purpose (spend or call cap reached, or the operation bound)."""


class GatewayCallFailed(GatewayError):
    """The sidecar made the call and the provider side failed; `error_type` is the exception class name only."""

    def __init__(self, error_type: str) -> None:
        super().__init__(f"provider call failed: {error_type}")
        self.error_type = error_type


def read_token(path: str | Path) -> str:
    token = Path(path).read_text(encoding="ascii").strip()
    if len(token) < 32:
        raise ValueError("internal gateway token file is empty or too short")
    return token


class RemoteGateway:
    def __init__(self, base_url: str, token: str, *, client: httpx.AsyncClient | None = None) -> None:
        if not base_url.startswith("http://127.0.0.1:") and not base_url.startswith("http://[::1]:"):
            raise ValueError("the gateway sidecar must be on loopback")
        if len(token) < 32:
            raise ValueError("internal gateway token too short")
        self._base_url, self._headers = base_url.rstrip("/"), {"X-Gateway-Token": token}
        self._client = client
        self._capabilities: ModelCapabilities | None = None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url, headers=self._headers, trust_env=False,
                                             follow_redirects=False, timeout=15,
                                             limits=httpx.Limits(max_connections=64, max_keepalive_connections=16))
        return self._client

    async def generate(self, request: LlmRequest) -> LlmResponse:
        timeout = request.deadline_ms / 1000 + QUEUE_ALLOWANCE_S
        try:
            reply = await self._http().post("/v1/generate", json=request_to_json(request), timeout=timeout)
        except (httpx.TimeoutException, httpx.TransportError) as error:
            raise GatewayUnavailable(f"gateway sidecar unavailable ({type(error).__name__})") from None
        if reply.status_code == 429:
            raise GatewayRefused("gateway refused the call (cap reached)")
        if reply.status_code in (400, 413):
            raise GatewayRefused("gateway refused the call (operation bound)")
        if reply.status_code in (401, 403):
            raise GatewayUnavailable("gateway sidecar rejected the internal token")
        if reply.status_code == 502:
            try:
                raise GatewayCallFailed(str(reply.json().get("error_type", "unknown"))[:64])
            except ValueError:
                raise GatewayCallFailed("unknown") from None
        if reply.status_code != 200 or len(reply.content) > MAX_BODY_BYTES:
            raise GatewayUnavailable(f"gateway sidecar answered {reply.status_code}")
        try:
            return response_from_json(reply.json())
        except (ValueError, WireError):
            raise GatewayUnavailable("gateway sidecar sent a malformed response") from None

    def capabilities(self, provider_id: str, model_id: str) -> ModelCapabilities:
        if self._capabilities is None:
            try:
                reply = httpx.get(self._base_url + "/v1/capabilities", headers=self._headers, trust_env=False, timeout=3)
                reply.raise_for_status()
                self._capabilities = ModelCapabilities(**reply.json())
            except (httpx.HTTPError, ValueError, TypeError):
                raise GatewayUnavailable("gateway sidecar unavailable (capabilities)") from None
        return self._capabilities

    def close(self) -> None:
        """Process exit closes the connections; kept because the platform calls close() on its gateway."""

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
