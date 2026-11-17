"""Durable multi-agent adapter retaining safety, output and action graph gates."""
from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, replace
from datetime import datetime, timezone

from campus247.agent.graph import CampusAgentWorkflow
from campus247.agent.state import AgentState, Terminal
from campus247.application.conversation.stream_result import prepare_chat_result, StreamFailure
from campus247.application.multi_agent.contracts import MultiAgentPolicy, CoordinationBinding, ContinuationCheckpoint, ControllerCheckpoint
from campus247.application.multi_agent.coordination import bind_run, trace_metadata
from campus247.application.single_agent.contracts import digest
from campus247.application.multi_agent.orchestrator import MultiAgentOrchestrator
from campus247.application.single_agent.controller import EvidenceController
from campus247.application.single_agent.resources import AgentStop, BoundedGateway, RunResources


class RunSession:
    def __init__(self, workflow, turn, record, version, progress):
        self.workflow, self.store = workflow, workflow.store
        self.run_id, self.owner, self.conversation = turn.turn_id, turn.user_id, turn.session_id
        self.turn = turn
        self.record, self.version = record, version
        self.binding = CoordinationBinding.model_validate(record["binding"]) if record.get("binding") else None
        self.current_binding = self.binding
        self.on_progress = progress or (lambda _: None)
        self.resources = RunResources(workflow.policy, usage=record.get("usage"), persist=self.save,
            cancelled=lambda: self.store.cancelled(self.run_id))

    def save(self, *, status="running", event=None, receipt=None):
        self.resources.usage["elapsed_ms"] = self.resources.elapsed_ms()
        self.record["usage"] = dict(self.resources.usage)
        if self.binding is not None:
            state = "pending" if status == "running" else status
            next_action = {"pending": "wait", "waiting_user": "clarify", "uncertain": "read_receipt",
                "interrupted": "read_sources", "partial": "read_sources", "failed": "new_run",
                "cancelled": "new_run", "completed": "none"}[state]
            blockers = self.record.get("error_codes", [])[-16:] if state != "completed" else []
            self.record["continuation"] = ContinuationCheckpoint(binding=self.binding, state=state,
                blockers=blockers, next_action=next_action, receipt_id=receipt["id"] if receipt else None,
                draft=self.binding.resource, task_versions={r["id"]: r["version"] for r in self.store.tasks(self.run_id)}).model_dump()
        self.version = self.store.save(self.run_id, self.owner, self.conversation, self.version, status, self.record, event, receipt)

    def checkpoint(self, value):
        self.record["controller"] = ControllerCheckpoint.model_validate({**self.record.get("controller", {}), **value}).model_dump(exclude_none=True)
        self.save()

    def event(self, task_id, tool, status, duration_ms, data):
        self.save(event={"task_id": task_id, "tool": tool, "status": status,
                         "duration_ms": duration_ms, "data": trace_metadata(data)})

    def pending(self, task_id, phase):
        self.record.setdefault("pending", {})
        if phase is None:
            self.record["pending"].pop(task_id, None)
        else:
            self.record["pending"][task_id] = phase
        self.save()

    def gateway(self, task_id):
        def validate():
            if self.turn.context_guard is not None:
                self.turn.context_guard()
            if self.turn.coordination_guard is not None:
                actor = self.turn.coordination_guard()
                binding = self.binding
                if (binding is None or actor.subject_id != binding.actor_id or actor.tenant_id != binding.tenant_id or
                        sorted(str(r) for r in actor.roles) != binding.roles or digest(actor.session_id) != binding.session_sha256 or
                        actor.expires_at <= datetime.now(timezone.utc) or not actor.is_active):
                    raise AgentStop("COORDINATION_SCOPE_CHANGED")
        return BoundedGateway(self.workflow._gateway, self.resources,
            event=lambda *args: self.event(task_id, *args), pending=lambda phase: self.pending(task_id, phase), validate=validate)

    def progress(self, phase):
        tasks = self.store.tasks(self.run_id)
        self.on_progress({"version": 1, "run_id": self.run_id, "phase": phase,
                          "tasks": [{"id": row["id"], "role": row["spec"]["role"], "status": row["status"]} for row in tasks],
                          "source_count": len(self.record.get("controller", {}).get("evidence_refs", []))})


class MultiAgentWorkflow(CampusAgentWorkflow):
    def __init__(self, *, store, source_reader, policy=None, snapshot=None, admission=None, policy_graph=None, graph_search=None, **kwargs):
        super().__init__(**kwargs)
        self.store, self.source_reader = store, source_reader
        self.policy = policy or MultiAgentPolicy()
        self.snapshot = snapshot or {"corpus": "unknown", "index": "unknown", "model": "unknown"}
        self.active = {}
        self.admission = admission
        self.policy_graph, self.graph_search = policy_graph, graph_search
        if policy_graph is not None:
            self.snapshot = {**self.snapshot, "policy_graph": policy_graph.snapshot}

    async def arun(self, input_val, *, retrieval_context=None, current_context=None, progress=None):
        if not hasattr(input_val, "turn_id"):
            raise ValueError("server-created turn required")
        from campus247.agent.nodes import definitions as nodes
        resolved_goal = nodes.retrieval_query(AgentState(request=input_val))
        binding = bind_run(input_val, retrieval_context, resolved_goal) if retrieval_context is not None else None
        record = {"schema_version": 1, "goal": resolved_goal, "original_goal": resolved_goal,
                  "binding": binding.model_dump() if binding else None, "snapshot": self.snapshot,
                  "config_fingerprint": self.policy.fingerprint, "controller": {}, "pending": {},
                  "created_at": datetime.now(timezone.utc).isoformat(), "cursor": "safety"}
        version = self.store.create(input_val.turn_id, input_val.user_id, input_val.session_id,
                                    record, self.policy.deadline_seconds+2, max_active=self.policy.max_active_runs)
        return await self._run(input_val, retrieval_context, current_context, record, version, progress)

    async def aresume(self, turn, *, expected_version, retrieval_context, current_context, progress=None):
        record = self.store.get(turn.turn_id, turn.user_id, turn.session_id)
        if (record is None or type(record.get("schema_version")) is not int or record["schema_version"] != 1
                or record["config_fingerprint"] != self.policy.fingerprint or record["snapshot"] != self.snapshot):
            raise ValueError("run unavailable or snapshot changed")
        # Context comes from the authenticated request, never from checkpoint.
        if retrieval_context.authorized_scope.actor_id != turn.user_id:
            raise ValueError("resume actor mismatch")
        if not record.get("binding") or not record.get("original_goal"):
            raise ValueError("LEGACY_RUN_SCOPE_UNBOUND")
        if bind_run(turn, retrieval_context, record["original_goal"]) != CoordinationBinding.model_validate(record["binding"]):
            raise ValueError("COORDINATION_SCOPE_CHANGED")
        await self.validate_sources(record, retrieval_context, turn=turn)
        version = self.store.claim_resume(turn.turn_id, turn.user_id, turn.session_id, expected_version,
                                         self.policy.deadline_seconds+2, max_active=self.policy.max_active_runs)
        content = record["goal"] + ("\nThông tin người dùng bổ sung: " + turn.query if turn.query else "")
        turn = replace(turn, query=content)
        for key in ("id", "owner", "conversation_id", "version", "status", "lease_until", "events"):
            record.pop(key, None)
        for key in ("transition_receipt", "final_result", "continuation"):
            record.pop(key, None)  # Prior immutable receipt remains in its table.
        record["resuming"] = True
        record["goal"] = content
        return await self._run(turn, retrieval_context, current_context, record, version, progress)

    async def _run(self, turn, context, refresh, record, version, progress):
        session = RunSession(self, turn, record, version, progress)
        self.active[turn.turn_id] = asyncio.current_task()
        started = time.monotonic()
        initial = AgentState(request=turn, trusted_context_ref=context.trace_id if context else None)
        try:
            if context is not None and bind_run(turn, context, record["original_goal"]) != session.binding:
                raise AgentStop("COORDINATION_SCOPE_CHANGED")
            if context is not None:
                from datetime import timedelta
                from campus247.application.multi_agent.contracts import RunContext
                trusted_run = RunContext(turn.turn_id, turn.session_id, turn.user_id, context.trace_id,
                    context.effective_at, self.snapshot, self.policy.fingerprint,
                    (datetime.now(timezone.utc)+timedelta(seconds=max(0,
                        self.policy.deadline_seconds-session.resources.elapsed_before/1000))).isoformat())
                record["run_context"] = {**asdict(trusted_run), "as_of": trusted_run.as_of.isoformat()}
            admitted = self.admission(self.policy) if self.admission else True
            if context is not None and record.get("resuming") and record.get("pending"):
                # Known lost response is a zero-dispatch terminal path. It does
                # not need fresh-run headroom and cannot resend/refund usage.
                result = EvidenceController.stop(initial, "MODEL_OUTCOME_UNKNOWN")
            elif not admitted:
                from campus247.agent.nodes import definitions as nodes
                from campus247.application.conversation.understanding import conversational_response
                if conversational_response(turn.query, turn.history) is not None:
                    result = nodes.finalize_node(nodes.output_guard_node(nodes.route_intent_node(
                        nodes.pre_safety_rules_node(nodes.normalize_input_node(initial)))))
                else:
                    result = EvidenceController.stop(initial, "MODEL_BUDGET_EXHAUSTED")
            elif context is None:
                result = EvidenceController.stop(initial, "AUTHORIZATION_UNAVAILABLE")
            else:
                from campus247.application.multi_agent.service_adapter import prepare_certificate_response
                orchestrator = MultiAgentOrchestrator(session, search=self._context_search_fn,
                    reader=self.source_reader, current_context=refresh or (lambda: context),
                    support_threshold=self._evidence_support_threshold, policy_graph=self.policy_graph,
                    graph_search=self.graph_search)
                prepared_turn, initial, graph = self._prepare(turn, context, async_mode=True,
                    gateway=session.gateway("preflight"), multi_agent_node=orchestrator.run,
                    service_draft_node=prepare_certificate_response)
                async with asyncio.timeout(self.policy.deadline_seconds):
                    raw = await graph.ainvoke(initial, config={"recursion_limit": self._max_steps})
                result = self._finish(raw, initial, prepared_turn)
        except asyncio.CancelledError:
            result = replace(EvidenceController.stop(initial, "CANCELLED"), agent_run_id=turn.turn_id)
            self._finish_session(session, result, started)
            raise
        except TimeoutError:
            result = EvidenceController.stop(initial, "DEADLINE_EXCEEDED")
        except AgentStop as failure:
            result = EvidenceController.stop(initial, failure.code)
        except Exception:
            result = EvidenceController.stop(initial, "WORKFLOW_FAILURE")
        finally:
            self.active.pop(turn.turn_id, None)
        result = replace(result, agent_run_id=turn.turn_id)
        self._finish_session(session, result, started)
        return result

    def _finish_session(self, session, result, started):
        record = session.record
        record["cursor"] = "terminal"
        record["duration_ms"] = round((time.monotonic()-started)*1000)
        record["finished_at"] = datetime.now(timezone.utc).isoformat()
        record["error_codes"] = [code for code in result.errors if code.startswith(("AI_", "EVIDENCE_"))]
        self.store.close_pending_tasks(session.run_id, "RUN_CANCELLED" if result.terminal == Terminal.CANCELLED else "RUN_TERMINAL")
        try:
            record["final_result"] = asdict(prepare_chat_result(result))
        except StreamFailure:
            record["final_result"] = {"status": "failed", "response_class": "system_error",
                "content": result.draft.text if result.draft else "Dịch vụ xử lý yêu cầu chưa hoàn tất.", "citations": []}
        status = "waiting_user" if "AI_CLARIFICATION_REQUIRED" in result.errors else (
            "cancelled" if result.terminal == Terminal.CANCELLED else
            "failed" if result.terminal == Terminal.SAFE_FAILURE or record["final_result"]["response_class"] == "system_error" else
            "partial" if "AI_PARTIAL_COVERAGE" in result.errors else
            "completed" if result.terminal in {Terminal.ANSWERED, Terminal.COMPLETED} else "partial")
        if record.get("pending") and status != "cancelled":
            status = "uncertain"
        elif any(code in record["error_codes"] for code in ("AI_AGENT_DEADLINE_EXCEEDED", "AI_AGENT_SOURCE_TIMEOUT")):
            status = "interrupted"
        # Receipt and final checkpoint share the run-store CAS transaction.
        # Transcript storage remains a separate store and is not called atomic.
        receipt = {"id": digest({"run": session.run_id, "version": session.version + 1}),
            "run_id": session.run_id, "version": session.version + 1, "state": status,
            "binding_sha256": digest(record.get("binding")), "result_sha256": digest(record["final_result"])}
        record["transition_receipt"] = receipt
        session.save(status=status, receipt=receipt)
        session.progress(status)

    def cancel(self, run_id, owner, conversation_id, version):
        self.store.cancel(run_id, owner, conversation_id, version)
        task = self.active.get(run_id)
        if task:
            task.cancel()
        else:
            record = self.store.get(run_id, owner, conversation_id)
            for key in ("id", "owner", "conversation_id", "version", "status", "lease_until", "events"):
                record.pop(key, None)
            record["final_result"] = {"status": "cancelled", "response_class": "safe_refusal", "content": "Đã dừng xử lý yêu cầu này.", "citations": []}
            record["cursor"] = "terminal"
            receipt = {"id": digest({"run": run_id, "version": version + 1}), "run_id": run_id,
                "version": version + 1, "state": "cancelled", "binding_sha256": digest(record.get("binding")),
                "result_sha256": digest(record["final_result"])}
            record["transition_receipt"] = receipt
            if record.get("binding"):
                record["continuation"] = ContinuationCheckpoint(binding=CoordinationBinding.model_validate(record["binding"]),
                    state="cancelled", next_action="new_run", receipt_id=receipt["id"]).model_dump()
            self.store.save(run_id, owner, conversation_id, version, "cancelled", record, receipt=receipt)

    async def validate_sources(self, record, context, *, turn=None):
        ControllerCheckpoint.model_validate(record.get("controller", {}))
        if record.get("continuation"):
            checkpoint = ContinuationCheckpoint.model_validate(record["continuation"])
            if checkpoint.binding.model_dump() != record.get("binding"):
                raise ValueError("CHECKPOINT_BINDING_CHANGED")
        for event in record.get("events", []):
            if trace_metadata(event.get("data", {})) != event.get("data", {}):
                raise ValueError("TRACE_METADATA_INVALID")
        if record.get("binding"):
            binding = CoordinationBinding.model_validate(record["binding"])
            if (binding.actor_id != context.authorized_scope.actor_id or
                    binding.scope_sha256 != digest(context.to_dict()["authorized_scope"]) or
                    turn is not None and bind_run(turn, context, record["original_goal"]) != binding):
                raise ValueError("COORDINATION_SCOPE_CHANGED")
        else:
            raise ValueError("LEGACY_RUN_SCOPE_UNBOUND")
        resources = RunResources(self.policy)
        tools = EvidenceController(search=None, reader=self.source_reader, gateway=None, resources=resources,
            current_context=lambda: context, checkpoint=lambda _: None, event=lambda *_: None,
            support_threshold=self._evidence_support_threshold, claim_verifier=None)
        turn = type("Turn", (), {"user_id": context.authorized_scope.actor_id, "context_guard": None})()
        state = type("State", (), {"request": turn, "trusted_context_ref": context.trace_id})()
        for ref in record.get("controller", {}).get("evidence_refs", []):
            await tools.read(state, ref)
