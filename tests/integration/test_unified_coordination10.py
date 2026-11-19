"""UNI-016–020 deterministic integration on new disposable fixtures only."""
import json
import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from campus247.agent.state import Terminal, Route
from campus247.application.multi_agent.contracts import (
    CoordinationBinding, TaskBinding, TaskSpec, TaskResult, ControllerCheckpoint, ContinuationCheckpoint,
)
from campus247.application.multi_agent.coordination import bind_run, bind_task, trace_metadata, validate_task_binding
from campus247.application.multi_agent.service_adapter import ResourceSpecialistResult, ResourceSpecialistAdapter
from campus247.application.single_agent.contracts import CoverageItem, digest
from campus247.application.single_agent.resources import RunResources, BoundedGateway, AgentStop
from campus247.agent.tools.registry import ToolRegistry, ToolDefinition, ToolValidationError
from campus247.agent.tools.executor import ScopedSpecialistExecutor
from campus247.infrastructure.repositories.sqlite_agent_runs import SQLiteAgentRunStore, RunConflict
from campus247.domain.shared.values import generate_uuid7
from campus247.ports.llm import LlmRequest
from tests.unit.agent.test_multi_agent_integrated import setup, item, task, ScriptedModel
from tests.integration.test_unified_actor_features import runtime as runtime_fixture, tables, grant
from tests.integration.test_unified_durable_services import actor, proposal
from tests.api.test_service_stage6 import login, draft, sent
from tests.api.test_multi_agent_api import make, frames

runtime = runtime_fixture


@pytest.mark.parametrize("contract", [CoordinationBinding, TaskBinding, TaskSpec, TaskResult, ControllerCheckpoint, ContinuationCheckpoint, ResourceSpecialistResult])
def test_exported_schemas_are_exact_and_forbid_extra_authority(contract):
    root = Path(__file__).resolve().parents[2]
    exported = root / "contracts/json-schema/assistance/coordination-v1-02" / (contract.__name__ + ".schema.json")
    assert json.loads(exported.read_text(encoding="utf-8")) == contract.model_json_schema()
    assert contract.model_json_schema()["additionalProperties"] is False


@pytest.mark.asyncio
async def test_real_orchestrator_task_bindings_receipt_checkpoint_reload(tmp_path):
    workflow, turn, context, reader, model, _ = setup(tmp_path)
    result = await workflow.arun(turn, retrieval_context=context)
    assert result.terminal == Terminal.ANSWERED
    store = SQLiteAgentRunStore(workflow.store.path)
    run = store.get(turn.turn_id, turn.user_id, turn.session_id)
    binding = CoordinationBinding.model_validate(run["binding"])
    assert binding.goal_sha256 == binding.purpose_sha256 == digest(turn.query)
    items = [CoverageItem.model_validate(i) for i in run["controller"]["items"]]
    for row in store.tasks(turn.turn_id):
        spec = TaskSpec.model_validate(row["spec"])
        validate_task_binding(spec, binding, items, workflow.policy)
    checkpoint = ContinuationCheckpoint.model_validate(run["continuation"])
    assert checkpoint.state == "completed" and checkpoint.next_action == "none"
    receipt = store.transition_receipt(turn.turn_id, turn.user_id, turn.session_id, checkpoint.receipt_id)
    assert receipt == run["transition_receipt"] and receipt["version"] == run["version"]
    assert receipt["result_sha256"] == digest(run["final_result"])
    assert store.transition_receipt(turn.turn_id, "other", turn.session_id, checkpoint.receipt_id) is None
    calls = len(model.calls)
    with pytest.raises(RunConflict):
        await workflow.aresume(replace(turn, query=""), expected_version=run["version"], retrieval_context=context, current_context=lambda: context)
    assert len(model.calls) == calls and len(reader.reads) >= 5


@pytest.mark.asyncio
@pytest.mark.parametrize("dimension", ["tenant_id", "roles", "audiences", "faculty_codes", "program_codes"])
async def test_resume_rejects_scope_changes_before_claim_or_model(tmp_path, dimension):
    workflow, turn, context, _, model, _ = setup(tmp_path, model=ScriptedModel(clarify=True))
    await workflow.arun(turn, retrieval_context=context)
    before = workflow.store.get(turn.turn_id, turn.user_id, turn.session_id)
    value = "other-tenant" if dimension == "tenant_id" else frozenset({"OTHER"})
    changed = replace(context, authorized_scope=replace(context.authorized_scope, **{dimension: value}))
    count = len(model.calls)
    with pytest.raises(ValueError, match="SCOPE_CHANGED"):
        await workflow.aresume(turn, expected_version=before["version"], retrieval_context=changed, current_context=lambda: changed)
    assert workflow.store.get(turn.turn_id, turn.user_id, turn.session_id)["version"] == before["version"]
    assert len(model.calls) == count


@pytest.mark.asyncio
async def test_session_switch_invalidates_cache_and_resume(tmp_path):
    identity = actor()
    workflow, turn, context, reader, model, _ = setup(tmp_path)
    turn = replace(turn, user_id=identity.subject_id, coordination_guard=lambda: identity)
    context = replace(context, authorized_scope=replace(context.authorized_scope, actor_id=identity.subject_id))
    async def search(*_): return reader.rows
    workflow._context_search_fn = search
    await workflow.arun(turn, retrieval_context=context)
    first = workflow.store.get(turn.turn_id, turn.user_id, turn.session_id)
    identity = replace(identity, session_id=generate_uuid7())
    second = replace(turn, turn_id=generate_uuid7())
    await workflow.arun(second, retrieval_context=context)
    run = workflow.store.get(second.turn_id, second.user_id, second.session_id)
    assert first["binding"]["session_sha256"] != run["binding"]["session_sha256"]
    assert not any(e["tool"] == "cache" for e in run["events"])
    with pytest.raises(ValueError, match="SCOPE_CHANGED"):
        await workflow.aresume(turn, expected_version=first["version"], retrieval_context=context, current_context=lambda: context)


@pytest.mark.asyncio
@pytest.mark.parametrize("drift", ["hash", "locator", "effective", "revoke"])
async def test_source_change_during_generation_blocks_publication(tmp_path, drift):
    class ChangingModel(ScriptedModel):
        async def generate(self, request):
            response = await super().generate(request)
            if request.route_id == "grounded_semantic_verification":
                if drift == "hash": reader.drift = True
                elif drift == "revoke": reader.deny = True
                elif drift == "locator": reader.rows[0]["locator"] = {"section_path": "Different article"}
            return response
    workflow, turn, context, reader, _, _ = setup(tmp_path, model=ChangingModel())
    original = reader.read
    async def read(*args, **kwargs):
        result = await original(*args, **kwargs)
        if drift == "effective" and any(c.route_id == "grounded_semantic_verification" for c in workflow._gateway.calls):
            from datetime import datetime, timezone
            return replace(result, effective_from=datetime(2027, 1, 1, tzinfo=timezone.utc))
        return result
    reader.read = read
    result = await workflow.arun(turn, retrieval_context=context)
    assert result.terminal != Terminal.ANSWERED
    assert any("SOURCE_" in code for code in result.errors)
    run = workflow.store.get(turn.turn_id, turn.user_id, turn.session_id)
    assert run["status"] != "completed" and run["controller"]["evidence_refs"]


@pytest.mark.parametrize("tool", ["confirm", "approve", "send", "shell", "search_knowledge"])
def test_specialist_role_cannot_invent_or_expand_tools(tmp_path, tool):
    workflow, turn, context, _, _, _ = setup(tmp_path)
    binding = bind_run(turn, context, turn.query)
    items = [CoverageItem.model_validate(item())]
    spec = bind_task(TaskSpec.model_validate(task("T2", "verifier", dependencies=("T1",))), binding, items, workflow.policy)
    with pytest.raises(ToolValidationError):
        ToolRegistry.specialist_reads().authorize_specialist(tool, spec, binding, binding, {tool})


def test_specialist_registry_rechecks_capability_and_output_contract(tmp_path):
    workflow, turn, context, _, _, _ = setup(tmp_path)
    items = [CoverageItem.model_validate(item())]
    binding = bind_run(turn, context, turn.query)
    spec = bind_task(TaskSpec.model_validate(task("T1", "research")), binding, items, workflow.policy)
    registry = ToolRegistry.specialist_reads()
    with pytest.raises(ToolValidationError):
        registry.authorize_specialist("read_source", spec, binding, binding, set())
    with pytest.raises(ValueError, match="BINDING_CHANGED"):
        validate_task_binding(spec, binding, [CoverageItem.model_validate(item(question="Another purpose"))], workflow.policy)
    executor = ScopedSpecialistExecutor(registry, authorize=lambda *_: None)
    with pytest.raises(ValidationError):
        executor.execute("read_source", {"items": []}, ControllerCheckpoint, TaskResult,
            lambda _: {"task_id": "T1", "status": "succeeded", "coverage": [], "confirmation_token": "forged"})
    write = ToolRegistry({"send": ToolDefinition("send", "send", "Business", True, True)})
    with pytest.raises(PermissionError):
        ScopedSpecialistExecutor(write, authorize=lambda *_: None).execute("send", {}, ControllerCheckpoint, ControllerCheckpoint, lambda v: v)


@pytest.mark.parametrize("field", ["confirmation_token", "raw_token", "private_notes", "hidden_prompt", "system_instructions"])
def test_checkpoint_and_trace_exclude_secrets(field):
    with pytest.raises(ValidationError): ControllerCheckpoint.model_validate({field: "secret"})
    assert field not in trace_metadata({field: "secret", "query": "private", "code": "SOURCE_DENIED", "model": "raw secret with spaces"})
    assert trace_metadata({field: "secret", "code": "SOURCE_DENIED"}) == {"code": "SOURCE_DENIED"}


def test_capacity_and_resume_lease_are_atomic_across_repository_instances(tmp_path):
    path = tmp_path / "capacity.sqlite3"
    stores = [SQLiteAgentRunStore(path), SQLiteAgentRunStore(path)]
    def create(index):
        try:
            stores[index].create("run-"+str(index), "actor", "chat", {}, 30, max_active=1)
            return True
        except RunConflict: return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(create, (0, 1))) == 1
    lease_path = tmp_path / "resume.sqlite3"
    stores = [SQLiteAgentRunStore(lease_path), SQLiteAgentRunStore(lease_path)]
    stores[0].create("run", "actor", "chat", {}, 0)
    def claim(index):
        try:
            stores[index].claim_resume("run", "actor", "chat", 1, 30, max_active=1)
            return True
        except RunConflict: return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(claim, (0, 1))) == 1


@pytest.mark.asyncio
async def test_cost_budget_blocks_before_dispatch_and_preserves_reservations(tmp_path):
    from campus247.application.multi_agent.contracts import MultiAgentPolicy
    model = ScriptedModel()
    resources = RunResources(MultiAgentPolicy(max_reserved_cost_usd=0))
    gateway = BoundedGateway(model, resources)
    with pytest.raises(AgentStop, match="COST_BUDGET_EXHAUSTED"):
        await gateway.generate(LlmRequest("id", "route_intent", "default", "classify", (), max_output_tokens=100))
    assert not model.calls and resources.usage["model_calls"] == 0


@pytest.mark.asyncio
async def test_timeout_after_dispatch_keeps_pending_and_never_refunds_or_retries():
    from campus247.application.multi_agent.contracts import MultiAgentPolicy
    model = ScriptedModel(); model.wait = True
    pending = []
    resources = RunResources(MultiAgentPolicy(deadline_seconds=1, model_timeout_ms=50))
    gateway = BoundedGateway(model, resources, pending=pending.append)
    job = asyncio.create_task(gateway.generate(LlmRequest("id", "multi_coordinator_plan", "default", "classify", (), max_output_tokens=100)))
    await asyncio.wait_for(model.entered.wait(), .5)
    with pytest.raises(AgentStop, match="MODEL_TIMEOUT"):
        await job
    assert len(model.calls) == 1 and pending == ["model"]
    assert resources.usage["model_calls"] == 1 and resources.usage["reserved_tokens"] > 0
    assert resources.usage["usage_complete"] is False


@pytest.mark.asyncio
async def test_legacy_unbound_run_is_readable_but_cannot_resume(tmp_path):
    workflow, turn, context, _, model, _ = setup(tmp_path)
    workflow.store.create(turn.turn_id, turn.user_id, turn.session_id, {"schema_version": 1, "goal": turn.query,
        "snapshot": workflow.snapshot, "config_fingerprint": workflow.policy.fingerprint}, 0)
    with pytest.raises(ValueError, match="LEGACY_RUN_SCOPE_UNBOUND"):
        await workflow.aresume(turn, expected_version=1, retrieval_context=context, current_context=lambda: context)
    assert not model.calls and workflow.store.get(turn.turn_id, turn.user_id, turn.session_id)["version"] == 1


def test_surface_consumer_uses_short_document_verifier_path_and_no_notes(runtime):
    app, client, identity, _, _, _, paths = runtime
    headers = login(client)
    record = draft(client, headers)
    body = {"surface": "service", "resource": {"kind": "service_request", "id": record["id"], "expected_version": record["version"]}}
    before = tables(paths[0])
    result = client.post("/v1/assistant/surface:resolve", headers=headers, json=body)
    assert result.status_code == 200, result.text
    value = result.json()
    assert value["specialist"]["status"] == "observed"
    assert value["specialist"]["workflow"]["binding"]["template_version"]
    assert "internal_note" not in json.dumps(value["context"])
    assert tables(paths[0]) == before
    assert client.post("/v1/assistant/surface:resolve", headers=login(client,"SV024"), json=body).status_code == 404
    assert client.post("/v1/assistant/surface:resolve", headers=headers, json={**body, "confirmation_token": "forged"}).status_code == 422
    caps = client.get("/v1/assistant/consumer-capabilities", headers=headers).json()["coordination"]
    assert caps["profile"] is None and not caps["read"] and not caps["resume"]


def test_native_composition_exposes_bound_receipts_and_refuses_session_change(tmp_path, monkeypatch):
    app, headers, _, _, model, _ = make(tmp_path, monkeypatch)
    with TestClient(app) as client:
        cid = client.post("/v1/conversations", headers=headers, json={}).json()["id"]
        response = client.post(f"/v1/conversations/{cid}/messages:stream", headers=headers, json={"content": "Xin giấy xác nhận sinh viên bắt đầu từ đâu?"})
        final = next(data for event, data in frames(response.text) if event == "message.completed")
        rid = final["run_id"]
        path = f"/v1/conversations/{cid}/agent-runs/{rid}"
        run = client.get(path, headers=headers)
        assert run.status_code == 200, run.text
        value = run.json()
        assert value["continuation"]["state"] == "completed"
        receipt = client.get(path+"/receipt", headers=headers)
        assert receipt.status_code == 200 and receipt.json()["id"] == value["continuation"]["receipt_id"]
        assert app.state.coordination_capabilities["profile"] == "coordination-checkpoint.v1"
        from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
        settings = app.state.runtime_settings
        adapter = SyntheticIdentityAdapter(settings.IDENTITY_SECRET_KEY, environment="development", tenant_id="huce-local-public")
        owner = app.state.multi_agent_workflow.store.get(rid, value["continuation"]["binding"]["actor_id"], cid)["owner"]
        switched = {"Authorization": "Bearer " + adapter.mint_token(owner)}
        assert client.get(path, headers=switched).status_code == 403
        assert not any("system_instructions" in json.dumps(e) for e in app.state.multi_agent_workflow.store.get(rid, owner, cid)["events"])


def test_resource_work_survives_fixture_restart_revalidates_scope_and_never_writes(runtime, tmp_path):
    from campus247.bootstrap.unified_demo import create_unified_demo_app
    app, client, identity, _, _, _, paths = runtime
    headers = login(client)
    record = draft(client, headers)
    request = {"surface": "service", "resource": {"kind": "service_request", "id": record["id"], "expected_version": record["version"]}, "operation_id": generate_uuid7()}
    store_path = tmp_path / "resource-runs.sqlite3"
    composed = create_unified_demo_app(paths[0], state_database=paths[1], consent_mode="sqlite",
        coordination_store=SQLiteAgentRunStore(store_path, tenant="huce-local-public"))
    before = tables(paths[0])
    with TestClient(composed) as local:
        response = local.post("/v1/assistant/surface:resolve", headers=headers, json=request)
        assert response.status_code == 200, response.text
        run = response.json()["specialist"]["run"]
        assert run["state"] == "partial" and not run["is_replay"]
        retry = local.post("/v1/assistant/surface:resolve", headers=headers, json=request)
        assert retry.status_code == 200 and retry.json()["specialist"]["run"]["is_replay"]
    restarted = create_unified_demo_app(paths[0], state_database=paths[1], consent_mode="sqlite",
        coordination_store=SQLiteAgentRunStore(store_path, tenant="huce-local-public"))
    with TestClient(restarted) as local:
        read = local.get("/v1/assistant/resource-runs/" + run["id"], headers=headers)
        assert read.status_code == 200, read.text
        assert read.json()["continuation"]["case"] == request["resource"]
        assert read.json()["run"]["receipt_id"] == run["receipt_id"]
        assert local.get("/v1/assistant/resource-runs/" + run["id"], headers=login(local,"SV024")).status_code == 404
        assert local.get("/v1/assistant/resource-runs/" + run["id"], headers=login(local)).status_code == 409
    assert tables(paths[0]) == before


def test_document_adapter_rechecks_changed_template_before_return(runtime):
    app, client, identity, _, _, _, _ = runtime
    record = draft(client, login(client))
    candidate = {"surface": "service", "resource": {"kind": "service_request", "id": record["id"], "expected_version": record["version"]}}
    from campus247.application.assistance.contracts import AssistanceRequest
    from campus247.application.document_request.certificates import CertificateError
    service = app.state.assistant_proposals.workflow
    original = service.resolve
    calls = 0
    def changed(*args):
        nonlocal calls
        calls += 1
        value = original(*args)
        if calls > 1:
            value = value.model_copy(update={"definition_version": "changed-v2"})
        return value
    service.resolve = changed
    with pytest.raises(CertificateError, match="Quy tắc"):
        ResourceSpecialistAdapter(app.state.assistance_context, service).resolve(identity, AssistanceRequest.model_validate(candidate))


@pytest.mark.parametrize("corruption", ["checkpoint", "trace", "final_result"])
def test_run_read_rejects_corrupted_checkpoint_trace_or_receipt_result(tmp_path, monkeypatch, corruption):
    app, headers, _, _, model, _ = make(tmp_path, monkeypatch)
    with TestClient(app) as client:
        cid = client.post("/v1/conversations", headers=headers, json={}).json()["id"]
        response = client.post(f"/v1/conversations/{cid}/messages:stream", headers=headers,
            json={"content": "Xin giấy xác nhận sinh viên bắt đầu từ đâu?"})
        final = next(data for event, data in frames(response.text) if event == "message.completed")
        rid = final["run_id"]
        store = app.state.multi_agent_workflow.store
        calls = len(model.calls)
        with sqlite3.connect(store.path) as connection:
            if corruption == "trace":
                row = connection.execute("SELECT seq,record FROM agent_event WHERE run_id=? ORDER BY seq LIMIT 1", (rid,)).fetchone()
                event = json.loads(row[1]); event["data"]["private_notes"] = "fixture-private"
                connection.execute("UPDATE agent_event SET record=? WHERE run_id=? AND seq=?", (json.dumps(event), rid, row[0]))
            else:
                row = connection.execute("SELECT record FROM agent_run WHERE id=?", (rid,)).fetchone()
                record = json.loads(row[0])
                if corruption == "checkpoint": record["continuation"]["confirmation_token"] = "fixture-private"
                else: record["final_result"]["content"] = "Changed after receipt"
                connection.execute("UPDATE agent_run SET record=? WHERE id=?", (json.dumps(record), rid))
        result = client.get(f"/v1/conversations/{cid}/agent-runs/{rid}", headers=headers)
        assert result.status_code == 403 and "fixture-private" not in result.text
        assert len(model.calls) == calls


@pytest.mark.asyncio
@pytest.mark.parametrize("route", [Route.TICKET_CREATE, Route.ROOM_BOOKING, Route.PERSONAL_SCHEDULE, Route.HUMAN_HANDOVER])
async def test_native_multi_agent_unconfigured_tool_routes_never_report_business_success(tmp_path, route):
    class RouteModel(ScriptedModel):
        async def generate(self, request):
            response = await super().generate(request)
            return replace(response, output_text=json.dumps({"route": route.value})) if request.route_id == "route_intent" else response
    workflow, turn, context, _, model, _ = setup(tmp_path, model=RouteModel())
    turn = replace(turn, query={Route.TICKET_CREATE: "Tạo ticket báo cáo sự cố", Route.ROOM_BOOKING: "Đặt phòng họp cho câu lạc bộ",
        Route.PERSONAL_SCHEDULE: "Xem lịch học cá nhân của em", Route.HUMAN_HANDOVER: "Chuyển cho chuyên viên, em muốn gặp cán bộ"}[route])
    result = await workflow.arun(turn, retrieval_context=context)
    assert result.route == route
    assert result.terminal == Terminal.ABSTAINED
    assert "CAPABILITY_UNAVAILABLE" in " ".join(result.errors)
    assert result.execution_context is None and result.confirmation_context is None
    record = workflow.store.get(turn.turn_id, turn.user_id, turn.session_id)
    assert record["status"] != "completed" and not workflow.store.tasks(turn.turn_id)
    assert all(not call.allowed_tools for call in model.calls)


def test_staff_document_consumer_uses_current_queue_and_never_projects_private_notes(runtime):
    app, client, identity, _, _, _, paths = runtime
    student, record, _ = sent(client)
    before = tables(paths[0])
    body = {"surface": "service", "resource": {"kind": "service_request", "id": record["id"], "expected_version": record["version"]}}
    staff = client.post("/v1/assistant/surface:resolve", headers=login(client,"OF002"), json=body)
    assert staff.status_code == 200, staff.text
    value = staff.json()
    assert value["audience"] == "staff" and value["specialist"]["workflow"]["resource"]["view"] == "staff"
    assert client.post("/v1/assistant/surface:resolve", headers=login(client,"OF001"), json=body).status_code == 404
    student_view = client.post("/v1/assistant/surface:resolve", headers=student, json=body).json()
    assert student_view["context"]["evidence"] == value["context"]["evidence"]
    assert "private_notes" not in json.dumps(student_view) and "internal_note" not in json.dumps(student_view)
    assert tables(paths[0]) == before


@pytest.mark.parametrize("claim", ["invented_span", "foreign_source", "literal_span"])
def test_granted_prepare_candidate_checks_field_source_and_does_not_mutate_business(runtime, claim):
    app, client, identity, _, _, _, paths = runtime
    record = draft(client, login(client))
    gid, target = grant(app, client, identity, lifetime="timed", capability="prepare_draft", record=record)
    candidate = proposal(app, identity, record)
    change = candidate["changes"][0]
    change["origin"], change["evidence"] = "source_reference", dict(candidate["workflow_binding"]["source"])
    with app.state.service_requests.repository.transaction() as tx:
        source = app.state.service_requests.knowledge._version(tx, change["evidence"]["version_id"])
    change["candidate"] = source["text"][:500]
    if claim == "invented_span": change["candidate"] = "A fact invented by agreement of models"
    elif claim == "foreign_source": change["evidence"]["source_id"] = "unrelated-source"
    before, actor_before = tables(paths[0]), tables(paths[1])
    service = app.state.assistant_grant_consumers
    if claim != "literal_span":
        from campus247.application.document_request.certificates import CertificateError
        with pytest.raises((CertificateError, ValidationError)):
            service.prepare_candidate(identity, gid, candidate, generate_uuid7())
        assert tables(paths[1]) == actor_before
    else:
        result = service.prepare_candidate(identity, gid, candidate, generate_uuid7())
        assert result["result"]["action_authority"] == "none"
        assert result["result"]["evidence"]["binding"]["template_version"]
    assert tables(paths[0]) == before
