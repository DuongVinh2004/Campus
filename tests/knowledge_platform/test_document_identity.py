from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from campus247.application.knowledge.document_identity import (
    ApplicabilityScope, EditionIdentity, EffectiveInterval, ObservationIdentity,
    RenditionIdentity, ScopeAxis, SourceWitness, StageBinding, DraftIntakeInput,
)
from campus247.application.knowledge.platform_models import digest


def witness():
    text = "Hiệu lực từ ngày 01/11/2026."
    return SourceWitness(artifact_id=uuid4(), artifact_sha256="a"*64,
        locator={"page": 1}, verbatim=text, text_sha256=digest(text.encode()))


def test_unknown_scope_is_not_all_and_same_name_is_not_identity():
    assert ScopeAxis() != ScopeAxis(kind="ALL")
    for kwargs in ({"kind": "VALUES"}, {"kind": "ALL", "values": ["K71"]}):
        with pytest.raises(ValidationError):
            ScopeAxis(**kwargs)
    common = dict(tenant_id="test", family_id=uuid4(), issuer="HUCE")
    k70 = EditionIdentity(**common, scope=ApplicabilityScope(cohorts=ScopeAxis(kind="VALUES", values=("K70",))))
    k71 = EditionIdentity(**common, scope=ApplicabilityScope(cohorts=ScopeAxis(kind="VALUES", values=("K71",))))
    assert k70 != k71


def test_two_observations_do_not_merge_authority_for_identical_bytes():
    artifact = uuid4()
    first = ObservationIdentity(tenant_id="one", artifact_id=artifact, observed_at=datetime.now(UTC), source_uri="https://one.example")
    second = first.model_copy(update={"tenant_id": "two", "source_uri": "https://two.example"})
    assert first != second


def test_ocr_is_a_new_rendition_of_the_same_edition():
    edition = uuid4()
    first = RenditionIdentity(edition_id=edition, source_sha256="a"*64, artifact_id=uuid4(),
        processor_revision="ocr-v1", config_sha256="b"*64, schema_revision="1")
    second = first.model_copy(update={"artifact_id": uuid4(), "processor_revision": "ocr-v2"})
    assert first.edition_id == second.edition_id and first != second
    assert "issued_on" not in second.model_dump()


def test_effective_dates_require_real_basis_and_preserve_day_precision():
    assert EffectiveInterval().from_day is None
    valid = EffectiveInterval(from_day=date(2026, 11, 1), basis=witness())
    assert valid.model_dump(mode="json")["from_day"] == "2026-11-01"
    for values in ({"from_day": date.today()}, {"until_day": date.today()},
                   {"from_day": date.today(), "until_day": date.today(), "basis": witness()}):
        with pytest.raises(ValidationError):
            EffectiveInterval(**values)


def test_draft_needs_no_fake_dates_or_scopes():
    assert DraftIntakeInput().model_dump() == {"title_hint": None, "source_uri": None}
    with pytest.raises(ValidationError):
        DraftIntakeInput(effective_from=datetime.now(UTC))


def test_full_cache_binding_changes_with_each_dependency():
    binding = StageBinding(tenant_id="a", authorization_scope_sha256="a"*64, stage="EMBED",
        input_sha256="b"*64, dependency_sha256=("c"*64,), processor_revision="parser1",
        config_sha256="d"*64, schema_revision="1", validator_revision="1", model_identity="bge@revision:profile")
    for field, value in {"tenant_id": "b", "authorization_scope_sha256": "e"*64,
        "input_sha256": "f"*64, "dependency_sha256": ("d"*64,), "processor_revision": "parser2",
        "config_sha256": "e"*64, "schema_revision": "2", "validator_revision": "2", "model_identity": "bge@other"}.items():
        assert binding.model_copy(update={field: value}).cache_key() != binding.cache_key()
    with pytest.raises(ValidationError):
        StageBinding(**(binding.model_dump() | {"model_identity": None}))
