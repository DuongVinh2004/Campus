"""Strict memory API. Caller cannot select an owner/tenant or import history."""
from fastapi import APIRouter, Request, Query
from starlette.responses import JSONResponse

from campus247.application.document_request.certificates import CertificateError
from campus247.domain.assistant_memory import MemoryChange
from campus247.presentation.assistant_state import ConfirmBody
from campus247.presentation.identity import get_current_identity


def create_assistant_memory_router(service=None):
    router = APIRouter(prefix='/v1/assistant/memory')

    def available():
        if service is None:
            raise CertificateError(503, 'MEMORY_CONSUMER_UNAVAILABLE', 'Chưa nối memory; settings hiện có vẫn dùng được')
        return service

    def response(value):
        return JSONResponse(value, headers={'Cache-Control': 'no-store'})

    def invoke(request, method, *args, **kwargs):
        current = available()
        with current.request_guard(getattr(request.state, 'revalidate_identity', None)):
            return response(getattr(current, method)(get_current_identity(request), *args, **kwargs))

    @router.get('')
    async def read(request: Request, cursor: str = Query(default='', max_length=64)):
        return invoke(request, 'management', cursor=cursor)

    @router.get('/export')
    async def export(request: Request, cursor: str = Query(default='', max_length=64)):
        # Bounded, authorized projection; not an account-wide export receipt.
        return invoke(request, 'management', cursor=cursor, limit=50)

    @router.post('/preview')
    async def preview(request: Request, body: MemoryChange):
        return invoke(request, 'prepare', body)

    @router.post('/confirm')
    async def confirm(request: Request, body: ConfirmBody):
        return invoke(request, 'confirm', body.normalized_payload, body.confirmation_token, confirmed=body.confirmed)

    @router.get('/receipts/{client_id}')
    async def receipt(request: Request, client_id: str):
        return invoke(request, 'receipt', client_id)

    return router
