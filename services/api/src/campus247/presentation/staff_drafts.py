from fastapi import APIRouter, Request
from pydantic import Field
from starlette.responses import JSONResponse

from campus247.application.assistance.contracts import ResourceRef, StrictDTO
from campus247.application.assistance.unified_contracts import UUID
from campus247.presentation.identity import get_current_identity
from campus247.presentation.staff_workspace import revalidator


class DraftRead(StrictDTO):
    resource: ResourceRef


class DraftSave(DraftRead):
    expected_draft_version: int = Field(ge=0)
    client_id: UUID
    text: str = Field(max_length=8000)


def create_staff_draft_router(service):
    router = APIRouter(tags=["Private staff drafts"])

    @router.post("/v1/assistant/staff-drafts/read")
    def read(body: DraftRead,request: Request):
        return JSONResponse(service.read(get_current_identity(request),body.resource,revalidate=revalidator(request)),headers={"Cache-Control":"no-store"})

    @router.post("/v1/assistant/staff-drafts/save")
    def save(body: DraftSave,request: Request):
        result = service.save(get_current_identity(request),body.resource,body.text,body.expected_draft_version,body.client_id,
                              revalidate=revalidator(request))
        return JSONResponse(result,status_code=200 if result["is_replay"] else 201,headers={"Cache-Control":"no-store"})

    return router
