"""F8.1/F8.5 over HTTP: POST /v1/input/image:ocr (one PNG) and POST /v1/input/voice:transcribe (one recording, local recognizer).

A signed-in person sends the file; the text comes back for them to check and send themselves; nothing is kept."""
from __future__ import annotations

from fastapi import APIRouter, File, Request, UploadFile
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from campus247.application.input_media.image_ocr import MAX_BYTES
from campus247.ports.campus_ops import OpsError
from campus247.presentation.identity import get_current_identity

NO_STORE = {"Cache-Control": "no-store"}


def create_input_media_router(image_service, voice_service=None) -> APIRouter:
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

    @r.post("/v1/input/voice:transcribe")
    async def voice_transcribe(request: Request, audio: UploadFile = File(...)):
        from campus247.application.input_media.voice import MAX_BYTES as VOICE_MAX
        who = get_current_identity(request)
        if voice_service is None:
            raise OpsError(503, "VOICE_UNAVAILABLE", "Nhận dạng giọng nói chưa sẵn sàng.")
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > VOICE_MAX + 64 * 1024:
            raise OpsError(413, "VOICE_TOO_LARGE", "Đoạn ghi âm lớn hơn 2 MB.")
        data = await audio.read(VOICE_MAX + 1)
        result = await run_in_threadpool(voice_service.transcribe, who.subject_id, data, audio.content_type or "")
        return JSONResponse(result, headers=NO_STORE)

    return r
