"""GET /v1/answer-receipts/{id}: the owner re-checks an answer against the current release (F4.2)."""
from __future__ import annotations

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

from campus247.presentation.identity import get_current_identity

# Staff who work on answers see the reason codes of dropped statements (decision D5); everyone else sees counts only.
REASON_CODE_ROLES = {"SUPPORT_OFFICER", "KNOWLEDGE_ADMIN"}


def _view(receipt: dict, who) -> dict:
    roles = {str(getattr(role, "value", role)) for role in (getattr(who, "roles", None) or ())}
    return receipt | {"show_reason_codes": bool(roles & REASON_CODE_ROLES)}


def create_answer_receipts_router(service) -> APIRouter:
    r = APIRouter(tags=["Answer evidence"])

    @r.get("/v1/answer-receipts/by-message/{conversation_id}/{message_id}")
    def open_for_message(conversation_id: str, message_id: str, request: Request):
        who = get_current_identity(request)
        return JSONResponse(_view(service.open_for_message(who.subject_id, conversation_id, message_id), who), headers={"Cache-Control": "no-store"})

    @r.get("/v1/answer-receipts/{receipt_id}")
    def open_receipt(receipt_id: str, request: Request):
        who = get_current_identity(request)
        return JSONResponse(_view(service.open(who.subject_id, receipt_id), who), headers={"Cache-Control": "no-store"})

    return r
