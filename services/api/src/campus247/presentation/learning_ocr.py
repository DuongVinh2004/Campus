"""Typed request shapes and authenticated routes for reviewed accessible text."""
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Path, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.responses import JSONResponse

PageNumber = Annotated[int, Field(strict=True, ge=1, le=500)]
Revision = Annotated[int, Field(strict=True, ge=1)]
Cell = Annotated[str, Field(max_length=200)]
Row = Annotated[list[Cell], Field(min_length=1, max_length=12)]
Pages = Annotated[list[PageNumber], Field(min_length=1, max_length=100)]
ReviewOperation = Literal["REVIEW_PAGE", "PUBLISH", "WITHDRAW", "CLONE"]


class LearningOcrBlockReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=160)
    type: Literal["PARAGRAPH", "HEADING", "LIST", "TABLE", "FORMULA", "FIGURE", "PLACEHOLDER"]
    text: str | None = Field(default=None, max_length=4000)
    level: int | None = Field(default=None, strict=True, ge=2, le=4)
    items: list[Annotated[str, Field(max_length=500)]] | None = Field(default=None, max_length=40)
    ordered: bool | None = Field(default=None, strict=True)
    headers: Row | None = None
    rows: list[Row] | None = Field(default=None, max_length=40)
    risk_verified: bool | None = Field(default=None, strict=True)


class LearningOcrReleaseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: ReviewOperation
    revision: Revision
    page_no: PageNumber | None = None
    candidate_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    review_confirmed: bool | None = Field(default=None, strict=True)
    blocks: list[LearningOcrBlockReview] | None = Field(default=None, max_length=600)
    pages: Pages | None = None
    expected_current_release_id: UUID | None = None
    preview_id: str | None = None
    confirmation_token: str | None = None

    @model_validator(mode="after")
    def operation_fields(self):
        fields = self.model_fields_set - {"operation", "revision", "preview_id", "confirmation_token"}
        if self.operation == "REVIEW_PAGE":
            if fields != {"page_no", "candidate_sha256", "review_confirmed", "blocks"} or (
                self.page_no is None or self.candidate_sha256 is None or self.review_confirmed is not True or self.blocks is None
            ):
                raise ValueError("A page review requires the exact candidate and explicit confirmation")
        elif self.operation == "PUBLISH":
            if fields != {"pages", "expected_current_release_id"} or self.pages is None:
                raise ValueError("Publication requires selected pages and the expected release")
        elif fields:
            raise ValueError("Unexpected fields for this OCR operation")
        return self


def ocr_input_models(model):
    return {
        "ocr-job-create": model("LearningOcrJobInput", pages=(Pages, ...)),
        "ocr-job-update": model("LearningOcrJobUpdate", operation=(Literal["CANCEL", "RESUME"], ...), revision=(Revision, ...)),
        "ocr-release-update": LearningOcrReleaseUpdate,
    }


def register_ocr_routes(router, read_endpoint, write_endpoint, actor, service):
    for path, kind, target in (
        ("/versions/{version_id}/ocr-jobs", "ocr_jobs", "version_id"),
        ("/ocr-jobs/{job_id}", "ocr_job", "job_id"),
        ("/versions/{version_id}/accessible-text", "accessible_text", "version_id"),
    ):
        router.add_api_route(path, read_endpoint(kind, target), methods=["GET"], name=f"learning_{kind}")
    for path, method, action, target in (
        ("/versions/{version_id}/ocr-jobs", "POST", "ocr-job-create", "version_id"),
        ("/ocr-jobs/{job_id}", "PATCH", "ocr-job-update", "job_id"),
        ("/ocr-releases/{release_id}", "PATCH", "ocr-release-update", "release_id"),
    ):
        router.add_api_route(path, write_endpoint(action, target), methods=[method], name=f"learning_{action}")

    @router.get("/ocr-releases/{release_id}", name="learning_ocr_release")
    async def review(request: Request, release_id: UUID, page_no: int | None = Query(default=None, ge=1, le=500)):
        current = actor(request)
        result = await service.query(current, "ocr_release", str(release_id), page_no=page_no)
        return JSONResponse(result, headers={"Cache-Control": "no-store"})

    @router.get("/versions/{version_id}/accessible-text/pages/{page_no}", name="learning_accessible_text_page")
    async def page(request: Request, version_id: UUID, page_no: int = Path(ge=1, le=500)):
        current = actor(request)
        result = await service.query(current, "accessible_text_page", str(version_id), page_no=page_no)
        return JSONResponse(result, headers={"Cache-Control": "no-store"})

    @router.get("/versions/{version_id}/accessible-text/search", name="learning_accessible_text_search")
    async def search(request: Request, version_id: UUID, q: str = Query(min_length=1, max_length=120)):
        current = actor(request)
        result = await service.query(current, "accessible_text_search", str(version_id), q=q)
        return JSONResponse(result, headers={"Cache-Control": "no-store"})
