from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

from campus247.application.assistance.baseline import BaselineEvent, BaselineStart
from campus247.presentation.identity import get_current_identity


def create_baseline_router(service):
    router = APIRouter(tags=["Baseline measurement"])
    def response(value):
        return JSONResponse(value, headers={"Cache-Control":"no-store"})

    @router.get("/v1/assistant/baseline/cases")
    def cases(request: Request):
        return response(service.available(get_current_identity(request)))

    @router.get("/v1/assistant/baseline/sessions")
    def sessions(request: Request):
        return response(service.list(get_current_identity(request)))

    @router.post("/v1/assistant/baseline/sessions", status_code=201)
    def start(body: BaselineStart, request: Request):
        return JSONResponse(service.start(get_current_identity(request),body),status_code=201,headers={"Cache-Control":"no-store"})

    @router.get("/v1/assistant/baseline/sessions/{identifier}")
    def read(identifier: str, request: Request):
        return response(service.read(get_current_identity(request),identifier))

    @router.post("/v1/assistant/baseline/sessions/{identifier}/events")
    def event(identifier: str, body: BaselineEvent, request: Request):
        return response(service.event(get_current_identity(request),identifier,body))

    @router.get("/v1/assistant/baseline/sessions/{identifier}/receipts")
    def receipts(identifier: str, request: Request):
        return response(service.receipts(get_current_identity(request),identifier))

    return router
