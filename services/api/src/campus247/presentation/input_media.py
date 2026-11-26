"""F8.1 over HTTP: POST /v1/input/image:ocr. A signed-in person sends one PNG; the text comes back and nothing is kept."""
from __future__ import annotations

from fastapi import APIRouter, File, Request, UploadFile
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from campus247.application.input_media.image_ocr import MAX_BYTES
from campus247.ports.campus_ops import OpsError
from campus247.presentation.identity import get_current_identity

NO_STORE = {"Cache-Control": "no-store"}


def create_input_media_router(image_service) -> APIRouter:
    r = APIRouter(tags=["Input media"])

    @r.post("/v1/input/image:ocr")
    async def image_ocr(request: Request, image: UploadFile = File(...)):
        who = get_current_identity(request)
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > MAX_BYTES + 64 * 1024:
            raise OpsError(413, "IMAGE_TOO_LARGE", "Ảnh lớn hơn 4 MB.")
        data = await image.read(MAX_BYTES + 1)
        result = await run_in_threadpool(image_service.ocr, who.subject_id, data)
        return JSONResponse(result, headers=NO_STORE)

    return r
