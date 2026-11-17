"""Explicit local durable consent composition; configured failures never fall back."""
from campus247.infrastructure.repositories.sqlite_actor_state import SQLiteActorStateStore
from campus247.infrastructure.repositories.sqlite_consents import SQLiteConsentRepository


def consent_storage(settings, tenant, provided=None):
    mode = settings.CONSENT_STORAGE_MODE
    if provided is not None:
        if mode == "sqlite":
            raise ValueError("choose configured SQLite consent or explicit injection, not both")
        if not isinstance(provided, SQLiteConsentRepository):
            raise ValueError("typed durable consent repository required")
        if tenant != provided.tenant:
            raise ValueError("consent repository tenant must match configured identity tenant")
        mode = "injected"
    elif mode == "injected":
        raise ValueError("configured consent repository missing")
    elif mode == "sqlite":
        if settings.CONSENT_SQLITE_PATH is None or tenant is None:
            raise ValueError("explicit consent SQLite path and identity tenant required")
        if settings.ENVIRONMENT not in {"development", "testing"} or not settings.DEMO_MODE:
            raise ValueError("local consent SQLite requires explicit synthetic environment")
        from campus247.infrastructure.repositories.sqlite_certificates import workspace_path
        from campus247.application.assistance.state_storage import StorageUnavailable
        if not workspace_path(settings.CONSENT_SQLITE_PATH).is_file():
            raise StorageUnavailable("CONSENT_STORAGE_NOT_INITIALIZED")
        provided = SQLiteConsentRepository(SQLiteActorStateStore(settings.CONSENT_SQLITE_PATH), tenant=tenant)
    if provided is not None and (settings.ENVIRONMENT not in {"development", "testing"} or not settings.DEMO_MODE):
        raise ValueError("local consent SQLite requires explicit synthetic environment")
    return provided, {"mode": "sqlite" if provided is not None else "ephemeral", "fallback": False,
                      "grants_authority": False}
