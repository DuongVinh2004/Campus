"""Authenticated transport for the real PostgreSQL-backed knowledge platform."""
from __future__ import annotations

import json
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError
from starlette.responses import JSONResponse, Response

from campus247.application.knowledge.platform_models import (
    ApplicabilityInput, ConfirmInput, IntakeMetadata, PlatformError, PreviewInput, ReviewInput,
)
from campus247.application.knowledge.document_identity import DraftIntakeInput, ResolveIntakeInput, UrlIntakeInput, LinkExistingInput, SeparateIntakeInput, RecheckIntakeInput, RefreshUrlInput
from campus247.application.knowledge.intake import KnowledgeIntake
from campus247.application.knowledge.version_resolver import ResolutionQuery, preview_resolution
from campus247.application.knowledge.edition_decisions import EditionDecisions, EditionDecisionInput, RelationDecisionInput
from campus247.application.knowledge.rendition_corrections import RenditionCorrections, CorrectionInput, CorrectionReviewInput
from campus247.application.knowledge.schedules import KnowledgeSchedules, ScheduleInput
from campus247.presentation.identity import get_current_identity
from campus247.ports.reranker import RerankerContractError, RerankerTimeoutError


class SearchPreviewInput(BaseModel):
    release_id: UUID
    query: str = Field(min_length=3, max_length=2000)


def create_knowledge_platform_router(platform, runtime, context_factory, upload_parser=None):
    async def parse_upload(request, storage):
        # The multipart adapter is injected by bootstrap; presentation never imports infrastructure.
        if upload_parser is None:
            raise PlatformError(503, "UPLOAD_PARSER_NOT_CONFIGURED", "Chưa cấu hình bộ đọc tệp tải lên.")
        return await upload_parser(request, storage)

    router = APIRouter(tags=["Knowledge platform"])
    intake = KnowledgeIntake(platform)
    edition_decisions = EditionDecisions(platform)
    corrections = RenditionCorrections(platform)
    schedules = KnowledgeSchedules(platform)
    platform.schedules = schedules

    def actor(request):
        identity = get_current_identity(request)
        platform.admin(identity)
        if request.method not in {"GET","HEAD"}:
            origin=request.headers.get("origin")
            if origin is not None and origin.rstrip("/") != str(request.base_url).rstrip("/"):
                raise PlatformError(403,"UNTRUSTED_ORIGIN","Thao tác quản trị cần cùng origin với ứng dụng.")
        return identity

    def key(request):
        value = request.headers.get("Idempotency-Key", "")
        if not value.strip() or len(value) > 128:
            raise HTTPException(422, "Cần Idempotency-Key để thử lại an toàn.")
        return value

    @router.get("/v1/knowledge/platform/availability")
    async def availability():
        return JSONResponse(await platform.availability(), headers={"Cache-Control": "no-store"})

    @router.get("/v1/knowledge/platform/state")
    async def state(request: Request):
        return JSONResponse(await platform.state(actor(request)), headers={"Cache-Control": "no-store"})

    @router.get("/v1/knowledge/platform/schedules")
    async def list_schedules(request: Request):
        return JSONResponse(await schedules.list(actor(request)), headers={"Cache-Control": "no-store"})

    @router.post("/v1/knowledge/platform/schedules", status_code=201)
    async def create_schedule(body: ScheduleInput, request: Request):
        return await schedules.create(actor(request), body, key(request), request.state.revalidate_identity)

    @router.post("/v1/knowledge/platform/schedules/resume")
    async def resume_schedules(request: Request):
        return schedules.resume(actor(request), request.state.revalidate_identity)

    @router.post("/v1/knowledge/platform/schedules/tick")
    async def tick_schedules(request: Request):
        return await schedules.tick(actor(request), request.state.revalidate_identity)

    @router.post("/v1/knowledge/platform/schedules/{schedule_id}/cancel")
    async def cancel_schedule(schedule_id: UUID, request: Request):
        return await schedules.cancel(actor(request), schedule_id)

    @router.post("/v1/knowledge/platform/uploads", status_code=202,
        openapi_extra={"requestBody": {"required": True, "content": {"multipart/form-data": {
            "schema": {"type": "object", "required": ["file", "metadata"], "properties": {
                "file": {"type": "string", "format": "binary"},
                "metadata": {"type": "string", "description": "IntakeMetadata JSON; explicit audiences/programs/effective dates"}}}}}}})
    async def upload(request: Request):
        identity, request_key = actor(request), key(request)  # Authenticate before parsing any bytes.
        try:
            file, artifact, metadata = await parse_upload(request, platform.storage)
            body = IntakeMetadata.model_validate_json(metadata)
        except PlatformError:
            raise
        except (ValidationError, UnicodeError, ValueError):
            raise HTTPException(422, "Multipart/metadata không hợp lệ; kiểm định dạng, phạm vi và ngày hiệu lực.") from None
        result = await platform.upload(identity, body, file, request_key, artifact=artifact)
        return JSONResponse(result, status_code=202, headers={"Cache-Control": "no-store"})

    @router.get("/v1/knowledge/platform/versions/{version_id}/original")
    async def original(version_id: UUID, request: Request):
        content, media, filename = await platform.artifact(actor(request), str(version_id), "original")
        # Attachment + sandbox avoids rendering active uploaded content in the app origin.
        if content.startswith(b"%PDF-"):
            media="application/pdf"
            if not filename.lower().endswith(".pdf"):
                filename += ".pdf"
        return Response(content, media_type=media, headers={"Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox",
            "Content-Disposition": "attachment; filename=source.bin; filename*=UTF-8''"+quote(filename,safe="")})

    @router.post("/v1/knowledge/platform/intakes", status_code=202)
    async def accept_intake(request: Request):
        identity, request_key = actor(request), key(request)
        await intake.ready()
        try:
            file, artifact, hints = await parse_upload(request, platform.storage)
            body = DraftIntakeInput.model_validate_json(hints)
        except (ValidationError, UnicodeError, ValueError):
            raise HTTPException(422, "Thông tin tiếp nhận không hợp lệ.") from None
        return JSONResponse(await intake.accept(identity, file, body, request_key, artifact=artifact),
            status_code=202, headers={"Cache-Control": "no-store"})

    @router.get("/v1/knowledge/platform/intakes")
    async def list_intakes(request: Request):
        return JSONResponse(await intake.list(actor(request)), headers={"Cache-Control": "no-store"})

    @router.get("/v1/knowledge/platform/intakes/{intake_id}/evidence")
    async def intake_evidence(intake_id: UUID, request: Request, offset: int = 0, limit: int = 20):
        return JSONResponse(await intake.evidence(actor(request), str(intake_id), offset, limit), headers={"Cache-Control": "no-store"})

    @router.post("/v1/knowledge/platform/url-intakes", status_code=202)
    async def accept_url_intake(body: UrlIntakeInput, request: Request):
        return await intake.accept_url(actor(request), body, key(request))

    @router.post("/v1/knowledge/platform/intakes/{intake_id}/metadata", status_code=202)
    async def resolve_intake(intake_id: UUID, body: ResolveIntakeInput, request: Request):
        return await intake.resolve(actor(request), str(intake_id), body.expected_revision, body.metadata, key(request))

    @router.post("/v1/knowledge/platform/intakes/{intake_id}/recheck",status_code=202)
    async def recheck_intake(intake_id: UUID,body: RecheckIntakeInput,request: Request):
        return await intake.recheck(actor(request),intake_id,body,key(request))

    @router.post("/v1/knowledge/platform/intakes/{intake_id}/url-refresh", status_code=202)
    async def refresh_url(intake_id: UUID, body: RefreshUrlInput, request: Request):
        return await intake.refresh_url(actor(request), intake_id, body, key(request))

    @router.post("/v1/knowledge/platform/intakes/{intake_id}/link-existing")
    async def link_existing(intake_id: UUID, body: LinkExistingInput, request: Request):
        return await intake.link_existing(actor(request), str(intake_id), body, key(request))

    @router.post("/v1/knowledge/platform/intakes/{intake_id}/keep-separate", status_code=202)
    async def keep_separate(intake_id: UUID, body: SeparateIntakeInput, request: Request):
        return await intake.separate(actor(request), str(intake_id), body, key(request))

    @router.get("/v1/knowledge/platform/intakes/{intake_id}/original")
    async def intake_original(intake_id: UUID, request: Request):
        content, media, filename = await intake.original(actor(request), str(intake_id))
        return Response(content, media_type=media, headers={"Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox",
            "Content-Disposition": "attachment; filename=source.bin; filename*=UTF-8''"+quote(filename,safe="")})

    @router.get("/v1/knowledge/platform/intakes/{intake_id}/pages/{page}/preview")
    async def intake_preview(intake_id: UUID, page: int, request: Request):
        return Response(await intake.preview(actor(request), str(intake_id), page), media_type="image/png",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox"})

    @router.get("/v1/knowledge/platform/intakes/{intake_id}/pages/{page}/ocr")
    async def intake_ocr(intake_id: UUID, page: int, request: Request, offset: int = 0, limit: int = 20):
        return JSONResponse(await intake.ocr(actor(request),str(intake_id),page,offset,limit),headers={"Cache-Control":"no-store"})

    @router.get("/v1/knowledge/platform/versions/{version_id}/rendition")
    async def rendition(version_id: UUID, request: Request):
        content, _, _ = await platform.artifact(actor(request), str(version_id), "rendition")
        return JSONResponse(json.loads(content), headers={"Cache-Control": "no-store"})

    @router.post("/v1/knowledge/platform/versions/{version_id}/reviews")
    async def review(version_id: UUID, body: ReviewInput, request: Request):
        return await platform.review(actor(request), str(version_id), body)

    @router.post("/v1/knowledge/platform/versions/{version_id}/applicability-versions",status_code=201)
    async def applicability(version_id: UUID,body: ApplicabilityInput,request: Request):
        from campus247.application.knowledge.applicability import applicability_version
        return await applicability_version(platform,actor(request),str(version_id),body,key(request))

    @router.post("/v1/knowledge/platform/versions/{version_id}/releases", status_code=201)
    async def release(version_id: UUID, request: Request):
        return await platform.build_release(actor(request), str(version_id), key(request))

    @router.post("/v1/knowledge/platform/previews")
    async def preview(body: PreviewInput, request: Request):
        return await platform.preview(actor(request), body)

    @router.post("/v1/knowledge/platform/confirmations")
    async def confirm(body: ConfirmInput, request: Request):
        return await platform.confirm(actor(request), body, key(request))

    @router.post("/v1/knowledge/platform/jobs/{job_id}/retry")
    async def retry(job_id: UUID, request: Request):
        return await platform.job_action(actor(request), str(job_id), "retry")

    @router.post("/v1/knowledge/platform/jobs/{job_id}/cancel")
    async def cancel(job_id: UUID, request: Request):
        return await platform.job_action(actor(request), str(job_id), "cancel")

    @router.post("/v1/knowledge/platform/search-preview")
    async def search_preview(body: SearchPreviewInput, request: Request):
        identity = actor(request)
        context = context_factory(identity)
        try:
            return {"items": await runtime.preview_search(identity, body.query, context, str(body.release_id))}
        except (RerankerContractError, RerankerTimeoutError):
            from campus247.presentation.errors import create_problem_details
            response = create_problem_details(status=503, code="KNOWLEDGE_SEARCH_UNAVAILABLE",
                title="Chưa thể tra cứu thử", detail="Dịch vụ tìm kiếm tạm thời chưa sẵn sàng. Vui lòng thử lại sau.",
                request=request, retryable=True)
            response.headers["Cache-Control"] = "no-store"
            return response

    @router.post("/v1/knowledge/platform/resolve-preview")
    async def resolve_preview(body: ResolutionQuery, request: Request):
        return await preview_resolution(platform, actor(request), body)

    @router.post("/v1/knowledge/platform/editions/{edition_id}/decisions", status_code=201)
    async def edition_decision(edition_id: UUID, body: EditionDecisionInput, request: Request):
        return await edition_decisions.identity(actor(request), edition_id, body, key(request))

    @router.get("/v1/knowledge/platform/versions/{version_id}/edition-workspace")
    async def edition_workspace(version_id: UUID, request: Request, page_index: int = 0):
        return JSONResponse(await edition_decisions.workspace(actor(request), version_id, page_index), headers={"Cache-Control": "no-store"})

    @router.get("/v1/knowledge/platform/versions/{version_id}/correction-preview")
    async def correction_preview(version_id: UUID,request: Request):
        return JSONResponse(await corrections.preview(actor(request),version_id),headers={"Cache-Control":"no-store"})

    @router.post("/v1/knowledge/platform/versions/{version_id}/corrections",status_code=201)
    async def propose_correction(version_id: UUID,body: CorrectionInput,request: Request):
        return await corrections.propose(actor(request),version_id,body,key(request))

    @router.get("/v1/knowledge/platform/versions/{version_id}/corrections")
    async def correction_history(version_id: UUID,request: Request):
        return JSONResponse(await corrections.history(actor(request),version_id),headers={"Cache-Control":"no-store"})

    @router.get("/v1/knowledge/platform/corrections/{correction_id}")
    async def correction_detail(correction_id: UUID,request: Request):
        return JSONResponse(await corrections.detail(actor(request),correction_id),headers={"Cache-Control":"no-store"})

    @router.post("/v1/knowledge/platform/corrections/{correction_id}/reviews",status_code=201)
    async def correction_review(correction_id: UUID,body: CorrectionReviewInput,request: Request):
        return await corrections.review(actor(request),correction_id,body,key(request))

    @router.post("/v1/knowledge/platform/edition-relations/decisions", status_code=201)
    async def relation_decision(body: RelationDecisionInput, request: Request):
        return await edition_decisions.relation(actor(request), body, key(request))

    # Existing read catalog paths now project the same database used by this runtime.
    @router.get("/v1/knowledge/sources")
    async def sources(request: Request):
        result = await platform.state(actor(request))
        return {"items": result["sources"], "page": {"next_cursor": None, "has_more": False, "limit": 200}}

    @router.get("/v1/knowledge/document-versions/{version_id}")
    async def version(version_id: UUID, request: Request):
        identity = actor(request)
        result = await platform.state(identity)
        for item in result["versions"]:
            if item["version_id"] == str(version_id):
                return item
        raise HTTPException(404, "Không tìm thấy phiên bản.")

    @router.get("/v1/knowledge/sources/{source_id}")
    async def source(source_id: UUID, request: Request):
        result = await platform.state(actor(request))
        for item in result["sources"]:
            if item["id"] == str(source_id):
                return item
        raise HTTPException(404,"Không tìm thấy nguồn.")

    return router
