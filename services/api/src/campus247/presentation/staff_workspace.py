"""Thin internal projection; no public or business-write tool registration."""
from fastapi import APIRouter, Request, HTTPException
from starlette.responses import JSONResponse
from campus247.application.assistance.staff_contracts import StaffRead, StaffReview, StaffSourceRead
from campus247.presentation.identity import get_current_identity
from campus247.application.document_request.certificates import CertificateError


def revalidator(request):
    def current(transaction=None):
        try:
            # Local business sessions use this same SQLite database. Read the
            # revocation under its existing lock instead of opening a second
            # BEGIN IMMEDIATE connection while waiting on ourselves.
            from pathlib import Path
            session = getattr(request.app.state, "current_session_service", None)
            store = getattr(session, "_store", None)
            if transaction is not None and getattr(store, "shares_session_database", False) is True:
                database = transaction.connection.execute("PRAGMA database_list").fetchone()[2]
                if Path(database).resolve() == store.path:
                    token = request.headers.get("authorization", "").removeprefix("Bearer ").strip() or request.cookies.get("auth_token", "")
                    if not token or transaction.connection.execute("SELECT 1 FROM certificate_revocation WHERE key IN (?,?)",
                        (session.hash_token(token), token)).fetchone():
                        raise ValueError("session revoked")
                    return get_current_identity(request)
            return request.state.revalidate_identity()
        except ValueError:
            raise HTTPException(401, "Phiên đã đổi hoặc bị thu hồi; giữ nội dung chưa lưu") from None
    return current


def create_staff_workspace_router(service):
    router = APIRouter(tags=["Internal staff workspace"])
    def available():
        if service is None:
            raise CertificateError(503, "STAFF_WORKSPACE_UNAVAILABLE", "Composition chưa có consumer hồ sơ cán bộ; mở hồ sơ nghiệp vụ và đối chiếu thủ công, giữ nháp hiện có")
        return service

    @router.post("/v1/assistant/staff-workspace/read")
    def read(body: StaffRead, request: Request):
        actor = get_current_identity(request)
        value = available().prepare(actor, body, revalidate=revalidator(request))
        return JSONResponse(value.model_dump(mode="json"), headers={"Cache-Control": "no-store"})

    @router.post("/v1/assistant/staff-workspace/review")
    def review(body: StaffReview, request: Request):
        actor = get_current_identity(request)
        return JSONResponse(available().review(actor, body, revalidate=revalidator(request)), headers={"Cache-Control": "no-store"})

    @router.post("/v1/assistant/staff-workspace/source")
    def source(body: StaffSourceRead, request: Request):
        actor = get_current_identity(request)
        return JSONResponse(available().open_source(actor, body, revalidate=revalidator(request)), headers={"Cache-Control": "no-store"})

    return router
