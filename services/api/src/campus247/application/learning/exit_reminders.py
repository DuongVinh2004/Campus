"""Which students still owe an answer to an exit ticket (phiếu ra lớp) that closes soon.

A pure read over the learning state: nothing here changes it. The reminder loop turns the result into notifications
(see campus_ops/reminders.py).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

DEFAULT_HORIZON = timedelta(hours=26)


def _instant(value: dict[str, Any]) -> datetime:
    moment = datetime.fromisoformat(value["utc"].replace("Z", "+00:00"))
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def open_exit_ticket_deadlines(state: dict[str, Any], *, offerings: set[str] | frozenset[str], now: datetime,
                               horizon: timedelta = DEFAULT_HORIZON) -> list[dict[str, Any]]:
    """Published tickets of classes that have the feature on, open now and closing within `horizon`, with the active students who
    have not submitted an answer. Tickets with nobody left to remind are left out."""
    rows = []
    for ticket_id, ticket in sorted(state.get("exit_tickets", {}).items()):
        if ticket.get("status") != "PUBLISHED" or ticket.get("published_question_revision") is None:
            continue
        if ticket["offering_id"] not in offerings:
            continue
        opens, closes = _instant(ticket["opens"]), _instant(ticket["closes"])
        if not opens <= now < closes <= now + horizon:
            continue
        answered = state.get("exit_submissions", {})
        students = sorted({m["actor_subject_id"] for m in state.get("members", {}).values()
                           if m.get("offering_id") == ticket["offering_id"] and m.get("status") == "ACTIVE" and m.get("role") == "STUDENT"
                           and f"{ticket_id}:{m['actor_subject_id']}" not in answered})
        if not students:
            continue
        session = state.get("sessions", {}).get(ticket.get("session_id"), {})
        rows.append({"ticket_id": ticket_id, "session_title": session.get("title") or "buổi học", "closes": closes, "students": students})
    return rows


async def exit_ticket_deadlines(learning_service, now: datetime, horizon: timedelta = DEFAULT_HORIZON) -> list[dict[str, Any]]:
    """Read the learning state of a running service (changes nothing: the store only writes a transaction that altered the state)."""
    if not learning_service.exit_ticket_offerings:
        return []
    async with learning_service.repository.transaction() as state:
        return open_exit_ticket_deadlines(state, offerings=learning_service.exit_ticket_offerings, now=now, horizon=horizon)
