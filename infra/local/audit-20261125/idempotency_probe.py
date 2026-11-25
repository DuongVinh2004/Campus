"""Live idempotency/confirmation probe: room booking preview -> confirm twice with the same key -> cancel (demo account sv.demo05).

Also: confirm without a preview id, confirm another student's preview, cancel another student's booking. Prints no secret.
The booking it makes is cancelled again through the app at the end; purpose carries the AUDIT-20261125 tag.
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_http import call, directory, login  # noqa: E402  (re-signs the authz accounts; read-only there)

_, _, a, _ = login(directory["sv.demo05"])
_, _, b, _ = login(directory["sv.demo06"])
out = {}
rooms = call("GET", "/v1/rooms", a)[1]
room_list = rooms.get("items", rooms) if isinstance(rooms, dict) else rooms
day = date.today() + timedelta(days=2)
while day.weekday() >= 5:
    day += timedelta(days=1)
preview = None
for room in room_list[:8]:
    for start, end in (("19:00", "20:00"), ("18:00", "19:00"), ("07:00", "08:00")):
        s, p, _ = call("POST", "/v1/rooms/book/preview", a, body={"room_id": room["id"], "date": day.isoformat(), "start": start, "end": end,
                                                               "purpose": "AUDIT-20261125 kiểm tra idempotency", "attendees": 1})
        if s in (200, 201):
            preview = p
            break
    if preview:
        break
out["preview_status"] = "ok" if preview else "none"
if preview:
    pid = preview.get("preview_id") or preview.get("id")
    key = "audit-" + uuid.uuid4().hex
    s1, c1, _ = call("POST", "/v1/rooms/book", a, body={"preview_id": pid, "idempotency_key": key})
    s2, c2, _ = call("POST", "/v1/rooms/book", a, body={"preview_id": pid, "idempotency_key": key})
    booking = (c1 or {}).get("booking", c1) or {}
    booking2 = (c2 or {}).get("booking", c2) or {}
    out["confirm_1"], out["confirm_2_same_key"] = s1, s2
    out["same_booking_returned"] = booking.get("id") == booking2.get("id") and bool(booking.get("id"))
    out["confirm_without_key"] = call("POST", "/v1/rooms/book", a, body={"preview_id": pid})[0]
    out["other_student_confirms_preview"] = call("POST", "/v1/rooms/book", b, body={"preview_id": pid, "idempotency_key": "x-" + key})[0]
    bid = booking.get("id")
    if bid:
        out["other_student_cancels"] = call("POST", f"/v1/rooms/bookings/{bid}/cancel", b, body={"reason": "audit"})[0]
        out["owner_cancels"] = call("POST", f"/v1/rooms/bookings/{bid}/cancel", a, body={"reason": "AUDIT-20261125 dọn dữ liệu"})[0]
        out["booking_code"] = booking.get("code")
    audit = call("GET", "/v1/admin/overview", login(json.loads((Path(__file__).resolve().parents[1] / "knowledge-platform-20261023/owner-credentials.json").read_text(encoding="utf-8")))[2])[1]
    text = json.dumps(audit, ensure_ascii=False)
    out["audit_mentions_booking"] = bool(booking.get("code")) and booking.get("code") in text
out["confirm_unknown_preview"] = call("POST", "/v1/rooms/book", a, body={"preview_id": "khong-ton-tai", "idempotency_key": "k1"})[0]
print(json.dumps(out, ensure_ascii=False, indent=1))
