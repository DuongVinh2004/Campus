"""Authenticated local draft routes; university submission remains unavailable."""
from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field
from campus247.application.document_request.local_preparation import PreparationForm
from campus247.presentation.identity import get_current_identity
from campus247.presentation.staff_workspace import revalidator


class PreviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    form: PreparationForm
    document_id: str | None = Field(default=None, max_length=64)
    expected_version: int = Field(default=0, ge=0)


class SaveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preview_id: str = Field(min_length=1, max_length=64)
    confirmation_token: str = Field(min_length=1, max_length=4000)
    client_id: str = Field(min_length=8, max_length=100)
    confirmed: bool


def create_local_preparation_router(service):
    router = APIRouter(prefix="/v1/student-preparations", tags=["Student preparation"])

    @router.get("")
    def listing(request: Request):
        return service.list(get_current_identity(request))

    @router.get("/{identifier}")
    def read(identifier: str, request: Request):
        return service.read(get_current_identity(request), identifier)

    @router.post("/preview")
    def preview(body: PreviewBody, request: Request):
        return service.preview(get_current_identity(request), body.form, body.document_id, body.expected_version)

    @router.post("/save")
    def save(body: SaveBody, request: Request):
        return service.save(get_current_identity(request), body.preview_id, body.confirmation_token,
                            body.client_id, body.confirmed, revalidator(request))

    return router
