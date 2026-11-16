"""Authenticated endpoints; absent business consumer fails closed."""
from fastapi import APIRouter, Request
from starlette.responses import JSONResponse
from campus247.application.assistance.case_contracts import CaseDraftPrepare, CaseDraftRead, CaseDraftPreview, CaseConfirm, ReceiptRead
from campus247.application.assistance.case_contracts import SupplementResponse
from campus247.application.assistance.case_contracts import StaffIntent, BatchPrepare, BatchConfirm, QueueRead
from campus247.application.assistance.case_contracts import NotificationOpen
from campus247.application.document_request.certificates import CertificateError
from campus247.presentation.identity import get_current_identity
from campus247.presentation.staff_workspace import revalidator

def create_case_workflow_router(service):
    router = APIRouter(tags=["Reviewed case workflow"])
    def available():
        if service is None:
            raise CertificateError(503, "CASE_WORKFLOW_UNAVAILABLE", "Consumer chưa cấu hình; giữ nháp và đối chiếu hồ sơ thủ công")
        return service

    def response(value):
        return JSONResponse(value, headers={"Cache-Control": "no-store"})

    @router.post("/v1/assistant/cases/draft:prepare")
    def prepare(body: CaseDraftPrepare, request: Request):
        return response(available().prepare(get_current_identity(request), body, revalidate=revalidator(request)))

    @router.post("/v1/assistant/cases/draft:read")
    def read(body: CaseDraftRead, request: Request):
        return response(available().read_draft(get_current_identity(request), body.resource, revalidate=revalidator(request)))

    @router.post("/v1/assistant/cases/draft:preview")
    def preview(body: CaseDraftPreview, request: Request):
        return response(available().preview(get_current_identity(request), body, revalidate=revalidator(request)))

    @router.post("/v1/assistant/cases:confirm")
    def confirm(body: CaseConfirm, request: Request):
        return response(available().confirm(get_current_identity(request), body, revalidate=revalidator(request)))

    @router.post("/v1/assistant/cases/receipt:read")
    def receipt(body: ReceiptRead, request: Request):
        return response(available().receipt(get_current_identity(request), body.client_id, revalidate=revalidator(request)))

    @router.post("/v1/assistant/cases/supplement:read")
    def checklist(body: CaseDraftRead, request: Request):
        return response(available().checklist(get_current_identity(request), body.resource, revalidate=revalidator(request)))

    @router.post("/v1/assistant/cases/supplement:preview")
    def response_preview(body: SupplementResponse, request: Request):
        return response(available().response_preview(get_current_identity(request), body, revalidate=revalidator(request)))

    @router.post("/v1/assistant/cases/supplement:confirm")
    def response_confirm(body: CaseConfirm, request: Request):
        return response(available().response_confirm(get_current_identity(request), body, revalidate=revalidator(request)))

    @router.post("/v1/assistant/cases/projection:read")
    def projection(body: CaseDraftRead, request: Request):
        return response(available().projection(get_current_identity(request), body.resource, revalidate=revalidator(request)))

    @router.post("/v1/assistant/cases/events:read")
    def events(body: CaseDraftRead, request: Request):
        return response(available().events(get_current_identity(request), body.resource, revalidate=revalidator(request)))

    @router.post("/v1/assistant/cases/notification:open")
    def notification_open(body: NotificationOpen, request: Request):
        return response(available().notification_open(get_current_identity(request), body.event_id, revalidate=revalidator(request)))

    @router.post("/v1/assistant/cases/intent:resolve")
    def intent(body: StaffIntent, request: Request):
        return response(available().staff_intent(get_current_identity(request), body, revalidate=revalidator(request)))

    @router.post("/v1/assistant/cases/batch:prepare")
    def batch_prepare(body: BatchPrepare, request: Request):
        return response(available().batch_prepare(get_current_identity(request), body, revalidate=revalidator(request)))

    @router.post("/v1/assistant/cases/batch:confirm")
    def batch_confirm(body: BatchConfirm, request: Request):
        return response(available().batch_confirm(get_current_identity(request), body, revalidate=revalidator(request)))

    @router.post("/v1/assistant/cases/batch:read")
    def batch_read(body: ReceiptRead, request: Request):
        return response(available().batch_read(get_current_identity(request), body.client_id, revalidate=revalidator(request)))

    @router.post("/v1/assistant/cases/queue:read")
    def queue(body: QueueRead, request: Request):
        return response(available().queue(get_current_identity(request), body, revalidate=revalidator(request)))

    @router.post("/v1/assistant/cases/dashboard:read")
    def dashboard(body: QueueRead, request: Request):
        return response(available().dashboard(get_current_identity(request), body, revalidate=revalidator(request)))

    return router
