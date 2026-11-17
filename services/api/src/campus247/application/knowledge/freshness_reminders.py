"""Reminders for the people who manage the knowledge base: a source is about to expire or to be due for a review, or several are overdue.

Uses the same once-only reminder engine as exam reminders. A source gets a notice 30 days and 7 days before its date (the date is
part of the key, so confirming a review, which moves the date, starts a fresh cycle). Sources already past their date cannot be
reminded "before" anything, so one summary per week says how many are overdue.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from campus247.application.campus_ops.reminders import Candidate, deliver, time_left_text

LOG = logging.getLogger("campus247.freshness")
VN = ZoneInfo("Asia/Ho_Chi_Minh")
OFFSETS = (timedelta(days=30), timedelta(days=7))
LINK = "/knowledge/freshness"


def _days_text(left: timedelta) -> str:
    days = max(0, round(left.total_seconds() / 86400))
    return f"{days} ngày" if days >= 1 else time_left_text(left)


def source_candidates(items: list[dict[str, Any]], managers: list[str], *, now: datetime) -> list[Candidate]:
    candidates: list[Candidate] = []
    overdue = [item for item in items if item["state"] == "OVERDUE"]
    for manager in managers:
        for item in items:
            if item["state"] != "DUE_SOON" or not item.get("due_at"):
                continue
            due = datetime.fromisoformat(item["due_at"].replace("Z", "+00:00"))
            expires = item["reason"] == "EFFECTIVE_UNTIL"

            def describe(left: timedelta, item: dict[str, Any] = item, due: datetime = due, expires: bool = expires) -> tuple[str, str]:
                what = "sắp hết hiệu lực" if expires else "sắp đến hạn rà soát"
                action = "Sau ngày này nguồn không còn xuất hiện trong câu trả lời." if expires else "Hãy đối chiếu với văn bản gốc rồi ghi nhận đã rà soát."
                return (f"Nguồn {what}: {item['title']}", f"Còn {_days_text(left)} (ngày {due.astimezone(VN):%d/%m/%Y}). {action}")

            candidates.append(Candidate(item_key=f"source:{item['version_id']}:{due.date().isoformat()}", recipient=manager, kind="REMINDER",
                                        deadline=due, describe=describe, link=LINK, offsets=OFFSETS))
        if overdue:
            local = now.astimezone(VN)
            monday = (local - timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            week_end = (monday + timedelta(days=7)).astimezone(UTC)
            count = len(overdue)
            candidates.append(Candidate(item_key=f"overdue-summary:{monday.date().isoformat()}", recipient=manager, kind="REMINDER", deadline=week_end,
                                        describe=lambda left, count=count: (f"{count} nguồn quá hạn rà soát", "Mở trang Hiệu lực của nguồn để xem và ghi nhận việc rà soát."),
                                        link=LINK, offsets=(timedelta(days=7),)))
    return candidates


async def run_freshness_reminders(service, store, managers: Callable[[], list[str]], *, every_s: float = 3600.0,
                                  clock: Callable[[], datetime] = lambda: datetime.now(UTC), passes: int | None = None) -> None:
    done = 0
    while passes is None or done < passes:
        try:
            now = clock()
            report = await service.report(now=now)
            sent = await asyncio.to_thread(lambda: deliver(store, source_candidates(report["items"], managers(), now=now), now=now))
            if sent:
                LOG.info("freshness_reminders_sent count=%d", sent)
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001 -- keep the loop alive; the next pass tries again
            LOG.warning("freshness_reminders_failed kind=%s", type(error).__name__)
        done += 1
        if passes is None or done < passes:
            await asyncio.sleep(every_s)
