from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from campus247.application.retrieval.context import (
    ResolvedRetrievalScope,
    RetrievalContextError,
    RetrievalContextFactory,
)
from campus247.domain.retrieval import SimulationPolicy
from campus247.domain.shared.values import generate_uuid7
from campus247.ports.identity import AccountState, IdentityContext, IdentityRole


NOW = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
TRACE_ID = "123456789abcdef0123456789abcdef0"


class StaticTrustedScopeResolver:
    def __init__(self, scope: ResolvedRetrievalScope) -> None:
        self.scope = scope

    def resolve(self, identity: IdentityContext) -> ResolvedRetrievalScope:
        assert identity.subject_id
        return self.scope


def identity(**overrides: object) -> IdentityContext:
    values: dict[str, object] = {
        "subject_id": generate_uuid7(),
        "external_subject": "verified-subject",
        "issuer": "urn:campus247:issuer:synthetic",
        "roles": (IdentityRole.STUDENT,),
        "display_name": "Synthetic Student",
        "auth_time": NOW - timedelta(minutes=5),
        "expires_at": NOW + timedelta(hours=1),
        "tenant_id": "tenant-huce",
        "student_code": "SYN001",
        "faculty_code": "FIT",
        "is_synthetic": True,
    }
    values.update(overrides)
    return IdentityContext(**values)  # type: ignore[arg-type]


def factory(scope: ResolvedRetrievalScope | None = None) -> RetrievalContextFactory:
    return RetrievalContextFactory(
        scope_resolver=StaticTrustedScopeResolver(
            scope
            or ResolvedRetrievalScope(
                tenant_id="tenant-huce",
                campus_id="HUCE",
                audiences=frozenset({"STUDENT"}),
                faculty_codes=frozenset({"FIT"}),
                program_codes=frozenset({"SOFTWARE_ENGINEERING"}),
            )
        ),
        configured_tenant_id="tenant-huce",
        configured_campus_id="HUCE",
        clock=lambda: NOW,
    )


def test_factory_uses_only_verified_identity_and_resolved_scope() -> None:
    actor = identity()
    context = factory().create(
        actor,
        effective_at=NOW,
        locale="vi",
        trace_id=TRACE_ID,
        allow_simulation=True,
    )

    assert context.authorized_scope.actor_id == actor.subject_id
    assert context.authorized_scope.roles == frozenset({"STUDENT"})
    assert context.authorized_scope.faculty_codes == frozenset({"FIT"})
    assert context.simulation_policy is SimulationPolicy.ALLOW_LABELED


def test_request_controlled_authorization_fields_are_not_accepted() -> None:
    with pytest.raises(TypeError):
        factory().create(
            identity(),
            effective_at=NOW,
            locale="vi",
            trace_id=TRACE_ID,
            role="SYSTEM_ADMIN",  # type: ignore[call-arg]
            tenant_id="other-tenant",  # type: ignore[call-arg]
        )


def test_missing_or_inactive_identity_fails_closed() -> None:
    with pytest.raises(RetrievalContextError, match="verified identity"):
        factory().create(None, effective_at=NOW, locale="vi", trace_id=TRACE_ID)  # type: ignore[arg-type]
    with pytest.raises(RetrievalContextError, match="active"):
        factory().create(
            identity(account_state=AccountState.SUSPENDED),
            effective_at=NOW,
            locale="vi",
            trace_id=TRACE_ID,
        )


def test_expired_identity_and_tenant_crossing_fail_closed() -> None:
    with pytest.raises(RetrievalContextError, match="expired"):
        factory().create(
            identity(expires_at=NOW),
            effective_at=NOW,
            locale="vi",
            trace_id=TRACE_ID,
        )

    crossed = ResolvedRetrievalScope(
        tenant_id="other-tenant",
        campus_id="OTHER",
        audiences=frozenset({"STUDENT"}),
        faculty_codes=frozenset({"FIT"}),
        program_codes=frozenset({"SOFTWARE_ENGINEERING"}),
    )
    with pytest.raises(RetrievalContextError, match="crosses"):
        factory(crossed).create(
            identity(),
            effective_at=NOW,
            locale="vi",
            trace_id=TRACE_ID,
        )


def test_real_identity_cannot_enable_simulation() -> None:
    context = factory().create(
        identity(is_synthetic=False),
        effective_at=NOW,
        locale="vi",
        trace_id=TRACE_ID,
        allow_simulation=True,
    )
    assert context.simulation_policy is SimulationPolicy.DENY


@pytest.mark.parametrize("trace", ["", "trace\nforged-entry", "person@example.invalid", "a" * 33,
                                  "0" * 32, " " + TRACE_ID, None])
def test_trace_id_rejects_log_injection_pii_and_unbounded_values(trace):
    with pytest.raises(RetrievalContextError, match="audit-safe") as error:
        factory().create(identity(), effective_at=NOW, locale="vi", trace_id=trace)
    assert str(error.value) == "audit-safe trace ID is required"


def test_historical_query_cannot_revive_an_expired_session():
    with pytest.raises(RetrievalContextError, match="expired"):
        factory().create(identity(expires_at=NOW), effective_at=NOW - timedelta(days=10),
                         locale="vi", trace_id=TRACE_ID)


def test_future_policy_query_uses_current_session_not_effective_time():
    future = NOW + timedelta(days=10)
    context = factory().create(identity(), effective_at=future, locale="vi", trace_id=TRACE_ID)
    assert context.effective_at == future
    assert context.trace_id == TRACE_ID


def test_future_authentication_time_is_rejected():
    with pytest.raises(RetrievalContextError, match="future"):
        factory().create(identity(auth_time=NOW + timedelta(minutes=1)), effective_at=NOW,
                         locale="vi", trace_id=TRACE_ID)


def test_naive_identity_timestamps_are_rejected():
    with pytest.raises(RetrievalContextError, match="timezone-aware"):
        factory().create(identity(auth_time=NOW.replace(tzinfo=None) - timedelta(minutes=5),
                                  expires_at=NOW.replace(tzinfo=None) + timedelta(hours=1)),
                         effective_at=NOW, locale="vi", trace_id=TRACE_ID)


def test_unverified_roles_are_rejected():
    with pytest.raises(RetrievalContextError, match="verified role"):
        factory().create(identity(roles=("SYSTEM_ADMIN",)), effective_at=NOW,
                         locale="vi", trace_id=TRACE_ID)


def test_invalid_actor_does_not_reach_scope_resolver():
    class MustNotResolve:
        def resolve(self, actor):
            pytest.fail("invalid actor must be rejected before trusted data lookup")

    builder = RetrievalContextFactory(scope_resolver=MustNotResolve(),
                                      configured_tenant_id="tenant-huce", configured_campus_id="HUCE",
                                      clock=lambda: NOW)
    with pytest.raises(RetrievalContextError, match="tenant"):
        builder.create(identity(tenant_id="other-tenant"), effective_at=NOW,
                       locale="vi", trace_id=TRACE_ID)


def test_server_clock_defaults_to_current_utc_time():
    class MustNotResolve:
        def resolve(self, actor):
            pytest.fail("expired identity must not reach resolver")

    builder = RetrievalContextFactory(scope_resolver=MustNotResolve(),
                                      configured_tenant_id="tenant-huce", configured_campus_id="HUCE")
    expired_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(RetrievalContextError, match="expired"):
        builder.create(identity(auth_time=expired_at - timedelta(minutes=5), expires_at=expired_at),
                       effective_at=expired_at - timedelta(minutes=1), locale="vi", trace_id=TRACE_ID)
