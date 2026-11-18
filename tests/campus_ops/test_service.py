from datetime import datetime, timedelta, timezone

import pytest

from campus247.application.campus_ops.service import CampusOpsService
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.repositories.sqlite_campus_ops import ICT, CampusOpsStore, OpsError
from campus247.ports.identity import IdentityContext, IdentityRole


def identity(role, name="Tester", code=None):
    now = datetime.now(timezone.utc)
    return IdentityContext(generate_uuid7(), "ext:" + name, "test", (role,), name, now, now + timedelta(hours=1),
                           student_code=code if role == IdentityRole.STUDENT else None)


@pytest.fixture()
def svc(tmp_path):
    return CampusOpsService(CampusOpsStore(tmp_path / "ops.sqlite3"))


@pytest.fixture()
def student():
    return identity(IdentityRole.STUDENT, "Sinh viên A", "LOCAL-STUDENT-001")


@pytest.fixture()
def staff():
    return identity(IdentityRole.SUPPORT_OFFICER, "Cán bộ B")


def room(svc, code="H3-205"):
    items = svc.list_rooms(building=None, kind=None, min_capacity=None, q=None)["items"]
    return next(r for r in items if r["room_code"] == code)


def future_day(days=3):
    return (datetime.now(ICT) + timedelta(days=days)).date().isoformat()


def slot(svc, who, start="09:00", end="10:30", code="H3-205", purpose="Họp nhóm đồ án", days=3, attendees=5):
    return svc.preview_booking(who, {"room_id": room(svc, code)["id"], "date": future_day(days), "start": start, "end": end,
                                     "purpose": purpose, "attendees": attendees})


def test_seed_is_idempotent(tmp_path):
    first = CampusOpsStore(tmp_path / "ops.sqlite3")
    count = first.one("SELECT COUNT(*) n FROM ops_rooms")["n"]
    sched = first.one("SELECT COUNT(*) n FROM ops_schedule")["n"]
    again = CampusOpsStore(tmp_path / "ops.sqlite3")
    assert again.one("SELECT COUNT(*) n FROM ops_rooms")["n"] == count > 20
    assert again.one("SELECT COUNT(*) n FROM ops_schedule")["n"] == sched > 80


def test_booking_requires_preview_then_confirm_and_is_idempotent(svc, student):
    preview = slot(svc, student)
    assert preview["can_confirm"] and not preview["problems"]
    booking = svc.confirm_booking(student, preview["preview_id"], "key-1")
    assert booking["status"] == "CONFIRMED" and booking["code"].startswith("BK-") and booking["replayed"] is False
    replay = svc.confirm_booking(student, preview["preview_id"], "key-1")
    assert replay["id"] == booking["id"] and replay["replayed"] is True
    with pytest.raises(OpsError) as e:
        svc.confirm_booking(student, preview["preview_id"], "key-2")
    assert e.value.code == "PREVIEW_USED"
    assert svc.list_notifications(student, False, 10)["unread_count"] == 1


def test_booking_conflict_and_rules(svc, student):
    svc.confirm_booking(student, slot(svc, student)["preview_id"], "a")
    other = identity(IdentityRole.STUDENT, "Sinh viên C", "LOCAL-STUDENT-002")
    clash = slot(svc, other, start="10:00", end="11:00")
    assert not clash["can_confirm"] and clash["conflicts"]
    with pytest.raises(OpsError) as e:
        svc.confirm_booking(other, clash["preview_id"], "b")
    assert e.value.code == "SLOT_TAKEN"
    cases = [({"start": "06:00", "end": "07:30"}, "OUTSIDE_HOURS"), ({"start": "09:00", "end": "09:10"}, "INVALID_DURATION"),
             ({"start": "09:07", "end": "10:07"}, "INVALID_DURATION"), ({"attendees": 999}, "CAPACITY_EXCEEDED"),
             ({"days": -1}, "IN_THE_PAST"), ({"days": 30}, "TOO_FAR"), ({"code": "L2-04"}, "ROOM_UNAVAILABLE")]
    for kwargs, code in cases:
        with pytest.raises(OpsError) as e:
            slot(svc, other, **kwargs)
        assert e.value.code == code


def test_class_occupancy_blocks_booking(svc, student):
    rows = svc.store.query("SELECT starts_at, ends_at FROM ops_schedule WHERE location='H3-301' AND kind='CLASS' ORDER BY starts_at")
    future = next(r for r in rows if r["starts_at"] > (datetime.now(timezone.utc) + timedelta(days=1)).isoformat())
    start = datetime.fromisoformat(future["starts_at"]).astimezone(ICT)
    if start > datetime.now(ICT) + timedelta(days=13):
        pytest.skip("timetable seed ends before the booking horizon")
    preview = svc.preview_booking(student, {"room_id": room(svc, "H3-301")["id"], "date": start.date().isoformat(),
                                            "start": start.strftime("%H:%M"), "end": (start + timedelta(minutes=60)).strftime("%H:%M"),
                                            "purpose": "Thử trùng lịch lớp", "attendees": 3})
    assert preview["conflicts"][0]["type"] == "CLASS" and not preview["can_confirm"]


def test_booking_limit_and_cancel(svc, student):
    ids = []
    for i, start in enumerate(("08:00", "09:00", "10:00")):
        preview = slot(svc, student, start=start, end=f"{start[:2]}:45", code=f"TV-0{i + 1}", attendees=4)
        ids.append(svc.confirm_booking(student, preview["preview_id"], f"k{i}")["id"])
    blocked = slot(svc, student, start="14:00", end="15:00", code="A1-M01", attendees=4)
    assert not blocked["can_confirm"] and "3" in " ".join(blocked["problems"])
    assert svc.cancel_booking(student, ids[0], "đổi kế hoạch")["status"] == "CANCELLED"
    assert slot(svc, student, start="14:00", end="15:00", code="A1-M01", attendees=4)["can_confirm"]
    stranger = identity(IdentityRole.STUDENT, "Khác", "LOCAL-STUDENT-009")
    with pytest.raises(OpsError):
        svc.cancel_booking(stranger, ids[1], "")


def test_schedule_is_owner_scoped_and_personal_events_crud(svc, student):
    frm, to = "2026-09-01T00:00:00+07:00", "2027-01-31T00:00:00+07:00"
    data = svc.list_schedule(student, frm, to)
    assert any(i["kind"] == "EXAM" for i in data["items"]) and any(i["kind"] == "CLASS" for i in data["items"])
    assert all(not i["editable"] for i in data["items"])
    stranger = identity(IdentityRole.STUDENT, "Khác", "LOCAL-STUDENT-009")
    assert svc.list_schedule(stranger, frm, to)["items"] == []
    event = svc.create_event(student, {"title": "Nhóm đồ án", "starts_at": "2026-11-20T19:00:00+07:00",
                                       "ends_at": "2026-11-20T21:00:00+07:00", "location": "TV-01"})
    assert event["editable"] and event["kind"] == "PERSONAL"
    changed = svc.update_event(student, event["id"], {"title": "Nhóm đồ án (đổi)", "starts_at": "2026-11-20T20:00:00+07:00",
                                                      "ends_at": "2026-11-20T21:00:00+07:00"})
    assert changed["course_name"] == "Nhóm đồ án (đổi)"
    seeded = next(i for i in data["items"] if i["kind"] == "CLASS")
    with pytest.raises(OpsError) as e:
        svc.update_event(student, seeded["id"], {"title": "x", "starts_at": "2026-11-20T20:00:00+07:00", "ends_at": "2026-11-20T21:00:00+07:00"})
    assert e.value.code == "EVENT_READ_ONLY"
    with pytest.raises(OpsError):
        svc.delete_event(stranger, event["id"])
    svc.delete_event(student, event["id"])
    assert all(i["id"] != event["id"] for i in svc.list_schedule(student, frm, to)["items"])


def test_ticket_lifecycle_between_student_and_staff(svc, student, staff):
    body = {"service_kind": "STUDENT_CERTIFICATE", "title": "Giấy xác nhận", "summary": "Xin giấy xác nhận để làm hồ sơ vay vốn.",
            "fields": {"purpose": "Vay vốn"}}
    ticket = svc.submit_ticket(student, body, "t-1")
    assert ticket["status"] == "SUBMITTED" and ticket["code"].startswith("HS-")
    assert svc.submit_ticket(student, body, "t-1")["replayed"] is True
    with pytest.raises(OpsError) as e:
        svc.staff_queue(student, None, False, None)
    assert e.value.code == "FORBIDDEN"
    queue = svc.staff_queue(staff, "OPEN", False, None)
    assert any(item["id"] == ticket["id"] for item in queue["items"]) and queue["counts"]["SUBMITTED"] >= 4
    assert any(item["overdue"] for item in queue["items"])  # one synthetic seed ticket is past its due date
    assert svc.staff_claim(staff, ticket["id"])["status"] == "IN_REVIEW"
    other_staff = identity(IdentityRole.SUPPORT_OFFICER, "Cán bộ khác")
    with pytest.raises(OpsError) as e:
        svc.staff_claim(other_staff, ticket["id"])
    assert e.value.code == "ALREADY_CLAIMED"
    svc.staff_note(staff, ticket["id"], "Cần đối chiếu mã sinh viên.")
    assert svc.staff_reply(staff, ticket["id"], "Bạn bổ sung ảnh thẻ sinh viên.", "NEED_INFO")["status"] == "NEED_INFO"
    seen = svc.ticket_detail(student, ticket["id"])
    assert all(ev["visibility"] == "PUBLIC" for ev in seen["events"]) and not any(ev["kind"] == "NOTE" for ev in seen["events"])
    assert svc.student_reply(student, ticket["id"], "Em đã bổ sung.")["status"] == "IN_REVIEW"
    with pytest.raises(OpsError) as e:
        svc.staff_set_status(staff, ticket["id"], "RESOLVED", "")
    assert e.value.code == "REASON_REQUIRED"
    done = svc.staff_set_status(staff, ticket["id"], "RESOLVED", "Đã cấp giấy xác nhận, nhận tại Phòng Đào tạo.")
    assert done["status"] == "RESOLVED" and done["allowed_actions"] == ["note"]
    with pytest.raises(OpsError):
        svc.student_reply(student, ticket["id"], "thêm")
    stranger = identity(IdentityRole.STUDENT, "Khác", "LOCAL-STUDENT-009")
    with pytest.raises(OpsError) as e:
        svc.ticket_detail(stranger, ticket["id"])
    assert e.value.code == "TICKET_NOT_FOUND"
    assert svc.list_notifications(student, False, 50)["unread_count"] >= 4


def test_student_cancel_and_admin_overview(svc, student):
    t = svc.submit_ticket(student, {"service_kind": "GENERAL_SUPPORT", "summary": "Cần hỗ trợ đăng ký học phần muộn."}, "c-1")
    assert svc.cancel_ticket(student, t["id"], "đã tự giải quyết")["status"] == "CANCELLED"
    admin = identity(IdentityRole.KNOWLEDGE_ADMIN, "Quản trị")
    overview = svc.admin_overview(admin)
    assert overview["tickets"]["by_status"]["CANCELLED"] == 1 and overview["recent_audit"]
    with pytest.raises(OpsError):
        svc.admin_overview(student)


def _submitted(svc, student, key="q-1"):
    return svc.submit_ticket(student, {"service_kind": "GENERAL_SUPPORT", "summary": "Cần hỗ trợ đăng ký học phần muộn."}, key)


def test_a_staff_reply_without_a_chosen_status_starts_the_review_instead_of_asking_for_information(svc, student, staff):
    ticket = _submitted(svc, student)
    reply = svc.staff_reply(staff, ticket["id"], "Đã nhận hồ sơ, đang kiểm tra.", None)
    assert reply["status"] == "IN_REVIEW" and reply["assignee_display"] == "Cán bộ B"


def test_the_claim_action_disappears_once_the_viewer_is_the_assignee(svc, student, staff):
    ticket = _submitted(svc, student, "q-2")
    other = identity(IdentityRole.SUPPORT_OFFICER, "Cán bộ khác")
    assert "claim" in svc.ticket_detail(staff, ticket["id"])["allowed_actions"]
    svc.staff_claim(staff, ticket["id"])
    assert "claim" not in svc.ticket_detail(staff, ticket["id"])["allowed_actions"]
    assert "claim" in svc.ticket_detail(other, ticket["id"])["allowed_actions"]


def test_events_say_who_wrote_them_and_use_vietnamese_status_labels(svc, student, staff):
    ticket = _submitted(svc, student, "q-3")
    svc.staff_reply(staff, ticket["id"], "Bạn bổ sung ảnh thẻ.", "NEED_INFO")
    for viewer in (student, staff):
        events = svc.ticket_detail(viewer, ticket["id"])["events"]
        reply = next(e for e in events if e["kind"] == "STAFF_REPLY")
        assert reply["actor_kind"] == "staff" and reply["actor_role_label"] == "Cán bộ Một cửa"
        assert reply["is_mine"] is (viewer is staff)
        created = next(e for e in events if e["kind"] == "CREATED")
        assert created["actor_kind"] == "student" and created["is_mine"] is (viewer is student)
        change = next(e for e in events if e["kind"] == "STATUS_CHANGE")
        assert "SUBMITTED" not in change["body"] and "NEED_INFO" not in change["body"]
        assert "Cần bổ sung thông tin" in change["body"]


def test_the_operations_log_shows_names_and_business_codes_instead_of_ids(svc, student, staff):
    ticket = _submitted(svc, student, "q-audit")
    svc.staff_reply(staff, ticket["id"], "Đã nhận.", None)
    admin = identity(IdentityRole.SYSTEM_ADMIN, "Quản trị A")
    rows = svc.admin_overview(admin)["recent_audit"]
    submit = next(r for r in rows if r["action"] == "ticket.submit")
    assert submit["actor"] == "Sinh viên A" and submit["resource"] == ticket["code"]
    reply = next(r for r in rows if r["action"] == "ticket.staff_reply")
    assert reply["actor"] == "Cán bộ B"


def test_the_operations_log_names_the_kind_of_thing_when_it_has_no_business_code(svc, student):
    svc.create_event(student, {"title": "Ôn thi", "starts_at": "2026-12-20T20:00:00+07:00", "ends_at": "2026-12-20T21:00:00+07:00"})
    admin = identity(IdentityRole.SYSTEM_ADMIN, "Quản trị A")
    row = next(r for r in svc.admin_overview(admin)["recent_audit"] if r["action"] == "schedule.create")
    assert row["resource"] == "Sự kiện lịch cá nhân"
    assert row["actor"].startswith("Tài khoản …") and len(row["actor"]) < 20  # no name is recorded for someone who only used the calendar
