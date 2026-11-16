"""Thin stage6 HTTP boundary. All resource/state rules live in services."""
from __future__ import annotations

from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import HTMLResponse, Response

from campus247.domain.service_request import ServiceForm, SourceInput, VersionInput
from campus247.presentation.identity import get_current_identity as identity
from campus247.presentation.staff_workspace import revalidator


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Draft(Body):
    form: ServiceForm
    document_id: str | None = None
    expected_version: int | None = Field(default=None, ge=1)


class Version(Body):
    expected_version: int = Field(ge=1)


class Preview(Version):
    form: ServiceForm | None = None
    note: str = Field(default="", max_length=1000)


class Confirm(Body):
    preview_id: str
    confirmation_token: str = Field(min_length=1, max_length=4000)
    idempotency_key: str = Field(min_length=8, max_length=100)
    form: ServiceForm


class Action(Version):
    idempotency_key: str = Field(min_length=8, max_length=100)
    note: str = Field(min_length=1, max_length=1000)
    target_user_id: str | None = None
    target_queue: str | None = None
    outcome: Literal["UNCHANGED", "CORRECTED", "UNABLE_TO_REVIEW"] | None = None


class Review(Version):
    verdict: Literal["approved", "rejected"]
    note: str = Field(min_length=1, max_length=1000)


class Publication(Body):
    preview_id: str
    confirmation_token: str = Field(min_length=1, max_length=4000)
    idempotency_key: str = Field(min_length=8, max_length=100)
    confirmed: bool


class Proposal(Body):
    message: str = Field(min_length=1, max_length=2000)


def create_service_operations_router(service, knowledge):
    router = APIRouter(tags=["Service and knowledge demo operations"])

    @router.get("/v1/service-course-records")
    def courses(request: Request):
        return service.courses(identity(request))

    @router.get("/v1/service-guidance/{kind}")
    def guidance(kind: Literal["GRADE_APPEAL", "GENERAL_SUPPORT"], request: Request):
        return knowledge.guidance(identity(request), kind)

    @router.post("/v1/service-assistant")
    def propose(body: Proposal, request: Request):
        return service.propose(identity(request), body.message)

    @router.post("/v1/service-requests/drafts", status_code=201)
    def save(body: Draft, request: Request):
        return service.save_draft(identity(request), body.form, body.document_id, body.expected_version)

    @router.get("/v1/service-requests")
    def my_list(request: Request, cursor: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100)):
        return service.list(identity(request), offset=cursor, limit=limit)

    @router.get("/v1/staff/service-requests")
    def staff_list(request: Request, cursor: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100)):
        return service.list(identity(request), staff=True, offset=cursor, limit=limit)

    @router.get("/v1/service-staff-directory")
    def staff(request: Request):
        return service.staff(identity(request))

    @router.get("/v1/service-requests/{identifier}")
    def read(identifier: str, request: Request):
        return service.read(identity(request), identifier)

    @router.get("/v1/staff/service-requests/{identifier}")
    def read_staff(identifier: str, request: Request):
        return service.read(identity(request), identifier, staff=True)

    @router.post("/v1/service-requests/{identifier}/preview")
    def preview(identifier: str, body: Preview, request: Request):
        return service.preview(identity(request), identifier, body.expected_version, body.form, body.note)

    @router.get("/v1/service-requests/{identifier}/preview")
    def resume(identifier: str, request: Request):
        return service.resume(identity(request), identifier)

    @router.post("/v1/service-requests/{identifier}/confirm", status_code=201)
    def confirm(identifier: str, body: Confirm, request: Request):
        return service.confirm(identity(request), identifier, body.preview_id, body.confirmation_token, body.idempotency_key, body.form)

    @router.post("/v1/staff/service-requests/{identifier}/{action}")
    def act(identifier: str, action: str, body: Action, request: Request):
        return service.act(identity(request), identifier, action, body.expected_version, body.idempotency_key,
                           body.note, body.target_user_id, body.target_queue, body.outcome, revalidate=revalidator(request))

    @router.get("/v1/service-requests/{identifier}/result")
    def result(identifier: str, request: Request):
        html, checksum = service.result_html(identity(request), identifier)
        return HTMLResponse(html, headers={"X-Content-SHA256": checksum, "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'", "Cache-Control": "no-store"})

    @router.get("/v1/service-requests/{identifier}/attachments/{index}")
    def attachment(identifier: str, index: int, request: Request):
        value = service.attachment(identity(request), identifier, index)
        return Response(value["content"].encode(), media_type="text/plain; charset=utf-8", headers={
            "Content-Disposition": "attachment; filename*=UTF-8''" + quote(value["name"], safe=""),
            "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})

    @router.get("/v1/knowledge-operations")
    def knowledge_list(request: Request):
        return knowledge.list(identity(request))

    @router.post("/v1/knowledge-operations/sources", status_code=201)
    def upload(body: SourceInput, request: Request):
        return knowledge.upload(identity(request), body)

    @router.post("/v1/service-knowledge/search")
    def search(body: Proposal, request: Request):
        return knowledge.search(identity(request), body.message)

    @router.get("/v1/knowledge-operations/sources/{identifier}")
    def source(identifier: str, request: Request):
        return knowledge.source(identity(request), identifier)

    @router.post("/v1/knowledge-operations/versions", status_code=201)
    def version(body: VersionInput, request: Request):
        return knowledge.create_version(identity(request), body)

    @router.post("/v1/knowledge-operations/versions/{identifier}/review")
    def review(identifier: str, body: Review, request: Request):
        return knowledge.review(identity(request), identifier, body.expected_version, body.verdict, body.note)

    @router.post("/v1/knowledge-operations/versions/{identifier}/build")
    def build(identifier: str, body: Version, request: Request):
        return knowledge.build(identity(request), identifier, body.expected_version)

    @router.post("/v1/knowledge-operations/versions/{identifier}/{operation}/preview")
    def publish_preview(identifier: str, operation: Literal["publish", "withdraw"], body: Version, request: Request):
        return knowledge.preview(identity(request), identifier, body.expected_version, operation)

    @router.post("/v1/knowledge-operations/versions/{identifier}/confirm")
    def publish(identifier: str, body: Publication, request: Request):
        return knowledge.publish(identity(request), identifier, body.preview_id, body.confirmation_token, body.idempotency_key, body.confirmed)

    return router
