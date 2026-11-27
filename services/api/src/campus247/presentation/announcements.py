"""Announcements over HTTP (F1.4). Routes only authenticate and translate; every rule lives in AnnouncementService."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, FastAPI, Header, Query, Request
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

from campus247.application.announcements.service import AnnouncementError, AnnouncementService
from campus247.domain.announcements import AnnouncementInvalid
from campus247.presentation.identity import get_current_identity

NO_STORE = {"Cache-Control": "no-store"}


def register_announcement_errors(app: FastAPI) -> None:
    @app.exception_handler(AnnouncementError)
    async def announcement_error(request: Request, exc: AnnouncementError):
        body = {"type": f"https://campus247.example/problems/{exc.code.lower().replace('_', '-')}", "title": exc.detail, "status": exc.status,
                "detail": exc.detail, "code": exc.code, "retryable": exc.status == 429, **exc.extra}
        if exc.errors:
            body["errors"] = exc.errors
        return JSONResponse(status_code=exc.status, headers=NO_STORE, content=body)

    @app.exception_handler(AnnouncementInvalid)
    async def invalid(request: Request, exc: AnnouncementInvalid):
        return JSONResponse(status_code=422, headers=NO_STORE, content={"title": "Nội dung chưa hợp lệ.", "status": 422, "detail": "Nội dung chưa hợp lệ.",
                                                                       "code": "ANNOUNCEMENT_INVALID", "errors": exc.errors})


class DraftBody(BaseModel):
    title: str = ""
    body: str = ""
    category: str = "ACADEMIC"
    priority: str = "NORMAL"
    audience: dict = Field(default_factory=dict)
    publish_at: Optional[str] = None
    expires_at: Optional[str] = None
    requires_ack: bool = False
    ack_deadline: Optional[str] = None
    source_ref: dict = Field(default_factory=dict)
    links: list = Field(default_factory=list)
    issuer_unit: str = ""
    row_version: Optional[int] = None


class AudienceBody(BaseModel):
    audience: dict


class ConfirmBody(BaseModel):
    preview_id: str
    confirmation_token: str = ""


class NoteBody(BaseModel):
    note: str = ""
    row_version: int


class ReasonBody(BaseModel):
    reason: str = ""


def create_announcements_router(service: AnnouncementService) -> APIRouter:
    r = APIRouter(tags=["Announcements"])

    def out(content: Any, status: int = 200) -> JSONResponse:
        return JSONResponse(content, status_code=status, headers=NO_STORE)

    def key(value: Optional[str]) -> str:
        return value or ""

    # ---- authors and approvers
    @r.post("/v1/announcements/drafts")
    def create(body: DraftBody, request: Request):
        return out(service.create_draft(get_current_identity(request), body.model_dump(exclude={"row_version"})), 201)

    @r.put("/v1/announcements/{announcement_id}/draft")
    def update(announcement_id: str, body: DraftBody, request: Request):
        return out(service.update_draft(get_current_identity(request), announcement_id, body.model_dump(exclude={"row_version"}), body.row_version or 0))

    @r.delete("/v1/announcements/{announcement_id}/draft")
    def delete(announcement_id: str, request: Request):
        service.delete_draft(get_current_identity(request), announcement_id)
        return out({"id": announcement_id, "deleted": True})

    @r.post("/v1/announcements:audience-preview")
    def audience_spec(body: AudienceBody, request: Request):
        return out(service.audience_preview_spec(get_current_identity(request), body.audience))

    @r.post("/v1/announcements/{announcement_id}:audience-preview")
    def audience(announcement_id: str, request: Request):
        return out(service.audience_preview(get_current_identity(request), announcement_id))

    @r.post("/v1/announcements/{announcement_id}:publish-preview")
    def publish_preview(announcement_id: str, request: Request):
        return out(service.publish_preview(get_current_identity(request), announcement_id))

    @r.post("/v1/announcements:publish-confirm")
    def publish_confirm(body: ConfirmBody, request: Request, idempotency_key: Optional[str] = Header(None)):
        return out(service.publish_confirm(get_current_identity(request), body.preview_id, body.confirmation_token, key(idempotency_key)))

    @r.post("/v1/announcements/{announcement_id}:approve")
    def approve(announcement_id: str, body: NoteBody, request: Request):
        return out(service.approve(get_current_identity(request), announcement_id, body.note, body.row_version))

    @r.post("/v1/announcements/{announcement_id}:reject")
    def reject(announcement_id: str, body: NoteBody, request: Request):
        return out(service.approve(get_current_identity(request), announcement_id, body.note, body.row_version, approve=False))

    @r.post("/v1/announcements/{announcement_id}:unschedule")
    def unschedule(announcement_id: str, request: Request):
        return out(service.unschedule(get_current_identity(request), announcement_id))

    @r.post("/v1/announcements/{announcement_id}:revision-preview")
    def revision_preview(announcement_id: str, body: dict, request: Request):
        return out(service.revision_preview(get_current_identity(request), announcement_id, body))

    @r.post("/v1/announcements:revision-confirm")
    def revision_confirm(body: ConfirmBody, request: Request, idempotency_key: Optional[str] = Header(None)):
        return out(service.revision_confirm(get_current_identity(request), body.preview_id, body.confirmation_token, key(idempotency_key)))

    @r.post("/v1/announcements/{announcement_id}:withdraw-preview")
    def withdraw_preview(announcement_id: str, body: ReasonBody, request: Request):
        return out(service.withdraw_preview(get_current_identity(request), announcement_id, body.reason))

    @r.post("/v1/announcements:withdraw-confirm")
    def withdraw_confirm(body: ConfirmBody, request: Request, idempotency_key: Optional[str] = Header(None)):
        return out(service.withdraw_confirm(get_current_identity(request), body.preview_id, body.confirmation_token, key(idempotency_key)))

    @r.get("/v1/announcements/authored")
    def authored(request: Request, status: Optional[str] = None, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
        return out(service.authored(get_current_identity(request), status, offset, limit))

    @r.get("/v1/announcements/approvals")
    def approvals(request: Request):
        return out(service.approvals(get_current_identity(request)))

    @r.get("/v1/announcements/{announcement_id}/stats")
    def stats(announcement_id: str, request: Request):
        return out(service.stats(get_current_identity(request), announcement_id))

    @r.get("/v1/announcements/{announcement_id}/pending-acks")
    def pending_acks(announcement_id: str, request: Request):
        return out(service.pending_acks(get_current_identity(request), announcement_id))

    # ---- recipients
    @r.get("/v1/announcements/mine")
    def mine(request: Request, filter: str = Query("active", pattern="^(active|unread|all)$"), category: Optional[str] = None,
             offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
        return out(service.mine(get_current_identity(request), filter=filter, category=category, offset=offset, limit=limit))

    @r.get("/v1/announcements/public")
    def public(offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
        return out(service.public(offset, limit))

    @r.get("/v1/announcements/{announcement_id}")
    def detail(announcement_id: str, request: Request):
        return out(service.get(get_current_identity(request), announcement_id))

    @r.post("/v1/announcements/{announcement_id}/ack")
    def ack(announcement_id: str, request: Request):
        return out(service.ack(get_current_identity(request), announcement_id))

    return r
