"""Explicit composition for settings, consent, requests, feedback and revocation."""
from campus247.application.assistance.state_storage import (
    StateScope,
    StorageUnavailable,
)
from campus247.infrastructure.repositories.sqlite_actor_state import (
    SQLiteActorStateStore,
)
from campus247.infrastructure.repositories.sqlite_auxiliary import (
    SQLiteFeedbackRepository,
    SQLitePrivacyRequestRepository,
    SQLiteRevocationStore,
)
from campus247.infrastructure.repositories.sqlite_certificates import workspace_path


def actor_storage(settings, tenant, provided=None):
    mode = settings.ACTOR_STATE_STORAGE_MODE
    if provided is not None:
        if mode == "sqlite":
            raise ValueError("choose configured actor SQLite or injection, not both")
        if not isinstance(provided, SQLiteActorStateStore):
            raise ValueError("typed actor store required")
        mode = "injected"
    elif mode == "injected":
        raise ValueError("configured actor store missing")
    elif mode == "sqlite":
        if settings.ACTOR_STATE_SQLITE_PATH is None:
            raise ValueError("explicit actor state SQLite path required")
        path = workspace_path(settings.ACTOR_STATE_SQLITE_PATH)
        if not path.is_file():
            raise StorageUnavailable("ACTOR_STORAGE_NOT_INITIALIZED")
        if settings.ENVIRONMENT not in {"development","testing"} or not settings.DEMO_MODE or tenant is None:
            raise ValueError("local durable actor services require explicit synthetic tenant")
        provided = SQLiteActorStateStore(path)
    if provided is not None:
        if settings.ENVIRONMENT not in {"development","testing"} or not settings.DEMO_MODE or tenant is None:
            raise ValueError("local durable actor services require explicit synthetic tenant")
        StateScope(tenant,"019a0000-0000-7000-8000-000000000007")
        provided.check_available()
    return provided, {"mode":mode,"durability":"durable" if provided is not None else "ephemeral","fallback":False}


def auxiliary_repositories(store, tenant):
    if store is None:
        return None,None,None
    return (SQLiteFeedbackRepository(store,tenant=tenant),SQLitePrivacyRequestRepository(store,tenant=tenant),
            SQLiteRevocationStore(store,tenant=tenant))
