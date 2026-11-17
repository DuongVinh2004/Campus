"""A configured orchestration store is mandatory, scoped and never memory."""
from campus247.infrastructure.repositories.sqlite_agent_runs import (
    RunStorageUnavailable,
    SQLiteAgentRunStore,
)
from campus247.infrastructure.repositories.sqlite_certificates import workspace_path


def run_storage(settings, tenant, provided=None):
    mode = settings.AGENT_RUN_STORAGE_MODE
    if provided is not None:
        if mode == "sqlite":
            raise ValueError("choose configured run SQLite or injection, not both")
        if not isinstance(provided,SQLiteAgentRunStore):
            raise ValueError("typed durable run store required")
        if provided.tenant is not None and provided.tenant != tenant:
            raise ValueError("run store tenant must match server identity tenant")
        mode = "injected"
    elif mode == "injected":
        raise ValueError("configured run store missing")
    elif mode == "sqlite":
        if settings.AGENT_RUN_SQLITE_PATH is None or tenant is None:
            raise ValueError("explicit run SQLite path and tenant required")
        if settings.ENVIRONMENT not in {"development","testing"} or not settings.DEMO_MODE:
            raise ValueError("local SQLite runs require synthetic environment")
        path = workspace_path(settings.AGENT_RUN_SQLITE_PATH)
        if not path.is_file():
            raise RunStorageUnavailable("RUN_STORAGE_NOT_INITIALIZED")
        provided = SQLiteAgentRunStore(path,tenant=tenant)
    return provided,{"mode":mode,"durability":"durable" if provided is not None else "disabled",
        "tenant_binding":"bound" if provided is not None and provided.tenant is not None else "legacy_unverified" if provided is not None else "not_configured",
        "fallback":False}
