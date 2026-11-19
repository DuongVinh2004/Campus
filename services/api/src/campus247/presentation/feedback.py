from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import JSONResponse

from campus247.application.assistance.state_storage import StorageConflict
from campus247.application.assistance.unified_contracts import UUID
from campus247.application.conversation.messages import ConversationStorageUnavailable
from campus247.application.conversations.feedback import (
    FeedbackRating,
    FeedbackService,
    FeedbackStorageError,
)
from campus247.presentation.identity import get_current_identity


class CreateAnswerFeedbackPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rating: FeedbackRating
    comment: str | None = Field(default=None, min_length=1, max_length=2000)
    client_id: UUID | None = None


def create_feedback_router(feedback_service: FeedbackService, authorize=None) -> APIRouter:
    router = APIRouter(tags=["Feedback"])

    @router.post("/v1/conversations/{conversation_id}/messages/{message_id}/feedback")
    async def create_answer_feedback(
        conversation_id: str,
        message_id: str,
        payload: CreateAnswerFeedbackPayload,
        request: Request,
    ) -> JSONResponse:
        identity = get_current_identity(request)
        if authorize is not None:authorize(identity)

        try:
            receipt = await feedback_service.record_feedback(
                actor_id=identity.subject_id,
                conversation_id=conversation_id,
                message_id=message_id,
                rating=payload.rating,
                comment=payload.comment,
                client_id=payload.client_id,
            )
        except StorageConflict:
            raise HTTPException(status_code=409,detail="Feedback client ID conflict") from None
        except ValueError:
            raise HTTPException(status_code=422,detail="Feedback requires a valid assistant answer") from None
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except ConversationStorageUnavailable:
            raise HTTPException(status_code=503,detail="Conversation storage unavailable") from None
        except FeedbackStorageError as e:
            raise HTTPException(status_code=503, detail=str(e))

        content = {
            "id": receipt.id,
            "conversation_id": receipt.conversation_id,
            "rating": receipt.rating.value,
            "comment_recorded": receipt.comment_recorded,
            "answer_reference": {
                "answer_id": receipt.answer_reference.answer_id,
                "source_document_version_ids": receipt.answer_reference.source_document_version_ids,
                "model_version": receipt.answer_reference.model_version,
                "prompt_version": receipt.answer_reference.prompt_version,
            },
            "recorded_at": receipt.recorded_at.isoformat(),
        }

        location = f"/v1/conversations/{conversation_id}/messages/{message_id}/feedback/{receipt.id}"
        return JSONResponse(
            status_code=201,
            content=content,
            headers={
                "Location": location,
                "Cache-Control": "no-store",
            },
        )

    @router.get("/v1/conversations/{conversation_id}/messages/{message_id}/feedback/{feedback_id}")
    async def read_feedback(conversation_id: str,message_id: str,feedback_id: str,request: Request):
        actor = get_current_identity(request)
        if authorize is not None:authorize(actor)
        try:
            receipt = await feedback_service.read_feedback(actor.subject_id,conversation_id,message_id,feedback_id)
        except KeyError:
            raise HTTPException(404,"Feedback not found") from None
        except (FeedbackStorageError,ConversationStorageUnavailable):
            raise HTTPException(503,"Feedback storage unavailable") from None
        except ValueError:
            raise HTTPException(404,"Feedback not found") from None
        from dataclasses import asdict
        value = asdict(receipt);value["recorded_at"] = receipt.recorded_at.isoformat()
        return JSONResponse(value,headers={"Cache-Control":"no-store"})

    return router
