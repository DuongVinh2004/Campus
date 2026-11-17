"""Explicit B registrar. Absence never implies memory/model/event capability."""
from campus247.application.assistant_memory.service import AssistantMemoryService
from campus247.application.assistant_tracking.service import AssistantTrackingService
from campus247.presentation.assistant_memory import create_assistant_memory_router
from campus247.presentation.assistant_tracking import create_assistant_tracking_router


def wire_assistant_personal_features(app, *, memory_store, tenant, authorize, tokens, preferences,
        tracking_store=None, grants=None, conversation_mode=None, minimize=None, tracking_source=None,
        resolve_recipient=None, project_notification=None, memory_context_consumer=False):
    options = {'tenant': tenant, 'authorize': authorize, 'tokens': tokens}
    memory = AssistantMemoryService(memory_store, preferences=preferences, grants=grants,
        conversation_mode=conversation_mode, minimize=minimize, **options) if memory_store is not None else None
    tracking = AssistantTrackingService(tracking_store, grants=grants, source=tracking_source,
        resolve_recipient=resolve_recipient, project_notification=project_notification,
        minimize=minimize, **options) if tracking_store is not None else None
    app.state.assistant_memory, app.state.assistant_tracking = memory, tracking
    # Unified demo has a retained generic /v1 proxy. Specific local routes must
    # precede it even when this registrar is invoked after app composition.
    for router in (create_assistant_memory_router(memory), create_assistant_tracking_router(tracking)):
        for route in reversed(router.routes):
            app.router.routes.insert(0, route)
    # A must supply a real writer/context hook before publishing this flag.
    app.state.assistant_personal_capabilities = {
        'memory_management': bool(memory and conversation_mode and minimize),
        'memory_context': bool(memory and conversation_mode and minimize and memory_context_consumer),
        'tracking': bool(tracking and tracking.configured), 'notification_channel': 'in_app',
        'remote_delivery': False, 'physical_memory_erasure': False,
        'temporary_chat': 'requires_server_mode_reader', 'action_authority': 'none'}
    from fastapi import APIRouter, Request
    from starlette.responses import JSONResponse
    from campus247.presentation.identity import get_current_identity

    capabilities_router = APIRouter()

    @capabilities_router.get('/v1/assistant/personal-capabilities')
    async def personal_capabilities(request: Request):
        actor = get_current_identity(request)
        preferences.scope(actor)
        return JSONResponse(app.state.assistant_personal_capabilities, headers={'Cache-Control': 'no-store'})
    for route in reversed(capabilities_router.routes):
        app.router.routes.insert(0, route)
    return memory, tracking
