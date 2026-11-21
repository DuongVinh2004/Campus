"""GET /v1/rooms/availability: every room's busy times for one day in a single call (replaces 34 calls per page load)."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from campus247.application.campus_ops.service import CampusOpsService
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.repositories.sqlite_campus_ops import ICT, CampusOpsStore, OpsError
from campus247.ports.identity import IdentityContext, IdentityRole
from campus247.presentation.campus_ops import create_campus_ops_router, register_ops_errors
from campus247.presentation.identity import IdentityMiddleware

H = timedelta(hours=1)


class Adapter:
    def __init__(self):
        self.contexts = {}

    def resolve_token(self, token):
        if token in self.contexts:
            return self.contexts[token]
        raise ValueError("bad token")


def identity(token, role=IdentityRole.STUDENT, code="LOCAL-STUDENT-001"):
    now = datetime.now(timezone.utc)
    return IdentityContext(generate_uuid7(), "ext:" + token, "test", (role,), token, now, now + H,
                           student_code=code, tenant_id="t", session_id=generate_uuid7())


class CountingStore(CampusOpsStore):
    def __init__(self, path):
        super().__init__(path)
        self.counting = False
        self.queries = []

    def query(self, sql, params=()):
        if self.counting:
            self.queries.append(sql)
        return super().query(sql, params)


@pytest.fixture
def env(tmp_path):
    store = CountingStore(tmp_path / "ops.sqlite3")
    service = CampusOpsService(store)
    adapter = Adapter()
    adapter.contexts["student"] = identity("student")
    app = FastAPI()
    app.add_middleware(IdentityMiddleware, adapter=adapter)
    app.include_router(create_campus_ops_router(service))
    register_ops_errors(app)
    with TestClient(app) as client:
        yield client, service, store


AUTH = {"Authorization": "Bearer student"}


def all_rooms(service):
    return service.list_rooms(building=None, kind=None, min_capacity=None, q=None)["items"]


def busy_days(store):
    rows = store.query("SELECT DISTINCT substr(starts_at,1,10) d FROM ops_schedule WHERE location IS NOT NULL AND kind IN ('CLASS','EXAM') ORDER BY d")
    assert rows, "the seed has timetable rows with a room"
    return [r["d"] for r in rows]


def book_tomorrow(service, room):
    who = identity("booker")
    day = (datetime.now(ICT) + timedelta(days=3)).date().isoformat()
    preview = service.preview_booking(who, {"room_id": room["id"], "date": day, "start": "09:00", "end": "10:30",
                                            "purpose": "Họp nhóm đồ án", "attendees": 2})
    service.confirm_booking(who, preview["preview_id"], "k-batch")
    return day


def test_batch_equals_the_single_room_answer_for_every_room(env):
    client, service, store = env
    rooms = all_rooms(service)
    booked_day = book_tomorrow(service, rooms[0])
    days = {booked_day, *busy_days(store)[:3]}
    for day in days:
        batch = service.availability_many([r["id"] for r in rooms], day)
        assert batch["missing"] == [] and len(batch["items"]) == len(rooms)
        for item in batch["items"]:
            single = service.availability(item["room"]["id"], day)
            assert item["busy"] == single["busy"] and item["room"] == single["room"]
        assert batch["open"] == "07:00" and batch["close"] == "21:00" and batch["limits"] == service.booking_limits()
    assert any(item["busy"] for day in days for item in service.availability_many([r["id"] for r in rooms], day)["items"])


def test_batch_uses_a_constant_number_of_queries(env):
    client, service, store = env
    ids = [r["id"] for r in all_rooms(service)]
    assert len(ids) > 20
    day = busy_days(store)[0]
    store.counting = True
    service.availability_many(ids, day)
    selects = [q for q in store.queries if "ops_room_bookings" in q or "ops_schedule" in q]
    assert len(selects) <= 2, selects
    assert len(store.queries) <= 3


def test_unknown_ids_are_reported_not_fatal(env):
    client, service, store = env
    good = all_rooms(service)[0]["id"]
    reply = client.get("/v1/rooms/availability", params={"date": busy_days(store)[0], "room_ids": f"{good},nope"}, headers=AUTH)
    assert reply.status_code == 200 and reply.headers["cache-control"] == "no-store"
    body = reply.json()
    assert [i["room"]["id"] for i in body["items"]] == [good] and body["missing"] == ["nope"]


@pytest.mark.parametrize("params,code", [
    ({"date": "2026-13-40", "room_ids": "a"}, "INVALID_DATE"),
    ({"date": "2026-11-20", "room_ids": ""}, "INVALID_ROOM_IDS"),
    ({"date": "2026-11-20", "room_ids": "a,a"}, "INVALID_ROOM_IDS"),
    ({"date": "2026-11-20", "room_ids": ",".join(f"r{i}" for i in range(61))}, "INVALID_ROOM_IDS"),
    ({"date": "2026-11-20", "room_ids": "x" * 65}, "INVALID_ROOM_IDS"),
])
def test_bad_input_is_a_422_with_a_code(env, params, code):
    client, _, _ = env
    reply = client.get("/v1/rooms/availability", params=params, headers=AUTH)
    assert reply.status_code == 422 and reply.json()["code"] == code


def test_signed_out_callers_get_401(env):
    client, service, _ = env
    reply = client.get("/v1/rooms/availability", params={"date": "2026-11-20", "room_ids": all_rooms(service)[0]["id"]})
    assert reply.status_code == 401


def test_the_single_room_route_still_works(env):
    client, service, store = env
    room = all_rooms(service)[0]["id"]
    reply = client.get(f"/v1/rooms/{room}/availability", params={"date": busy_days(store)[0]}, headers=AUTH)
    assert reply.status_code == 200 and reply.json()["room"]["id"] == room
