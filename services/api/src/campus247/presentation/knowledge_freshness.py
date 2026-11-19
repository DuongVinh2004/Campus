"""Source freshness for people who manage the knowledge base: which sources are due, and a way to say "I checked this one"."""
from __future__ import annotations

import re

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from campus247.application.knowledge.freshness_service import FreshnessService
from campus247.ports.identity import IdentityRole
from campus247.presentation.identity import get_current_identity

NO_STORE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
MANAGERS = {IdentityRole.KNOWLEDGE_ADMIN, IdentityRole.SYSTEM_ADMIN}
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class ReviewedBody(BaseModel):
    note: str = Field(min_length=10, max_length=1000)


def problem(status: int, code: str, detail: str) -> JSONResponse:
    return JSONResponse({"status": status, "code": code, "detail": detail}, status_code=status, headers=NO_STORE)


def create_freshness_router(service: FreshnessService) -> APIRouter:
    router = APIRouter(tags=["Knowledge freshness"])

    def manager(request: Request):
        identity = get_current_identity(request)
        return identity if MANAGERS.intersection(identity.roles) else None

    @router.get("/v1/knowledge/freshness")
    async def report(request: Request):
        if manager(request) is None:
            return problem(403, "FORBIDDEN", "Chỉ quản trị tri thức mới xem được hiệu lực của nguồn.")
        return JSONResponse(await service.report(), headers=NO_STORE)

    @router.post("/v1/knowledge/freshness/{source_id}/reviewed")
    async def reviewed(source_id: str, body: ReviewedBody, request: Request):
        identity = manager(request)
        if identity is None:
            return problem(403, "FORBIDDEN", "Chỉ quản trị tri thức mới ghi nhận được việc rà soát nguồn.")
        if not UUID.match(source_id):
            return problem(422, "VALIDATION_FAILED", "Mã nguồn không hợp lệ.")
        try:
            result = await service.mark_reviewed(source_id, identity.subject_id, body.note)
        except LookupError:
            return problem(404, "NOT_FOUND", "Nguồn không thuộc bản phát hành hiện hành.")
        return JSONResponse(result, headers=NO_STORE)

    return router
