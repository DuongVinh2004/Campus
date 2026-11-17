from fastapi import APIRouter, HTTPException, Query, Request
from datetime import datetime, timezone
from starlette.responses import JSONResponse

from campus247.application.authorization.concealment import ResourceNotFoundError
from campus247.application.conversation.read import StoredMessageError, public_message
from campus247.ports.identity import IdentityRole
from campus247.presentation.errors import create_problem_details
from campus247.presentation.identity import get_current_identity


def create_held_history_router(service, authorize):
    router = APIRouter(tags=["Held owned history"])

    @router.get("/v1/conversations/{conversation_id}/messages")
    async def messages(conversation_id: str,request: Request,cursor: str | None = Query(None,min_length=16,max_length=2048),
                       limit: int = Query(20,ge=1,le=100)):
        actor = get_current_identity(request);authorize(actor,IdentityRole.STUDENT)
        try:
            conversation = await service.get_conversation(conversation_id)
            items,next_cursor,has_more = await service.list_owned_page(actor.subject_id,conversation_id,cursor=cursor,limit=limit)
            values = [public_message(message) for message in items]
        except ResourceNotFoundError:
            raise HTTPException(404,"Conversation unavailable") from None
        except ValueError as error:
            if isinstance(error,StoredMessageError):
                return create_problem_details(request=request,status=503,code="DEPENDENCY_UNAVAILABLE",title="Chưa xác nhận được lịch sử",detail="Kết quả đã lưu chưa thể xác nhận.")
            raise HTTPException(422,"Invalid message page") from None
        except TimeoutError:
            return create_problem_details(request=request,status=503,code="DEPENDENCY_UNAVAILABLE",title="Chưa đọc được lịch sử",detail="Lịch sử được giữ; dependency chưa sẵn sàng.")
        return JSONResponse({"items":values,"page":{"next_cursor":next_cursor,"has_more":has_more,"limit":limit},
            "retention_state": "expired" if conversation.retention_expires_at <= datetime.now(timezone.utc) else "available"},headers={"Cache-Control":"no-store"})

    return router
