from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from itertools import combinations

import pytest

from campus247.application.retrieval.filters import RetrievalFilterCompiler, RetrievalFilterError
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy
from campus247.ports.identity import IdentityRole


def context(**scope_changes):
    scope = AuthorizedScope("tenant-huce", "HUCE", "synthetic-actor", frozenset({"STUDENT"}),
                            frozenset({"STUDENT"}), frozenset({"FIT"}), frozenset({"SYN-CS"}))
    return RetrievalContext(replace(scope, **scope_changes), "vi", datetime(2026, 10, 3, tzinfo=timezone.utc),
                            SimulationPolicy.ALLOW_LABELED, "123456789abcdef0123456789abcdef0")


def compiler(simulation=False):
    return RetrievalFilterCompiler(tenant_id="tenant-huce", campus_id="HUCE", profile_allows_simulation=simulation)


ROLES = tuple(role.value for role in IdentityRole)
ROLE_SETS = [frozenset(values) for size in range(1, 5) for values in combinations(ROLES, size)]


@pytest.mark.parametrize("roles", ROLE_SETS)
@pytest.mark.parametrize("audience", ROLES)
def test_every_approved_role_combination_keeps_trusted_scope_as_bound_data(roles, audience):
    value = context(roles=roles, audiences=frozenset({audience}))
    result = compiler().compile(value)
    assert result.parameters["audiences"] == (audience,)
    assert result.parameters["faculties"] == ("FIT",)
    assert result.parameters["programs"] == ("SYN-CS",)
    assert result.parameters["effective_at"] == value.effective_at
    assert audience not in result.named_sql
    assert result.asyncpg_sql.count("$3") == 2
    assert "$8" in result.asyncpg_sql and ":effective_at" not in result.asyncpg_sql


@pytest.mark.parametrize("tenant,campus", [("other", "HUCE"), ("tenant-huce", "OTHER")])
def test_cross_tenant_or_campus_fails_closed(tenant, campus):
    with pytest.raises(RetrievalFilterError, match="configured boundary"):
        compiler().compile(context(tenant_id=tenant, campus_id=campus))


@pytest.mark.parametrize("value", [None, {}, {"roles": ["SYSTEM_ADMIN"]}, "context"])
def test_untrusted_untyped_context_is_rejected(value):
    with pytest.raises(RetrievalFilterError, match="typed trusted"):
        compiler().compile(value)


@pytest.mark.parametrize("field", ["roles", "audiences", "faculty_codes", "program_codes"])
def test_empty_scope_cannot_compile_even_if_constructor_was_bypassed(field):
    value = context()
    object.__setattr__(value.authorized_scope, field, frozenset())
    with pytest.raises(RetrievalFilterError, match="invalid trusted"):
        compiler().compile(value)


def test_unknown_roles_fail_closed_and_errors_do_not_echo_input():
    with pytest.raises(RetrievalFilterError) as error:
        compiler().compile(context(roles=frozenset({"private-invalid-role"})))
    assert str(error.value) == "approved identity roles required"


@pytest.mark.parametrize("profile", [False, True])
@pytest.mark.parametrize("policy", [SimulationPolicy.DENY, SimulationPolicy.ALLOW_LABELED])
def test_simulation_requires_both_profile_and_trusted_context(profile, policy):
    result = compiler(profile).compile(replace(context(), simulation_policy=policy))
    assert result.parameters["allow_synthetic"] is (profile and policy is SimulationPolicy.ALLOW_LABELED)


def test_injection_like_values_never_enter_sql_and_filter_is_immutable():
    payload = "SYN-CS'); SELECT 'private-input'; --"
    result = compiler().compile(context(program_codes=frozenset({payload})))
    assert payload not in result.named_sql and payload not in result.asyncpg_sql
    assert result.parameters["programs"] == (payload,)
    with pytest.raises(TypeError):
        result.parameters["programs"] = ("OTHER",)
    with pytest.raises(FrozenInstanceError):
        result.values = ()
    assert "private-input" not in repr(result)


@pytest.mark.parametrize("changes", [{"tenant_id": ""}, {"campus_id": "OTHER"},
                                     {"profile_allows_simulation": "true"}])
def test_invalid_server_configuration_is_rejected(changes):
    with pytest.raises(RetrievalFilterError, match="configuration"):
        RetrievalFilterCompiler(**({"tenant_id": "tenant-huce", "campus_id": "HUCE"} | changes))
