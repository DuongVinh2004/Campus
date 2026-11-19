"""Control-flow/authorization/fault checks with explicitly scripted model ports."""
import asyncio
import hashlib
import json
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from campus247.agent.multi_rag import MultiAgentWorkflow
from campus247.agent.state import NormalizedTurn, Terminal
from campus247.application.multi_agent.contracts import MultiAgentPolicy, TaskPlan, TaskSpec, fit_initial_plan, fit_supplemental_tasks, validate_dag
from campus247.application.single_agent.contracts import CoverageItem
from campus247.application.single_agent.resources import AgentStop, BoundedGateway, RunResources
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.repositories.sqlite_agent_runs import SQLiteAgentRunStore, RunConflict
from campus247.ports.citation_source import CitationSourceExcerpt
from campus247.ports.llm import LlmResponse, LlmResponseStatus, TokenUsage

SOURCE = "Phí cấp giấy xác nhận là 50.000 đồng. Hồ sơ nộp tại Phòng Công tác sinh viên."


def row(content=SOURCE):
    return {"chunk_id": generate_uuid7(), "source_id": generate_uuid7(), "document_version_id": generate_uuid7(),
        "content_text": content, "quote_span_hash": hashlib.sha256(content.encode()).hexdigest(),
        "title": "Synthetic test source", "issuer": "HUCE", "canonical_uri": "https://synthetic.example/policy",
        "version_label": "test-v1", "source_status": "SYNTHETIC", "simulation_label": True,
        "locator": {"section_path": "Điều 1"}, "effective_from": "2026-01-01T00:00:00+00:00", "effective_until": None}


def item(key="Q1", question="Phí cấp giấy xác nhận là bao nhiêu?"):
    return {"id": key, "question": question, "requirements": [{"id": "R1", "question": question}]}


def task(key, role, coverage=("Q1",), dependencies=()):
    return {"id": key, "role": role, "goal": "Mức phí giấy xác nhận" if "Q1" in coverage else "Nơi nộp hồ sơ",
        "coverage_ids": list(coverage), "dependencies": list(dependencies),
        "tools": ["search_knowledge", "read_source", "inspect_evidence"] if role == "research" else ["read_source", "inspect_evidence"]}


def plan(two=False):
    return {"items": [item(), *([item("Q2", "Nộp hồ sơ ở đâu?")] if two else [])],
        "tasks": [task("T1", "research"), *([task("T2", "research", ("Q2",))] if two else []),
                  task("T3" if two else "T2", "verifier", ("Q1", "Q2") if two else ("Q1",), ("T1", "T2") if two else ("T1",))],
        "clarification": None}


def test_costly_independent_plan_is_grouped_without_dropping_requirements():
    items = [item("Q1"), item("Q2", "Nộp hồ sơ ở đâu?"), item("Q3", "Lịch hẹn khi nào?")]
    tasks = [task("T1", "research"), task("T2", "verifier", dependencies=("T1",)),
        task("T3", "research", ("Q2",)), task("T4", "verifier", ("Q2",), ("T3",)),
        task("T5", "research", ("Q3",)), task("T6", "verifier", ("Q3",), ("T5",))]
    proposal = TaskPlan(items=items, tasks=tasks)
    original = proposal.model_dump()
    fitted = fit_initial_plan(proposal, MultiAgentPolicy(), 9)
    assert fitted.items == proposal.items and len(fitted.tasks) == 2
    assert all(task.coverage_ids == ["Q1", "Q2", "Q3"] for task in fitted.tasks)
    assert fitted.tasks[1].dependencies == [fitted.tasks[0].id]
    assert fitted.tasks[0].tools == ["search_knowledge", "read_source", "inspect_evidence"]
    assert fitted.tasks[1].tools == ["read_source", "inspect_evidence"]
    assert fitted.tasks[0].goal == "; ".join(row["goal"] for row in tasks if row["role"] == "research")
    assert proposal.model_dump() == original
    # Affordable fan-out is retained, and insufficient room fails closed.
    assert fit_initial_plan(proposal, MultiAgentPolicy(), 11) is proposal
    with pytest.raises(ValueError, match="BUDGET_NOT_FEASIBLE"):
        fit_initial_plan(proposal, MultiAgentPolicy(), 4)


def test_grouping_cannot_hide_invalid_dag_or_tool_rights():
    invalid_value = plan(True)
    invalid_value["tasks"][0]["dependencies"] = [invalid_value["tasks"][-1]["id"]]
    invalid = TaskPlan.model_validate(invalid_value)
    with pytest.raises(ValueError, match="TASK_CYCLE"):
        fit_initial_plan(invalid, MultiAgentPolicy(), 5)
    denied = TaskPlan.model_validate(plan(True))
    denied.tasks[0].tools.append("shell")
    with pytest.raises(ValueError, match="TASK_TOOL_DENIED"):
        fit_initial_plan(denied, MultiAgentPolicy(), 5)


def test_partial_loan_note_only_when_sufficiency_requirement_is_uncovered():
    from campus247.application.multi_agent.orchestrator import MultiAgentOrchestrator
    controller = object.__new__(MultiAgentOrchestrator)
    controller.items = [CoverageItem.model_validate({"id": "Q1", "question": "Có giấy thì chắc chắn được duyệt vay không?",
        "requirements": [{"id": "R1", "question": "Giấy tờ xác nhận vay?"},
                         {"id": "R2", "question": "Điều kiện đủ để được duyệt vay?"}]})]
    controller.coverage = [{"item_id": "Q1", "status": "missing_source", "supports": [{"requirement_id": "R1"}]}]
    assert "chưa xác minh được điều kiện đủ" in controller.partial_note()
    controller.coverage[0]["supports"].append({"requirement_id": "R2"})
    assert controller.partial_note() is None
    controller.coverage[0] = {"item_id": "Q1", "status": "supported", "supports": []}
    assert controller.partial_note() is None


def test_supplement_narrows_to_missing_targets_without_hiding_invalid_references():
    items = [CoverageItem.model_validate(item()), CoverageItem.model_validate(item("Q2", "Nộp hồ sơ ở đâu?"))]
    prior = [TaskSpec.model_validate(task("T1", "research", ("Q1", "Q2"))),
             TaskSpec.model_validate(task("T2", "verifier", ("Q1", "Q2"), ("T1",)))]
    proposal = [TaskSpec.model_validate(task("T3", "research", ("Q1", "Q2"))),
                TaskSpec.model_validate(task("T4", "verifier", ("Q1", "Q2"), ("T3",)))]
    original = [row.model_dump() for row in proposal]
    fitted = fit_supplemental_tasks(proposal, items, MultiAgentPolicy(), prior, {"Q2"}, 5)
    assert all(row.coverage_ids == ["Q2"] for row in fitted)
    assert fitted[1].dependencies == ["T3"] and [row.model_dump() for row in proposal] == original
    bad = TaskSpec.model_validate(task("T3", "research", ("Q3",)))
    with pytest.raises(ValueError, match="INVALID_TASK_REFERENCE"):
        fit_supplemental_tasks([bad, proposal[1]], items, MultiAgentPolicy(), prior, {"Q2"}, 5)
    with pytest.raises(ValueError, match="BUDGET_NOT_FEASIBLE"):
        fit_supplemental_tasks(proposal, items, MultiAgentPolicy(), prior, {"Q2"}, 4)


def test_missing_student_identifier_requests_verification_without_inventing_one():
    from campus247.application.conversation.understanding import conversational_response
    answer = conversational_response("Em quên mã sinh viên và muốn xin xác nhận đang học.")
    assert "không thể tự suy ra mã sinh viên" in answer and "xác minh thông tin" in answer
    assert conversational_response("Mã sinh viên 2027 xin xác nhận đang học ở đâu?") is None


def test_same_template_selection_for_different_statuses_needs_user_facts():
    from campus247.application.conversation.understanding import conversational_response
    response = conversational_response("Hai người đang học và đã tốt nghiệp đều xin cùng mẫu giấy, chọn mẫu thế nào?")
    assert response and "mục đích" in response and "chương trình hiện tại" in response
    assert conversational_response("Sinh viên đang học và đã tốt nghiệp có cùng quy trình nhận giấy xác nhận không?") is None
    assert conversational_response("Cựu sinh viên cần xác nhận ngành đào tạo có dịch vụ nào?") is None


class Reader:
    def __init__(self, rows):
        self.rows, self.reads, self.deny, self.drift = rows, [], False, False

    async def read(self, source, version, chunk, *, context):
        self.reads.append(context)
        if self.deny:
            return None
        value = next((row for row in self.rows if (row["source_id"], row["document_version_id"], row["chunk_id"]) == (source, version, chunk)), None)
        if value is None:
            return None
        content = value["content_text"] + (" changed" if self.drift else "")
        return CitationSourceExcerpt(source, version, chunk, value["title"], value["canonical_uri"], "test-v1", "SYNTHETIC",
            value["locator"], "HUCE", datetime(2026, 1, 1, tzinfo=timezone.utc), None, content, hashlib.sha256(content.encode()).hexdigest())


@pytest.mark.asyncio
@pytest.mark.parametrize("repair_succeeds", [True, False])
async def test_non_exact_coverage_quote_is_repaired_once_or_rejected(tmp_path, repair_succeeds):
    class QuoteModel(ScriptedModel):
        report_attempts = 0
        async def generate(self, request):
            response = await super().generate(request)
            if request.route_id == "multi_research_report":
                self.report_attempts += 1
                if self.report_attempts == 1 or not repair_succeeds:
                    value = json.loads(response.output_text)
                    value["coverage"][0]["supports"][0].pop("span_id", None)
                    value["coverage"][0]["supports"][0]["quote"] = "Invented source quote"
                    return replace(response, output_text=json.dumps(value))
            return response
    model = QuoteModel()
    workflow, turn, ctx, _, _, _ = setup(tmp_path, model=model)
    result = await workflow.arun(turn, retrieval_context=ctx)
    assert model.report_attempts == 2
    record = workflow.store.get(turn.turn_id, turn.user_id, turn.session_id)
    assert any(event["tool"] == "inspect_evidence" and event["status"] == "invalid_provenance" for event in record["events"])
    assert record["usage"]["model_calls"] == len(model.calls) <= workflow.policy.max_model_calls
    if repair_succeeds:
        assert result.terminal == Terminal.ANSWERED
    else:
        assert "AI_AGENT_COVERAGE_INVALID_PROVENANCE" in result.errors
        assert not any(call.route_id == "multi_verifier_coverage" for call in model.calls)


@pytest.mark.asyncio
async def test_known_invalid_json_has_one_charged_repair_without_dispatching_bad_plan(tmp_path):
    class FormatModel(ScriptedModel):
        plans = 0
        async def generate(self, request):
            response = await super().generate(request)
            if request.route_id == "multi_coordinator_plan":
                self.plans += 1
                if self.plans == 1:
                    return replace(response, output_text="Explanation before malformed JSON")
            return response
    model = FormatModel()
    workflow, turn, ctx, _, _, _ = setup(tmp_path, model=model)
    result = await workflow.arun(turn, retrieval_context=ctx)
    record = workflow.store.get(turn.turn_id, turn.user_id, turn.session_id)
    assert result.terminal == Terminal.ANSWERED and model.plans == 2
    assert record["usage"]["model_calls"] == len(model.calls)
    assert len(workflow.store.tasks(turn.turn_id)) == 2
    assert record["pending"] == {}
    assert any(event["tool"] == "validate_model_output" for event in record["events"])


@pytest.mark.asyncio
async def test_forged_span_id_cannot_supply_evidence_or_reach_synthesis(tmp_path):
    class SpanModel(ScriptedModel):
        async def generate(self, request):
            response = await super().generate(request)
            if request.route_id == "multi_research_report":
                value = json.loads(response.output_text)
                value["coverage"][0]["supports"][0]["span_id"] = "S999"
                return replace(response, output_text=json.dumps(value))
            return response
    model = SpanModel()
    workflow, turn, ctx, _, _, _ = setup(tmp_path, model=model)
    result = await workflow.arun(turn, retrieval_context=ctx)
    assert "AI_AGENT_COVERAGE_INVALID_PROVENANCE" in result.errors
    assert sum(call.route_id == "multi_research_report" for call in model.calls) == 2
    assert not any(call.route_id == "grounded_faq" for call in model.calls)


class ScriptedModel:
    def __init__(self, plan_value=None, *, false_claim=False, supplement=False, clarify=False):
        self.plan = plan_value or plan()
        self.false_claim, self.supplement, self.clarify = false_claim, supplement, clarify
        self.calls, self.entered = [], asyncio.Event()
        self.wait = False
        if clarify:
            self.plan = {"items": [item()], "tasks": [], "clarification": "Bạn hỏi học bổng loại nào?"}

    async def generate(self, request):
        self.calls.append(request)
        if self.wait and request.route_id == "multi_coordinator_plan":
            self.entered.set()
            await asyncio.Event().wait()
        route = request.route_id
        if route == "sensitive_classifier":
            value = {"severity": "normal", "is_crisis": False, "confidence": .9}
        elif route == "route_intent":
            value = {"route": "grounded_faq"}
        elif route == "multi_coordinator_plan":
            value = self.plan
        elif route == "multi_coordinator_decision":
            value = {"action": "research" if self.supplement else "stop", "tasks":
                [task("T3", "research"), task("T4", "verifier", dependencies=("T3",))] if self.supplement else [], "clarification": None}
        elif route == "multi_research_query":
            data = json.loads(request.input_items[0]["content"])["untrusted_data"]
            value = {"query": "Mức phí giấy xác nhận bổ sung" if data["task"]["id"] == "T3" else data["task"]["goal"]}
        elif route in {"multi_research_report", "multi_verifier_coverage"}:
            data = json.loads(request.input_items[0]["content"])["untrusted_data"]
            evidence = data["evidence"]
            value = {"coverage": [{"item_id": item["id"], "status": "supported" if evidence else "missing_source",
                "supports": [{"requirement_id": "R1", "evidence_id": evidence[0]["evidence_id"],
                             "span_id": evidence[0]["original_spans"][0]["span_id"]}] if evidence else []} for item in data["items"]]}
        elif route == "grounded_faq":
            value = {"claims": [{"text": "Phí cấp giấy xác nhận là 90.000 đồng." if self.false_claim else "Phí cấp giấy xác nhận là 50.000 đồng.",
                                 "citation_ids": ["CIT-001"], "claim_type": "fee"}]}
        elif route == "grounded_semantic_verification":
            value = {"answers_question": True, "verdicts": [{"claim_id": "CLM-001", "status": "SUPPORTED"}]}
        else:
            raise AssertionError(route)
        if route in {"multi_coordinator_plan", "multi_coordinator_decision"}:
            value = {**value, "tasks": [{key: part for key, part in spec.items() if key != "tools"} for spec in value["tasks"]]}
        return LlmResponse(LlmResponseStatus.COMPLETED, "scripted", "scripted-control-flow", output_text=json.dumps(value, ensure_ascii=False), usage=TokenUsage(10, 0, 20))


def setup(tmp_path, *, model=None, search=None, policy=None):
    rows = [row()]
    reader = Reader(rows)
    turn = NormalizedTurn(generate_uuid7(), generate_uuid7(), "test-student", "Phí cấp giấy xác nhận là bao nhiêu?")
    context = RetrievalContext(AuthorizedScope("huce-local-public", "HUCE", turn.user_id,
        frozenset({"STUDENT"}), frozenset({"STUDENT"}), frozenset({"PUBLIC"}), frozenset({"PUBLIC"})),
        "vi", datetime.now(timezone.utc), SimulationPolicy.ALLOW_LABELED, "1"*32)
    model = model or ScriptedModel()
    async def default_search(query, ctx):
        assert ctx.authorized_scope.actor_id == turn.user_id
        return rows
    store = SQLiteAgentRunStore(tmp_path / "runs.sqlite3")
    workflow = MultiAgentWorkflow(store=store, source_reader=reader, policy=policy, snapshot={"index": "test-source"},
        context_search_fn=search or default_search, llm_gateway=model, require_retrieval_context=True,
        evidence_support_threshold=.78)
    return workflow, turn, context, reader, model, rows


@pytest.mark.asyncio
async def test_coordinator_research_verifier_claims_and_durable_terminal(tmp_path):
    workflow, turn, ctx, reader, model, _ = setup(tmp_path)
    result = await workflow.arun(turn, retrieval_context=ctx)
    assert result.terminal == Terminal.ANSWERED
    assert len(reader.reads) >= 4 and all(value == ctx for value in reader.reads)
    record = SQLiteAgentRunStore(workflow.store.path).get(turn.turn_id, turn.user_id, turn.session_id)
    assert record["status"] == "completed" and record["final_result"]["response_class"] == "grounded_answer"
    assert [row["status"] for row in workflow.store.tasks(turn.turn_id)] == ["succeeded", "succeeded"]
    assert record["usage"]["model_calls"] == 8
    assert record["usage"]["cost_usd"] is None
    assert "system_instructions" not in json.dumps(record) and "confidence" not in json.dumps(record)
    assert any(event["tool"] == "read_source" for event in record["events"])
    assert [call.route_id for call in model.calls][-2:] == ["grounded_faq", "grounded_semantic_verification"]


@pytest.mark.asyncio
async def test_independent_tasks_fan_out_and_verifier_waits(tmp_path):
    entered, released, count = asyncio.Event(), asyncio.Event(), 0
    workflow, turn, ctx, reader, model, rows = setup(tmp_path, model=ScriptedModel(plan(True)))
    async def search(query, context):
        nonlocal count
        count += 1
        if count == 2:
            entered.set(); released.set()
        await asyncio.wait_for(released.wait(), 1)
        return rows
    workflow._context_search_fn = search
    result = await workflow.arun(turn, retrieval_context=ctx)
    assert entered.is_set() and result.terminal == Terminal.ANSWERED
    events = workflow.store.get(turn.turn_id, turn.user_id, turn.session_id)["events"]
    started = {event["task_id"]: event["seq"] for event in events if event["tool"] == "task" and event["status"] == "running"}
    finished = {event["task_id"]: event["seq"] for event in events if event["tool"] == "task" and event["status"] == "succeeded"}
    assert max(started["T1"], started["T2"]) < min(finished["T1"], finished["T2"])
    assert started["T3"] > max(finished["T1"], finished["T2"])


@pytest.mark.asyncio
async def test_missing_first_search_is_supplemented_usefully(tmp_path):
    workflow, turn, ctx, _, model, rows = setup(tmp_path, model=ScriptedModel(supplement=True))
    queries = []
    async def search(query, context):
        queries.append(query)
        return [] if len(queries) == 1 else rows
    workflow._context_search_fn = search
    result = await workflow.arun(turn, retrieval_context=ctx)
    assert len(queries) == 2 and "bổ sung" in queries[1] and result.terminal == Terminal.ANSWERED
    record = workflow.store.get(turn.turn_id, turn.user_id, turn.session_id)
    assert record["usage"]["model_calls"] == 10
    assert [event["status"] for event in record["events"] if event["tool"] == "search_knowledge"] == ["empty", "completed"]
    decision = next(request for request in model.calls if request.route_id == "multi_coordinator_decision")
    inputs = json.loads(decision.input_items[0]["content"])["untrusted_data"]
    assert inputs["available_task_ids"] == ["T3", "T4", "T5", "T6", "T7", "T8"]
    assert [row["status"] for row in inputs["existing_task_states"]] == ["partial", "partial"]
    assert not any(request.route_id in {"multi_research_report", "multi_verifier_coverage"}
        and json.loads(request.input_items[0]["content"])["untrusted_data"]["task"]["id"] in {"T1", "T2"}
        for request in model.calls)
    assert record["coverage_proposals"][0]["origin"] == "server_empty_evidence"


@pytest.mark.asyncio
async def test_agreeing_agents_cannot_publish_wrong_numeric_claim(tmp_path):
    workflow, turn, ctx, _, model, _ = setup(tmp_path, model=ScriptedModel(false_claim=True))
    result = await workflow.arun(turn, retrieval_context=ctx)
    assert result.terminal == Terminal.ABSTAINED
    assert "90.000" not in result.draft.text and "AI_AGENT_CLAIMS_UNSUPPORTED" in result.errors
    assert not any(call.route_id == "grounded_semantic_verification" for call in model.calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["drift", "denied", "timeout", "missing"])
async def test_source_missing_denied_hash_and_timeout_are_distinct(tmp_path, failure):
    workflow, turn, ctx, reader, _, _ = setup(tmp_path)
    if failure == "drift": reader.drift = True
    if failure == "denied": reader.deny = True
    if failure in {"timeout", "missing"}:
        async def search(*_):
            if failure == "timeout": raise TimeoutError()
            return []
        workflow._context_search_fn = search
    result = await workflow.arun(turn, retrieval_context=ctx)
    expected = {"drift": "SOURCE_HASH_MISMATCH", "denied": "SOURCE_DENIED", "timeout": "RETRIEVAL_TIMEOUT", "missing": "MISSING_SOURCE"}[failure]
    assert "AI_AGENT_"+expected in result.errors
    assert result.terminal != Terminal.ANSWERED


@pytest.mark.asyncio
async def test_clarification_and_resume_reauthorize_current_actor(tmp_path):
    workflow, turn, ctx, _, model, _ = setup(tmp_path, model=ScriptedModel(clarify=True))
    result = await workflow.arun(turn, retrieval_context=ctx)
    assert "AI_CLARIFICATION_REQUIRED" in result.errors
    record = workflow.store.get(turn.turn_id, turn.user_id, turn.session_id)
    assert record["status"] == "waiting_user"
    bad = replace(ctx, authorized_scope=replace(ctx.authorized_scope, actor_id="another-student"))
    with pytest.raises(ValueError, match="actor"):
        await workflow.aresume(turn, expected_version=record["version"], retrieval_context=bad, current_context=lambda: bad)
    assert len(model.calls) == 3


@pytest.mark.asyncio
async def test_budget_exhaustion_and_cancel_join_work(tmp_path):
    workflow, turn, ctx, _, _, _ = setup(tmp_path, policy=MultiAgentPolicy(max_model_calls=3))
    result = await workflow.arun(turn, retrieval_context=ctx)
    assert "AI_AGENT_MODEL_BUDGET_EXHAUSTED" in result.errors
    assert not workflow.store.tasks(turn.turn_id)
    workflow, turn, ctx, _, model, _ = setup(tmp_path, model=ScriptedModel())
    model.wait = True
    job = asyncio.create_task(workflow.arun(turn, retrieval_context=ctx))
    await asyncio.wait_for(model.entered.wait(), 2)
    record = workflow.store.get(turn.turn_id, turn.user_id, turn.session_id)
    workflow.cancel(turn.turn_id, turn.user_id, turn.session_id, record["version"])
    with pytest.raises(asyncio.CancelledError):
        await job
    assert workflow.store.get(turn.turn_id, turn.user_id, turn.session_id)["status"] == "cancelled"


@pytest.mark.asyncio
async def test_concurrent_reservations_never_exceed_shared_call_cap():
    resources = RunResources(MultiAgentPolicy(max_model_calls=1))
    model = ScriptedModel()
    from campus247.ports.llm import LlmRequest
    request = LlmRequest("test", "route_intent", "default", "classify", (), max_output_tokens=100, deadline_ms=1000)
    gateway = BoundedGateway(model, resources)
    result = await asyncio.gather(gateway.generate(request), gateway.generate(request), return_exceptions=True)
    assert sum(isinstance(value, AgentStop) for value in result) == 1 and len(model.calls) == 1
    assert resources.usage["model_calls"] == 1


@pytest.mark.parametrize("fault", ["cycle", "unknown", "duplicate", "no_verifier", "tools"])
def test_invalid_dag_is_rejected_before_dispatch(fault):
    value = plan()
    if fault == "cycle": value["tasks"][0]["dependencies"] = ["T2"]
    if fault == "unknown": value["tasks"][0]["dependencies"] = ["T8"]
    if fault == "duplicate": value["tasks"][1]["id"] = "T1"
    if fault == "no_verifier": value["tasks"] = value["tasks"][:1]
    if fault == "tools": value["tasks"][1]["tools"].append("search_knowledge")
    parsed = TaskPlan.model_validate(value)
    with pytest.raises(ValueError):
        validate_dag(parsed.tasks, parsed.items, MultiAgentPolicy())


def test_compact_assignment_binds_same_permissions_and_rejects_model_permission_fields():
    from campus247.application.multi_agent.contracts import TaskPlanProposal
    value = plan()
    compact = {**value, "tasks": [{key: part for key, part in spec.items() if key != "tools"} for spec in value["tasks"]]}
    parsed = TaskPlanProposal.model_validate(compact).to_plan()
    assert parsed.model_dump() == TaskPlan.model_validate(value).model_dump()
    validate_dag(parsed.tasks, parsed.items, MultiAgentPolicy())
    compact["tasks"][1]["tools"] = ["search_knowledge"]
    with pytest.raises(ValueError):
        TaskPlanProposal.model_validate(compact)


def test_task_lease_and_run_cas_reject_two_claimers(tmp_path):
    store = SQLiteAgentRunStore(tmp_path / "leases.sqlite3")
    store.create("run", "student", "conversation", {}, 30)
    spec = TaskSpec.model_validate(task("T1", "research"))
    store.add_tasks("run", [spec])
    assert store.claim_task("run", "T1", 1, lease_seconds=30, max_attempts=2) == 2
    with pytest.raises(RunConflict):
        store.claim_task("run", "T1", 1, lease_seconds=30, max_attempts=2)
    with pytest.raises(RunConflict):
        store.claim_resume("run", "student", "conversation", 1, 30)


@pytest.mark.asyncio
async def test_cache_reopens_original_sources_and_revocation_blocks_hit(tmp_path):
    workflow, turn, ctx, reader, model, _ = setup(tmp_path)
    first = await workflow.arun(turn, retrieval_context=ctx)
    assert first.terminal == Terminal.ANSWERED
    count = len(model.calls)
    again = replace(turn, turn_id=generate_uuid7())
    second = await workflow.arun(again, retrieval_context=ctx)
    assert second.terminal == Terminal.ANSWERED
    record = workflow.store.get(again.turn_id, again.user_id, again.session_id)
    assert any(event["tool"] == "cache" and event["status"] == "revalidated_hit" for event in record["events"])
    assert len(model.calls)-count == 6
    reader.deny = True
    denied = await workflow.arun(replace(turn, turn_id=generate_uuid7()), retrieval_context=ctx)
    assert "AI_AGENT_SOURCE_DENIED" in denied.errors and denied.terminal != Terminal.ANSWERED


@pytest.mark.asyncio
async def test_deadline_and_token_reservation_stop_before_new_effect(tmp_path):
    workflow, turn, ctx, _, model, _ = setup(tmp_path, policy=MultiAgentPolicy(max_reserved_tokens=1))
    result = await workflow.arun(turn, retrieval_context=ctx)
    assert not model.calls and "AI_AGENT_MODEL_BUDGET_EXHAUSTED" in result.errors
    workflow, turn, ctx, _, model, _ = setup(tmp_path, policy=MultiAgentPolicy(deadline_seconds=.05))
    model.wait = True
    result = await workflow.arun(turn, retrieval_context=ctx)
    assert "AI_AGENT_DEADLINE_EXCEEDED" in result.errors
    interrupted = workflow.store.get(turn.turn_id, turn.user_id, turn.session_id)
    if interrupted["pending"]:
        assert interrupted["status"] == "uncertain" and interrupted["pending"]
        assert interrupted["continuation"]["next_action"] == "read_receipt"
        assert interrupted["usage"]["model_calls"] == len(model.calls)
    else:
        assert interrupted["status"] == "interrupted" and not interrupted["pending"]
        assert interrupted["continuation"]["next_action"] == "read_sources"
        assert interrupted["usage"]["usage_complete"] is True
        assert interrupted["usage"]["model_calls"] == len(model.calls)
    assert interrupted["transition_receipt"]["state"] == interrupted["status"]


@pytest.mark.asyncio
async def test_repeated_query_and_fake_output_provenance_fail_closed(tmp_path):
    class Repeated(ScriptedModel):
        async def generate(self, request):
            if request.route_id == "multi_research_query":
                self.calls.append(request)
                return LlmResponse(LlmResponseStatus.COMPLETED, "scripted", "scripted", output_text='{"query":"same query"}', usage=TokenUsage(10, 0, 20))
            return await super().generate(request)
    workflow, turn, ctx, _, _, _ = setup(tmp_path, model=Repeated(supplement=True))
    async def empty(*_): return []
    workflow._context_search_fn = empty
    result = await workflow.arun(turn, retrieval_context=ctx)
    assert "AI_AGENT_REPEATED_QUERY" in result.errors
    assert "chưa xác minh được mức phí" in result.draft.text
    assert workflow.store.get(turn.turn_id, turn.user_id, turn.session_id)["usage"]["searches"] == 1
    class Invalid(ScriptedModel):
        async def generate(self, request):
            response = await super().generate(request)
            if request.route_id == "multi_research_report":
                value = json.loads(response.output_text)
                value["coverage"][0]["supports"][0]["evidence_id"] = "invented-chunk"
                return replace(response, output_text=json.dumps(value))
            return response
    workflow, turn, ctx, _, _, _ = setup(tmp_path, model=Invalid())
    result = await workflow.arun(turn, retrieval_context=ctx)
    assert "AI_AGENT_COVERAGE_INVALID_PROVENANCE" in result.errors


@pytest.mark.asyncio
async def test_crash_checkpoint_unknown_model_is_retained_without_retry(tmp_path):
    workflow, turn, ctx, _, model, _ = setup(tmp_path)
    resources = RunResources(workflow.policy)
    resources.usage["model_calls"] = 1
    resources.usage["reserved_tokens"] = 1000
    record = {"schema_version": 1, "goal": turn.query, "snapshot": workflow.snapshot,
        "config_fingerprint": workflow.policy.fingerprint, "controller": {}, "pending": {"T1": "model"},
        "usage": resources.usage, "cursor": "research"}
    from campus247.application.multi_agent.coordination import bind_run
    record.update(original_goal=turn.query, binding=bind_run(turn, ctx, turn.query).model_dump())
    workflow.store.create(turn.turn_id, turn.user_id, turn.session_id, record, 0)
    reloaded = SQLiteAgentRunStore(workflow.store.path)
    workflow.store = reloaded
    # A known unknown-provider terminal needs no new run admission/reservation.
    workflow.admission = lambda _: False
    result = await workflow.aresume(replace(turn, query=""), expected_version=1, retrieval_context=ctx, current_context=lambda: ctx)
    assert not model.calls and "AI_AGENT_MODEL_OUTCOME_UNKNOWN" in result.errors
    stored = reloaded.get(turn.turn_id, turn.user_id, turn.session_id)
    assert stored["usage"]["model_calls"] == 1 and stored["usage"]["reserved_tokens"] == 1000


@pytest.mark.asyncio
async def test_crash_resume_reuses_completed_task_and_current_source_read(tmp_path):
    from campus247.application.multi_agent.contracts import TaskResult
    from campus247.application.single_agent.contracts import CoverageFinding
    workflow, turn, ctx, reader, model, rows = setup(tmp_path)
    source = rows[0]
    record = {"schema_version": 1, "goal": turn.query, "snapshot": workflow.snapshot,
        "config_fingerprint": workflow.policy.fingerprint, "controller": {"items": [item()]},
        "pending": {}, "usage": RunResources(workflow.policy).usage, "cursor": "verifier"}
    from campus247.application.multi_agent.coordination import bind_run, bind_task
    binding = bind_run(turn, ctx, turn.query)
    record.update(original_goal=turn.query, binding=binding.model_dump())
    workflow.store.create(turn.turn_id, turn.user_id, turn.session_id, record, 0)
    specs = [bind_task(spec, binding, [CoverageItem.model_validate(item())], workflow.policy) for spec in TaskPlan.model_validate(plan()).tasks]
    workflow.store.add_tasks(turn.turn_id, specs)
    workflow.store.claim_task(turn.turn_id, "T1", 1, lease_seconds=0, max_attempts=2)
    result = TaskResult(task_id="T1", status="succeeded", evidence_refs=[{key: source[key] for key in ("source_id", "document_version_id", "chunk_id", "quote_span_hash")}],
        coverage=[CoverageFinding(item_id="Q1", status="supported", supports=[{"requirement_id": "R1", "evidence_id": source["chunk_id"], "quote": SOURCE}])])
    workflow.store.finish_task(turn.turn_id, "T1", 2, result)
    workflow.store = SQLiteAgentRunStore(workflow.store.path)
    resumed = await workflow.aresume(replace(turn, query=""), expected_version=1, retrieval_context=ctx, current_context=lambda: ctx)
    assert resumed.terminal == Terminal.ANSWERED
    assert not any(call.route_id.startswith("multi_research") for call in model.calls)
    assert reader.reads and len(model.calls) == 5


@pytest.mark.asyncio
async def test_no_progress_stops_and_claim_revision_is_bounded(tmp_path):
    workflow, turn, ctx, _, model, _ = setup(tmp_path, model=ScriptedModel(supplement=True), policy=MultiAgentPolicy(max_no_progress=1))
    async def empty(*_): return []
    workflow._context_search_fn = empty
    result = await workflow.arun(turn, retrieval_context=ctx)
    assert "AI_AGENT_NO_PROGRESS" in result.errors
    class Repair(ScriptedModel):
        async def generate(self, request):
            response = await super().generate(request)
            if request.route_id == "grounded_faq":
                self.false_claim = False
            return response
    workflow, turn, ctx, _, model, _ = setup(tmp_path, model=Repair(false_claim=True))
    result = await workflow.arun(turn, retrieval_context=ctx)
    record = workflow.store.get(turn.turn_id, turn.user_id, turn.session_id)
    assert result.terminal == Terminal.ANSWERED and len(record["claim_attempts"]) == 2
    assert record["claim_attempts"][0]["claims"][0]["verdict"] == "insufficient"
    assert record["claim_attempts"][1]["claims"][0]["verdict"] == "supported"
    assert record["usage"]["model_calls"] == 9
    repair = [request for request in model.calls if request.route_id == "grounded_faq"][1]
    feedback = json.loads(repair.input_items[-1]["content"])["verification_requests"]
    assert feedback[0]["claim_id"] == "CLM-001" and feedback[0]["reason_code"] != "SUPPORTED"
    assert "90.000" in feedback[0]["rejected_text"] and feedback[0]["citation_ids"] == ["CIT-001"]


@pytest.mark.asyncio
async def test_partial_answer_is_not_reported_as_full_coverage(tmp_path):
    from campus247.application.conversation.stream_result import prepare_chat_result
    class Partial(ScriptedModel):
        async def generate(self, request):
            response = await super().generate(request)
            if request.route_id == "multi_verifier_coverage":
                value = json.loads(response.output_text)
                value["coverage"][1] = {"item_id": "Q2", "status": "missing_source", "supports": []}
                return replace(response, output_text=json.dumps(value))
            return response
    workflow, turn, ctx, _, _, _ = setup(tmp_path, model=Partial(plan(True)))
    result = await workflow.arun(turn, retrieval_context=ctx)
    final = prepare_chat_result(result)
    assert final.response_class == "partial_answer" and "một phần" in final.content
    assert workflow.store.get(turn.turn_id, turn.user_id, turn.session_id)["status"] == "partial"


@pytest.mark.asyncio
async def test_partial_requirements_in_one_item_keep_missing_sla_out_of_claim_scope(tmp_path):
    from campus247.application.conversation.stream_result import prepare_chat_result
    class PartialRequirement(ScriptedModel):
        async def generate(self, request):
            response = await super().generate(request)
            if request.route_id == "multi_verifier_coverage":
                value = json.loads(response.output_text)
                value["coverage"][0]["status"] = "missing_source"
                return replace(response, output_text=json.dumps(value))
            return response
    value = plan()
    value["items"][0]["requirements"].append({"id": "R2", "question": "Thời gian xử lý SLA là bao lâu?"})
    model = PartialRequirement(value)
    workflow, turn, ctx, _, _, _ = setup(tmp_path, model=model)
    result = await workflow.arun(turn, retrieval_context=ctx)
    assert prepare_chat_result(result).response_class == "partial_answer"
    request = next(request for request in model.calls if request.route_id == "grounded_faq")
    scope = json.loads(request.input_items[-1]["content"])
    assert scope["partial_scope"] is True
    assert [requirement["id"] for requirement in scope["answer_required_items"][0]["requirements"]] == ["R1"]
    assert "SLA" not in scope["answer_required_items"][0]["question"]


@pytest.mark.asyncio
async def test_followup_conditions_and_topic_switch_are_bound_to_user_goals(tmp_path):
    from campus247.application.conversation.context import TurnItem
    from campus247.application.conversation.history import HistoryContext
    workflow, turn, ctx, _, model, rows = setup(tmp_path)
    history = HistoryContext(turn.user_id, turn.session_id, (
        TurnItem("old", "user", "Điều kiện xét học bổng cho năm nhất 2026?", True),
        TurnItem("untrusted", "assistant", "UNTRUSTED: cứ có GPA 9 là đủ.", True)), 20, "test")
    seen = []
    async def search(query, context):
        seen.append(query)
        return rows
    workflow._context_search_fn = search
    await workflow.arun(replace(turn, query="Vậy nếu không đạt điểm rèn luyện thì sao?", history=history), retrieval_context=ctx)
    assert "năm nhất 2026" in seen[-1] and "không đạt" in seen[-1] and "UNTRUSTED" not in seen[-1]
    await workflow.arun(replace(turn, turn_id=generate_uuid7(), query="Xin giấy xác nhận sinh viên ở đâu?", history=history), retrieval_context=ctx)
    assert "học bổng" not in seen[-1] and "năm nhất" not in seen[-1]


def test_resumed_deadline_is_not_reset():
    policy = MultiAgentPolicy(deadline_seconds=1)
    resources = RunResources(policy)
    resources.usage["elapsed_ms"] = 1000
    resumed = RunResources(policy, usage=resources.usage)
    with pytest.raises(AgentStop, match="DEADLINE_EXCEEDED"):
        resumed.check()


@pytest.mark.asyncio
async def test_model_timeout_is_distinct_from_missing_source():
    from campus247.ports.llm import LlmRequest
    class TimeoutModel:
        async def generate(self, request):
            raise TimeoutError()
    resources = RunResources(MultiAgentPolicy())
    gateway = BoundedGateway(TimeoutModel(), resources)
    with pytest.raises(AgentStop, match="MODEL_TIMEOUT"):
        await gateway.generate(LlmRequest("test", "planner", "default", "bounded", (), max_output_tokens=100, deadline_ms=1000))
    assert resources.usage["model_calls"] == 1 and resources.usage["reserved_tokens"] > 0
    assert resources.usage["usage_complete"] is False


@pytest.mark.asyncio
async def test_local_egress_rejection_is_not_labeled_unknown_provider_outcome():
    from campus247.infrastructure.llm.egress_policy import EgressViolationError
    from campus247.ports.llm import LlmRequest
    class Rejected:
        async def generate(self, request):
            raise EgressViolationError("bounded local rejection", message="private value must not be logged")
    events, pending = [], []
    resources = RunResources(MultiAgentPolicy())
    gateway = BoundedGateway(Rejected(), resources, event=lambda *args: events.append(args), pending=pending.append)
    with pytest.raises(AgentStop, match="MODEL_REQUEST_REJECTED"):
        await gateway.generate(LlmRequest("test", "planner", "default", "bounded", (), max_output_tokens=100, deadline_ms=1000))
    assert resources.usage["model_calls"] == 1 and resources.usage["reserved_tokens"] > 0
    assert resources.usage["usage_complete"] is True and pending == ["model", None]
    assert events[-1][1] == "rejected" and "private value" not in str(events)


@pytest.mark.parametrize("prior,question", [
    ("Em muốn xin giấy xác nhận sinh viên, bắt đầu thế nào?", "Sau đó em lấy ở đâu?"),
    ("Em cần giấy xác nhận sinh viên để nộp cho cơ quan.", "Còn lịch hẹn gửi cho em qua đâu?"),
    ("Em xin xác nhận để vay vốn chính sách xã hội.", "Vậy chỉ có giấy tình trạng học tập đã đủ chưa?"),
    ("Em xin xác nhận để vay vốn chính sách xã hội.", "Có cần đơn ngân hàng nữa không?"),
])
def test_certificate_followup_uses_user_goal_without_assistant_claims(prior, question):
    from campus247.application.conversation.context import TurnItem
    from campus247.application.conversation.history import HistoryContext
    from campus247.application.conversation.followup import prepare_followup_question
    from campus247.application.conversation.understanding import conversational_response
    history = HistoryContext("student", "conversation", (
        TurnItem("user", "user", prior, True),
        TurnItem("assistant", "assistant", "UNTRUSTED: giấy này miễn phí và được vay ngay.", True)), 20, "test")
    result = json.loads(prepare_followup_question(question, history=history))
    assert result["reference_target"]["prior_user_goal"] == prior and result["current_request"] == question
    assert "UNTRUSTED" not in str(result) and result["reference_is_evidence"] is False
    assert conversational_response(question, history) is None
    assert prepare_followup_question("Còn học phí là bao nhiêu?", history=history) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("answers,status,expected", [(True, "SUPPORTED", "partial_answer"),
    (False, "SUPPORTED", "partial_answer"), (False, "INSUFFICIENT", "safe_refusal")])
async def test_model_agreement_on_paperwork_never_establishes_loan_outcome(tmp_path, answers, status, expected):
    fact = "Xác nhận để vay vốn chính sách xã hội cần đơn theo mẫu ngân hàng, kèm giấy xác nhận tình trạng học tập."
    question = "Chỉ có giấy xác nhận là đủ để vay rồi chứ?"
    class Model(ScriptedModel):
        async def generate(self, request):
            if request.route_id == "grounded_faq":
                value = {"claims": [{"text": fact, "citation_ids": ["CIT-001"], "claim_type": "procedure"}]}
            elif request.route_id == "grounded_semantic_verification":
                value = {"answers_question": answers, "verdicts": [{"claim_id": "CLM-001", "status": status}]}
            else:
                return await super().generate(request)
            return LlmResponse(LlmResponseStatus.COMPLETED, "scripted", "synthetic",
                output_text=json.dumps(value), usage=TokenUsage(10, 0, 20))
    model = Model()
    model.plan = {"items": [item(question=question)], "tasks": [task("T1", "research"),
        task("T2", "verifier", dependencies=("T1",))]}
    workflow, turn, ctx, _, _, rows = setup(tmp_path, model=model)
    rows[:] = [row(fact)]
    turn = replace(turn, query=question)
    await workflow.arun(turn, retrieval_context=ctx)
    record = workflow.store.get(turn.turn_id, turn.user_id, turn.session_id)
    assert record["final_result"]["response_class"] == expected
    assert "chưa xác minh được điều kiện đủ" in record["final_result"]["content"]
    if expected == "partial_answer":
        assert record["semantic_question_coverage"] == "incomplete" and record["final_result"]["citations"]
    else:
        assert not record["final_result"]["citations"]


@pytest.mark.asyncio
async def test_supported_off_topic_semantic_result_is_not_salvaged_as_partial(tmp_path):
    class OffTopic(ScriptedModel):
        async def generate(self, request):
            response = await super().generate(request)
            if request.route_id == "grounded_semantic_verification":
                value = json.loads(response.output_text)
                value["answers_question"] = False
                return replace(response, output_text=json.dumps(value))
            return response
    workflow, turn, ctx, _, _, _ = setup(tmp_path, model=OffTopic())
    await workflow.arun(turn, retrieval_context=ctx)
    assert workflow.store.get(turn.turn_id, turn.user_id, turn.session_id)["final_result"]["response_class"] == "safe_refusal"


@pytest.mark.asyncio
async def test_known_malformed_claim_repairs_without_allowing_url_or_echoing_raw_output(tmp_path):
    class Model(ScriptedModel):
        malformed = True
        async def generate(self, request):
            response = await super().generate(request)
            if request.route_id == "grounded_faq" and self.malformed:
                self.malformed = False
                value = json.loads(response.output_text)
                value["claims"][0]["text"] += " https://untrusted.example"
                return replace(response, output_text=json.dumps(value))
            return response
    workflow, turn, ctx, _, _, _ = setup(tmp_path, model=Model())
    await workflow.arun(turn, retrieval_context=ctx)
    record = workflow.store.get(turn.turn_id, turn.user_id, turn.session_id)
    assert record["final_result"]["response_class"] == "grounded_answer"
    assert record["usage"]["model_calls"] == 9
    assert "untrusted.example" not in json.dumps(record)
    assert any(event["tool"] == "validate_claim_schema" and event["status"] == "rejected" for event in record["events"])


@pytest.mark.asyncio
@pytest.mark.parametrize("related,include_supported,semantic_supported,expected", [
    (True, True, True, "partial_answer"), (True, True, False, "safe_refusal"),
    (False, True, True, "safe_refusal"), (True, False, True, "safe_refusal"),
])
async def test_related_partial_subset_preserves_rejected_claims_and_all_gates(
        tmp_path, related, include_supported, semantic_supported, expected):
    fact = "Xác nhận để vay vốn chính sách xã hội cần đơn theo mẫu ngân hàng, kèm giấy xác nhận tình trạng học tập."
    bad = "Phí cấp giấy xác nhận là 99.000 đồng."
    question = "Chỉ có giấy xác nhận là đủ để vay rồi chứ?" if related else "Phí cấp giấy xác nhận là bao nhiêu?"
    class Model(ScriptedModel):
        semantic_calls = 0
        async def generate(self, request):
            if request.route_id == "grounded_faq":
                value = {"claims": [{"text": text, "citation_ids": ["CIT-001"], "claim_type": "procedure"}
                                    for text in ([fact] if include_supported else []) + [bad]]}
            elif request.route_id == "grounded_semantic_verification":
                self.semantic_calls += 1
                payload = str(request.input_items)
                assert fact in payload and bad not in payload
                value = {"answers_question": True, "verdicts": [{"claim_id": "CLM-001",
                    "status": "SUPPORTED" if semantic_supported else "INSUFFICIENT"}]}
            else:
                return await super().generate(request)
            return LlmResponse(LlmResponseStatus.COMPLETED, "scripted", "synthetic",
                output_text=json.dumps(value, ensure_ascii=False), usage=TokenUsage(10, 0, 20))
    model = Model()
    model.plan = {"items": [item(question=question)], "tasks": [task("T1", "research"),
        task("T2", "verifier", dependencies=("T1",))]}
    workflow, turn, ctx, _, _, rows = setup(tmp_path, model=model)
    rows[:] = [row(fact)]
    turn = replace(turn, query=question)
    await workflow.arun(turn, retrieval_context=ctx)
    record = workflow.store.get(turn.turn_id, turn.user_id, turn.session_id)
    assert record["final_result"]["response_class"] == expected
    assert all(claim["verdict"] == "insufficient" for attempt in record["claim_attempts"]
               for claim in attempt["claims"] if claim["text"] == bad)
    if expected == "partial_answer":
        assert fact in record["final_result"]["content"] and bad not in record["final_result"]["content"]
        assert record["claims"][0]["verdict"] == "supported" and record["usage"]["model_calls"] == 8
        assert record["semantic_question_coverage"] == "incomplete"
        event = next(event for event in record["events"] if event["tool"] == "question_scope")
        assert event["data"]["omitted_claim_ids"] == ["CLM-002"] and event["data"]["full_answer_allowed"] is False
    if not related or not include_supported:
        assert model.semantic_calls == 0 and not record["final_result"]["citations"]


@pytest.mark.parametrize("query,expected", [
    ("Thông báo ngày lấy giấy chứng nhận sinh viên HUCE", "Thông báo ngày lấy giấy xác nhận sinh viên HUCE"),
    ("chung nhan sinh vien nam 2027 khong nhan truc tiep", "giấy xác nhận sinh viên nam 2027 khong nhan truc tiep"),
    ("Giấy chứng nhận tốt nghiệp năm 2027", "Giấy chứng nhận tốt nghiệp năm 2027"),
    ("Chứng nhận IELTS", "Chứng nhận IELTS"),
    ("Phí giấy xác nhận sinh viên", "Phí giấy xác nhận sinh viên"),
])
def test_student_confirmation_search_alias_preserves_other_topics_and_qualifiers(query, expected):
    from campus247.application.multi_agent.query_aliases import canonical_search_query
    assert canonical_search_query(query) == expected


@pytest.mark.asyncio
async def test_search_alias_keeps_original_goal_and_current_source_rights(tmp_path):
    question = "Phí giấy chứng nhận sinh viên là bao nhiêu?"
    class Model(ScriptedModel):
        async def generate(self, request):
            response = await super().generate(request)
            if request.route_id == "multi_research_query":
                return replace(response, output_text=json.dumps({"query": question}, ensure_ascii=False))
            return response
    model = Model()
    model.plan = {"items": [item(question=question)], "tasks": [task("T1", "research"),
        task("T2", "verifier", dependencies=("T1",))]}
    workflow, turn, ctx, reader, _, rows = setup(tmp_path, model=model)
    seen = []
    async def search(query, context):
        seen.append(query)
        assert context == ctx
        return rows
    workflow._context_search_fn = search
    turn = replace(turn, query=question)
    await workflow.arun(turn, retrieval_context=ctx)
    record = workflow.store.get(turn.turn_id, turn.user_id, turn.session_id)
    assert seen == [question + "\nTruy vấn bổ sung: Phí giấy xác nhận sinh viên là bao nhiêu?"]
    assert record["goal"] == question and all(context == ctx for context in reader.reads)
    assert record["final_result"]["response_class"] == "grounded_answer"
    assert record["usage"]["model_calls"] == 8
    alias = next(e for e in record["events"] if e["tool"] == "query_alias")
    assert set(alias["data"]) == {"original_sha256", "search_sha256"}
