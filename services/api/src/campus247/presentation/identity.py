from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response, JSONResponse

from campus247.domain.shared.values import ErrorCode, ProblemDetails, generate_uuid7
from campus247.ports.identity import IdentityContext


from campus247.application.identity.session_service import get_session_service, SessionService, RevocationStoreError


class IdentityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, adapter: Any, session_service: SessionService | None = None) -> None:
        super().__init__(app)
        self._adapter = adapter
        self._session_service = session_service

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        auth_header = request.headers.get("Authorization")
        token: str | None = None
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        elif "auth_token" in request.cookies:
            token = request.cookies["auth_token"]

        identity: IdentityContext | None = None
        def revalidate_identity():
            session_svc = getattr(request.app.state, "current_session_service", None)
            if session_svc is None:
                session_svc = self._session_service if self._session_service is not None else get_session_service()
            if not token or session_svc.is_revoked(token):
                raise ValueError("Current session unavailable")
            return self._adapter.resolve_token(token)
        if token:
            # Revocation boundary: Revoked sessions fail closed immediately
            try:
                identity = revalidate_identity()
            except RevocationStoreError:
                from campus247.presentation.errors import create_problem_details
                response = create_problem_details(request=request,status=503,code="DEPENDENCY_UNAVAILABLE",
                    title="Không thể kiểm tra phiên",detail="Session storage chưa sẵn sàng; quyền truy cập chưa được xác nhận.")
                response.headers["Cache-Control"] = "no-store"
                return response
            except Exception:
                identity = None

        request.state.identity = identity
        # Request-local closure only: never serialized in run/task state.
        request.state.revalidate_identity = revalidate_identity
        return await call_next(request)


def get_current_identity(request: Request) -> IdentityContext:
    identity = getattr(request.state, "identity", None)
    if identity is None or not isinstance(identity, IdentityContext):
        problem = ProblemDetails(
            type="https://campus247.example/problems/authentication-required",
            title="Authentication Required",
            status=401,
            detail="A valid Bearer token or signed session is required.",
            instance=str(request.url.path),
            code=ErrorCode.AUTHENTICATION_REQUIRED,
            request_id=generate_uuid7(),
            retryable=False,
        )
        raise HTTPException(status_code=401, detail=problem.to_dict())
    return identity


def create_identity_router(adapter: Any | None = None, environment: str = "local") -> APIRouter:
    from fastapi import APIRouter
    from fastapi.responses import JSONResponse

    router = APIRouter(tags=["Identity"])

    is_prod = str(environment).strip().lower() == "production"

    if not is_prod:
        @router.get("/v1/auth/demo-session")
        @router.post("/v1/auth/demo-session")
        async def get_or_create_demo_session(request: Request) -> JSONResponse:
            student_id = "4b419a1b-6d41-7dfb-8943-2edd9f071385"
            token = adapter.mint_token(student_id) if adapter else ""
            content = {
                "token": token,
                "user_id": student_id,
                "display_name": "Nguyễn Văn Sinh Viên (Demo)",
                "student_code": "SYN24000001",
                "roles": ["STUDENT"],
            }
            resp = JSONResponse(
                status_code=200,
                content=content,
                headers={"Cache-Control": "no-store"},
            )
            if token:
                resp.set_cookie(
                    key="auth_token",
                    value=token,
                    httponly=True,
                    secure=is_prod,
                    samesite="lax",
                    path="/",
                )
            return resp

    @router.get("/v1/users/me")
    async def get_current_user_profile(request: Request) -> JSONResponse:
        identity = get_current_identity(request)
        content: dict[str, Any] = {
            "user_id": identity.subject_id,
            "display_name": identity.display_name,
            "roles": [r.value for r in identity.roles],
            "is_synthetic": identity.is_synthetic,
        }
        if identity.email:
            content["primary_email"] = identity.email
        if identity.faculty_code:
            content["faculty_code"] = identity.faculty_code
        if identity.student_code:
            content["student_code"] = identity.student_code

        return JSONResponse(
            status_code=200,
            content=content,
            headers={"Cache-Control": "no-store"},
        )

    return router


router = create_identity_router()

