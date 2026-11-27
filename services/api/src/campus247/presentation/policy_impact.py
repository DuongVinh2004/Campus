"""F3 over HTTP: which units a new release changed, what depends on them, and fact conflicts. Admins only; counts and unit paths, no user data."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel
from starlette.responses import JSONResponse

from campus247.ports.campus_ops import OpsError
from campus247.ports.identity import IdentityRole
from campus247.presentation.identity import get_current_identity

NO_STORE = {"Cache-Control": "no-store"}
ALLOWED = {IdentityRole.KNOWLEDGE_ADMIN, IdentityRole.SYSTEM_ADMIN}


class AnalyzeBody(BaseModel):
    old_release: Optional[str] = None
    new_release: Optional[str] = None


def create_policy_impact_router(service) -> APIRouter:
    r = APIRouter(tags=["Policy impact"])

    def admin(request: Request):
        who = get_current_identity(request)
        if not ALLOWED & set(who.roles):
            raise OpsError(403, "FORBIDDEN", "Chỉ quản trị tri thức mới xem được tác động.")
        return who

    def out(content, status=200):
        return JSONResponse(content, status_code=status, headers=NO_STORE)

    @r.get("/v1/policy-impact/releases")
    def releases(request: Request):
        admin(request)
        return out(service.releases())

    @r.get("/v1/policy-impact/report")
    def report(request: Request, release: Optional[str] = None):
        admin(request)
        return out(service.report(release))

    @r.post("/v1/policy-impact/snapshot")
    def snapshot(request: Request):
        admin(request)
        return out(service.on_new_release())

    @r.post("/v1/policy-impact/analyze")
    def analyze(body: AnalyzeBody, request: Request):
        admin(request)
        return out(service.analyze(body.old_release, body.new_release))

    @r.get("/v1/policy-conflicts")
    def conflicts(request: Request):
        admin(request)
        return out(service.conflicts())

    return r
