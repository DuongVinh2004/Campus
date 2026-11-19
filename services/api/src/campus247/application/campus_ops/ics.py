"""iCalendar (RFC 5545) text for a student's schedule. Same rules as apps/web/src/lib/ics.ts, so a file downloaded from the
server and one built in the browser import the same way.

Pure functions. Times are written in UTC (`Z`), so no VTIMEZONE block is needed and every calendar app reads them the same.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

CRLF = "\r\n"
PRODID = "-//Campus 24/7//Schedule//VI"


@dataclass(frozen=True)
class IcsEvent:
    id: str
    title: str
    starts_at: datetime
    ends_at: datetime
    location: str = ""
    description: str = ""


def escape_text(value: str) -> str:
    """Section 3.3.11: backslash, semicolon, comma and line breaks are escaped in TEXT values."""
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n")


def fold(line: str) -> str:
    """Section 3.1: at most 75 octets per line; a fold is CRLF plus one space and never splits a UTF-8 character."""
    if len(line.encode("utf-8")) <= 75:
        return line
    parts, current, size, limit = [], "", 0, 75
    for char in line:
        width = len(char.encode("utf-8"))
        if size + width > limit:
            parts.append(current)
            current, size, limit = "", 0, 74  # continuation lines start with one space
        current += char
        size += width
    parts.append(current)
    return (CRLF + " ").join(parts)


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _uid(identifier: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "-", identifier) + "@campus247.local"


def build_ics(events: list[IcsEvent], *, now: datetime, calendar_name: str = "Lịch học Campus 24/7") -> tuple[str, int]:
    """(text, number of events skipped). Events whose times are naive or not in order are skipped, not guessed."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             f"X-WR-CALNAME:{escape_text(calendar_name)}", "X-WR-TIMEZONE:Asia/Ho_Chi_Minh"]
    skipped = 0
    for event in events:
        if event.starts_at.tzinfo is None or event.ends_at.tzinfo is None or event.ends_at <= event.starts_at:
            skipped += 1
            continue
        lines += ["BEGIN:VEVENT", f"UID:{_uid(event.id)}", f"DTSTAMP:{_stamp(now)}", f"DTSTART:{_stamp(event.starts_at)}",
                  f"DTEND:{_stamp(event.ends_at)}", f"SUMMARY:{escape_text(event.title)}"]
        if event.location:
            lines.append(f"LOCATION:{escape_text(event.location)}")
        if event.description:
            lines.append(f"DESCRIPTION:{escape_text(event.description)}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return CRLF.join(fold(line) for line in lines) + CRLF, skipped
