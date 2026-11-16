"""HTTP contract for the certificate application service."""
from __future__ import annotations

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import HTMLResponse

from campus247.application.document_request.certificates import CertificateService
from campus247.domain.document_request.certificate import CertificateForm
from campus247.presentation.identity import get_current_identity
from campus247.presentation.staff_workspace import revalidator


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DraftBody(Body):
    form: CertificateForm
    document_id: str | None = None
    expected_version: int | None = Field(default=None, ge=1)


class VersionBody(Body):
    expected_version: int = Field(ge=1)


class ConfirmBody(Body):
    preview_id: str
    confirmation_token: str = Field(min_length=1, max_length=4000)
    idempotency_key: str = Field(min_length=8, max_length=100)
    form: CertificateForm


class ActionBody(VersionBody):
    idempotency_key: str = Field(min_length=8, max_length=100)
    note: str = Field(default="", max_length=1000)
    form: CertificateForm | None = None


def create_certificate_router(service: CertificateService, *, draft_adapter=None):
    router = APIRouter(tags=["Student certificate demo"])

    @router.post("/v1/document-requests/drafts", status_code=201)
    def save_draft(body: DraftBody, request: Request):
        return service.save_draft(get_current_identity(request), body.form, body.document_id, body.expected_version)

    @router.post("/v1/document-requests/{document_id}/preview")
    def preview(document_id: str, body: VersionBody, request: Request):
        handler = draft_adapter.preview_for_user if draft_adapter is not None else service.preview
        return handler(get_current_identity(request), document_id, body.expected_version)

    @router.get("/v1/document-requests/{document_id}/preview")
    def resume(document_id: str, request: Request):
        return service.resume(get_current_identity(request), document_id)

    @router.post("/v1/document-requests/{document_id}/confirm", status_code=201)
    def confirm(document_id: str, body: ConfirmBody, request: Request):
        return service.confirm(get_current_identity(request), document_id, body.preview_id,
                               body.confirmation_token, body.idempotency_key, body.form)

    @router.get("/v1/document-requests")
    def list_my(request: Request, cursor: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
        return service.list(get_current_identity(request), offset=cursor, limit=limit)

    @router.get("/v1/staff/document-requests")
    def list_staff(request: Request, cursor: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
        return service.list(get_current_identity(request), staff=True, offset=cursor, limit=limit)

    @router.get("/v1/document-requests/{document_id}")
    def read_my(document_id: str, request: Request):
        return service.read(get_current_identity(request), document_id)

    @router.get("/v1/staff/document-requests/{document_id}")
    def read_staff(document_id: str, request: Request):
        return service.read(get_current_identity(request), document_id, staff=True)

    @router.post("/v1/staff/document-requests/{document_id}/{action}")
    def staff_action(document_id: str, action: str, body: ActionBody, request: Request):
        # The service independently enforces role and every transition.
        if action not in {"accept", "request_supplement", "approve", "reject"}:
            from campus247.application.document_request.certificates import CertificateError
            raise CertificateError(422, "UNKNOWN_ACTION", "Thao tác không được hỗ trợ")
        return service.act(get_current_identity(request), document_id, action, body.expected_version,
                           body.idempotency_key, body.note, revalidate=revalidator(request))

    @router.post("/v1/document-requests/{document_id}/supplement")
    def supplement(document_id: str, body: ActionBody, request: Request):
        return service.act(get_current_identity(request), document_id, "supplement", body.expected_version,
                           body.idempotency_key, body.note, body.form)

    @router.get("/v1/document-requests/{document_id}/result")
    def result(document_id: str, request: Request):
        return HTMLResponse(service.result_html(get_current_identity(request), document_id),
                            headers={"Cache-Control": "no-store", "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})

    return router
