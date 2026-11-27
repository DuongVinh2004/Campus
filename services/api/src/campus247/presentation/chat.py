from __future__ import annotations

import asyncio
import json
import logging
import re
import inspect
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Literal
from collections.abc import Callable
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import Field
from starlette.responses import JSONResponse, StreamingResponse

from campus247.agent.state import NormalizedTurn
from campus247.application.conversation.messages import (
    ConversationMessageService,
    SenderType,
    ConversationConflict,
)
from campus247.domain.shared.values import generate_uuid7, is_valid_uuid7
from campus247.application.conversation.stream_result import (
    StreamFailure, prepare_chat_result, apply_stream_validation,
)
from campus247.presentation.errors import create_problem_details
from campus247.presentation.identity import get_current_identity
from campus247.ports.identity import IdentityContext
from campus247.observability.ops_metrics import OPS, TurnObserver
from campus247.agent.state import AgentState
from campus247.application.conversation.history import ConversationHistoryService
from campus247.application.conversation.read import StoredMessageError, final_payload, public_message
from campus247.application.assistance.contracts import StrictDTO
from campus247.application.assistance.unified_contracts import UUID
from campus247.ports.identity import IdentityRole
from campus247.application.authorization.concealment import ResourceNotFoundError


class CreateConversationPayload(StrictDTO):
    client_id: UUID | None = None
    mode: Literal["persistent", "temporary"] = "persistent"


class CreateMessagePayload(StrictDTO):
    content: str = Field(..., min_length=1, max_length=10000)
    client_id: UUID | None = None


def create_chat_router(
    conv_service: ConversationMessageService,
    agent_runner: Any | None = None,
    *, trusted_agent_runner: Callable[[NormalizedTurn, IdentityContext], AgentState] | None = None,
    history_service: ConversationHistoryService | None = None,
    agent_progress: bool = False,
    turn_preparer=None,
    result_guard=None,
    authorize_conversation=None,
    admission=None,
) -> APIRouter:
    router = APIRouter(tags=["Conversations"])

    def student(request):
        actor = get_current_identity(request)
        tenant = getattr(conv_service._repo, "tenant", None)
        if authorize_conversation is not None:
            authorize_conversation(actor)
            if tenant is not None and actor.tenant_id != tenant:
                raise HTTPException(403, "Conversation tenant unavailable")
            return actor
        if set(actor.roles) != {IdentityRole.STUDENT} or tenant is not None and actor.tenant_id != tenant:
            raise HTTPException(403, "Conversation audience or tenant unavailable")
        return actor

    @router.post("/v1/conversations")
    async def create_conversation_endpoint(request: Request, payload: CreateConversationPayload | None = None) -> JSONResponse:
        identity = student(request)
        try:
            conv = await conv_service.create_conversation(owner_user_id=identity.subject_id,
                client_id=payload.client_id if payload else None, mode=payload.mode if payload else "persistent")
        except ConversationConflict:
            raise HTTPException(409, "Conversation client ID unavailable") from None
        except TimeoutError:
            raise HTTPException(503, "Conversation storage unavailable") from None
        return JSONResponse(
            status_code=201,
            content={
                "id": conv.id,
                "owner_user_id": conv.owner_user_id,
                "status": str(conv.status),
                "created_at": conv.created_at.isoformat(),
                "mode": conv.mode,
                "retention_expires_at": conv.retention_expires_at.isoformat(),
                "disclosure": "Lưu vận hành 30 ngày; chat tạm thời không dùng personal memory và không hiện trong danh sách lịch sử. Không xóa vật lý dữ liệu/backup.",
                "receipt": {"client_id": payload.client_id if payload else None, "conversation_id": conv.id, "state": "committed"},
            },
        )

    @router.get("/v1/conversations/{conversation_id}/messages")
    async def list_messages_endpoint(conversation_id: str, request: Request,
                                     cursor: str | None = Query(None, min_length=16, max_length=2048),
                                     limit: int = Query(20, ge=1, le=100)) -> JSONResponse:
        identity = student(request)
        try:
            conversation = await conv_service.get_conversation(conversation_id)
            items, next_cursor, has_more = await conv_service.list_owned_page(
                identity.subject_id, conversation_id, cursor=cursor, limit=limit)
        except ResourceNotFoundError:
            raise HTTPException(404, 'Conversation not found') from None
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid message page") from None
        except TimeoutError:
            return create_problem_details(status=503, code="DEPENDENCY_UNAVAILABLE",
                title="Không thể đọc lịch sử", detail="Dịch vụ lịch sử chưa sẵn sàng.",
                request=request, retryable=False)
        try:
            public_items = [public_message(message) for message in items]
        except StoredMessageError:
            return create_problem_details(status=503, code="DEPENDENCY_UNAVAILABLE",
                title="Không thể xác nhận lịch sử", detail="Kết quả đã lưu chưa thể xác nhận.",
                request=request, retryable=False)
        return JSONResponse(content={"items": public_items, "mode": conversation.mode,
            "retention_state": "expired" if conversation.retention_expires_at <= datetime.now(timezone.utc) else "available",
            "page": {"next_cursor": next_cursor, "has_more": has_more, "limit": limit}},
            headers={"Cache-Control": "no-store"})

    @router.get("/v1/conversations/{conversation_id}/receipts/{client_id}")
    async def read_turn_receipt(conversation_id: UUID, client_id: UUID, request: Request):
        actor = student(request)
        try:
            receipt = await conv_service.turn_receipt(actor.subject_id, conversation_id, client_id)
        except TimeoutError:
            raise HTTPException(503, "Turn receipt unavailable") from None
        if receipt is None:
            raise HTTPException(404, "Turn receipt unavailable")
        return JSONResponse({k: v for k, v in receipt.items() if k != "owner"}, headers={"Cache-Control": "no-store"})

    @router.post("/v1/conversations/{conversation_id}/messages:stream")
    async def stream_message(
        conversation_id: str,
        payload: CreateMessagePayload,
        request: Request,
    ) -> StreamingResponse:
        identity = student(request)
        if admission is None:
            return await open_stream(conversation_id, payload, request, identity)
        # Admission control: a turn starts within the wait bound or is told at once that the system is busy.
        # Checked after authentication and before anything is saved, so a refused turn leaves no trace.
        observer = TurnObserver(OPS)  # counts the turn from here, so waiting for a slot is part of its time

        def publish_load() -> None:
            OPS.set_gauges(in_flight=admission.in_flight, waiting=admission.waiting, limit=admission.limit)

        slot = await admission.acquire()
        publish_load()
        if slot is None:
            OPS.record_admission_rejected()
            logging.getLogger("campus247.chat").warning(
                "chat_admission_rejected in_flight=%d waiting=%d limit=%d rejected_total=%d",
                admission.in_flight, admission.waiting, admission.limit, admission.rejected)
            busy = create_problem_details(
                status=503, code="DEPENDENCY_UNAVAILABLE", title="Hệ thống đang bận",
                detail="Hệ thống đang bận, thử lại sau ít giây. Câu hỏi của bạn chưa được gửi đi.",
                request=request, retryable=True)
            busy.headers["Retry-After"] = "5"
            return busy
        try:
            response = await open_stream(conversation_id, payload, request, identity)
        except BaseException:
            slot.release()
            publish_load()
            raise
        if not isinstance(response, StreamingResponse):
            slot.release()  # refused before streaming (conflict, not found, ...): the turn never ran
            publish_load()
            return response
        inner = response.body_iterator

        async def released_when_done():
            try:
                async for chunk in inner:
                    observer.feed(chunk)
                    yield chunk
            finally:
                observer.finish()
                slot.release()
                publish_load()
                close = getattr(inner, "aclose", None)
                if close is not None:
                    await close()

        response.body_iterator = released_when_done()
        return response

    async def open_stream(conversation_id: str, payload: CreateMessagePayload, request: Request, identity):
        try:
            conv = await conv_service.get_conversation(conversation_id)
        except TimeoutError:
            raise HTTPException(503, "Conversation storage unavailable") from None
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        if conv.owner_user_id != identity.subject_id:
            raise HTTPException(
                status_code=403, detail="Forbidden: conversation ownership required"
            )
        if conv.retention_expires_at <= datetime.now(timezone.utc):
            raise HTTPException(409, "Conversation retention expired")
        application = request.scope.get("app")
        catalog = getattr(getattr(application, "state", None), "conversation_catalog", None)
        if catalog is not None and not (await catalog.read(identity, conversation_id))["can_continue"]:
            raise HTTPException(409, "Conversation unavailable for continuation")

        request_id = getattr(request.state, "request_id", None)
        if not isinstance(request_id, str) or not is_valid_uuid7(request_id):
            request_id = generate_uuid7()
        request.state.request_id = request_id

        def safe_problem(code: str = "INTERNAL_ERROR") -> JSONResponse:
            unavailable = code in {"DEPENDENCY_UNAVAILABLE", "INTEGRATION_NOT_ENABLED"}
            return create_problem_details(
                status=503 if unavailable else 500,
                code=code if unavailable else "INTERNAL_ERROR",
                title="Không thể hoàn tất câu trả lời",
                detail="Dịch vụ trò chuyện chưa thể hoàn tất yêu cầu. Vui lòng kiểm tra lịch sử hoặc gửi yêu cầu hỗ trợ; hệ thống không tự gửi lại thao tác.",
                request=request, retryable=False,
            )

        if request.headers.get("last-event-id"):
            problem = create_problem_details(
                status=409, code="INVALID_STATE_TRANSITION", title="Không thể nối lại luồng",
                detail="Luồng này không hỗ trợ nối lại; hệ thống không tự tạo lại câu trả lời. Hãy kiểm tra lịch sử trò chuyện.",
                request=request, retryable=False,
            )
            problem.headers["Link"] = f'</v1/conversations/{conversation_id}/messages>; rel="alternate"'
            return problem

        # 1. Save user message
        try:
            saved_user = await conv_service.append_message(
                conversation_id=conversation_id,
                sender_type=SenderType.USER,
                content=payload.content,
                sender_user_id=identity.subject_id,
                message_id=payload.client_id,
                turn_client_id=payload.client_id,
            )
        except ConversationConflict as conflict:
            return JSONResponse({"code": str(conflict), "detail": "Read the existing receipt; no automatic regeneration.",
                "receipt_path": f"/v1/conversations/{conversation_id}/receipts/{payload.client_id}"}, status_code=409)
        except Exception:
            return safe_problem()

        async def event_generator() -> AsyncGenerator[str, None]:
            from campus247.agent.streaming import StreamGuardrail

            assistant_msg_id = generate_uuid7()
            guardrail = StreamGuardrail()

            def event(name: str, data: Any) -> str:
                return f"id: {generate_uuid7()}\nevent: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

            try:
                if await request.is_disconnected():
                    return
                yield event("message.started", {"conversation_id": conversation_id, "message_id": assistant_msg_id})

                # Generate answer using agent workflow if available
                if agent_runner is not None or trusted_agent_runner is not None:
                    turn = NormalizedTurn(
                        session_id=conversation_id,
                        turn_id=saved_user.id,
                        user_id=identity.subject_id,
                        query=payload.content,
                    )
                    if history_service is not None:
                        history = await history_service.load(identity.subject_id, conversation_id,
                            before_message_id=saved_user.id)
                        turn = replace(turn, history=history)
                    if turn_preparer is not None:
                        turn = await turn_preparer(turn, identity, getattr(request.state, "revalidate_identity", None))
                    if agent_progress and trusted_agent_runner is not None:
                        queue = asyncio.Queue(maxsize=64)
                        def progress(data):
                            if not queue.full():
                                queue.put_nowait(data)
                        job = asyncio.create_task(trusted_agent_runner(turn, identity, progress=progress,
                            current_identity=getattr(request.state, "revalidate_identity", None)))
                        try:
                            while not job.done() or not queue.empty():
                                if await request.is_disconnected():
                                    job.cancel()
                                    await asyncio.gather(job, return_exceptions=True)
                                    return
                                try:
                                    data = await asyncio.wait_for(queue.get(), .1)
                                    yield event("agent.status", data)
                                except TimeoutError:
                                    pass
                            state = await job
                        finally:
                            if not job.done():
                                job.cancel()
                            await asyncio.gather(job, return_exceptions=True)
                    else:
                        state = (trusted_agent_runner(turn, identity) if trusted_agent_runner is not None
                                 else agent_runner.run(turn))
                        if inspect.isawaitable(state):
                            state = await state
                else:
                    raise StreamFailure("INTEGRATION_NOT_ENABLED")

                if turn.context_guard is not None:
                    turn.context_guard()
                async def check_result_scope():
                    if result_guard is not None:
                        current_identity = getattr(request.state, "revalidate_identity", None)
                        current_actor = current_identity() if current_identity else identity
                        await result_guard(state, current_actor)
                await check_result_scope()
                if await request.is_disconnected():
                    return
                result = prepare_chat_result(state)
                # Apply the existing persistence policy before any content
                # delta, including legacy callers without a client turn ID.
                if not conv_service.can_persist_content(result.content):
                    from campus247.application.conversation.history_presentation import history_policy_alternative
                    result = history_policy_alternative(state, result)
                    if not conv_service.can_persist_content(result.content):
                        raise StreamFailure()
                # The current runner returns a whole draft, not provider token events.
                # Validate that draft before publishing any part of it. Keep the guard unchanged.
                guardrail.push_provisional(seq=1, delta=result.content)
                result = apply_stream_validation(result, guardrail.validate_and_commit())
                # Persist the validated terminal before sending deltas. A socket
                # drop after completion can recover this result without inference.
                saved_assistant = None
                if agent_progress or payload.client_id is not None:
                    saved_assistant = await conv_service.append_message(
                        conversation_id=conversation_id, sender_type=SenderType.ASSISTANT,
                        content=result.content, message_id=assistant_msg_id, final_result=result, turn_client_id=payload.client_id)

                # Split words into streamable chunks
                words = re.findall(r"\S+|\s+", result.content)
                chunk_buffer = []
                seq_counter = 0
                for w in words:
                    chunk_buffer.append(w)
                    if len(chunk_buffer) >= 3 or "\n" in w:
                        delta = "".join(chunk_buffer)
                        chunk_buffer = []
                        seq_counter += 1

                        if await request.is_disconnected():
                            return

                        yield event("message.delta", {"seq": seq_counter, "delta": delta})
                        await asyncio.sleep(0.01)

                if chunk_buffer:
                    delta = "".join(chunk_buffer)
                    seq_counter += 1
                    if await request.is_disconnected():
                        return
                    yield event("message.delta", {"seq": seq_counter, "delta": delta})

                if await request.is_disconnected():
                    return

                await check_result_scope()
                # Save validated completed assistant message
                if saved_assistant is None:
                    saved_assistant = await conv_service.append_message(
                        conversation_id=conversation_id, sender_type=SenderType.ASSISTANT,
                        content=result.content, message_id=assistant_msg_id, final_result=result, turn_client_id=payload.client_id)
                receipts = getattr(getattr(request.scope.get("app"), "state", None), "answer_receipts", None)
                if receipts is not None and getattr(result, "evidence", None) and receipts.enabled():
                    from campus247.application.answer_evidence.record import record_receipt
                    held = await conv_service.get_conversation(conversation_id)
                    first = saved_assistant.citations[0] if saved_assistant.citations else None
                    release = (json.loads(first.citation_json).get("release_id") if first else None)
                    if held is not None:
                        record_receipt(receipts, owner=identity.subject_id, conversation_id=conversation_id, message=saved_assistant, result=result,
                                       expires_at=held.retention_expires_at.isoformat(timespec="seconds"), release_id=release)
                citations_payload = [citation.to_dict() for citation in saved_assistant.citations]
                await check_result_scope()
                for citation in citations_payload:
                    if await request.is_disconnected():
                        return
                    if any(code.startswith("RAG_V2_") for code in state.errors):
                        await check_result_scope()
                    yield event("citation.added", {"message_id": saved_assistant.id, "citation": citation})

                # Event 3: message.completed
                complete_data = final_payload(saved_assistant)
                if complete_data is None:
                    raise StreamFailure()
                if any(code.startswith("RAG_V2_") for code in state.errors):
                    await check_result_scope()
                yield event("message.completed", complete_data)

            except asyncio.CancelledError:
                # Do not commit unvalidated partial semantics as complete
                raise
            except StreamFailure as failure:
                logging.getLogger("campus247.chat").warning("stream_failure code=%s", getattr(failure, "code", "?"))
                if not await request.is_disconnected():
                    yield event("message.failed", json.loads(safe_problem(failure.code).body))
            except TimeoutError:
                if not await request.is_disconnected():
                    yield event("message.failed", json.loads(safe_problem("DEPENDENCY_UNAVAILABLE").body))
            except Exception as exc:
                logging.getLogger("campus247.chat").warning("stream_exception kind=%s where=%s", type(exc).__name__,
                    exc.__traceback__.tb_next.tb_frame.f_code.co_name if exc.__traceback__ and exc.__traceback__.tb_next else "?")
                if not await request.is_disconnected():
                    yield event("message.failed", json.loads(safe_problem().body))
            finally:
                if payload.client_id is not None:
                    await conv_service.interrupt_turn(identity.subject_id, conversation_id, payload.client_id)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-store",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "X-Request-Id": request_id,
                **({"X-User-Message-Id": saved_user.id, "X-Turn-Client-Id": payload.client_id} if payload.client_id else {}),
            },
        )

    return router
