from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from starlette.responses import JSONResponse

from campus247.application.identity.logout import LogoutService, RevocationError
from campus247.application.identity.session_service import RevocationStoreError
from campus247.presentation.identity import get_current_identity


def create_logout_router(logout_service: LogoutService, session_service=None) -> APIRouter:
    router = APIRouter()

    @router.post("/logout")
    async def logout(request: Request,authorization: str | None = Header(default=None)):
        token = None
        if authorization and authorization.startswith("Bearer "):
            token = authorization[7:].strip()
        if not token:
            token = authorization
        if not token and session_service is not None:
            token = request.cookies.get("auth_token")

        if not token:
            raise HTTPException(status_code=400, detail="Missing authorization token")

        try:
            if session_service is not None:
                if session_service.is_revoked(token):
                    response = JSONResponse({"status":"revoked","idempotent":True})
                else:
                    actor = get_current_identity(request)
                    response = JSONResponse(session_service.revoke_session(token,actor_id=actor.subject_id))
                response.delete_cookie("auth_token",path="/")
                return response
            logout_service.logout(token)
            return JSONResponse(status_code=200, content={"status": "revoked"})
        except RevocationError as e:
            return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})
        except RevocationStoreError:
            raise HTTPException(status_code=503,detail="Session revocation storage unavailable") from None

    return router
