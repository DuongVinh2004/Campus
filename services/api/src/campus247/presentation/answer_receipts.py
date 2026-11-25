"""GET /v1/answer-receipts/{id}: the owner re-checks an answer against the current release (F4.2)."""
from __future__ import annotations

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

from campus247.presentation.identity import get_current_identity


def create_answer_receipts_router(service) -> APIRouter:
    r = APIRouter(tags=["Answer evidence"])

    @r.get("/v1/answer-receipts/{receipt_id}")
    def open_receipt(receipt_id: str, request: Request):
        who = get_current_identity(request)
        return JSONResponse(service.open(who.subject_id, receipt_id), headers={"Cache-Control": "no-store"})

    return r
