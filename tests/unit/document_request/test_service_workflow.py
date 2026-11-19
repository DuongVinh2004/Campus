from dataclasses import FrozenInstanceError, replace
from datetime import timedelta

import pytest

from campus247.domain.service_request import ServiceForm, staff_transition, TEMPLATE_VERSION
from campus247.domain.service_workflow import WORKFLOWS, workflow_at, record_workflow


def test_version_selection_uses_half_open_milestone_intervals_and_preserves_old_template():
    original = WORKFLOWS[0]
    boundary = original.effective_from + timedelta(days=1)
    old = replace(original, effective_until=boundary)
    new = replace(original, version="fixture-v2", effective_from=boundary,
                  template=replace(original.template, version="fixture-template-v2"))
    assert workflow_at(original.kind, boundary - timedelta(microseconds=1), (new, old)) == old
    assert workflow_at(original.kind, boundary, (old, new)) == new
    assert old.template.version == TEMPLATE_VERSION
    with pytest.raises(ValueError, match="VERSION_UNRESOLVED"):
        workflow_at(original.kind, original.effective_from - timedelta(seconds=1), (old, new))
    with pytest.raises(ValueError, match="VERSION_UNRESOLVED"):
        workflow_at(original.kind, boundary, (original, new))
    with pytest.raises(ValueError, match="MILESTONE_UNRESOLVED"):
        workflow_at(original.kind, boundary.replace(tzinfo=None))


def test_submitted_milestone_wins_over_later_updates():
    original = WORKFLOWS[0]
    record = {"document_type": original.kind, "created_at": "2020-01-01T00:00:00+00:00",
              "submitted_at": original.effective_from.isoformat(), "updated_at": "2030-01-01T00:00:00+00:00"}
    assert record_workflow(record) == original
    record["submitted_at"] = None
    with pytest.raises(ValueError, match="VERSION_UNRESOLVED"):
        record_workflow(record)


def test_shared_form_fields_reviews_and_templates_are_immutable():
    for definition in WORKFLOWS:
        assert all(c.required and c.reviewer == "SUPPORT_OFFICER" for c in definition.mandatory_reviews)
        assert "decision_reason" in {c.id for c in definition.mandatory_reviews}
        assert definition.classification == "synthetic"
        with pytest.raises(FrozenInstanceError):
            definition.version = "changed"
        body = {"kind": definition.kind, "reason": "Fixture", "course_record_id": "fixture-course" if definition.kind == "GRADE_APPEAL" else None}
        assert ServiceForm(**body).kind == definition.kind
        for field in definition.required_form_fields:
            with pytest.raises(ValueError):
                ServiceForm(**{**body, field: ""})


@pytest.mark.parametrize("status,action,result", [("SUBMITTED", "claim", "VALIDATING"),
    ("PROCESSING", "request_information", "WAITING_STUDENT"), ("WAITING_STUDENT", "supplement", "VALIDATING"),
    ("WAITING_STUDENT", "transfer", "WAITING_STUDENT"), ("PROCESSING", "resolve", "READY")])
def test_existing_state_rules_are_preserved(status, action, result):
    assert staff_transition(status, action) == result


@pytest.mark.parametrize("status,action", [("DRAFT", "claim"), ("SUBMITTED", "resolve"),
    ("READY", "resolve"), ("REJECTED", "claim"), ("PROCESSING", "approve")])
def test_invalid_or_terminal_actions_remain_rejected(status, action):
    with pytest.raises(ValueError, match="INVALID_STATE"):
        staff_transition(status, action)
