"""F5 over HTTP: start a procedure, fill it in, preview, and confirm. The student presses every button that writes."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

from campus247.ports.campus_ops import OpsError
from campus247.presentation.identity import get_current_identity

NO_STORE = {"Cache-Control": "no-store"}


class StartBody(BaseModel):
    procedure_id: str


class TextBody(BaseModel):
    text: str = Field(max_length=1000)
    procedure_id: Optional[str] = None


class FieldsBody(BaseModel):
    fields: dict[str, Any] = Field(default_factory=dict)
    confirm_extracted: list[str] = Field(default_factory=list)
    row_version: int


class ConfirmBody(BaseModel):
    preview_id: str
    confirmation_token: str = ""


def register_procedure_errors(app) -> None:
    @app.exception_handler(OpsError)
    async def ops_error(request: Request, exc: OpsError):
        body = {"type": f"https://campus247.example/problems/{exc.code.lower().replace('_', '-')}", "title": exc.detail, "status": exc.status,
                "detail": exc.detail, "code": exc.code, "retryable": exc.status in (503, 429)}
        if getattr(exc, "errors", None):
            body["errors"] = exc.errors
        return JSONResponse(status_code=exc.status, headers=NO_STORE, content=body)


def create_procedures_router(service) -> APIRouter:
    r = APIRouter(tags=["Procedures"])

    def out(content, status=200):
        return JSONResponse(content, status_code=status, headers=NO_STORE)

    @r.get("/v1/procedures")
    def catalog(request: Request):
        get_current_identity(request)
        return out(service.catalog())

    @r.post("/v1/procedures/runs")
    def start(body: StartBody, request: Request):
        return out(service.start(get_current_identity(request), body.procedure_id), 201)

    @r.post("/v1/procedures/runs:from-text")
    def from_text(body: TextBody, request: Request):
        return out(service.from_text(get_current_identity(request), body.text, body.procedure_id))

    @r.get("/v1/procedures/runs")
    def list_runs(request: Request, state: Optional[str] = None):
        return out(service.list_runs(get_current_identity(request), state))

    @r.get("/v1/procedures/runs/{run_id}")
    def get(run_id: str, request: Request):
        return out(service.get(get_current_identity(request), run_id))

    @r.put("/v1/procedures/runs/{run_id}/fields")
    def put_fields(run_id: str, body: FieldsBody, request: Request):
        return out(service.put_fields(get_current_identity(request), run_id, body.fields, body.row_version, body.confirm_extracted))

    @r.post("/v1/procedures/runs/{run_id}:submit-preview")
    def submit_preview(run_id: str, request: Request):
        return out(service.submit_preview(get_current_identity(request), run_id))

    @r.post("/v1/procedures/runs:submit-confirm")
    def submit_confirm(body: ConfirmBody, request: Request, idempotency_key: Optional[str] = Header(None)):
        return out(service.submit_confirm(get_current_identity(request), body.preview_id, body.confirmation_token, idempotency_key or ""))

    @r.post("/v1/procedures/runs/{run_id}:cancel")
    def cancel(run_id: str, request: Request):
        return out(service.cancel(get_current_identity(request), run_id))

    return r
