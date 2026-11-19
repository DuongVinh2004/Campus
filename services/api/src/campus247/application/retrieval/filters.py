"""One fail-closed eligibility predicate shared by lexical and vector SQL."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping

from campus247.domain.retrieval import RetrievalContext, SimulationPolicy
from campus247.ports.identity import IdentityRole


class RetrievalFilterError(ValueError):
    """Constant safe errors; never echo claims, SQL parameters or query text."""


# Only these fixed identifiers/operators enter SQL. All context values are binds.
# Aliases s/v belong to the candidate relation, before ranking and LIMIT.
_NAMED_SQL = """s.approval_status = 'APPROVED' AND v.status = 'PUBLISHED'
    AND v.effective_from <= :effective_at
    AND (v.effective_until > :effective_at
         OR (v.effective_until IS NULL AND v.applicability_reviewed_at IS NOT NULL))
    AND s.campus_scope = :campus
    AND s.faculty_scope && CAST(:faculties AS varchar[])
    AND s.program_scope && CAST(:programs AS varchar[])
    AND s.audiences && CAST(:audiences AS varchar[])
    AND (NOT s.is_synthetic OR :allow_synthetic)"""
_NAMES = ("effective_at", "campus", "faculties", "programs", "audiences", "allow_synthetic")
_ASYNCPG_SQL = _NAMED_SQL
for _number, _name in enumerate(_NAMES, start=3):
    _ASYNCPG_SQL = _ASYNCPG_SQL.replace(":" + _name, "$" + str(_number))


@dataclass(frozen=True)
class CompiledRetrievalFilter:
    """Immutable eligibility binds; no raw actor/trace/query in diagnostics."""

    values: tuple[object, ...] = field(repr=False)

    @property
    def named_sql(self) -> str:
        return _NAMED_SQL

    @property
    def asyncpg_sql(self) -> str:
        """$1/$2 reserved for query and candidate limit in either branch."""
        return _ASYNCPG_SQL

    @property
    def parameters(self) -> Mapping[str, object]:
        return MappingProxyType(dict(zip(_NAMES, self.values, strict=True)))


class RetrievalFilterCompiler:
    """Consume server-created context and independently configured trust boundary.

    V1 is one institution: tenant is checked against server configuration before
    SQL, campus is stored on knowledge_source. No tenant column is invented.
    Compilation validates structure; it does not authenticate client claims.
    """

    def __init__(self, *, tenant_id: str, campus_id: str,
                 profile_allows_simulation: bool = False) -> None:
        if (not isinstance(tenant_id, str) or not tenant_id.strip()
                or tenant_id != tenant_id.strip() or campus_id != "HUCE"
                or type(profile_allows_simulation) is not bool):
            raise RetrievalFilterError("trusted retrieval configuration required")
        self._tenant_id = tenant_id
        self._campus_id = campus_id
        self._simulation = profile_allows_simulation

    def compile(self, context: RetrievalContext) -> CompiledRetrievalFilter:
        if not isinstance(context, RetrievalContext):
            raise RetrievalFilterError("typed trusted retrieval context required")
        # Revalidate every typed field at this boundary, including empty scope.
        try:
            validated = RetrievalContext.from_dict(context.to_dict())
        except (AttributeError, TypeError, ValueError):
            raise RetrievalFilterError("invalid trusted retrieval context") from None
        scope = validated.authorized_scope
        if scope.tenant_id != self._tenant_id or scope.campus_id != self._campus_id:
            raise RetrievalFilterError("retrieval context crosses configured boundary")
        if not scope.roles <= frozenset(role.value for role in IdentityRole):
            raise RetrievalFilterError("approved identity roles required")
        return CompiledRetrievalFilter((
            validated.effective_at, scope.campus_id, tuple(sorted(scope.faculty_codes)),
            tuple(sorted(scope.program_codes)), tuple(sorted(scope.audiences)),
            self._simulation and validated.simulation_policy is SimulationPolicy.ALLOW_LABELED,
        ))


def _parse_dt(val: Any) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if isinstance(val, str):
        # Handle ISO strings ending in Z or offset
        cleaned = val.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return None


@dataclass(frozen=True)
class RetrievalFilter:
    """Metadata and effective-date filter for knowledge retrieval candidate gating."""

    status: str = "PUBLISHED"
    reference_date: datetime | None = None
    audience: str | None = None
    faculty_scope: str | None = None
    is_synthetic: bool | None = None

    def matches(self, meta: dict[str, Any]) -> bool:
        # Status gate: must be exactly PUBLISHED
        doc_status = meta.get("status")
        if doc_status != self.status:
            return False

        # Synthetic match if specified
        if self.is_synthetic is not None:
            if meta.get("is_synthetic", True) != self.is_synthetic:
                return False

        # Effective date gate
        ref = self.reference_date or datetime.now(timezone.utc)
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)

        eff_from = _parse_dt(meta.get("effective_from"))
        if eff_from and eff_from > ref:
            return False

        eff_until = _parse_dt(meta.get("effective_until"))
        if eff_until and eff_until < ref:
            return False

        # Audience gate
        if self.audience:
            audiences = meta.get("audiences")
            if audiences is not None:
                if not any(a in ("ALL", self.audience) for a in audiences):
                    return False

        # Faculty scope gate
        if self.faculty_scope and self.faculty_scope != "ALL":
            scope = meta.get("faculty_scope")
            if scope and scope not in ("ALL", self.faculty_scope):
                return False

        return True
