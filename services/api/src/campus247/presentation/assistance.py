from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

from campus247.application.assistance.contracts import AssistanceRequest, AssistanceResponse
from campus247.application.assistance.unified_contracts import CONTRACT_MODELS
from campus247.application.assistance.workflow import WorkflowResolveRequest, WorkflowResolveResponse
from campus247.presentation.identity import get_current_identity


def create_assistance_router(service, workflow=None):
    router = APIRouter(tags=["Unified assistance"])

    @router.get("/v1/assistant/contracts")
    def contracts(request: Request):
        actor = get_current_identity(request)
        service.certificates.authorize(actor)
        return JSONResponse({"version":"unified-contracts.v1", "execution_authority":"none",
            "models":{name:model.model_json_schema() for name,model in CONTRACT_MODELS.items()}},
            headers={"Cache-Control":"no-store"})

    @router.post("/v1/assistant/context", response_model=AssistanceResponse)
    def context(body: AssistanceRequest, request: Request):
        actor = get_current_identity(request)
        result = service.resolve(actor, body)
        return JSONResponse(result.model_dump(mode="json"), headers={"Cache-Control": "no-store"})

    if workflow is not None:
        @router.post("/v1/assistant/workflows/resolve", response_model=WorkflowResolveResponse)
        def resolve_workflow(body: WorkflowResolveRequest, request: Request):
            actor = get_current_identity(request)
            return JSONResponse(workflow.resolve(actor, body).model_dump(mode="json"), headers={"Cache-Control": "no-store"})

    return router
