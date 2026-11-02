"""Owned run readback/resume/cancel; orchestration remains in application code."""
from dataclasses import replace

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import JSONResponse

from campus247.agent.state import NormalizedTurn
from campus247.application.conversation.messages import SenderType
from campus247.application.conversation.stream_result import prepare_chat_result
from campus247.application.conversation.read import final_payload
from campus247.domain.shared.values import generate_uuid7
from campus247.application.single_agent.contracts import digest
from campus247.ports.agent_runs import RunConflict
from campus247.presentation.identity import get_current_identity


class ResumeBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_version: int = Field(ge=1)
    content: str = Field(default="", max_length=2000)


class CancelBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_version: int = Field(ge=1)


def create_agent_run_router(*, workflow, conversations, history, context_factory, turn_preparer=None):
    router = APIRouter(tags=["Agent runs"])
    base = "/v1/conversations/{conversation_id}/agent-runs/{run_id}"

    async def owned(request, conversation_id, run_id):
        actor = get_current_identity(request)
        conv = await conversations.get_conversation(conversation_id)
        record = workflow.store.get(run_id, actor.subject_id, conversation_id)
        if not conv or conv.owner_user_id != actor.subject_id or not record:
            raise HTTPException(404, "Run unavailable")
        # Refresh current authorization on every read/resume, not just ownership.
        turn = NormalizedTurn(conversation_id, run_id, actor.subject_id, record["goal"])
        try:
            if turn_preparer is not None:
                turn = await turn_preparer(turn, actor, getattr(request.state, "revalidate_identity", None))
            context = context_factory(turn, actor)
            if context is None:
                raise ValueError()
            await workflow.validate_sources(record, context, turn=turn)
            if record.get("transition_receipt"):
                expected = record["transition_receipt"]
                receipt = workflow.store.transition_receipt(run_id, actor.subject_id, conversation_id, expected["id"])
                if (receipt != expected or expected["result_sha256"] != digest(record.get("final_result")) or
                        expected["binding_sha256"] != digest(record.get("binding")) or expected["state"] != record["status"] or
                        expected["version"] != record["version"]):
                    raise ValueError("run receipt mismatch")
        except Exception:
            raise HTTPException(403, "Current source scope unavailable") from None
        return actor, record, turn, context

    def public(record):
        controller = record.get("controller", {})
        return {"id": record["id"], "version": record["version"], "status": record["status"],
            "config_fingerprint": record["config_fingerprint"], "snapshot": record["snapshot"],
            "coverage": controller.get("coverage", []), "usage": record.get("usage"),
            "final_result": record.get("final_result"), "error_codes": record.get("error_codes", []),
            "continuation": record.get("continuation"), "transition_receipt": record.get("transition_receipt"),
            "tasks": [{"id": row["id"], "role": row["spec"]["role"], "status": row["status"],
                       "dependencies": row["spec"]["dependencies"], "version": row["version"],
                       "attempt": row["attempt"]} for row in workflow.store.tasks(record["id"])]}

    @router.get(base)
    async def get_run(conversation_id: str, run_id: str, request: Request):
        _, record, _, _ = await owned(request, conversation_id, run_id)
        return JSONResponse(public(record), headers={"Cache-Control": "no-store"})

    @router.get(base + "/events")
    async def events(conversation_id: str, run_id: str, request: Request, after: int = Query(0, ge=0)):
        _, record, _, _ = await owned(request, conversation_id, run_id)
        values = [event for event in record["events"] if event["seq"] > after]
        return JSONResponse({"run_id": run_id, "events": values,
            "cursor": record["events"][-1]["seq"] if record["events"] else 0}, headers={"Cache-Control": "no-store"})

    @router.get(base + "/receipt")
    async def receipt(conversation_id: str, run_id: str, request: Request):
        actor, record, _, _ = await owned(request, conversation_id, run_id)
        expected = record.get("transition_receipt")
        value = workflow.store.transition_receipt(run_id, actor.subject_id, conversation_id, expected["id"]) if expected else None
        if value is None or value != expected:
            raise HTTPException(409, "Run result has no committed receipt")
        return JSONResponse(value, headers={"Cache-Control": "no-store"})

    @router.post(base + ":resume")
    async def resume(conversation_id: str, run_id: str, body: ResumeBody, request: Request):
        actor, record, turn, context = await owned(request, conversation_id, run_id)
        if record["status"] == "waiting_user" and not body.content.strip():
            raise HTTPException(422, "Clarification response required")
        if turn_preparer is not None:
            turn = await turn_preparer(turn, actor, getattr(request.state, "revalidate_identity", None))
        # Claim/CAS is performed by workflow before any model dispatch. No write
        # service is called by this endpoint or by restored checkpoint content.
        try:
            result = await workflow.aresume(replace(turn, query=body.content), expected_version=body.expected_version,
                retrieval_context=context, current_context=lambda: context_factory(turn,
                    request.state.revalidate_identity() if hasattr(request.state, "revalidate_identity") else actor,
                    effective_at=context.effective_at, trace_id=context.trace_id))
        except RunConflict:
            raise HTTPException(409, "Run changed or is still leased") from None
        except ValueError:
            raise HTTPException(409, "Run snapshot unavailable") from None
        final = prepare_chat_result(result)
        if body.content.strip():
            await conversations.append_message(conversation_id=conversation_id, sender_type=SenderType.USER,
                sender_user_id=actor.subject_id, content=body.content, message_id=generate_uuid7())
        message = await conversations.append_message(conversation_id=conversation_id,
            sender_type=SenderType.ASSISTANT, content=final.content, message_id=generate_uuid7(), final_result=final)
        return JSONResponse({"run": public(workflow.store.get(run_id, actor.subject_id, conversation_id)),
                             "message": final_payload(message)}, headers={"Cache-Control": "no-store"})

    @router.post(base + ":cancel")
    async def cancel(conversation_id: str, run_id: str, body: CancelBody, request: Request):
        actor, _, _, _ = await owned(request, conversation_id, run_id)
        try:
            workflow.cancel(run_id, actor.subject_id, conversation_id, body.expected_version)
        except RunConflict:
            raise HTTPException(409, "Run changed or already terminal") from None
        return JSONResponse({"run_id": run_id, "cancel_requested": True}, headers={"Cache-Control": "no-store"})
    return router
