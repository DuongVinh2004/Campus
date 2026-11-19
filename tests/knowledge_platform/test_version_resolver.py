from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from campus247.application.knowledge.document_identity import ApplicabilityScope, EditionIdentity, EffectiveInterval, ScopeAxis, SourceWitness
from campus247.application.knowledge.platform_models import digest
from campus247.application.knowledge.version_resolver import EditionCandidate, EditionRelation, ResolutionQuery, resolve_editions

KNOWN = datetime(2026, 10, 26, tzinfo=UTC)
FAMILY = uuid4()


def witness():
    text = "\n Có hiệu lực kể từ ngày 01/01/2026.\n"
    return SourceWitness(artifact_id=uuid4(), artifact_sha256="a"*64, locator={"page": 1}, verbatim=text, text_sha256=digest(text.encode()))


def interval(start=date(2026,1,1), end=None):
    return EffectiveInterval(from_day=start, until_day=end, end_kind="KNOWN" if end else "OPEN", basis=witness())


def candidate(*, cohorts=("K71",), start=date(2026,1,1), end=None, units=("rule", "exception"), **updates):
    scope = ApplicabilityScope(programmes=ScopeAxis(kind="ALL"), cohorts=ScopeAxis(kind="VALUES", values=cohorts), academic_years=ScopeAxis(kind="ALL"))
    identity = EditionIdentity(tenant_id="test", family_id=FAMILY, issuer="Synthetic issuer", scope=scope,
        effective=interval(start, end), verification="VERIFIED", identity_basis=witness())
    return EditionCandidate(**({"edition_id": uuid4(), "identity": identity, "recorded_at": KNOWN,
        "unit_ids": frozenset(units), "dependency_graph_verified": True} | updates))


def query(cohorts=("K71",), day=date(2026,10,26), known=KNOWN):
    return ResolutionQuery(family_ids=(FAMILY,), at_day=day, known_at=known, cohorts=cohorts)


def relation(new, old, kind="REPLACES", **kwargs):
    return EditionRelation(from_edition=new.edition_id, to_edition=old.edition_id, kind=kind,
        effective=interval(), recorded_at=KNOWN, witness=witness(), decision_state="VERIFIED", **kwargs)


def selected(result, segment=0):
    return {row["edition_id"]: row["unit_ids"] for row in result["segments"][segment]["selected"]}


def test_verbatim_hash_preserves_whitespace_and_day_precision_is_not_invented():
    assert witness().verbatim.startswith("\n ")
    with pytest.raises(ValidationError):
        EffectiveInterval(from_day=datetime.now(UTC), basis=witness())


def test_future_and_history_use_business_time_not_recent_upload():
    old = candidate()
    future = candidate(start=date(2027,1,1), recorded_at=datetime(2026,10,26,1,tzinfo=UTC))
    result = resolve_editions(query(known=datetime(2026,10,27,tzinfo=UTC)), [old, future])
    assert set(selected(result)) == {str(old.edition_id)}
    assert any(r["reason"] == "FUTURE_EDITION" for r in result["segments"][0]["excluded"])
    historical = candidate(start=date(2025,1,1), end=date(2026,1,1))
    result = resolve_editions(query(day=date(2025,6,1)), [old, historical])
    assert set(selected(result)) == {str(historical.edition_id)}


def test_unknown_end_is_not_forever_and_unknown_scope_is_not_all():
    item = candidate()
    unknown_end = item.model_copy(update={"identity": item.identity.model_copy(update={"effective": EffectiveInterval(from_day=date(2026,1,1), basis=witness())})})
    result = resolve_editions(query(), [unknown_end])
    assert not selected(result) and result["state"] == "NEEDS_INFORMATION"
    unknown_scope = item.model_copy(update={"identity": item.identity.model_copy(update={"scope": ApplicabilityScope()})})
    assert not selected(resolve_editions(query(), [unknown_scope]))


def test_late_knowledge_does_not_rewrite_what_was_known_before():
    item = candidate(recorded_at=datetime(2026,10,27,tzinfo=UTC))
    result = resolve_editions(query(), [item])
    assert not selected(result)
    assert result["segments"][0]["excluded"][0]["reason"] == "NOT_KNOWN_AT_QUERY_TIME"


def test_no_latest_upload_winner_without_replacement_witness():
    first, second = candidate(), candidate(recorded_at=datetime(2026,10,26,1,tzinfo=UTC))
    result = resolve_editions(query(known=datetime(2026,10,27,tzinfo=UTC)), [first,second])
    assert result["state"] == "NEEDS_INFORMATION" and not selected(result)
    assert any(r["reason"] == "EDITION_CONFLICT" for r in result["segments"][0]["issues"])


def test_replacement_preserves_other_cohort_in_a_multi_scope_question():
    old = candidate(cohorts=("K70","K71"))
    new = candidate(cohorts=("K71",))
    result = resolve_editions(query(cohorts=("K70","K71")), [old,new], [relation(new,old)])
    assert set(selected(result,0)) == {str(old.edition_id)}
    assert set(selected(result,1)) == {str(new.edition_id)}


def test_partial_amendment_retains_unmodified_rule_and_exception():
    old = candidate(units=("rule-1","rule-2","exception"))
    new = candidate(units=("rule-1-amended",), dependencies={"rule-1-amended": frozenset({"exception"})})
    result = resolve_editions(query(), [old,new], [relation(new,old,"PARTIAL_AMEND",target_unit_ids=frozenset({"rule-1"}))])
    assert selected(result)[str(old.edition_id)] == ["exception","rule-2"]
    assert selected(result)[str(new.edition_id)] == ["rule-1-amended"]


def test_partial_amendment_cannot_cut_the_exception_or_guess_unknown_targets():
    old = candidate(dependencies={"rule": frozenset({"exception"})})
    new = candidate(units=("amended",))
    bad = relation(new,old,"PARTIAL_AMEND",target_unit_ids=frozenset({"exception"}))
    result = resolve_editions(query(), [old,new], [bad])
    assert not selected(result)
    assert any(r["reason"] == "EVIDENCE_DEPENDENCY_MISSING" for r in result["segments"][0]["issues"])
    unknown = relation(new,old,"PARTIAL_AMEND",target_unit_ids=frozenset({"missing"}))
    assert not selected(resolve_editions(query(), [old,new], [unknown]))


def test_supplement_combines_both_and_proposal_does_not_grant_authority():
    old,new = candidate(),candidate(units=("addition",))
    allowed = relation(new,old,"SUPPLEMENTS")
    assert len(selected(resolve_editions(query(), [old,new], [allowed]))) == 2
    assert not selected(resolve_editions(query(), [old,new], [allowed.model_copy(update={"decision_state":"PROPOSED"})]))


def test_replacement_cycle_current_revocation_and_missing_query_scope_fail_closed():
    a,b = candidate(),candidate()
    assert not selected(resolve_editions(query(), [a,b], [relation(a,b),relation(b,a)]))
    assert not selected(resolve_editions(query(), [a.model_copy(update={"currently_authorized":False})]))
    assert not selected(resolve_editions(query(cohorts=()), [a]))


def test_cycle_blocks_only_related_families_and_long_history_does_not_recurse():
    from campus247.application.knowledge.version_resolver import cyclic_component
    chain = {str(index): {str(index+1)} for index in range(1500)}
    assert not cyclic_component(chain)
    a,b = candidate(),candidate()
    independent = candidate()
    independent = independent.model_copy(update={"identity": independent.identity.model_copy(update={"family_id":uuid4()})})
    request = query().model_copy(update={"family_ids":(FAMILY,independent.identity.family_id)})
    result = resolve_editions(request,[a,b,independent],[relation(a,b),relation(b,a)])
    assert set(selected(result)) == {str(independent.edition_id)}


def test_partial_amendment_requires_base_context_even_when_only_new_family_is_requested():
    old,new = candidate(),candidate(units=("amended",))
    result = resolve_editions(query(),[new],[relation(new,old,"PARTIAL_AMEND",target_unit_ids=frozenset({"rule"}))])
    assert not selected(result)
    assert any(issue["reason"] == "AMENDMENT_CONTEXT_UNAVAILABLE" for issue in result["segments"][0]["issues"])
