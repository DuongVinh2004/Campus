"""Feature flags over HTTP (F0.4/F0.6): the gate that closes a disabled feature's routes, the public snapshot and the admin API."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from campus247.ports.campus_ops import OpsError

NO_STORE = {"Cache-Control": "no-store"}
BLOCKED = {"total": 0, "by_key": {}}  # read by the ops metrics (F0.8)


def disabled_response(key: str, path: str) -> JSONResponse:
    BLOCKED["total"] += 1
    BLOCKED["by_key"][key] = BLOCKED["by_key"].get(key, 0) + 1
    return JSONResponse(status_code=404, headers=NO_STORE, content={
        "type": "https://campus247.example/problems/feature-disabled", "title": "Tính năng này đang tắt.", "status": 404,
        "detail": "Tính năng này đang tắt.", "code": "FEATURE_DISABLED", "feature": key, "retryable": False})


class FeatureGateMiddleware(BaseHTTPMiddleware):
    """Return 404 FEATURE_DISABLED for a route whose feature is off. Sits inside the identity middleware so audience rules see the caller."""

    def __init__(self, app, service) -> None:
        super().__init__(app)
        self._service = service

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/v1/"):
            try:
                blocked = self._service.gate(path, request.method, getattr(request.state, "identity", None))
            except Exception:  # noqa: BLE001 -- a broken flag lookup must not take the whole API down
                blocked = None
            if blocked:
                return disabled_response(blocked, path)
        return await call_next(request)


class ChangeBody(BaseModel):
    value: Any = None
    audience: dict = Field(default_factory=dict)
    expires_at: Optional[str] = None
    reason: str = ""
    expected_version: int
    remove: bool = False


class ConfirmBody(BaseModel):
    preview_id: str
    confirmation_token: str = ""


def create_features_router(service) -> APIRouter:
    r = APIRouter(tags=["Feature flags"])

    def actor(request: Request):
        from campus247.presentation.identity import get_current_identity
        return get_current_identity(request)

    @r.get("/v1/features")
    def features(request: Request, if_none_match: Optional[str] = Header(None)):
        snap = service.snapshot(getattr(request.state, "identity", None), client_only=True)
        digest = hashlib.sha256(json.dumps(snap["features"], sort_keys=True).encode()).hexdigest()[:12]
        etag = f'"{snap["version"]}-{digest}"'
        if if_none_match == etag:
            return Response(status_code=304, headers={**NO_STORE, "ETag": etag})
        return JSONResponse(snap, headers={**NO_STORE, "ETag": etag})

    @r.get("/v1/admin/features")
    def admin_list(request: Request):
        who = actor(request)
        service.require_admin(who)
        return JSONResponse(service.admin_items(), headers=NO_STORE)

    @r.get("/v1/admin/features/audit")
    def admin_audit(request: Request, key: Optional[str] = None, cursor: Optional[int] = None, limit: int = 50):
        return JSONResponse(service.audit(actor(request), key, cursor, limit), headers=NO_STORE)

    @r.post("/v1/admin/features/confirm")
    def admin_confirm(body: ConfirmBody, request: Request, idempotency_key: Optional[str] = Header(None)):
        receipt = service.confirm_change(actor(request), body.preview_id, body.confirmation_token, idempotency_key or "")
        return JSONResponse({"receipt_id": receipt["receipt_id"], "key": receipt["key"], "value": receipt["after"].get("value"),
                             "removed": bool(receipt["after"].get("removed")), "version": receipt["version"], "applied_at": receipt["applied_at"],
                             "replayed": receipt["replayed"]}, headers=NO_STORE)

    @r.post("/v1/admin/features/{key}/preview")
    def admin_preview(key: str, body: ChangeBody, request: Request):
        return JSONResponse(service.preview_change(actor(request), key, value=body.value, audience=body.audience, expires_at=body.expires_at,
                                                   reason=body.reason, expected_version=body.expected_version, remove=body.remove), headers=NO_STORE)

    return r
