"""For knowledge managers: which sources are behind answers marked "not helpful", and which refusals keep pointing at the same sources.

Counts only; see application/knowledge/answer_quality.py. Nothing here exposes a person, a conversation or a question.
"""
from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from campus247.application.knowledge.answer_quality import GAP_ACTIONS, AnswerQualityStore, titled_report
from campus247.ports.identity import IdentityRole
from campus247.presentation.identity import get_current_identity

NO_STORE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
MANAGERS = {IdentityRole.KNOWLEDGE_ADMIN, IdentityRole.SYSTEM_ADMIN}
LOG = logging.getLogger("campus247.quality")
CLUSTER_KEY = re.compile(r"^[0-9a-f]{40}$")


class DecisionBody(BaseModel):
    action: str = Field(max_length=20)
    note: str = Field(min_length=1, max_length=500)
    release_ref: str = Field(default="", max_length=100)


def _problem(status: int, code: str, detail: str) -> JSONResponse:
    return JSONResponse({"status": status, "code": code, "detail": detail}, status_code=status, headers=NO_STORE)


async def _title_gaps(gaps: dict, freshness_service) -> None:
    """Name the sources of each cluster (sources of the current release only; others stay as ids)."""
    try:
        titles = {row["version_id"]: row for row in await freshness_service.current_rows()}
    except Exception as error:  # noqa: BLE001 -- the counts are useful without titles
        LOG.warning("answer_gaps_titles_failed kind=%s", type(error).__name__)
        titles = {}
    for cluster in gaps["clusters"]:
        cluster["sources"] = [{"version_id": v, "title": titles.get(v, {}).get("title"), "owner_unit": titles.get(v, {}).get("owner_unit")}
                              for v in cluster["version_ids"]]


def create_quality_router(store: AnswerQualityStore, freshness_service, *, clock=None) -> APIRouter:
    from datetime import UTC, datetime
    router = APIRouter(tags=["Knowledge quality"])

    def manager(request: Request):
        identity = get_current_identity(request)
        return identity if MANAGERS.intersection(identity.roles) else None

    @router.get("/v1/knowledge/answer-quality")
    async def answer_quality(request: Request, days: int = Query(30, ge=1, le=180)):
        if manager(request) is None:
            return _problem(403, "FORBIDDEN", "Chỉ quản trị tri thức mới xem được thống kê này.")
        now = clock() if clock else datetime.now(UTC)
        try:
            body = await titled_report(store, freshness_service, now=now, days=days)
        except Exception as error:  # noqa: BLE001 -- titles come from the knowledge database; the counts themselves are still useful
            LOG.warning("answer_quality_titles_failed kind=%s", type(error).__name__)
            body = store.report(now=now, days=days)
            for source in body["sources"]:
                source["title"] = source["owner_unit"] = None
                source["in_current_release"] = False
        body["gaps"] = store.gaps_report(now=now, days=days)
        await _title_gaps(body["gaps"], freshness_service)
        return JSONResponse(body, headers=NO_STORE)

    @router.post("/v1/knowledge/answer-quality/gaps/{cluster_key}/decision")
    async def decide(cluster_key: str, body: DecisionBody, request: Request):
        identity = manager(request)
        if identity is None:
            return _problem(403, "FORBIDDEN", "Chỉ quản trị tri thức mới ghi nhận được quyết định này.")
        if not CLUSTER_KEY.match(cluster_key) or body.action not in GAP_ACTIONS:
            return _problem(422, "VALIDATION_FAILED", "Cụm hoặc hành động không hợp lệ.")
        try:
            store.decide(cluster_key, action=body.action, note=body.note, release_ref=body.release_ref, actor=identity.subject_id)
        except ValueError:
            return _problem(422, "VALIDATION_FAILED", "Cần ghi chú (tối đa 500 ký tự); trạng thái đã xử lý cần mã bản phát hành đã thay đổi.")
        except LookupError:
            return _problem(404, "NOT_FOUND", "Không tìm thấy cụm này.")
        return JSONResponse({"cluster_key": cluster_key, "action": body.action}, headers=NO_STORE)

    return router
