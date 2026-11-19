from __future__ import annotations
from typing import Literal, List

import asyncio
from fastapi import APIRouter, Response, status, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text


class HealthStatus(BaseModel):
    """Liveness response schema conforming to OpenAPI contract API-SYS-001."""
    model_config = ConfigDict(extra="forbid")

    status: Literal["alive"] = "alive"


class DependencyItem(BaseModel):
    """Status of an individual dependency."""
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., pattern=r"^[a-z][a-z0-9_-]{1,63}$")
    status: Literal["ready", "unavailable", "disabled"]


class SecurityConfiguration(BaseModel):
    """Startup security configuration evidence conforming to API-SYS-002."""
    model_config = ConfigDict(extra="forbid")

    demo_auth_guard: Literal["ENFORCED", "NOT_APPLICABLE"] = "ENFORCED"


class ReadinessStatus(BaseModel):
    """Readiness response schema conforming to OpenAPI contract API-SYS-002."""
    model_config = ConfigDict(extra="forbid")

    status: Literal["ready", "degraded"]
    dependencies: List[DependencyItem]
    security_configuration: SecurityConfiguration
    rag_v2: dict = Field(default_factory=lambda: {
        "enabled": False, "snapshot_state": "disabled", "stale": False,
        "unit_count": 0, "release_id": None, "warm": None})


async def check_database_connectivity(request: Request) -> Literal["ready", "unavailable", "disabled"]:
    """Bounded database connectivity probe. Returns status string."""
    try:
        if getattr(request.app.state, "database_initialization_failed", False):
            return "unavailable"
        engine = getattr(request.app.state, "db_engine", None)
        if engine is None:
            return "disabled"
        
        async def probe() -> None:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))

        # Connection acquisition is part of the same budget as the query.
        await asyncio.wait_for(probe(), timeout=2.0)
        return "ready"
    except Exception:
        return "unavailable"


async def probe_scanner(scanner) -> Literal["ready", "unavailable"] | None:
    """State of a scanner that can report one (the ClamAV daemon client), or None for scanners that cannot."""
    probe = getattr(scanner, "health", None)
    if probe is None:
        return None
    try:
        state = await asyncio.wait_for(probe(), timeout=2.0)
    except Exception:
        return "unavailable"
    return "ready" if state.get("up") and not state.get("stale") else "unavailable"


async def check_learning_scanner(request: Request) -> Literal["ready", "unavailable"] | None:
    """The learning module's upload scanner, or None when the module is off or has no reporting scanner."""
    service = getattr(request.app.state, "learning_service", None)
    return await probe_scanner(getattr(service, "scanner", None))


async def check_upload_scanner(request: Request) -> Literal["ready", "unavailable"] | None:
    """The scanner behind knowledge uploads and crawled files (separate from learning: the cloud runs this one alone)."""
    runtime = getattr(request.app.state, "knowledge_runtime", None)
    storage = getattr(getattr(runtime, "platform", None), "storage", None)
    return await probe_scanner(getattr(storage, "scanner", None))


router = APIRouter(tags=["System"])


@router.get(
    "/health/live",
    response_model=HealthStatus,
    summary="Process liveness",
    operation_id="getLiveness",
)
async def get_liveness() -> HealthStatus:
    """Return process liveness confirmation without asserting dependency readiness."""
    return HealthStatus(status="alive")


@router.get(
    "/health/ready",
    response_model=ReadinessStatus,
    responses={
        200: {"model": ReadinessStatus, "description": "Required dependencies are ready."},
        503: {"description": "Required dependencies are unavailable."},
    },
    summary="Dependency readiness",
    operation_id="getReadiness",
)
async def get_readiness(request: Request) -> Response:
    """Check bounded database connectivity and startup configuration."""
    db_status = await check_database_connectivity(request)
    node = getattr(request.app.state, "rag_v2_node", None)
    v2 = ReadinessStatus.model_fields["rag_v2"].default_factory()
    if node is not None:
        try:
            v2 = await asyncio.wait_for(node.rag_v2_status.refresh(), timeout=2.0)
        except Exception:
            v2 = {**v2, "enabled": True, "snapshot_state": "unavailable", "stale": None}
    v2_ready = not v2["enabled"] or (v2["snapshot_state"] == "complete" and v2["stale"] is False)
    # A newer release is being indexed and loaded in the background (bounded by the reloader): chat keeps serving the
    # current index, so the process stays ready instead of looking dead to a proxy or supervisor.
    if not v2_ready and node is not None and getattr(node, "refreshing", False) is True and v2.get("stale") is True:
        v2 = {**v2, "snapshot_state": "refreshing"}
        v2_ready = True
    
    # We consider "disabled" to mean it's running without DB (e.g. synthetic mode).
    # But if it's "unavailable", we fail readiness.
    if db_status == "unavailable":
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "type": "https://campus247.example/problems/dependency-unavailable",
                "title": "Service Unavailable",
                "status": 503,
                "detail": "Required database dependency is currently unreachable.",
                "instance": "/health/ready",
                "code": "DEPENDENCY_UNAVAILABLE",
                "request_id": getattr(request.state, "request_id", "unknown"),
                "retryable": True,
                "rag_v2": v2,
            },
        )

    dependencies = [
        DependencyItem(name="database", status=db_status),
        DependencyItem(name="redis", status="disabled"),
    ]
    # Informational: chat does not depend on the upload scanners, so a stale or stopped one never fails readiness;
    # it blocks only new uploads (they fail closed) and shows up here and in the metrics.
    for name, check in (("learning-scanner", check_learning_scanner), ("upload-scanner", check_upload_scanner)):
        scanner_status = await check(request)
        if scanner_status is not None:
            dependencies.append(DependencyItem(name=name, status=scanner_status))

    # No Redis client or connectivity probe is bound by this composition root.
    return JSONResponse(
        status_code=status.HTTP_200_OK if v2_ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        content=ReadinessStatus(
            status="ready" if v2_ready else "degraded",
            dependencies=dependencies,
            security_configuration=SecurityConfiguration(demo_auth_guard="ENFORCED"),
            rag_v2=v2,
        ).model_dump(),
    )
