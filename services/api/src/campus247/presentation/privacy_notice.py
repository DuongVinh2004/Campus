from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import JSONResponse

from campus247.application.privacy.consent import (
    PrivacyConsentService,
    ServiceUnavailableError,
)
from campus247.presentation.identity import get_current_identity


class RecordConsentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purpose: str = Field(min_length=1, max_length=100)
    decision: str = Field(min_length=1, max_length=100)
    notice_version: str = Field(min_length=1, max_length=100)


def create_privacy_router(consent_service: PrivacyConsentService, authorize=None) -> APIRouter:
    router = APIRouter(tags=["Privacy"])

    @router.get("/v1/privacy/notice")
    async def get_privacy_notice() -> JSONResponse:
        try:
            notice = consent_service.get_active_notice()
        except ServiceUnavailableError:
            raise HTTPException(status_code=503, detail="Active privacy notice is currently unavailable")

        content = {
            "notice_id": notice.notice_id,
            "version": notice.version,
            "effective_at": notice.effective_at.isoformat(),
            "status": notice.status,
            "disclaimer": notice.disclaimer,
            "data_categories": notice.data_categories,
            "purposes": notice.purposes,
            "retention_summary": notice.retention_summary,
        }
        return JSONResponse(
            status_code=200,
            content=content,
            headers={
                "ETag": f'"{notice.version}"',
                "Cache-Control": "public, max-age=3600",
            },
        )

    @router.get("/v1/privacy/consents")
    async def list_my_consents(request: Request) -> JSONResponse:
        identity = get_current_identity(request)
        if authorize is not None:
            authorize(identity)
        consents = consent_service.list_user_consents(identity.subject_id)

        items = [
            {
                "id": c.id,
                "purpose": c.purpose,
                "decision": c.decision,
                "notice_version": c.notice_version,
                "recorded_at": c.recorded_at.isoformat(),
            }
            for c in consents
        ]
        return JSONResponse(
            status_code=200,
            content={"items": items},
            headers={"Cache-Control": "no-store"},
        )

    @router.post("/v1/privacy/consents")
    async def record_consent(body: RecordConsentBody, request: Request) -> JSONResponse:
        identity = get_current_identity(request)
        if authorize is not None:
            authorize(identity)
        try:
            record = consent_service.record_consent(
                actor=identity,
                purpose=body.purpose,
                decision=body.decision,
                notice_version=body.notice_version,
            )
        except ServiceUnavailableError:
            raise HTTPException(status_code=503, detail="Consent service unavailable")
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        content = {
            "id": record.id,
            "purpose": record.purpose,
            "decision": record.decision,
            "notice_version": record.notice_version,
            "recorded_at": record.recorded_at.isoformat(),
        }
        return JSONResponse(
            status_code=201,
            content=content,
            headers={
                "Location": f"/v1/privacy/consents/{record.id}",
                "Cache-Control": "no-store",
            },
        )

    return router
