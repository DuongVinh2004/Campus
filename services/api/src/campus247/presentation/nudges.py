"""F6 over HTTP: today's tasks, done / snooze / restore, and the nudge preferences of the signed-in person."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel
from starlette.responses import JSONResponse

from campus247.application.proactive.engine import ALL_KINDS
from campus247.ports.campus_ops import OpsError
from campus247.presentation.identity import get_current_identity

NO_STORE = {"Cache-Control": "no-store"}


class SnoozeBody(BaseModel):
    hours: int


class PrefsBody(BaseModel):
    preferences: dict[str, bool]


def create_nudges_router(engine) -> APIRouter:
    r = APIRouter(tags=["Nudges"])

    def out(content, status=200):
        return JSONResponse(content, status_code=status, headers=NO_STORE)

    def owned(subject_id: str, item_key: str) -> None:
        if not engine.owns(subject_id, item_key):
            raise OpsError(404, "NUDGE_NOT_FOUND", "Không tìm thấy việc này.")

    @r.get("/v1/nudges/today")
    def today(request: Request):
        return out({"items": engine.today(get_current_identity(request).subject_id)})

    @r.get("/v1/nudges/preferences")
    def preferences(request: Request):
        return out({"preferences": engine.preferences(get_current_identity(request).subject_id)})

    @r.put("/v1/nudges/preferences")
    def set_preferences(body: PrefsBody, request: Request):
        who = get_current_identity(request)
        unknown = set(body.preferences) - ALL_KINDS - {"DIGEST"}
        if unknown:
            raise OpsError(422, "NUDGE_PREFERENCE_UNKNOWN", "Loại nhắc không hợp lệ.")
        for kind, enabled in body.preferences.items():
            engine.set_preference(who.subject_id, kind, enabled)
        return out({"preferences": engine.preferences(who.subject_id)})

    @r.post("/v1/nudges/{item_key}/done")
    def done(item_key: str, request: Request):
        who = get_current_identity(request)
        owned(who.subject_id, item_key)
        engine.mark(who.subject_id, item_key, "DONE")
        return out({"key": item_key, "state": "DONE"})

    @r.post("/v1/nudges/{item_key}/snooze")
    def snooze(item_key: str, body: SnoozeBody, request: Request):
        who = get_current_identity(request)
        if body.hours not in (1, 3, 24):
            raise OpsError(422, "NUDGE_SNOOZE_INVALID", "Chỉ hoãn được 1, 3 hoặc 24 giờ.")
        owned(who.subject_id, item_key)
        engine.mark(who.subject_id, item_key, "SNOOZED", hours=body.hours)
        return out({"key": item_key, "state": "SNOOZED", "hours": body.hours})

    @r.post("/v1/nudges/{item_key}/restore")
    def restore(item_key: str, request: Request):
        who = get_current_identity(request)
        engine.mark(who.subject_id, item_key, "RESTORED")
        return out({"key": item_key, "state": "RESTORED"})

    return r
