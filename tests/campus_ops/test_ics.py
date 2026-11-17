"""The server-side calendar text follows the same rules as the browser's (apps/web/src/lib/ics.test.ts)."""
from datetime import UTC, datetime, timedelta, timezone

import pytest

from campus247.application.campus_ops.ics import IcsEvent, build_ics, escape_text, fold

NOW = datetime(2026, 11, 17, 3, 0, tzinfo=UTC)


def parse(text: str) -> list[dict[str, str]]:
    assert text.endswith("\r\n") and "\n" not in text.replace("\r\n", "")
    unfolded = text.replace("\r\n ", "").split("\r\n")
    events, current = [], None
    for line in unfolded:
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT":
            events.append(current)
            current = None
        elif current is not None and line:
            name, _, value = line.partition(":")
            current[name] = value
    return events


def event(**over):
    base = dict(id="abc-1", title="Mạng máy tính (IT3080)", starts_at=datetime(2026, 11, 16, 9, 35, tzinfo=timezone(timedelta(hours=7))),
                ends_at=datetime(2026, 11, 16, 11, 55, tzinfo=timezone(timedelta(hours=7))), location="H3-204", description="Giảng viên: TS. Trần Văn Minh")
    return IcsEvent(**(base | over))


def test_has_the_properties_a_calendar_app_needs_and_times_in_utc():
    text, skipped = build_ics([event()], now=NOW)
    (item,) = parse(text)
    assert skipped == 0 and text.startswith("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n") and text.endswith("END:VCALENDAR\r\n")
    assert item == {"UID": "abc-1@campus247.local", "DTSTAMP": "20261117T030000Z", "DTSTART": "20261116T023500Z", "DTEND": "20261116T045500Z",
                    "SUMMARY": "Mạng máy tính (IT3080)", "LOCATION": "H3-204", "DESCRIPTION": "Giảng viên: TS. Trần Văn Minh"}


def test_escapes_special_characters():
    assert escape_text("A, B; C\\D\nE\r\nF") == "A\\, B\\; C\\\\D\\nE\\nF"
    (item,) = parse(build_ics([event(title="Toán, rời rạc; nhóm 1")], now=NOW)[0])
    assert item["SUMMARY"] == "Toán\\, rời rạc\\; nhóm 1"


def test_long_lines_fold_at_75_octets_without_splitting_a_character_and_unfold_back():
    title = "Phương pháp luận nghiên cứu khoa học và kỹ năng viết báo cáo kỹ thuật bằng tiếng Việt có dấu đầy đủ"
    text, _ = build_ics([event(title=title)], now=NOW)
    assert all(len(line.encode("utf-8")) <= 75 for line in text.split("\r\n"))
    assert any(line.startswith(" ") for line in text.split("\r\n"))
    assert parse(text)[0]["SUMMARY"] == title
    assert fold("SUMMARY:ngắn") == "SUMMARY:ngắn"


def test_events_with_bad_times_are_skipped_and_counted():
    text, skipped = build_ics([event(), event(id="naive", starts_at=datetime(2026, 11, 16, 9, 0)), event(id="reversed", ends_at=NOW - timedelta(days=30))], now=NOW)
    assert skipped == 2 and [e["UID"] for e in parse(text)] == ["abc-1@campus247.local"]


def test_uid_is_made_safe_and_optional_fields_are_left_out():
    (item,) = parse(build_ics([event(id="a b/c:d", location="", description="")], now=NOW)[0])
    assert item["UID"] == "a-b-c-d@campus247.local" and "LOCATION" not in item and "DESCRIPTION" not in item


def test_a_naive_clock_is_refused():
    with pytest.raises(ValueError):
        build_ics([], now=datetime(2026, 11, 17))
