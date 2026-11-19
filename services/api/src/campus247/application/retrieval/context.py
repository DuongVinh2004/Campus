from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Callable, Protocol

from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy
from campus247.ports.identity import AccountState, IdentityContext, IdentityRole


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RetrievalContextError(ValueError):
    """Raised when trusted retrieval context cannot be established."""


@dataclass(frozen=True)
class ResolvedRetrievalScope:
    tenant_id: str
    campus_id: str
    audiences: frozenset[str]
    faculty_codes: frozenset[str]
    program_codes: frozenset[str]


class TrustedScopeResolver(Protocol):
    def resolve(self, identity: IdentityContext) -> ResolvedRetrievalScope:
        ...


class RetrievalContextFactory:
    """Builds authorization scope only from verified identity and server-side data."""

    def __init__(
        self,
        *,
        scope_resolver: TrustedScopeResolver,
        configured_tenant_id: str,
        configured_campus_id: str,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._scope_resolver = scope_resolver
        self._clock = clock
        self._tenant_id = configured_tenant_id.strip()
        self._campus_id = configured_campus_id.strip()
        if not self._tenant_id or not self._campus_id:
            raise RetrievalContextError("configured tenant and campus are required")

    def create(
        self,
        identity: IdentityContext,
        *,
        effective_at: datetime,
        locale: str,
        trace_id: str,
        allow_simulation: bool = False,
    ) -> RetrievalContext:
        if not isinstance(identity, IdentityContext):
            raise RetrievalContextError("verified identity is required")
        if identity.account_state is not AccountState.ACTIVE:
            raise RetrievalContextError("identity must be active")
        if not isinstance(effective_at, datetime) or effective_at.tzinfo is None or effective_at.utcoffset() is None:
            raise RetrievalContextError("effective_at must be timezone-aware")
        # Match the opaque IDs emitted by bootstrap.telemetry. Never interpolate
        # rejected values into errors: they may contain PII or log control bytes.
        if not isinstance(trace_id, str) or re.fullmatch(r"[0-9a-f]{32}", trace_id) is None or trace_id == "0" * 32:
            raise RetrievalContextError("audit-safe trace ID is required")

        at_utc = effective_at.astimezone(timezone.utc)
        now = self._clock()
        for instant in (now, identity.auth_time, identity.expires_at):
            if not isinstance(instant, datetime) or instant.tzinfo is None or instant.utcoffset() is None:
                raise RetrievalContextError("identity and server times must be timezone-aware")
        now_utc = now.astimezone(timezone.utc)
        # Applicability time may describe a past/future policy. It must never be
        # used as the authentication clock, or a past query revives an expired session.
        if identity.expires_at.astimezone(timezone.utc) <= now_utc:
            raise RetrievalContextError("identity session is expired")
        if identity.auth_time.astimezone(timezone.utc) > now_utc:
            raise RetrievalContextError("identity authentication time is in the future")
        if not identity.roles:
            raise RetrievalContextError("identity roles are required")
        if any(not isinstance(role, IdentityRole) for role in identity.roles):
            raise RetrievalContextError("identity roles must be verified role codes")

        identity_tenant = (identity.tenant_id or "").strip()
        if not identity_tenant or identity_tenant != self._tenant_id:
            raise RetrievalContextError("identity tenant does not match configured tenant")
        resolved = self._scope_resolver.resolve(identity)
        if not isinstance(resolved, ResolvedRetrievalScope):
            raise RetrievalContextError("trusted scope resolution is required")
        if resolved.tenant_id != self._tenant_id or resolved.campus_id != self._campus_id:
            raise RetrievalContextError("resolved scope crosses the configured tenant or campus")
        if identity.faculty_code and identity.faculty_code not in resolved.faculty_codes:
            raise RetrievalContextError("resolved scope does not contain the trusted faculty claim")

        return RetrievalContext(
            authorized_scope=AuthorizedScope(
                tenant_id=resolved.tenant_id,
                campus_id=resolved.campus_id,
                actor_id=identity.subject_id,
                roles=frozenset(role.value for role in identity.roles),
                audiences=resolved.audiences,
                faculty_codes=resolved.faculty_codes,
                program_codes=resolved.program_codes,
            ),
            locale=locale,
            effective_at=at_utc,
            simulation_policy=(
                SimulationPolicy.ALLOW_LABELED
                if allow_simulation and identity.is_synthetic
                else SimulationPolicy.DENY
            ),
            trace_id=trace_id,
        )
