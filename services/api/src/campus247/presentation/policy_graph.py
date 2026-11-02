"""Authenticated graph discovery and admin review with explicit publication preview."""
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import JSONResponse

from campus247.agent.state import NormalizedTurn
from campus247.application.policy_graph.service import PolicyGraphError
from campus247.domain.policy_graph import TraversalBounds, fingerprint
from campus247.ports.policy_graph import GraphConflict
from campus247.presentation.identity import get_current_identity


class RevisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_revision: int = Field(ge=0)


class ReviewBody(RevisionBody):
    target: str = Field(min_length=1, max_length=100)
    verdict: str = Field(pattern=r"^(approved|rejected|needs_source|conflicting)$")
    note: str = Field(min_length=8, max_length=2000)


class PublishBody(RevisionBody):
    confirmation: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmed: bool


class QueryBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: str = Field(min_length=1, max_length=2000)
    depth: int = Field(default=2, ge=0, le=4)
    nodes: int = Field(default=24, ge=1, le=64)


class ExtractBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    target_ids: list[str] = Field(min_length=1, max_length=4)


def create_policy_graph_router(service, *, context_factory, gateway=None, policy=None, admission=None):
    router = APIRouter(prefix="/v1/policy-graph", tags=["Policy graph"])

    def context(request, *, admin=False):
        actor = get_current_identity(request)
        if hasattr(request.state, "revalidate_identity"):
            try:
                actor = request.state.revalidate_identity()
            except Exception:
                raise HTTPException(401, "Current session unavailable") from None
        if admin and not any(actor.has_role(role) for role in ("KNOWLEDGE_ADMIN", "SYSTEM_ADMIN")):
            raise HTTPException(403, "Graph review requires knowledge administrator")
        request.state.graph_session_binding = fingerprint(actor.session_id)
        try:
            value = context_factory(NormalizedTurn("graph-review", "graph-review", actor.subject_id, "",
                locale="vi"), actor, effective_at=datetime.now(timezone.utc))
            if value is None or value.authorized_scope.actor_id != actor.subject_id:
                raise ValueError()
            return value
        except Exception:
            raise HTTPException(403, "Current source scope unavailable") from None

    def response(value):
        return JSONResponse(value, headers={"Cache-Control": "no-store"})

    def error(failure):
        code = str(failure)
        raise HTTPException(404 if code in {"GRAPH_UNAVAILABLE", "GRAPH_NOT_PUBLISHED"} else
            403 if code in {"GRAPH_REVIEW_DENIED", "GRAPH_AUTHORIZATION_UNAVAILABLE"} else 409, code) from None

    @router.get("/versions")
    async def versions(request: Request):
        current = context(request, admin=True)
        items = []
        for graph_id in service.repository.list_ids():
            try:
                view = await service.review_view(graph_id, current)
                items.append({"id": graph_id, "revision": view["revision"], "published": bool(view["publication"])})
            except PolicyGraphError:
                continue  # No inaccessible version counts, IDs or diagnostics.
        return response({"items": items})

    @router.get("/versions/{graph_id}")
    async def view(graph_id: str, request: Request):
        current = context(request, admin=True)
        try:
            return response(await service.review_view(graph_id, current))
        except PolicyGraphError as failure:
            error(failure)

    @router.post("/versions/{graph_id}/reviews")
    async def review(graph_id: str, body: ReviewBody, request: Request):
        current = context(request, admin=True)
        try:
            revision = await service.review(graph_id, current, **body.model_dump())
            return response({"revision": revision})
        except (PolicyGraphError, GraphConflict) as failure:
            error(failure)

    @router.post("/versions/{graph_id}:publish-preview")
    async def preview(graph_id: str, body: RevisionBody, request: Request):
        current = context(request, admin=True)
        try:
            value = service.publication_preview(graph_id, current, expected_revision=body.expected_revision,
                session_binding=request.state.graph_session_binding)
            return response({"preview": value, "confirmation": fingerprint(value)})
        except (PolicyGraphError, GraphConflict) as failure:
            error(failure)

    @router.post("/versions/{graph_id}:publish")
    async def publish(graph_id: str, body: PublishBody, request: Request):
        current = context(request, admin=True)
        if not body.confirmed:
            raise HTTPException(422, "Explicit publication confirmation required")
        try:
            manifest = await service.publish(graph_id, current, expected_revision=body.expected_revision,
                confirmation=body.confirmation, session_binding=request.state.graph_session_binding)
            return response({"publication": manifest})
        except (PolicyGraphError, GraphConflict) as failure:
            error(failure)

    @router.post("/relations:search")
    async def search(body: QueryBody, request: Request):
        current = context(request)
        try:
            return response(await service.traverse(context=current, query=body.query,
                bounds=TraversalBounds(depth=body.depth, nodes=body.nodes)))
        except PolicyGraphError as failure:
            error(failure)

    @router.post("/versions/{graph_id}:extract-candidate")
    async def extract(graph_id: str, body: ExtractBody, request: Request):
        current = context(request, admin=True)
        from campus247.application.multi_agent.contracts import MultiAgentPolicy
        from campus247.application.single_agent.resources import RunResources, BoundedGateway, AgentStop
        from campus247.application.policy_graph.extraction import extract_candidate
        from campus247.domain.shared.values import generate_uuid7
        import asyncio
        selected_policy = policy or MultiAgentPolicy()
        if gateway is None or admission is None or not admission(selected_policy):
            raise HTTPException(409, "Shared provider headroom unavailable; no extraction dispatched")
        try:
            proposal = service.proposal(graph_id, current, review=True)
            records = {row.id: row for row in (*proposal.nodes, *proposal.edges)}
            sources = []
            for key in dict.fromkeys(body.target_ids):
                row = records.get(key)
                if row is None or await service.source(row.source, current) is None:
                    raise PolicyGraphError("GRAPH_UNAVAILABLE")
                sources.append({"span_id": f"S{len(sources)+1}", "source": row.source.model_dump(mode="json"),
                    "scope": row.scope.model_dump(mode="json")})
            run_id = generate_uuid7()
            events, pending = [], {}
            def save():
                service.repository.extraction_usage(run_id, {"usage": resources.usage,
                    "events": events, "pending": pending, "actor": current.authorized_scope.actor_id})
            def event(tool, status, duration, data):
                events.append({"tool": tool, "status": status, "duration_ms": duration, "data": data})
                save()
            def phase(value):
                pending["model"] = value
                save()
            resources = RunResources(selected_policy, persist=save)
            bounded = BoundedGateway(gateway, resources, event=event, pending=phase)
            # This is the application's existing exclusive writer gateway.
            # No new paid writer/credentials/client capability is constructed.
            async with asyncio.timeout(selected_policy.deadline_seconds):
                candidate, _ = await extract_candidate(gateway=bounded, repository=service.repository,
                    source_inputs=sources, request_id=run_id, author=current.authorized_scope.actor_id,
                    graph_id="candidate-"+run_id, index_fingerprint=service.index_fingerprint,
                    source_fingerprint=service.source_fingerprint, acquired_at=datetime.now(timezone.utc))
            fresh = context(request, admin=True)
            if fresh.authorized_scope != current.authorized_scope:
                raise PolicyGraphError("GRAPH_REVIEW_DENIED")
            return response({"candidate_id": candidate.id, "status": "candidate_requires_review",
                "publication": None, "usage": resources.usage})
        except (PolicyGraphError, GraphConflict) as failure:
            error(failure)
        except (ValueError, AgentStop, TimeoutError):
            raise HTTPException(409, "Extraction incomplete or invalid; retained reservations are not retried") from None

    return router
