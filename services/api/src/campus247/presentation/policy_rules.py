"""F2 over HTTP: the public what-if simulator (/v1/policy-simulator) and the rule authoring API (/v1/policy-rules)."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Any, Optional

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

from campus247.application.policy_rules.service import PolicyInputInvalid
from campus247.ports.campus_ops import OpsError
from campus247.presentation.identity import get_current_identity

NO_STORE = {"Cache-Control": "no-store"}
RATE = 30  # evaluations per person per minute


class EvaluateBody(BaseModel):
    topic: str = Field(max_length=80)
    inputs: dict[str, Any] = Field(default_factory=dict)
    as_of: Optional[str] = Field(default=None, max_length=32)
    cohort: Optional[str] = Field(default=None, max_length=8)
    program: Optional[str] = Field(default=None, max_length=40)


class MatchBody(BaseModel):
    text: str = Field(max_length=1000)


class WhatIfBody(EvaluateBody):
    vary: str = Field(max_length=80)
    points: int = Field(default=11, ge=2, le=41)


class DraftBody(BaseModel):
    body: dict
    origin: str = "MANUAL"


class DraftUpdate(BaseModel):
    body: dict
    row_version: int


class ValidateBody(BaseModel):
    gold: Optional[list[dict]] = None


class ReviewBody(BaseModel):
    verdict: str
    note: str = ""


class ConfirmBody(BaseModel):
    preview_id: str
    confirmation_token: str = ""


def register_policy_rule_errors(app) -> None:
    @app.exception_handler(PolicyInputInvalid)
    async def invalid(request: Request, exc: PolicyInputInvalid):
        return JSONResponse(status_code=422, headers=NO_STORE, content={
            "type": "https://campus247.example/problems/policy-input-invalid", "title": exc.detail, "status": 422,
            "detail": exc.detail, "code": "POLICY_INPUT_INVALID", "errors": exc.errors, "retryable": False})


def create_policy_rules_router(service, *, now=time.monotonic) -> APIRouter:
    r = APIRouter(tags=["Policy rules"])
    hits: dict[str, deque] = defaultdict(deque)

    def out(content, status=200):
        return JSONResponse(content, status_code=status, headers=NO_STORE)

    def limited(who) -> None:
        window, t = hits[who.subject_id], now()
        while window and t - window[0] > 60:
            window.popleft()
        if len(window) >= RATE:
            raise OpsError(429, "RATE_LIMITED", "Bạn thao tác quá nhanh, thử lại sau một phút.")
        window.append(t)

    # ---- public simulator (flag policy.simulator)
    @r.get("/v1/policy-simulator/topics")
    def topics(request: Request):
        get_current_identity(request)
        return out({"topics": service.topics()})

    @r.get("/v1/policy-simulator/topics/{topic}/form")
    def form(topic: str, request: Request, as_of: Optional[str] = None, cohort: Optional[str] = None, program: Optional[str] = None):
        get_current_identity(request)
        return out(service.form(topic, as_of, cohort, program))

    @r.post("/v1/policy-simulator/evaluate")
    def evaluate(body: EvaluateBody, request: Request):
        who = get_current_identity(request)
        limited(who)
        return out(service.evaluate(body.topic, body.inputs, as_of=body.as_of, cohort=body.cohort, program=body.program))

    @r.post("/v1/policy-simulator/match")
    def match(body: MatchBody, request: Request):
        who = get_current_identity(request)
        limited(who)
        return out(service.match(body.text))

    @r.post("/v1/policy-simulator/what-if")
    def what_if(body: WhatIfBody, request: Request):
        who = get_current_identity(request)
        limited(who)
        return out(service.what_if(body.topic, body.inputs, body.vary, as_of=body.as_of, cohort=body.cohort, program=body.program, points=body.points))

    # ---- authoring (flag policy.rules)
    @r.get("/v1/policy-rules")
    def list_rules(request: Request, topic: Optional[str] = None, status: Optional[str] = None):
        return out(service.list_rules(get_current_identity(request), topic, status))

    @r.post("/v1/policy-rules/drafts")
    def create_draft(body: DraftBody, request: Request):
        return out(service.create_draft(get_current_identity(request), body.body, body.origin), 201)

    @r.get("/v1/policy-rules/drafts/{draft_id}")
    def draft_view(draft_id: str, request: Request):
        return out(service.draft_view(get_current_identity(request), draft_id))

    @r.get("/v1/policy-rules/rules/{rule_id}")
    def rule_view(rule_id: str, request: Request):
        return out(service.rule_view(get_current_identity(request), rule_id))

    @r.put("/v1/policy-rules/drafts/{draft_id}")
    def update_draft(draft_id: str, body: DraftUpdate, request: Request):
        return out(service.update_draft(get_current_identity(request), draft_id, body.body, body.row_version))

    @r.post("/v1/policy-rules/drafts/{draft_id}/validate")
    def validate(draft_id: str, body: ValidateBody, request: Request):
        return out(service.validate_draft(get_current_identity(request), draft_id, body.gold))

    @r.post("/v1/policy-rules/drafts/{draft_id}/review")
    def review(draft_id: str, body: ReviewBody, request: Request):
        return out(service.review(get_current_identity(request), draft_id, body.verdict, body.note))

    @r.post("/v1/policy-rules/drafts/{draft_id}/publish-preview")
    def publish_preview(draft_id: str, request: Request):
        return out(service.publish_preview(get_current_identity(request), draft_id))

    @r.post("/v1/policy-rules/rules/{rule_id}/retire-preview")
    def retire_preview(rule_id: str, request: Request):
        return out(service.retire_preview(get_current_identity(request), rule_id))

    @r.post("/v1/policy-rules/confirm")
    def confirm(body: ConfirmBody, request: Request, idempotency_key: Optional[str] = Header(None)):
        return out(service.confirm(get_current_identity(request), body.preview_id, body.confirmation_token, idempotency_key or ""))

    @r.get("/v1/policy-rules/rules/{rule_id}/versions/{version}/vectors")
    def vectors(rule_id: str, version: int, request: Request):
        return out(service.vectors(get_current_identity(request), rule_id, version))

    return r
