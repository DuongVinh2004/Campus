"""HTTP surface for rooms, personal timetable, notifications, tickets, staff queue and admin overview.

No ``from __future__ import annotations`` here: FastAPI resolves the request models by annotation.
"""
from typing import Any, Optional

from fastapi import APIRouter, FastAPI, Header, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import JSONResponse, Response

from campus247.application.campus_ops.service import CampusOpsService
from campus247.ports.campus_ops import OpsError
from campus247.presentation.identity import get_current_identity

NO_STORE = {"Cache-Control": "no-store"}


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RoomPreviewBody(_Body):
    room_id: str = Field(max_length=64)
    date: str = Field(max_length=10)
    start: str = Field(max_length=5)
    end: str = Field(max_length=5)
    purpose: str = Field(max_length=300)
    attendees: int = Field(default=1, ge=1, le=1000)


class RoomConfirmBody(_Body):
    preview_id: str = Field(max_length=64)
    idempotency_key: Optional[str] = Field(default=None, max_length=120)


class ReasonBody(_Body):
    reason: str = Field(default="", max_length=500)


class EventBody(_Body):
    title: str = Field(max_length=200)
    starts_at: str = Field(max_length=40)
    ends_at: str = Field(max_length=40)
    location: str = Field(default="", max_length=200)
    note: str = Field(default="", max_length=800)


class TicketBody(_Body):
    service_kind: str = Field(max_length=40)
    title: str = Field(default="", max_length=200)
    summary: str = Field(max_length=5000)
    fields: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = Field(default=None, max_length=120)


class TextBody(_Body):
    body: str = Field(max_length=3000)
    set_status: Optional[str] = Field(default=None, max_length=20)


class StatusBody(_Body):
    status: str = Field(max_length=20)
    reason: str = Field(default="", max_length=2000)


def register_ops_errors(app: FastAPI) -> None:
    @app.exception_handler(OpsError)
    async def ops_error(request: Request, exc: OpsError):
        return JSONResponse(status_code=exc.status, headers=NO_STORE, content={
            "type": f"https://campus247.example/problems/{exc.code.lower().replace('_', '-')}", "title": exc.detail,
            "status": exc.status, "detail": exc.detail, "code": exc.code, "retryable": exc.status in (503, 429)})


def _json(content: Any, status: int = 200) -> JSONResponse:
    return JSONResponse(content, status_code=status, headers=NO_STORE)


def create_campus_ops_router(service: CampusOpsService) -> APIRouter:
    r = APIRouter(tags=["Campus operations"])

    # ------------------------------------------------------------------ rooms
    @r.get("/v1/rooms")
    def list_rooms(request: Request, building: Optional[str] = Query(None, max_length=80), kind: Optional[str] = Query(None, max_length=20),
                   min_capacity: Optional[int] = Query(None, ge=1, le=1000), q: Optional[str] = Query(None, max_length=80)):
        get_current_identity(request)
        return _json(service.list_rooms(building=building, kind=kind, min_capacity=min_capacity, q=q))

    @r.get("/v1/rooms/bookings/mine")
    def my_bookings(request: Request):
        return _json(service.my_bookings(get_current_identity(request)))

    @r.get("/v1/rooms/{room_id}/availability")
    def availability(room_id: str, request: Request, date: str = Query(..., max_length=10)):
        get_current_identity(request)
        return _json(service.availability(room_id, date))

    @r.post("/v1/rooms/book/preview")
    def preview_booking(body: RoomPreviewBody, request: Request):
        return _json(service.preview_booking(get_current_identity(request), body.model_dump()))

    @r.post("/v1/rooms/book")
    def confirm_booking(body: RoomConfirmBody, request: Request, idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
        key = idempotency_key or body.idempotency_key or ""
        return _json(service.confirm_booking(get_current_identity(request), body.preview_id, key), 201)

    @r.post("/v1/rooms/bookings/{booking_id}/cancel")
    def cancel_booking(booking_id: str, body: ReasonBody, request: Request):
        return _json(service.cancel_booking(get_current_identity(request), booking_id, body.reason))

    # --------------------------------------------------------------- schedule
    @r.get("/v1/students/me/schedule")
    def my_schedule(request: Request, from_time: str = Query(..., alias="from", max_length=40), to_time: str = Query(..., alias="to", max_length=40)):
        return _json(service.list_schedule(get_current_identity(request), from_time, to_time))

    @r.get("/v1/students/me/schedule.ics")
    def my_schedule_ics(request: Request, from_time: str = Query(..., alias="from", max_length=40), to_time: str = Query(..., alias="to", max_length=40)):
        text = service.schedule_ics(get_current_identity(request), from_time, to_time)
        return Response(content=text, media_type="text/calendar; charset=utf-8",
                        headers={**NO_STORE, "Content-Disposition": 'attachment; filename="lich-hoc-campus247.ics"', "X-Content-Type-Options": "nosniff"})

    @r.post("/v1/students/me/schedule/events")
    def create_event(body: EventBody, request: Request):
        return _json(service.create_event(get_current_identity(request), body.model_dump()), 201)

    @r.put("/v1/students/me/schedule/events/{event_id}")
    def update_event(event_id: str, body: EventBody, request: Request):
        return _json(service.update_event(get_current_identity(request), event_id, body.model_dump()))

    @r.delete("/v1/students/me/schedule/events/{event_id}")
    def delete_event(event_id: str, request: Request):
        return _json(service.delete_event(get_current_identity(request), event_id))

    # ---------------------------------------------------------- notifications
    @r.get("/v1/notifications")
    def notifications(request: Request, unread_only: bool = Query(False), limit: int = Query(50, ge=1, le=100)):
        return _json(service.list_notifications(get_current_identity(request), unread_only, limit))

    @r.post("/v1/notifications/read-all")
    def read_all(request: Request):
        return _json(service.mark_read(get_current_identity(request), None))

    @r.post("/v1/notifications/{notification_id}/read")
    def read_one(notification_id: str, request: Request):
        return _json(service.mark_read(get_current_identity(request), notification_id))

    # ---------------------------------------------------------------- tickets
    @r.get("/v1/tickets")
    def my_tickets(request: Request):
        return _json(service.my_tickets(get_current_identity(request)))

    @r.post("/v1/tickets")
    def submit_ticket(body: TicketBody, request: Request, idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
        key = idempotency_key or body.idempotency_key or ""
        payload = body.model_dump(exclude={"idempotency_key"})
        return _json(service.submit_ticket(get_current_identity(request), payload, key), 201)

    @r.get("/v1/tickets/{ticket_id}")
    def ticket_detail(ticket_id: str, request: Request):
        return _json(service.ticket_detail(get_current_identity(request), ticket_id))

    @r.post("/v1/tickets/{ticket_id}/reply")
    def ticket_reply(ticket_id: str, body: TextBody, request: Request):
        return _json(service.student_reply(get_current_identity(request), ticket_id, body.body))

    @r.post("/v1/tickets/{ticket_id}/cancel")
    def ticket_cancel(ticket_id: str, body: ReasonBody, request: Request):
        return _json(service.cancel_ticket(get_current_identity(request), ticket_id, body.reason))

    # ------------------------------------------------------------------ staff
    @r.get("/v1/staff/tickets")
    def staff_queue(request: Request, status: Optional[str] = Query(None, max_length=20), mine: bool = Query(False), q: Optional[str] = Query(None, max_length=80)):
        return _json(service.staff_queue(get_current_identity(request), status, mine, q))

    @r.get("/v1/staff/tickets/{ticket_id}")
    def staff_detail(ticket_id: str, request: Request):
        identity = get_current_identity(request)
        from campus247.application.campus_ops.service import require_staff
        require_staff(identity)
        return _json(service.ticket_detail(identity, ticket_id))

    @r.post("/v1/staff/tickets/{ticket_id}/claim")
    def staff_claim(ticket_id: str, request: Request):
        return _json(service.staff_claim(get_current_identity(request), ticket_id))

    @r.post("/v1/staff/tickets/{ticket_id}/reply")
    def staff_reply(ticket_id: str, body: TextBody, request: Request):
        return _json(service.staff_reply(get_current_identity(request), ticket_id, body.body, body.set_status))

    @r.post("/v1/staff/tickets/{ticket_id}/status")
    def staff_status(ticket_id: str, body: StatusBody, request: Request):
        return _json(service.staff_set_status(get_current_identity(request), ticket_id, body.status, body.reason))

    @r.post("/v1/staff/tickets/{ticket_id}/note")
    def staff_note(ticket_id: str, body: TextBody, request: Request):
        return _json(service.staff_note(get_current_identity(request), ticket_id, body.body))

    # ------------------------------------------------------------------ admin
    @r.get("/v1/admin/overview")
    def admin_overview(request: Request):
        return _json(service.admin_overview(get_current_identity(request)))

    return r
