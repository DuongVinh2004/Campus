"""Authenticated learning transport. Domain decisions remain in LearningService."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import sqlite3
from datetime import UTC, date, datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    create_model,
    field_validator,
    model_validator,
)
from starlette.responses import JSONResponse, Response, StreamingResponse

from campus247.application.learning.accessible_text import OCR_WRITES
from campus247.application.learning.exit_tickets import EXIT_TICKET_WRITES
from campus247.application.learning.idea_cards import IDEA_WRITES
from campus247.domain.learning import LearningError, require, select_bytes
from campus247.application.learning.telemetry import record
from campus247.presentation.identity import get_current_identity
from campus247.presentation.learning_ideas import (
    idea_input_models,
    register_idea_routes,
)
from campus247.presentation.learning_ocr import ocr_input_models, register_ocr_routes


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preview_id: str | None = None
    confirmation_token: str | None = None


class LearningExplanationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_no: int = Field(strict=True, ge=1)
    question: str = Field(min_length=1, max_length=2000)
    quote: str | None = Field(default=None, max_length=2000)


class LearningVersionChangeItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["EDITED", "MOVED", "ADDED", "REMOVED"]
    old_page: int | None = Field(default=None, strict=True, ge=1, le=500)
    new_page: int | None = Field(default=None, strict=True, ge=1, le=500)
    description: str = Field(min_length=1, max_length=1000)
    guidance: str = Field(default="", max_length=1000)


class LearningExitWallTime(BaseModel):
    model_config = ConfigDict(extra="forbid")
    local: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$")
    offset_minutes: int | None = Field(default=None, strict=True, ge=-1440, le=1440)


class LearningExitInstructionBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    revision: int = Field(strict=True, ge=1)


class LearningExitTicketDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version_id: UUID
    page_no: int = Field(strict=True, ge=1, le=500)
    question: str = Field(min_length=1, max_length=1000)
    opens: LearningExitWallTime
    closes: LearningExitWallTime
    instruction: LearningExitInstructionBinding | None = None

    @field_validator("question")
    @classmethod
    def nonblank_question(cls, value):
        if not value.strip():
            raise ValueError("Question must contain text")
        return value


class LearningExitTicketInput(LearningExitTicketDraft, Payload):
    pass


class LearningExitTicketUpdate(Payload):
    revision: int = Field(strict=True, ge=1)
    operation: Literal["EDIT_DRAFT", "PUBLISH", "EXTEND", "CANCEL"]
    draft: LearningExitTicketDraft | None = None
    closes: LearningExitWallTime | None = None

    @model_validator(mode="after")
    def operation_fields(self):
        fields = {"draft", "closes"} & self.model_fields_set
        expected = {"EDIT_DRAFT": {"draft"}, "EXTEND": {"closes"}}.get(self.operation, set())
        if fields != expected or any(getattr(self, name) is None for name in expected):
            raise ValueError("Operation fields do not match")
        return self


class LearningExitSubmissionInput(Payload):
    revision: int = Field(strict=True, ge=0)
    answer: str = Field(min_length=1, max_length=1000)

    @field_validator("answer")
    @classmethod
    def nonblank_answer(cls, value):
        if not value.strip():
            raise ValueError("Answer must contain text")
        return value


class LearningExitReviewInput(Payload):
    revision: int = Field(strict=True, ge=0)
    operation: Literal["SAVE_DRAFT", "PUBLISH"]
    topics: str | None = Field(default=None, max_length=3000)
    next_plan: str | None = Field(default=None, max_length=3000)
    explanation: str | None = Field(default=None, max_length=3000)

    @model_validator(mode="after")
    def operation_fields(self):
        content = {"topics", "next_plan", "explanation"}
        expected = content if self.operation == "SAVE_DRAFT" else set()
        if (content & self.model_fields_set) != expected or any(getattr(self, name) is None for name in expected):
            raise ValueError("Operation fields do not match")
        return self


def model(model_name, **fields):
    return create_model(model_name, __base__=Payload, **fields)


Text = str
SCHEMAS = {
    "term-create": model("LearningTermInput", name=(str, ...), start_date=(date, ...), end_date=(date, ...), timezone=(str, "Asia/Bangkok")),
    "course-create": model("LearningCourseInput", code=(str, ...), name=(str, ...)),
    "offering-create": model("LearningOfferingInput", course_id=(UUID, ...), term_id=(UUID, ...), section_code=(str, ...), title=(str | None, None), download_allowed=(bool, True)),
    "member-create": model("LearningMemberInput", actor_subject_id=(UUID, ...), role=(Literal["INSTRUCTOR", "STUDENT"], ...)),
    "member-update": model("LearningMemberUpdate", status=(Literal["ACTIVE", "INACTIVE"], ...), revision=(int, ...)),
    "archive": model("LearningArchiveInput", revision=(int, ...)),
    "session-create": model("LearningSessionInput", title=(str, ...), description=(str, ""), sequence_no=(int | None, None), starts_at=(datetime | None, None)),
    "session-update": model("LearningSessionUpdate", title=(str | None, None), description=(str | None, None), starts_at=(datetime | None, None), revision=(int, ...)),
    "session-order": model("LearningSessionOrder", session_ids=(list[UUID], ...)),
    "material-create": model("LearningMaterialInput", title=(str, ...), description=(str, ""), session_id=(UUID | None, None)),
    "material-update": model("LearningMaterialUpdate", title=(str | None, None), description=(str | None, None), visibility=(Literal["VISIBLE", "HIDDEN"] | None, None), revision=(int, ...)),
    "material-links": model("LearningMaterialLinks", material_ids=(list[UUID], ...)),
    "upload-create": model("LearningUploadInput", filename=(str, ...), byte_size=(int, ...), content_type=(str, "application/pdf")),
    "publish": model("LearningPublishInput", scheduled_at=(datetime | None, None),
                     change_set_revision=(int | None, Field(default=None, strict=True, ge=1))),
    "retract": model("LearningRetractInput", replacement_version_id=(UUID | None, None)),
    "cancel-publication": model("LearningCancelPublicationInput"),
    "reader-state": model("LearningReaderStateInput", page_no=(int, ...), offset_x=(float, 0), offset_y=(float, 0), zoom_mode=(Literal["page-width", "page-fit", "custom"], "page-width"), zoom_value=(float, 1), rotation=(Literal[0, 90, 180, 270], 0), scroll_mode=(Literal["vertical", "horizontal", "page"], "vertical"), revision=(int, 0)),
    "bookmark-create": model("LearningBookmarkInput", version_id=(UUID, ...), page_no=(int, ...), label=(str, "")),
    "bookmark-update": model("LearningBookmarkUpdate", label=(str | None, None), status=(Literal["ACTIVE", "ARCHIVED"] | None, None), revision=(int | None, None)),
    "notification-update": model("LearningNotificationUpdate", read_at=(datetime | None, None), revision=(int | None, None)),
}
SCHEMAS.update({
    "exit-ticket-create": LearningExitTicketInput,
    "exit-ticket-update": LearningExitTicketUpdate,
    "exit-submission-save": LearningExitSubmissionInput,
    "exit-review-save": LearningExitReviewInput,
    "annotation-create": model("LearningAnnotationInput", version_id=(UUID, ...), rendition_id=(UUID | None, None), page_no=(int, ...), anchor=(dict[str, Any], {"kind": "PAGE"}), body=(str, ...)),
    "annotation-update": model("LearningAnnotationUpdate", body=(str | None, None), status=(Literal["ACTIVE", "ARCHIVED"] | None, None), revision=(int, ...)),
    "annotation-share": model("LearningAnnotationShare", revision=(int, Field(strict=True, ge=1))),
    "question-create": model("LearningQuestionInput", rendition_id=(UUID | None, None), page_no=(int, ...), anchor=(dict[str, Any], {"kind": "PAGE"}), body=(str, ...), visibility=(Literal["CLASS", "PRIVATE_TO_INSTRUCTORS"], "PRIVATE_TO_INSTRUCTORS")),
    "question-update": model("LearningQuestionUpdate", body=(str | None, None), status=(Literal["ACTIVE", "ARCHIVED"] | None, None), visibility=(Literal["CLASS", "PRIVATE_TO_INSTRUCTORS"] | None, None), revision=(int, ...)),
    "reply-create": model("LearningReplyInput", body=(str, ...), question_revision=(int, Field(strict=True, ge=1, description="Revision of the thread when the reply audience was shown."))),
    "reply-endorse": model("LearningReplyEndorse"),
    "instruction-create": model("LearningInstructionInput", version_id=(UUID, ...), page_ranges=(list[dict[str, int]], ...), purpose=(str, ...), timing=(Literal["BEFORE", "DURING", "AFTER"], "BEFORE"), questions=(list[str], [])),
    "instruction-update": model("LearningInstructionUpdate", version_id=(UUID | None, None), page_ranges=(list[dict[str, int]] | None, None), purpose=(str | None, None), timing=(Literal["BEFORE", "DURING", "AFTER"] | None, None), questions=(list[str] | None, None), status=(Literal["ACTIVE", "ARCHIVED"] | None, None), revision=(int, ...)),
    "instruction-seen": model("LearningInstructionSeen", revision=(int, Field(strict=True, ge=1))),
    "presentation-create": model("LearningPresentationInput", version_id=(UUID, ...)),
    "presentation-position": model("LearningPresentationPosition", page_no=(int, ...), sequence=(int, ...)),
    "presentation-end": model("LearningPresentationEnd"),
    "feedback-window-open": model("LearningFeedbackWindowInput", closes_at=(datetime, ...)),
    "page-feedback-save": model(
        "LearningPageFeedbackInput",
        session_id=(UUID, ...),
        category=(Literal["HARD_TO_UNDERSTAND", "NEED_EXAMPLE", "POSSIBLE_ERROR"], ...),
        revision=(int, Field(strict=True, ge=0)),
    ),
    "page-feedback-withdraw": model("LearningPageFeedbackWithdraw", revision=(int, Field(strict=True, ge=1))),
    "page-explanation-create": model(
        "LearningPageExplanationInput", version_id=(UUID, ...), page_no=(int, Field(strict=True, ge=1, le=500)),
        body=(str, ...), category=(Literal["RETEACH", "ADD_EXAMPLE", "CORRECTION"], ...),
    ),
    "page-explanation-update": model(
        "LearningPageExplanationUpdate", revision=(int, Field(strict=True, ge=1)), publish=(bool, Field(default=False, strict=True)),
        body=(str | None, None), category=(Literal["RETEACH", "ADD_EXAMPLE", "CORRECTION"] | None, None),
    ),
    "version-change-save": model(
        "LearningVersionChangeInput", revision=(int, Field(strict=True, ge=0)), base_version_id=(UUID, ...),
        mode=(Literal["PAGE_MAP", "WHOLE_DOCUMENT", "UNSPECIFIED"], ...),
        reason=(str, Field(min_length=1, max_length=2000)), target_guidance=(str, Field(max_length=2000)),
        items=(list[LearningVersionChangeItem], Field(max_length=100)),
    ),
})
SCHEMAS.update(idea_input_models(model))
SCHEMAS.update(ocr_input_models(model))
ALIASES = {"create_term": "term-create", "create_course": "course-create", "create_offering": "offering-create", "add_member": "member-create", "update_member": "member-update", "archive_offering": "archive", "hide_material": "material-update", "update_session": "session-update", "order_sessions": "session-order", "material_links": "material-links"}


def parse(action, raw):
    try:
        validated = SCHEMAS[action].model_validate(raw)
        value = validated.model_dump(mode="json", exclude_unset=True)
        for field in validated.model_fields_set:
            item = getattr(validated, field)
            if isinstance(item, datetime):
                require(item.tzinfo is not None, 422, "INVALID_TIMESTAMP", "Thời gian phải có múi giờ.")
                value[field] = item.astimezone(UTC).isoformat().replace("+00:00", "Z")
    except (ValidationError, KeyError):
        raise LearningError(422, "VALIDATION_FAILED", "Trường dữ liệu học liệu không hợp lệ.") from None
    for key, text in value.items():
        if key in {"title", "name", "code", "section_code", "filename"}:
            require(isinstance(text, str) and bool(text.strip()) and len(text) <= 250, 422, "VALIDATION_FAILED", "Tên hoặc tiêu đề không hợp lệ.")
        if key in {"label", "description"} and text is not None:
            require(len(text) <= (500 if key == "label" else 5000), 422, "VALIDATION_FAILED", "Nội dung quá dài.")
        if key in {"body", "purpose"}:
            require(isinstance(text, str) and 0 < len(text.strip()) <= 5000, 422, "INVALID_BODY", "Nội dung phải có từ 1 đến 5000 ký tự.")
        if key == "questions":
            require(len(text) <= 20 and all(len(q) <= 1000 for q in text), 422, "INVALID_QUESTIONS", "Danh sách câu hỏi quá dài.")
    if action == "reader-state":
        require(0 <= value.get("offset_x", 0) <= 1 and 0 <= value.get("offset_y", 0) <= 1 and 0.5 <= value.get("zoom_value", 1) <= 3, 422, "INVALID_VIEWPORT", "Vị trí hoặc mức phóng không hợp lệ.")
    if action == "session-create" and value.get("sequence_no") is not None:
        require(value["sequence_no"] > 0, 422, "INVALID_SEQUENCE", "Thứ tự buổi phải dương.")
    if action == "page-explanation-update":
        content_fields = {"body", "category"} & value.keys()
        require(not content_fields if value.get("publish") else content_fields == {"body", "category"} and value["category"] is not None,
                422, "VALIDATION_FAILED", "Sửa bản nháp hoặc công bố đúng revision đã xem trước.")
    if action == "version-change-save":
        require(value["reason"].strip() and all(item["description"].strip() for item in value["items"]),
                422, "INVALID_BODY", "Mô tả thay đổi phải có nội dung.")
    return value


class LearningRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handle(request):
            try:
                return await original(request)
            except LearningError as error:
                record("learning.request_rejected", status=error.status, code=error.code)
                return JSONResponse({"type": "https://campus247.example/problems/learning/" + error.code.lower().replace("_", "-"), "title": error.detail, "detail": error.detail, "status": error.status, "code": error.code, "request_id": getattr(request.state, "request_id", "")}, status_code=error.status, media_type="application/problem+json", headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
            except (OSError, json.JSONDecodeError, sqlite3.Error):
                return JSONResponse({"status": 503, "code": "LEARNING_STORAGE_UNAVAILABLE", "detail": "Kho học liệu chưa sẵn sàng."}, status_code=503, media_type="application/problem+json", headers={"Cache-Control": "no-store"})
            except (HTTPException, RequestValidationError) as error:
                status = error.status_code if isinstance(error, HTTPException) else 422
                record("learning.request_rejected", status=status, code="AUTHENTICATION_REQUIRED" if status == 401 else "REQUEST_INVALID")
                detail = "Vui lòng đăng nhập." if status == 401 else "Yêu cầu học liệu không hợp lệ."
                return JSONResponse({"type": "https://campus247.example/problems/learning/request-invalid", "title": detail, "detail": detail, "status": status, "code": "AUTHENTICATION_REQUIRED" if status == 401 else "VALIDATION_FAILED", "request_id": getattr(request.state, "request_id", "")}, status_code=status, media_type="application/problem+json", headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
        return handle


def create_learning_router(service):
    router = APIRouter(prefix="/v1/learning", tags=["Learning"], route_class=LearningRoute)

    def actor(request, *, write=False):
        identity = get_current_identity(request)
        revalidate = getattr(request.state, "revalidate_identity", None)
        if revalidate:
            try:
                identity = revalidate()
            except Exception:  # noqa: BLE001 -- Every failed identity revalidation denies source access.
                raise LearningError(401, "AUTHENTICATION_REQUIRED", "Phiên đăng nhập không còn hiệu lực.") from None
        require(service is not None, 503, "LEARNING_UNAVAILABLE", "Học liệu chưa được cấu hình.")
        expected_reader = request.headers.get("X-Campus-Reader-Actor")
        if expected_reader is not None:
            require(expected_reader == identity.subject_id, 401, "READER_SESSION_CHANGED", "Tài khoản đọc đã thay đổi. Hãy mở lại bài giảng.")
        if write and "auth_token" in request.cookies:
            require(request.headers.get("X-Campus-Request") == "learning", 403, "CSRF_REJECTED", "Yêu cầu thay đổi không hợp lệ.")
            origin = request.headers.get("Origin")
            require(origin is None or origin.rstrip("/") == str(request.base_url).rstrip("/"), 403, "CSRF_REJECTED", "Nguồn yêu cầu không hợp lệ.")
        return identity

    def response(value, request=None, current=None):
        if isinstance(value, list):
            try:
                limit = int(request.query_params.get("limit", "20"))
            except ValueError:
                raise LearningError(422, "INVALID_PAGE_SIZE", "Số mục mỗi trang không hợp lệ.") from None
            require(1 <= limit <= 100, 422, "INVALID_PAGE_SIZE", "Số mục mỗi trang phải từ 1 đến 100.")
            binding = hashlib.sha256(json.dumps({"path": request.url.path, "actor": current.subject_id, "tenant": service.tenant_id, "query": sorted((k, v) for k, v in request.query_params.items() if k not in {"cursor", "limit"})}, sort_keys=True).encode()).hexdigest()
            offset = 0
            cursor = request.query_params.get("cursor")
            def row_id(row):
                return row.get("id") or row.get("subject_id")
            if cursor:
                try:
                    require(len(cursor) <= 2048, 422)
                    encoded, signature = cursor.split(".")
                    expected = hmac.new(service.signing_key, encoded.encode(), hashlib.sha256).hexdigest()
                    require(hmac.compare_digest(signature, expected), 422)
                    data = json.loads(base64.urlsafe_b64decode(encoded.encode()))
                    require(data["binding"] == binding, 422)
                    offset = next(i + 1 for i, row in enumerate(value) if row_id(row) == data["last_id"])
                except (ValueError, KeyError, StopIteration, LearningError):
                    raise LearningError(422, "INVALID_CURSOR", "Mã phân trang không thuộc danh sách hiện tại.") from None
            selected = value[offset:offset + limit]
            more = offset + limit < len(value)
            next_cursor = None
            if more and selected:
                encoded = base64.urlsafe_b64encode(json.dumps({"binding": binding, "last_id": row_id(selected[-1])}, separators=(",", ":")).encode()).decode()
                next_cursor = encoded + "." + hmac.new(service.signing_key, encoded.encode(), hashlib.sha256).hexdigest()
            return {"items": selected, "page": {"next_cursor": next_cursor, "has_more": more, "limit": limit}}
        return value

    @router.get("/capabilities")
    async def capabilities(request: Request):
        if service is None:
            get_current_identity(request)
            return JSONResponse({"available": False, "enabled": False, "read": False, "manage": False, "admin": False}, headers={"Cache-Control": "no-store"})
        current = actor(request)
        return JSONResponse(await service.query(current, "capabilities"), headers={"Cache-Control": "no-store"})

    def read_endpoint(kind, target_field=None):
        async def read(request: Request):
            current = actor(request)
            result = await service.query(current, kind, request.path_params.get(target_field) if target_field else None, version_id=request.query_params.get("version_id"))
            return JSONResponse(response(result, request, current), headers={"Cache-Control": "no-store"})
        return read

    reads = [("/terms", "terms", None), ("/courses", "courses", None), ("/admin/offerings", "admin_offerings", None), ("/admin/eligible-actors", "directory", None), ("/offerings", "offerings", None), ("/offerings/{offering_id}", "offering", "offering_id"), ("/offerings/{offering_id}/members", "members", "offering_id"), ("/offerings/{offering_id}/sessions", "sessions", "offering_id"), ("/sessions/{session_id}/materials", "materials", "session_id"), ("/materials/{material_id}", "material", "material_id"), ("/materials/{material_id}/versions", "versions", "material_id"), ("/versions/{version_id}", "version", "version_id"), ("/upload-intents/{upload_id}", "upload", "upload_id"), ("/me/reader-state/{version_id}", "reader_state", "version_id"), ("/me/bookmarks", "bookmarks", None), ("/me/notifications", "notifications", None)]
    reads += [("/me/annotations", "annotations", None), ("/versions/{version_id}/questions", "questions", "version_id"), ("/sessions/{session_id}/reading-instructions", "reading-instructions", "session_id"), ("/offerings/{offering_id}/presentations", "presentations", "offering_id"), ("/presentations/{presentation_id}", "presentation", "presentation_id")]
    for path, kind, target_field in reads:
        router.add_api_route(path, read_endpoint(kind, target_field), methods=["GET"], name="learning_" + kind)
    router.add_api_route(
        "/versions/{version_id}/session-contexts",
        read_endpoint("session_contexts", "version_id"),
        methods=["GET"],
        name="learning_session_contexts",
    )

    @router.get("/versions/{version_id}/pages/{page_no}/me/feedback", name="learning_page_feedback")
    async def read_feedback(request: Request, version_id: UUID, page_no: int = Path(ge=1, le=500)):
        result = await service.query(actor(request), "page_feedback", str(version_id), page_no=page_no)
        return JSONResponse(result, headers={"Cache-Control": "no-store"})

    @router.put("/versions/{version_id}/pages/{page_no}/me/feedback", name="learning_page-feedback-save")
    async def save_feedback(request: Request, version_id: UUID, body: dict[str, Any], page_no: int = Path(ge=1, le=500)):
        current = actor(request, write=True)
        key = request.headers.get("Idempotency-Key")
        require(bool(key), 422, "IDEMPOTENCY_REQUIRED", "Cần khóa chống ghi trùng.")
        payload = parse("page-feedback-save", body) | {"page_no": page_no}
        result = await service.command(current, "page-feedback-save", str(version_id), payload, key=key)
        return JSONResponse(result, headers={"Cache-Control": "no-store"})

    router.add_api_route("/sessions/{session_id}/page-feedback-window", read_endpoint("feedback_window", "session_id"),
                         methods=["GET"], name="learning_feedback_window")
    router.add_api_route("/sessions/{session_id}/page-feedback-summary", read_endpoint("feedback_summary", "session_id"),
                         methods=["GET"], name="learning_feedback_summary")
    router.add_api_route("/sessions/{session_id}/page-explanations", read_endpoint("page_explanations", "session_id"),
                         methods=["GET"], name="learning_page_explanations")
    router.add_api_route("/versions/{version_id}/change-set", read_endpoint("version_changes", "version_id"),
                         methods=["GET"], name="learning_version_changes")
    exit_reads = [
        ("/sessions/{session_id}/exit-tickets", "exit_tickets", "session_id"),
        ("/exit-tickets/{ticket_id}", "exit_ticket", "ticket_id"),
        ("/exit-tickets/{ticket_id}/me/submission", "exit_submission", "ticket_id"),
        ("/exit-tickets/{ticket_id}/submissions", "exit_submissions", "ticket_id"),
        ("/exit-tickets/{ticket_id}/review", "exit_review", "ticket_id"),
    ]
    for path, kind, target_field in exit_reads:
        router.add_api_route(path, read_endpoint(kind, target_field), methods=["GET"], name="learning_" + kind)

    def write_endpoint(action, target_field=None):
        async def write(request: Request, body: dict[str, Any]):
            current = actor(request, write=True)
            payload = parse(action, body)
            key = request.headers.get("Idempotency-Key")
            private_write = action in EXIT_TICKET_WRITES | IDEA_WRITES | OCR_WRITES or action in {
                "feedback-window-open", "page-feedback-withdraw", "page-explanation-create",
                "page-explanation-update", "version-change-save",
            }
            if request.method == "POST" or private_write:
                require(bool(key), 422, "IDEMPOTENCY_REQUIRED", "Cần khóa chống ghi trùng.")
            if action == "idea-card-create":
                replay = await service.replay_idea_creation(current, payload, key)
                if replay is not None:
                    return JSONResponse(replay, headers={"Cache-Control": "no-store"})
                payload["_idea_source"] = await service.verify_idea_anchor(current, payload["source"])
                refreshed = actor(request, write=True)
                require(refreshed.subject_id == current.subject_id and refreshed.session_id == current.session_id,
                        401, "READER_SESSION_CHANGED", "Phiên đọc đã thay đổi.")
                current = refreshed
            target = request.path_params.get(target_field) if target_field else payload.get("version_id")
            result = await service.command(current, action, target, payload, key=key,
                                           still_valid=lambda: actor(request, write=True))
            return JSONResponse(result, headers={"Cache-Control": "no-store"}) if private_write else result
        return write

    register_idea_routes(router, read_endpoint, write_endpoint)
    register_ocr_routes(router, read_endpoint, write_endpoint, actor, service)
    writes = [("POST", "/terms", "term-create", None), ("POST", "/courses", "course-create", None), ("POST", "/offerings", "offering-create", None), ("POST", "/offerings/{offering_id}/members", "member-create", "offering_id"), ("PATCH", "/offerings/{offering_id}/members/{member_id}", "member-update", "member_id"), ("POST", "/offerings/{offering_id}/archive", "archive", "offering_id"), ("POST", "/offerings/{offering_id}/sessions", "session-create", "offering_id"), ("PATCH", "/sessions/{session_id}", "session-update", "session_id"), ("PUT", "/offerings/{offering_id}/session-order", "session-order", "offering_id"), ("POST", "/offerings/{offering_id}/materials", "material-create", "offering_id"), ("PATCH", "/materials/{material_id}", "material-update", "material_id"), ("PUT", "/sessions/{session_id}/material-links", "material-links", "session_id"), ("POST", "/materials/{material_id}/upload-intents", "upload-create", "material_id"), ("POST", "/versions/{version_id}/publish", "publish", "version_id"), ("POST", "/versions/{version_id}/retract", "retract", "version_id"), ("POST", "/versions/{version_id}/cancel-publication", "cancel-publication", "version_id"), ("PUT", "/me/reader-state/{version_id}", "reader-state", "version_id"), ("POST", "/me/bookmarks", "bookmark-create", None), ("PATCH", "/me/bookmarks/{bookmark_id}", "bookmark-update", "bookmark_id"), ("PATCH", "/me/notifications/{notification_id}", "notification-update", "notification_id")]
    writes += [("POST", "/me/annotations", "annotation-create", None), ("PATCH", "/me/annotations/{annotation_id}", "annotation-update", "annotation_id"), ("POST", "/versions/{version_id}/questions", "question-create", "version_id"), ("PATCH", "/questions/{question_id}", "question-update", "question_id"), ("POST", "/questions/{question_id}/replies", "reply-create", "question_id"), ("POST", "/replies/{reply_id}/endorse", "reply-endorse", "reply_id"), ("POST", "/sessions/{session_id}/reading-instructions", "instruction-create", "session_id"), ("PATCH", "/reading-instructions/{instruction_id}", "instruction-update", "instruction_id"), ("POST", "/offerings/{offering_id}/presentations", "presentation-create", "offering_id"), ("POST", "/presentations/{presentation_id}/position", "presentation-position", "presentation_id"), ("POST", "/presentations/{presentation_id}/end", "presentation-end", "presentation_id")]
    for method, path, action, target_field in writes:
        router.add_api_route(path, write_endpoint(action, target_field), methods=[method], name="learning_" + action)
    router.add_api_route("/reading-instructions/{instruction_id}/seen", write_endpoint("instruction-seen", "instruction_id"),
                         methods=["PUT"], name="learning_instruction-seen")
    router.add_api_route("/me/annotations/{annotation_id}/share", write_endpoint("annotation-share", "annotation_id"),
                         methods=["POST"], name="learning_annotation-share")
    router.add_api_route("/sessions/{session_id}/page-feedback-window", write_endpoint("feedback-window-open", "session_id"),
                         methods=["PUT"], name="learning_feedback-window-open")
    router.add_api_route("/me/page-feedback/{feedback_id}", write_endpoint("page-feedback-withdraw", "feedback_id"),
                         methods=["PATCH"], name="learning_page-feedback-withdraw")
    router.add_api_route("/sessions/{session_id}/page-explanations", write_endpoint("page-explanation-create", "session_id"),
                         methods=["POST"], name="learning_page-explanation-create")
    router.add_api_route("/page-explanations/{explanation_id}", write_endpoint("page-explanation-update", "explanation_id"),
                         methods=["PATCH"], name="learning_page-explanation-update")
    router.add_api_route("/versions/{version_id}/change-set", write_endpoint("version-change-save", "version_id"),
                         methods=["PUT"], name="learning_version-change-save")
    exit_writes = [
        ("POST", "/sessions/{session_id}/exit-tickets", "exit-ticket-create", "session_id"),
        ("PATCH", "/exit-tickets/{ticket_id}", "exit-ticket-update", "ticket_id"),
        ("PUT", "/exit-tickets/{ticket_id}/me/submission", "exit-submission-save", "ticket_id"),
        ("PUT", "/exit-tickets/{ticket_id}/review", "exit-review-save", "ticket_id"),
    ]
    for method, path, action, target_field in exit_writes:
        router.add_api_route(path, write_endpoint(action, target_field), methods=[method], name="learning_" + action)

    @router.post("/action-previews")
    async def action_preview(request: Request, body: dict[str, Any]):
        current = actor(request, write=True)
        require(set(body).issubset({"action", "target_id", "payload"}), 422, "VALIDATION_FAILED", "Trường xem trước không hợp lệ.")
        require(isinstance(body.get("action"), str) and (body.get("target_id") is None or isinstance(body["target_id"], str)),
                422, "VALIDATION_FAILED", "Thao tác hoặc tài nguyên xem trước không hợp lệ.")
        action = ALIASES.get(body.get("action"), body.get("action"))
        payload = parse(action, body.get("payload", {}))
        return JSONResponse(await service.preview(current, action, body.get("target_id"), payload), headers={"Cache-Control": "no-store"})

    @router.post("/versions/{version_id}/publication-preview")
    async def publication_preview(version_id: str, request: Request, body: dict[str, Any]):
        current = actor(request, write=True)
        require(set(body).issubset({"action", "scheduled_at", "replacement_version_id", "change_set_revision"}), 422, "VALIDATION_FAILED", "Trường xem trước không hợp lệ.")
        action = body.get("action", "publish")
        require(action in {"publish", "retract", "cancel-publication"}, 422, "INVALID_ACTION", "Thao tác công bố không hợp lệ.")
        payload = parse(action, {k: v for k, v in body.items() if k != "action"})
        return await service.preview(current, action, version_id, payload)

    @router.put("/upload-intents/{upload_id}/content")
    async def upload_content(upload_id: str, request: Request):
        current = actor(request, write=True)
        return await service.receive(current, upload_id, request.stream())

    @router.post("/upload-intents/{upload_id}/complete")
    async def upload_complete(upload_id: str, request: Request):
        key = request.headers.get("Idempotency-Key")
        require(bool(key), 422, "IDEMPOTENCY_REQUIRED", "Cần khóa chống ghi trùng.")
        current = actor(request, write=True)
        return await service.complete(current, upload_id, key=key, still_valid=lambda: actor(request, write=True))

    @router.post("/upload-intents/{upload_id}/abort")
    async def upload_abort(upload_id: str, request: Request):
        current = actor(request, write=True)
        return await service.abort(current, upload_id, still_valid=lambda: actor(request, write=True))

    async def content(version_id, request, download=False):
        current = actor(request)
        row = await service.query(current, "content", version_id, download=download)
        path = service.blobs.path(row["storage_key"])
        require(path.is_file() and path.stat().st_size == row["byte_size"], 503, "BLOB_UNAVAILABLE", "Tệp học liệu không đầy đủ.")
        await service.blobs.verify(row["storage_key"], row["sha256"], row["byte_size"])
        # The checksum is awaited; a session revoked meanwhile must not receive the first byte.
        service.recheck(current, lambda: actor(request))
        etag = '"' + row["sha256"] + '"'
        selection = select_bytes(row["byte_size"], request.headers.get("Range"), method=request.method, if_range=request.headers.get("If-Range"), etag=etag)
        media_type = row.get('content_type', 'application/pdf')
        extension = 'pdf' if media_type == 'application/pdf' else 'pptx'
        headers = {"Content-Type": media_type, "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "Accept-Ranges": "bytes", "ETag": etag, "Content-Length": str(selection.length), "Content-Disposition": ('attachment' if download else 'inline') + '; filename="lecture.' + extension + '"'}
        if selection.content_range:
            headers["Content-Range"] = selection.content_range
        if request.method == "HEAD" or selection.status == 416:
            return Response(status_code=selection.status, headers=headers)
        return StreamingResponse(service.blobs.chunks(row["storage_key"], selection.start, selection.length), status_code=selection.status, headers=headers)

    @router.get("/versions/{version_id}/content")
    async def file_content(version_id: str, request: Request):
        return await content(version_id, request)

    @router.head("/versions/{version_id}/content")
    async def file_content_head(version_id: str, request: Request):
        return await content(version_id, request)

    @router.get("/versions/{version_id}/download")
    async def download_content(version_id: str, request: Request):
        return await content(version_id, request, download=True)

    @router.get("/presentations/{presentation_id}/events")
    async def presentation_events(presentation_id: str, request: Request):
        current = actor(request)
        await service.query(current, "presentation", presentation_id)
        async def events():
            sequence = None
            while not await request.is_disconnected():
                try:
                    row = await service.query(actor(request), "presentation", presentation_id)
                except LearningError:
                    yield 'event: unavailable\ndata: {"available":false}\n\n'
                    return
                if row["sequence"] != sequence:
                    sequence = row["sequence"]
                    yield f'id: {sequence}\nevent: position\ndata: {json.dumps(row, ensure_ascii=False)}\n\n'
                if row["status"] != "ACTIVE":
                    return
                await asyncio.sleep(.5)
        return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "private, no-store", "X-Accel-Buffering": "no"})

    @router.post("/versions/{version_id}/explain")
    async def explain(version_id: str, request: Request, body: LearningExplanationInput):
        current = actor(request, write=True)
        result = await service.explain(current, version_id, page_no=body.page_no, question=body.question, quote=body.quote, gateway=service.ai_gateway, verifier=service.ai_verifier)
        await service.query(actor(request), "content", version_id)
        return result

    return router
