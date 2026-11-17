"""For knowledge managers: which sources are behind answers marked "not helpful". Counts only; see application/knowledge/answer_quality.py."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from campus247.application.knowledge.answer_quality import AnswerQualityStore, titled_report
from campus247.ports.identity import IdentityRole
from campus247.presentation.identity import get_current_identity

NO_STORE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
MANAGERS = {IdentityRole.KNOWLEDGE_ADMIN, IdentityRole.SYSTEM_ADMIN}
LOG = logging.getLogger("campus247.quality")


def create_quality_router(store: AnswerQualityStore, freshness_service, *, clock=None) -> APIRouter:
    from datetime import UTC, datetime
    router = APIRouter(tags=["Knowledge quality"])

    @router.get("/v1/knowledge/answer-quality")
    async def answer_quality(request: Request, days: int = Query(30, ge=1, le=180)):
        identity = get_current_identity(request)
        if not MANAGERS.intersection(identity.roles):
            return JSONResponse({"status": 403, "code": "FORBIDDEN", "detail": "Chỉ quản trị tri thức mới xem được thống kê này."}, status_code=403, headers=NO_STORE)
        now = clock() if clock else datetime.now(UTC)
        try:
            body = await titled_report(store, freshness_service, now=now, days=days)
        except Exception as error:  # noqa: BLE001 -- titles come from the knowledge database; the counts themselves are still useful
            LOG.warning("answer_quality_titles_failed kind=%s", type(error).__name__)
            body = store.report(now=now, days=days)
            for source in body["sources"]:
                source["title"] = source["owner_unit"] = None
                source["in_current_release"] = False
        return JSONResponse(body, headers=NO_STORE)

    return router
