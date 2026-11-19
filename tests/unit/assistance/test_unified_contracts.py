from copy import deepcopy

import pytest
from pydantic import ValidationError

from campus247.application.assistance.unified_contracts import (
    IntentProposal, DraftProposal, PreferencesPatch, GrantRequest, TaskRequest,
    SupplementProposal, BatchPreparationRequest, ConversationMetadataPatch, MessagePageRequest,
)

ID = "019a0000-0000-7000-8000-000000000001"
OTHER = "019a0000-0000-7000-8000-000000000002"
REF = {"kind":"service_request","id":ID,"expected_version":1}
EVIDENCE = {"source_id":"source","version_id":"version-1","locator":"demo fixture / section1",
            "sha256":"a"*64,"classification":"synthetic"}
BINDING = {"workflow":"GRADE_APPEAL","version":"demo-v1","source":EVIDENCE,"effective_from":"2026-10-13T00:00:00+00:00"}
PROPOSAL = {"client_id":ID,"target":REF,"workflow_binding":BINDING,"audience":"student","operation":"revise_draft",
            "changes":[{"field":"reason","before":"old","candidate":"new","origin":"user_statement"}]}


def test_valid_proposal_remains_preparation_not_confirmation():
    p = DraftProposal.model_validate(PROPOSAL)
    assert p.action_authority == "none" and p.target.expected_version == 1


@pytest.mark.parametrize("extra", [{"user_confirmed":True},{"confirmation_token":"fake"},{"role":"SUPPORT_OFFICER"},
    {"actor_id":ID},{"tools":["approve"]},{"receipt_id":OTHER}])
def test_model_cannot_add_authority_to_proposal(extra):
    with pytest.raises(ValidationError):
        DraftProposal.model_validate({**PROPOSAL,**extra})


@pytest.mark.parametrize("change", [
    {"operation":"approve"},{"action_authority":"execute"},
    {"changes":[{"field":"internal_note","before":None,"candidate":"private","origin":"inference"}]},
    {"changes":[{"field":"purpose","before":None,"candidate":"internship","origin":"inference"}]},
    {"target":{**REF,"expected_version":True}},
    {"workflow_binding":{**BINDING,"workflow":"STUDENT_CERTIFICATE"}},
    {"changes":[{"field":"reason","before":None,"candidate":True,"origin":"inference"}]},
    {"changes":[{"field":"course_record_id","before":None,"candidate":"x"*101,"origin":"inference"}]},
])
def test_target_role_field_and_operation_mismatches_rejected(change):
    with pytest.raises(ValidationError):
        DraftProposal.model_validate({**PROPOSAL,**change})


def test_staff_note_cannot_be_placed_in_student_projection():
    private = {**PROPOSAL,"operation":"prepare_internal_note",
               "changes":[{"field":"internal_note","before":None,"candidate":"private","origin":"user_statement"}]}
    with pytest.raises(ValidationError):
        DraftProposal.model_validate(private)
    assert DraftProposal.model_validate({**private,"audience":"staff_internal"}).action_authority == "none"


@pytest.mark.parametrize("start,end", [("2026-10-13T00:00:00",None),("2026-10-13T00:00:00Z","2026-10-12T00:00:00Z")])
def test_invalid_effective_interval_rejected(start,end):
    with pytest.raises(ValidationError):
        DraftProposal.model_validate({**PROPOSAL,"workflow_binding":{**BINDING,"effective_from":start,"effective_until":end}})


def test_inferred_fact_is_only_candidate_and_ambiguity_requires_question():
    body = {"goal":"Xin giấy","status":"needs_clarification","clarification":"Giấy nào?",
            "facts":[{"key":"purpose","value":"internship","origin":"inference"}]}
    assert IntentProposal.model_validate(body).facts[0].status == "candidate"
    with pytest.raises(ValidationError):
        IntentProposal.model_validate({**body,"clarification":None})
    with pytest.raises(ValidationError):
        IntentProposal.model_validate({**body,"facts":[{**body["facts"][0],"status":"verified"}]})


def test_preferences_do_not_grant_consent_or_tools():
    assert PreferencesPatch.model_validate({"expected_version":1,"reply_style":"steps"}).reply_style == "steps"
    for extra in [{"memory_enabled":True},{"consent":True},{"tools":["submit"]}]:
        with pytest.raises(ValidationError):
            PreferencesPatch.model_validate({"expected_version":1,"reply_style":"steps",**extra})


def test_grant_is_a_request_not_an_issued_permission():
    body = {"client_id":ID,"purpose":"source_assistance","capability":"read_source","resource":REF,"requested_lifetime_seconds":60}
    assert GrantRequest.model_validate(body).state == "requested"
    for change in [{"state":"granted"},{"capability":"approve"},{"purpose":"personalization"},{"requested_lifetime_seconds":True}]:
        with pytest.raises(ValidationError):
            GrantRequest.model_validate({**body,**change})


def task_plan():
    return {"items":[{"id":"Q1","question":"Procedure?","requirements":[{"id":"R1","question":"Source?"}]}],
            "tasks":[{"id":"T1","role":"research","goal":"Read source","coverage_ids":["Q1"]},
                     {"id":"T2","role":"verifier","goal":"Verify source","coverage_ids":["Q1"],"dependencies":["T1"]}]}


def test_task_contract_reuses_existing_dag_and_server_tool_binding():
    body = {"client_id":ID,"goal":"Procedure","resources":[REF],"plan":task_plan()}
    assert TaskRequest.model_validate(body).action_authority == "none"
    broken = deepcopy(body)
    broken["plan"]["tasks"][0]["dependencies"] = ["T2"]
    with pytest.raises(ValidationError):
        TaskRequest.model_validate(broken)
    broken = deepcopy(body)
    broken["plan"]["tasks"][0]["tools"] = ["approve"]
    with pytest.raises(ValidationError):
        TaskRequest.model_validate(broken)


def test_supplement_needs_source_and_typed_public_items():
    body = {"client_id":ID,"target":REF,"workflow_binding":BINDING,"items":[{
        "id":"SUP-001","criterion_id":"reason","field":"reason","public_reason":"Thiếu lý do","required_evidence":EVIDENCE}]}
    assert SupplementProposal.model_validate(body).state == "draft"
    with pytest.raises(ValidationError):
        SupplementProposal.model_validate({**body,"internal_note":"private"})
    with pytest.raises(ValidationError):
        SupplementProposal.model_validate({**body,"items":body["items"]*2})


def test_batch_cannot_expand_duplicate_targets_or_execute():
    assert BatchPreparationRequest.model_validate({"client_id":ID,"items":[PROPOSAL]}).mode == "prepare_only"
    with pytest.raises(ValidationError):
        BatchPreparationRequest.model_validate({"client_id":ID,"items":[PROPOSAL,PROPOSAL]})
    with pytest.raises(ValidationError):
        BatchPreparationRequest.model_validate({"client_id":ID,"items":[PROPOSAL],"mode":"execute"})


def test_metadata_and_pagination_have_cas_and_bounds():
    assert ConversationMetadataPatch.model_validate({"expected_version":1,"pinned":False}).pinned is False
    for body in [{"expected_version":1},{"expected_version":True,"title":"a"},{"expected_version":1,"title":"  "}]:
        with pytest.raises(ValidationError):
            ConversationMetadataPatch.model_validate(body)
    with pytest.raises(ValidationError):
        MessagePageRequest.model_validate({"conversation_id":ID,"limit":101})
