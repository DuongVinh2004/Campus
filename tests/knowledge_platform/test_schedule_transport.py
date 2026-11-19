"""Real ASGI identity/origin boundaries for session-schedule endpoints."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from campus247.application.knowledge.platform import KnowledgePlatform
from campus247.application.knowledge.platform_models import PlatformError
from campus247.domain.shared.values import generate_uuid7
from campus247.ports.identity import IdentityContext, IdentityRole
from campus247.presentation.identity import IdentityMiddleware
from campus247.presentation.knowledge_platform import create_knowledge_platform_router


def test_schedule_transport_requires_current_identity_trusted_origin_and_bounded_input():
    now = datetime.now(UTC)
    identity = IdentityContext(generate_uuid7(), "synthetic", "test", (IdentityRole.KNOWLEDGE_ADMIN,), "Test",
        now-timedelta(seconds=1), now+timedelta(hours=1), tenant_id="synthetic", session_id="session")
    class Adapter:
        def resolve_token(self, token):
            if token != "synthetic-session":
                raise ValueError("invalid")
            return identity
    platform = KnowledgePlatform(SimpleNamespace(tenant="synthetic"), SimpleNamespace(), None)
    app = FastAPI()
    @app.exception_handler(PlatformError)
    async def platform_error(request, error):
        return JSONResponse({"code": error.code}, status_code=error.status)
    app.add_middleware(IdentityMiddleware, adapter=Adapter())
    app.include_router(create_knowledge_platform_router(platform, None, None))
    platform.schedules.list = AsyncMock(return_value={"items": []})
    platform.schedules.create = AsyncMock(return_value={"id": "mechanical-test"})
    base = "/v1/knowledge/platform/schedules"
    headers = {"Authorization": "Bearer synthetic-session", "Idempotency-Key": "create"}
    body = {"kind": "URL_REFRESH", "target_id": generate_uuid7(), "confirmed": True,
        "not_before": now.isoformat(), "expires_at": (now+timedelta(minutes=10)).isoformat(),
        "interval_seconds": 900, "expected_original_sha256": "a"*64}
    with TestClient(app) as client:
        assert client.get(base).status_code == 401
        assert client.get(base, headers=headers).status_code == 200
        assert client.post(base, json=body, headers={**headers, "Origin": "https://untrusted.invalid"}).status_code == 403
        platform.schedules.create.assert_not_called()
        assert client.post(base, json={**body, "confirmed": False}, headers=headers).status_code == 422
        assert client.post(base, json={**body, "service_actor": "invented"}, headers=headers).status_code == 422
        assert client.post(base, json=body, headers={"Authorization": headers["Authorization"]}).status_code == 422
        assert client.post(base, json=body, headers=headers).status_code == 201
        args = platform.schedules.create.call_args.args
        assert args[0] == identity and args[3]() == identity
        assert client.post(base+"/resume", headers=headers).json()["publication_authority"] is False
