"""Bounded authenticated source read transport; domain decisions remain in service."""
import asyncio

from fastapi import APIRouter, HTTPException, Request
from starlette.responses import JSONResponse

from campus247.application.conversation.citation_source import (
    CitationSourceService,
    CitationSourceUnavailable,
)
from campus247.bootstrap.telemetry import extract_trace_context


def create_citation_source_router(*, service: CitationSourceService) -> APIRouter:
    router = APIRouter()

    @router.get("/v1/conversations/{conversation_id}/messages/{message_id}/citations/{citation_id}/source")
    async def read_source(conversation_id: str, message_id: str, citation_id: str, request: Request):
        identity = getattr(request.state, "identity", None)
        if identity is None:
            raise HTTPException(status_code=401, detail="Phiên đăng nhập hợp lệ là bắt buộc.")
        try:
            async with asyncio.timeout(5):
                result = await service.read(identity, conversation_id, message_id, citation_id,
                    trace_id=extract_trace_context({})["trace_id"],
                    request_id=getattr(request.state, "request_id", ""))
        except (CitationSourceUnavailable, TimeoutError):
            raise HTTPException(status_code=503, detail="Chưa thể xác minh quyền truy cập nguồn. Hãy thử lại sau.") from None
        return JSONResponse(result, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})

    return router
