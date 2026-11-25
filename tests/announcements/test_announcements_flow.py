"""F1: sending, permissions, scheduling, expiry, withdrawal, acknowledgement, durability and statistics."""
from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import pytest

from campus247.application.announcements.service import AnnouncementError
from campus247.ports.identity import IdentityRole
sys.path.insert(0, str(Path(__file__).parent))
from ann_helpers import NOW, demo_accounts, draft, make_service, person, sid

OFFICER = person(sid(1000), IdentityRole.SUPPORT_OFFICER)
OFFICER2 = person(sid(1001), IdentityRole.SUPPORT_OFFICER)
ADMIN = person(sid(2000), IdentityRole.KNOWLEDGE_ADMIN)
LECTURER = person(sid(3000), IdentityRole.LECTURER)


def student(n):
    return person(sid(n), IdentityRole.STUDENT)


def code_of(call):
    with pytest.raises(AnnouncementError) as caught:
        call()
    return caught.value.code


def send(svc, author, data, *, key="k"):
    created = svc.create_draft(author, data)
    preview = svc.publish_preview(author, created["id"])
    result = svc.publish_confirm(author, preview["preview_id"], preview["confirmation_token"], key + created["id"])
    return created["id"], result


def count(store, sql, *args):
    return store.one(sql, args)["n"]


def test_sends_to_exactly_the_class_and_others_get_404(tmp_path):
    svc, store, _ = make_service(tmp_path)
    ann, result = send(svc, OFFICER, draft(audience={"groups": [{"class_codes": ["66IT1"]}]}))
    assert result["status"] == "PUBLISHED"
    inbox = [s for s in range(1, 41) if svc.mine(student(s))["items"]]
    expected = [a["subject_id"] for a in demo_accounts() if a.get("class_code") == "66IT1"]
    assert [sid(s) for s in inbox] == expected and len(expected) == 5
    assert svc.get(student(1), ann)["title"] == "Lịch nộp học phí học kỳ 2"
    other = next(s for s in range(1, 41) if sid(s) not in expected)
    assert code_of(lambda: svc.get(student(other), ann)) == "ANNOUNCEMENT_NOT_FOUND"
    assert count(store, "SELECT COUNT(*) n FROM ops_notifications WHERE kind='ANNOUNCEMENT'") == 5


def test_permissions_matrix(tmp_path):
    svc, _, _ = make_service(tmp_path, lecturers=lambda offering: {sid(3000)} if offering == "off-1" else set(),
                             offering_members=lambda offering: {sid(1), sid(2)} if offering == "off-1" else set())
    assert code_of(lambda: svc.create_draft(student(1), draft())) == "FORBIDDEN"
    assert code_of(lambda: svc.create_draft(LECTURER, draft(audience={"groups": [{"roles": ["STUDENT"]}]}))) == "ANNOUNCEMENT_FORBIDDEN_AUDIENCE"
    assert code_of(lambda: svc.create_draft(LECTURER, draft(audience={"groups": [{"offering_ids": ["off-2"]}]}))) == "ANNOUNCEMENT_FORBIDDEN_AUDIENCE"
    ok = svc.create_draft(LECTURER, draft(audience={"groups": [{"offering_ids": ["off-1"]}]}))
    assert svc.publish_preview(LECTURER, ok["id"])["summary"]["total"] == 2
    assert svc.audience_preview(LECTURER, ok["id"])["total"] == 2
    assert code_of(lambda: svc.stats(student(1), ok["id"])) == "ANNOUNCEMENT_NOT_FOUND"
    assert code_of(lambda: svc.authored(student(1))) == "FORBIDDEN"


def test_validation_codes(tmp_path):
    svc, _, _ = make_service(tmp_path)

    def errors(**over):
        with pytest.raises(AnnouncementError) as caught:
            svc.create_draft(OFFICER, draft(**over))
        assert caught.value.status == 422
        return {(e["field"], e["code"]) for e in caught.value.errors}

    assert ("title", "TITLE_LENGTH") in errors(title="abc")
    assert ("expires_at", "EXPIRY_RANGE") in errors(expires_at=(NOW + timedelta(days=400)).isoformat())
    assert ("expires_at", "EXPIRY_RANGE") in errors(expires_at=(NOW - timedelta(days=1)).isoformat())
    assert ("ack_deadline", "ACK_DEADLINE") in errors(requires_ack=True)
    assert ("links[0]", "LINK_SCHEME") in errors(links=[{"label": "x", "url": "http://insecure.example"}])
    assert ("audience", "AUDIENCE_EMPTY") in errors(audience={"groups": []})
    assert ("audience.groups[0].roles", "AUDIENCE_ROLE_UNKNOWN") in errors(audience={"groups": [{"roles": ["KING"]}]})
    assert ("audience.include_guests", "GUESTS_NEED_EVERYONE_GROUP") in errors(audience={"groups": [{"roles": ["STUDENT"]}], "include_guests": True})
    too_many = {"groups": [{"subjects": [sid(i) for i in range(501)]}]}
    assert ("audience.groups[0].subjects", "AUDIENCE_TOO_MANY_SUBJECTS") in errors(audience=too_many)


def test_second_approval_rule_and_same_person_block(tmp_path):
    flag = {"on": True}
    svc, _, _ = make_service(tmp_path, enabled=lambda key: flag["on"] if key == "announcements.second_approval" else True)
    everyone = draft(audience={"groups": [{}], "include_guests": False})
    created = svc.create_draft(OFFICER, everyone)
    preview = svc.publish_preview(OFFICER, created["id"])
    assert preview["summary"]["needs_approval"] is True
    assert svc.publish_confirm(OFFICER, preview["preview_id"], preview["confirmation_token"], "i1")["status"] == "PENDING_APPROVAL"
    row_version = svc._row(created["id"])["row_version"]
    assert code_of(lambda: svc.approve(OFFICER, created["id"], "tự duyệt thử nghiệm", row_version)) == "SAME_PERSON_APPROVAL"
    assert code_of(lambda: svc.approve(OFFICER2, created["id"], "ngắn", row_version)) == "ANNOUNCEMENT_INVALID"
    assert svc.approvals(OFFICER2)["items"][0]["id"] == created["id"]
    assert svc.approve(OFFICER2, created["id"], "Đã kiểm tra nội dung", row_version)["status"] == "PUBLISHED"
    other = svc.create_draft(OFFICER, everyone)
    pv = svc.publish_preview(OFFICER, other["id"])
    svc.publish_confirm(OFFICER, pv["preview_id"], pv["confirmation_token"], "i2")
    assert svc.approve(OFFICER2, other["id"], "Cần sửa lại đối tượng", svc._row(other["id"])["row_version"], approve=False)["status"] == "DRAFT"
    flag["on"] = False
    third = svc.create_draft(OFFICER, everyone)
    assert svc.publish_preview(OFFICER, third["id"])["summary"]["needs_approval"] is False


def test_preview_token_expiry_replay_and_idempotency(tmp_path):
    svc, store, clock = make_service(tmp_path)
    created = svc.create_draft(OFFICER, draft())
    preview = svc.publish_preview(OFFICER, created["id"])
    assert code_of(lambda: svc.publish_confirm(OFFICER, preview["preview_id"], "bad", "a")) == "CONFIRMATION_REQUIRED"
    first = svc.publish_confirm(OFFICER, preview["preview_id"], preview["confirmation_token"], "a")
    again = svc.publish_confirm(OFFICER, preview["preview_id"], preview["confirmation_token"], "a")
    assert again["replayed"] and first["id"] == again["id"]
    assert count(store, "SELECT COUNT(*) n FROM ann_deliveries") == 40
    assert code_of(lambda: svc.publish_confirm(OFFICER, preview["preview_id"], preview["confirmation_token"], "b")) == "PREVIEW_EXPIRED"
    late = svc.create_draft(OFFICER, draft(title="Thông báo thứ hai"))
    p2 = svc.publish_preview(OFFICER, late["id"])
    clock.now += timedelta(minutes=11)
    assert code_of(lambda: svc.publish_confirm(OFFICER, p2["preview_id"], p2["confirmation_token"], "c")) == "PREVIEW_EXPIRED"


def test_scheduled_notice_goes_out_within_60_seconds_of_publish_at(tmp_path):
    svc, _, clock = make_service(tmp_path)
    at = NOW + timedelta(hours=2)
    created = svc.create_draft(OFFICER, draft(publish_at=at.isoformat(), expires_at=(at + timedelta(days=3)).isoformat()))
    pv = svc.publish_preview(OFFICER, created["id"])
    assert svc.publish_confirm(OFFICER, pv["preview_id"], pv["confirmation_token"], "s")["status"] == "SCHEDULED"
    clock.now = at - timedelta(seconds=1)
    assert svc.run_publisher_once() == 0 and svc.mine(student(1))["items"] == []
    clock.now = at + timedelta(seconds=30)  # the job polls every 30 s, so this is the first tick after publish_at
    assert svc.run_publisher_once() == 1
    assert svc._row(created["id"])["status"] == "PUBLISHED" and len(svc.mine(student(1))["items"]) == 1
    assert (clock.now - at).total_seconds() <= 60
    clock.now = NOW
    again = svc.create_draft(OFFICER, draft(title="Hẹn rồi hủy hẹn", publish_at=at.isoformat(), expires_at=(at + timedelta(days=3)).isoformat()))
    p = svc.publish_preview(OFFICER, again["id"])
    svc.publish_confirm(OFFICER, p["preview_id"], p["confirmation_token"], "u")
    assert svc.unschedule(OFFICER, again["id"])["status"] == "DRAFT"


def test_expiry_and_withdrawal_remove_it_and_revoke_the_knowledge_copy(tmp_path):
    class FakeKnowledge:
        def __init__(self):
            self.revoked = []

        def publish(self, public, row):
            return "ver-" + row["code"]

        def revoke(self, version, reason):
            self.revoked.append((version, reason))

    sync = FakeKnowledge()
    svc, _, clock = make_service(tmp_path, knowledge_sync=sync)
    open_to_all = draft(audience={"groups": [{}], "include_guests": True})
    a, _ = send(svc, OFFICER, open_to_all, key="a")
    b, _ = send(svc, OFFICER, {**open_to_all, "title": "Thông báo thứ hai về học phí"}, key="b")
    c, _ = send(svc, OFFICER, draft(title="Chỉ cho sinh viên, không đưa vào kho"), key="c")
    assert svc._row(a)["knowledge_version_id"] and not svc._row(c)["knowledge_version_id"]
    assert len(svc.public()["items"]) == 2
    wp = svc.withdraw_preview(OFFICER, b, "Gửi nhầm đối tượng")
    svc.withdraw_confirm(OFFICER, wp["preview_id"], wp["confirmation_token"], "w")
    assert sync.revoked == [(svc._row(b)["knowledge_version_id"], "withdrawn")]
    assert code_of(lambda: svc.get(student(1), b)) == "ANNOUNCEMENT_NOT_FOUND"
    clock.now = NOW + timedelta(days=11)
    assert svc.run_expiry_once() == 2
    assert (svc._row(a)["knowledge_version_id"], "expired") in sync.revoked
    assert svc.mine(student(1))["items"] == [] and len(svc.mine(student(1), filter="all")["items"]) == 2
    assert svc.public()["items"] == []


def test_ack_flow_revision_and_reminders(tmp_path):
    svc, store, clock = make_service(tmp_path)
    ann, _ = send(svc, OFFICER, draft(requires_ack=True, ack_deadline=(NOW + timedelta(days=2)).isoformat()))
    detail = svc.get(student(1), ann)
    assert detail["needs_ack"] and not detail["acked"]
    assert svc.ack(student(1), ann)["acked"] and svc.ack(student(1), ann)["acked"]
    assert not svc.get(student(1), ann)["needs_ack"]
    assert len(svc.pending_acks(OFFICER, ann)["items"]) == 39
    assert count(store, "SELECT COUNT(*) n FROM ops_audit WHERE action='ANNOUNCEMENT_PENDING_ACKS_VIEWED'") == 1
    rp = svc.revision_preview(OFFICER, ann, {"body": "Hạn nộp được dời sang ngày 5/1.", "change_note": "Dời hạn nộp", "material": True})
    svc.revision_confirm(OFFICER, rp["preview_id"], rp["confirmation_token"], "r")
    again = svc.get(student(1), ann)
    assert again["revision"] == 2 and again["needs_ack"] and again["revisions"][0]["material"] == 1
    assert count(store, "SELECT COUNT(*) n FROM ops_notifications WHERE title LIKE 'Đã cập nhật%'") == 40
    assert code_of(lambda: svc.revision_preview(OFFICER, ann, {"audience": {}, "change_note": "đổi đối tượng"})) == "ANNOUNCEMENT_INVALID"
    clock.now = NOW + timedelta(days=1, hours=1)
    assert svc.run_ack_reminders_once() == 39
    assert svc.run_ack_reminders_once() == 0


def test_statistics_merge_groups_smaller_than_five(tmp_path):
    svc, _, _ = make_service(tmp_path)
    ann, _ = send(svc, OFFICER, draft(audience={"groups": [{"roles": ["STUDENT"]}, {"subjects": [sid(1000)]}]}))
    for n in range(1, 8):
        svc.get(student(n), ann)
    stats = svc.stats(OFFICER, ann)
    assert stats["delivered"] == 41 and stats["read"] == 7
    assert {row["key"] for row in stats["by_faculty"]} <= {"CNTT", "XD", "KT", "KX", "khác"}
    assert all(row["delivered"] >= 5 or row["key"] == "khác" for row in stats["by_faculty"])
    pv = svc.audience_preview_spec(OFFICER, {"groups": [{"class_codes": ["66IT1"]}, {"subjects": [sid(1000)]}]})
    assert pv["total"] == 6 and all(row["n"] >= 5 or row["key"] == "khác" for row in pv["by_faculty"] + pv["by_cohort"])


def test_reconcile_adds_new_people_and_never_removes(tmp_path):
    accounts = demo_accounts()
    svc, store, _ = make_service(tmp_path, accounts)
    send(svc, OFFICER, draft(audience={"groups": [{"class_codes": ["66IT1"]}]}))
    assert count(store, "SELECT COUNT(*) n FROM ann_deliveries") == 5
    accounts.append({"role": "STUDENT", "subject_id": sid(500), "faculty_code": "CNTT", "class_code": "66IT1"})
    accounts[:] = [a for a in accounts if a["subject_id"] != sid(1)]
    assert svc.run_reconcile_once() == 1
    assert count(store, "SELECT COUNT(*) n FROM ann_deliveries") == 6
    assert svc.run_reconcile_once() == 0


@pytest.mark.parametrize("fail_at", list(range(0, 41, 4)))
def test_crash_at_any_point_leaves_one_delivery_and_one_notice_each(tmp_path, fail_at, monkeypatch):
    svc, store, _ = make_service(tmp_path)
    created = svc.create_draft(OFFICER, draft())
    preview = svc.publish_preview(OFFICER, created["id"])
    calls = {"n": 0}
    original = type(store).notify

    def flaky(c, recipient, kind, title, body, link=""):
        calls["n"] += 1
        if calls["n"] == fail_at + 1:
            raise RuntimeError("simulated crash")
        return original(c, recipient, kind, title, body, link)

    monkeypatch.setattr(type(store), "notify", staticmethod(flaky))
    try:
        svc.publish_confirm(OFFICER, preview["preview_id"], preview["confirmation_token"], "k")
    except RuntimeError:
        pass
    monkeypatch.undo()
    svc._snapshots.clear()  # a restarted process remembers nothing
    if svc._row(created["id"])["status"] == "DRAFT":
        preview = svc.publish_preview(OFFICER, created["id"])
        svc.publish_confirm(OFFICER, preview["preview_id"], preview["confirmation_token"], "k2")
    for _ in range(100):
        if svc.publish_step(created["id"], batch=7) != "PUBLISHING":
            break
    assert svc._row(created["id"])["status"] == "PUBLISHED"
    assert count(store, "SELECT COUNT(*) n FROM ann_deliveries") == 40
    assert count(store, "SELECT COUNT(*) n FROM ops_notifications WHERE kind='ANNOUNCEMENT'") == 40
    assert count(store, "SELECT COUNT(DISTINCT recipient_subject_id) n FROM ops_notifications WHERE kind='ANNOUNCEMENT'") == 40


def test_batch_step_resumes_from_cursor_after_a_failure_between_batches(tmp_path, monkeypatch):
    svc, store, _ = make_service(tmp_path)
    created = svc.create_draft(OFFICER, draft())
    with store.tx() as c:
        c.execute("UPDATE ann_announcements SET status='PUBLISHING' WHERE id=?", (created["id"],))
    original, calls = type(store).notify, {"n": 0}

    def flaky(c, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 12:
            raise RuntimeError("crash")
        return original(c, *args, **kwargs)

    monkeypatch.setattr(type(store), "notify", staticmethod(flaky))
    assert svc.publish_step(created["id"], batch=10) == "PUBLISHING"
    with pytest.raises(RuntimeError):
        svc.publish_step(created["id"], batch=10)
    assert count(store, "SELECT COUNT(*) n FROM ann_deliveries") == 10
    svc._snapshots.clear()
    while svc.publish_step(created["id"], batch=10) == "PUBLISHING":
        pass
    assert count(store, "SELECT COUNT(*) n FROM ann_deliveries") == 40
    assert count(store, "SELECT COUNT(*) n FROM ops_notifications WHERE kind='ANNOUNCEMENT'") == 40


def test_rate_limits(tmp_path):
    svc, _, _ = make_service(tmp_path)
    for i in range(3):
        svc.create_draft(OFFICER, draft(title=f"Thông báo khẩn số {i}", priority="URGENT"))
    assert code_of(lambda: svc.create_draft(OFFICER, draft(title="Thông báo khẩn số 4", priority="URGENT"))) == "ANNOUNCEMENT_RATE"
    for i in range(17):
        svc.create_draft(OFFICER, draft(title=f"Thông báo thường số {i}"))
    assert code_of(lambda: svc.create_draft(OFFICER, draft(title="Thông báo thường thứ 21"))) == "ANNOUNCEMENT_RATE"


def test_a_sent_notice_stays_readable_when_the_publish_flag_is_off(tmp_path):
    svc, _, _ = make_service(tmp_path, enabled=lambda key: key != "announcements.publish")
    ann, _ = send(svc, OFFICER, draft())
    assert svc.get(student(1), ann)["status"] == "PUBLISHED"
