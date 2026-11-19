from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone

import pytest

from campus247.domain.retrieval import (
    AuthorizedScope,
    RetrievalBranchDiagnostic,
    RetrievalBranchStatus,
    RetrievalCandidate,
    RetrievalContext,
    RetrievalDiagnostics,
    RetrievalQuery,
    RetrievalResult,
    SimulationPolicy,
)


def authorized_scope() -> AuthorizedScope:
    return AuthorizedScope(
        tenant_id="HUCE",
        campus_id="HUCE",
        actor_id="user-001",
        roles=frozenset({"STUDENT"}),
        audiences=frozenset({"STUDENT", "COHORT-2026"}),
        faculty_codes=frozenset({"FIT"}),
        program_codes=frozenset({"SOFTWARE_ENGINEERING"}),
    )


def candidate(chunk_id: str = "chunk-001") -> RetrievalCandidate:
    return RetrievalCandidate(
        source_id="source-001",
        document_version_id="version-001",
        chunk_id=chunk_id,
        content_text="Nội dung quy định đã được duyệt.",
        title="Quy định học vụ",
        issuer="HUCE",
        canonical_uri="https://example.invalid/regulation/1",
        quote_span_hash="sha256:abc",
        section_path=("Chương I", "Điều 1"),
        page_start=1,
        page_end=1,
    )


def diagnostics() -> RetrievalDiagnostics:
    return RetrievalDiagnostics(
        retrieval_profile_version="rag-prod-v1.0.0",
        index_version="index-001",
        embedding_model_version="bge-m3@5617a9f",
        reranker_model_version="bge-reranker-v2-m3@953dc6f",
        branches=(
            RetrievalBranchDiagnostic(
                branch="lexical",
                status=RetrievalBranchStatus.SUCCEEDED,
                candidate_count=1,
                duration_ms=10,
            ),
        ),
        total_duration_ms=20,
    )


def test_retrieval_context_serialization_round_trip() -> None:
    context = RetrievalContext(
        authorized_scope=authorized_scope(),
        locale="vi",
        effective_at=datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc),
        simulation_policy=SimulationPolicy.DENY,
        trace_id="trace-001",
    )

    restored = RetrievalContext.from_dict(context.to_dict())

    assert restored == context
    assert restored.effective_at.tzinfo is timezone.utc


def test_query_normalizes_exact_identifiers() -> None:
    query = RetrievalQuery("  học phí CT-101  ", exact_identifiers=(" CT-101 ", ""))
    assert query.text == "học phí CT-101"
    assert query.exact_identifiers == ("CT-101",)


def test_authorized_scope_fails_closed_for_empty_scope() -> None:
    with pytest.raises(ValueError, match="roles must not be empty"):
        AuthorizedScope(
            tenant_id="HUCE",
            campus_id="HUCE",
            actor_id="user-001",
            roles=frozenset(),
            audiences=frozenset({"STUDENT"}),
            faculty_codes=frozenset({"FIT"}),
            program_codes=frozenset({"SOFTWARE_ENGINEERING"}),
        )


def test_context_rejects_naive_effective_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        RetrievalContext(
            authorized_scope=authorized_scope(),
            locale="vi",
            effective_at=datetime(2026, 9, 29, 12, 0),
            simulation_policy=SimulationPolicy.DENY,
            trace_id="trace-001",
        )


def test_result_rejects_foreign_or_duplicate_selected_ids() -> None:
    with pytest.raises(ValueError, match="refer to returned candidates"):
        RetrievalResult(
            candidates=(candidate(),),
            selected_chunk_ids=("foreign-chunk",),
            diagnostics=diagnostics(),
        )
    with pytest.raises(ValueError, match="must not contain duplicates"):
        RetrievalResult(
            candidates=(candidate(),),
            selected_chunk_ids=("chunk-001", "chunk-001"),
            diagnostics=diagnostics(),
        )


def test_failed_branch_requires_reason_code() -> None:
    with pytest.raises(ValueError, match="reason_code is required"):
        RetrievalBranchDiagnostic(
            branch="vector",
            status=RetrievalBranchStatus.FAILED,
            candidate_count=0,
            duration_ms=700,
        )


def context() -> RetrievalContext:
    return RetrievalContext(
        authorized_scope=authorized_scope(), locale="vi",
        effective_at=datetime(2026, 10, 3, tzinfo=timezone.utc),
        simulation_policy=SimulationPolicy.DENY, trace_id="synthetic-contract-trace",
    )


@pytest.mark.parametrize("field,value", [
    ("authorized_scope", {"roles": ["SYSTEM_ADMIN"]}),
    ("authorized_scope", None), ("simulation_policy", "ALLOW_LABELED"),
    ("simulation_policy", True), ("effective_at", "2026-10-03T00:00:00Z"),
    ("effective_at", None), ("locale", 123), ("trace_id", None),
])
def test_context_rejects_untyped_fields(field, value):
    with pytest.raises(ValueError):
        replace(context(), **{field: value})


@pytest.mark.parametrize("field", ["roles", "audiences", "faculty_codes", "program_codes"])
@pytest.mark.parametrize("value", ["STUDENT", ["STUDENT"], {"STUDENT"}, frozenset({True})])
def test_scope_rejects_mutable_or_untyped_collections(field, value):
    with pytest.raises(ValueError, match="frozenset of strings"):
        replace(authorized_scope(), **{field: value})


@pytest.mark.parametrize("field", ["roles", "audiences", "faculty_codes", "program_codes"])
def test_every_empty_scope_is_rejected(field):
    with pytest.raises(ValueError, match="must not be empty"):
        replace(authorized_scope(), **{field: frozenset()})


@pytest.mark.parametrize("mutation", [
    "unknown_field", "unknown_scope_field", "string_roles", "mixed_roles",
    "missing_scope", "missing_actor", "numeric_actor", "numeric_locale",
    "numeric_time", "naive_time", "invalid_time", "empty_scope", "invalid_policy",
])
def test_deserialization_rejects_malformed_fields_without_echoing_input(mutation):
    value = context().to_dict()
    scope = value["authorized_scope"]
    if mutation == "unknown_field":
        value["unexpected"] = "private-input"
    elif mutation == "unknown_scope_field":
        scope["privileged"] = True
    elif mutation == "string_roles":
        scope["roles"] = "SYSTEM_ADMIN"
    elif mutation == "mixed_roles":
        scope["roles"] = ["STUDENT", 1]
    elif mutation == "missing_scope":
        del value["authorized_scope"]
    elif mutation == "missing_actor":
        del scope["actor_id"]
    elif mutation == "numeric_actor":
        scope["actor_id"] = 123
    elif mutation == "numeric_locale":
        value["locale"] = 123
    elif mutation == "numeric_time":
        value["effective_at"] = 123
    elif mutation == "naive_time":
        value["effective_at"] = "2026-10-03T00:00:00"
    elif mutation == "invalid_time":
        value["effective_at"] = "private-input"
    elif mutation == "empty_scope":
        scope["audiences"] = []
    else:
        value["simulation_policy"] = "private-input"
    with pytest.raises(ValueError) as error:
        RetrievalContext.from_dict(value)
    assert str(error.value) == "invalid serialized retrieval context"


def test_typed_context_is_immutable_and_round_trip_preserves_scope():
    original = context()
    assert RetrievalContext.from_dict(original.to_dict()) == original
    with pytest.raises(FrozenInstanceError):
        original.authorized_scope = authorized_scope()
    with pytest.raises(AttributeError):
        original.authorized_scope.roles.add("SYSTEM_ADMIN")


@pytest.mark.parametrize("values", [["CT-101"], "CT-101", (True,)])
def test_query_identifiers_require_typed_immutable_tuple(values):
    with pytest.raises(ValueError, match="tuple of strings"):
        RetrievalQuery("synthetic query", exact_identifiers=values)
