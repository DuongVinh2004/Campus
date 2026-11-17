"""Owner-only subscription and in-app inbox API."""
from fastapi import APIRouter, Request, Query
from starlette.responses import JSONResponse

from campus247.application.document_request.certificates import CertificateError
from campus247.domain.assistant_tracking import TrackingChange
from campus247.presentation.assistant_state import ConfirmBody
from campus247.presentation.identity import get_current_identity


def create_assistant_tracking_router(service=None):
    router = APIRouter(prefix='/v1/assistant/tracking')

    def available():
        if service is None:
            raise CertificateError(503, 'TRACKING_CONSUMER_UNAVAILABLE', 'Chưa nối tracking; mở hồ sơ để kiểm tra thủ công')
        return service

    def response(value):
        return JSONResponse(value, headers={'Cache-Control': 'no-store'})

    def invoke(request, method, *args, **kwargs):
        current = available()
        with current.request_guard(getattr(request.state, 'revalidate_identity', None)):
            return response(getattr(current, method)(get_current_identity(request), *args, **kwargs))

    @router.get('/subscriptions')
    async def subscriptions(request: Request):
        return invoke(request, 'subscriptions')

    @router.get('/notifications')
    async def notifications(request: Request, cursor: str = Query(default='', max_length=100)):
        return invoke(request, 'notifications', cursor=cursor)

    @router.post('/preview')
    async def preview(request: Request, body: TrackingChange):
        return invoke(request, 'prepare', body)

    @router.post('/confirm')
    async def confirm(request: Request, body: ConfirmBody):
        return invoke(request, 'confirm', body.normalized_payload, body.confirmation_token, confirmed=body.confirmed)

    @router.get('/receipts/{client_id}')
    async def receipt(request: Request, client_id: str):
        return invoke(request, 'receipt', client_id)

    return router
