"""Server bindings and metadata-only trace; no executable authority in state."""
import re
from datetime import datetime, timezone

from campus247.application.multi_agent.contracts import CoordinationBinding, TaskBinding
from campus247.application.single_agent.contracts import digest


def bind_run(turn, context, original_goal):
    scope = context.to_dict()["authorized_scope"]
    identity = turn.coordination_guard() if turn.coordination_guard else None
    session_hash = None
    if identity is not None:
        if (identity.subject_id != turn.user_id or identity.tenant_id != scope["tenant_id"] or
                sorted(str(r) for r in identity.roles) != scope["roles"] or not identity.session_id or not identity.is_active or
                identity.expires_at <= datetime.now(timezone.utc)):
            raise ValueError("COORDINATION_IDENTITY_CHANGED")
        session_hash = digest(identity.session_id)
    if scope["actor_id"] != turn.user_id:
        raise ValueError("COORDINATION_ACTOR_CHANGED")
    return CoordinationBinding(actor_id=turn.user_id, tenant_id=scope["tenant_id"],
        conversation_id=turn.session_id, scope_sha256=digest(scope), session_sha256=session_hash,
        roles=scope["roles"], audiences=scope["audiences"],
        goal_sha256=digest(original_goal), purpose_sha256=digest(original_goal))


def bind_task(spec, binding, items, policy):
    selected = [item.model_dump() for item in items if item.id in spec.coverage_ids]
    return spec.model_copy(update={"binding": TaskBinding(scope=binding,
        coverage_sha256=digest(selected), budget_sha256=policy.fingerprint)})


def validate_task_binding(spec, binding, items, policy):
    if spec.binding != bind_task(spec, binding, items, policy).binding:
        raise ValueError("TASK_BINDING_CHANGED")


def trace_metadata(data):
    """Drop unknown fields; allow no prose, prompt, quote, note or credential."""
    scalar = {"route", "model", "code", "reason_code", "error_type", "error_code", "role", "schema",
              "query_sha256", "chunk_id", "content_sha256", "quote_sha256", "original_sha256", "search_sha256",
              "graph_id", "resource_id", "resource_version", "receipt_id", "scope_sha256"}
    numbers = {"input_tokens", "output_tokens", "attempt", "proposed_tasks", "admitted_tasks"}
    lists = {"coverage_ids", "dependencies", "evidence_ids", "candidate_ids", "edge_ids", "source_ids",
             "reason_codes", "omitted_claim_ids"}
    def label(value):
        return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:/-]{1,128}", value) is not None
    result = {}
    for key, value in data.items():
        if key in scalar and (value is None or label(value) or key == "resource_version" and type(value) is int):
            result[key] = value
        elif key in numbers and type(value) is int and 0 <= value <= 1000000:
            result[key] = value
        elif key in lists and isinstance(value, list) and len(value) <= 64 and all(label(v) for v in value):
            result[key] = value
        elif key == "full_answer_allowed" and type(value) is bool:
            result[key] = value
        elif key == "coverage" and isinstance(value, list):
            result[key] = [{k: r[k] for k in ("item_id", "status") if k in r and label(r[k])} for r in value[:4]]
        elif key == "claims" and isinstance(value, list):
            result[key] = [{k: r[k] for k in ("claim_id", "claim_sha256", "verdict") if k in r and label(r[k])}
                           | {"evidence_ids": [v for v in r.get("evidence_ids", [])[:6] if label(v)]} for r in value[:16]]
        elif key == "errors" and isinstance(value, list):
            result[key] = [{"type": r["type"], "path": [v for v in r.get("path", [])[:8]
                            if type(v) is int or label(v)]} for r in value[:16] if label(r.get("type"))]
    return result
