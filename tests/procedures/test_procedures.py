"""F5: playbooks load against the real regulation, the state machine, preview->confirm->ticket, extraction checks, HTTP."""
from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "announcements"))
from ann_helpers import NOW, Clock, person, sid  # noqa: E402

from campus247.application.campus_ops.service import SERVICE_KINDS, CampusOpsService  # noqa: E402
from campus247.application.procedures.service import ProcedureService  # noqa: E402
from campus247.domain.procedures import StateError, advance, load_procedures, run_checks, validate_fields, verbatim_extraction  # noqa: E402
from campus247.infrastructure.knowledge.rag_v2_units import RagV2Units  # noqa: E402
from campus247.infrastructure.repositories.sqlite_campus_ops import CampusOpsStore  # noqa: E402
from campus247.ports.campus_ops import OpsError  # noqa: E402
from campus247.ports.identity import IdentityRole  # noqa: E402
from campus247.presentation.campus_ops import register_ops_errors  # noqa: E402
from campus247.presentation.procedures import create_procedures_router, register_procedure_errors  # noqa: E402

UNITS = RagV2Units(ROOT / "data" / "rag_v2_index")
PROCS = load_procedures(ROOT / "config" / "procedures", service_kinds=set(SERVICE_KINDS), unit_text=UNITS.text)


def student(n=1):
    p = person(sid(n), IdentityRole.STUDENT)
    return p


@pytest.fixture()
def svc(tmp_path):
    store = CampusOpsStore(tmp_path / "ops.sqlite3")
    store.seed()
    ops = CampusOpsService(store)
    clock = Clock()
    return ProcedureService(store, ops, PROCS, clock=clock, signing_key="k"), store, clock


def test_playbooks_validate_against_the_real_units():
    assert set(PROCS) == {"student-certificate", "grade-appeal", "leave-of-absence"}
    assert PROCS["leave-of-absence"].checks and PROCS["leave-of-absence"].sources


def test_bad_playbook_is_rejected(tmp_path):
    (tmp_path / "x.toml").write_text('id="x"\nversion=1\ntitle="t"\nservice_kind="NOPE"\n', encoding="utf-8")
    with pytest.raises(ValueError):
        load_procedures(tmp_path, service_kinds=set(SERVICE_KINDS))
    (tmp_path / "x.toml").write_text('id="x"\nversion=1\ntitle="t"\nservice_kind="GENERAL_SUPPORT"\n[[fields]]\nkey="a"\nlabel="A"\ntype="string"\n'
        '[[checks]]\nid="c"\nwhen={field="a",op="=",value="1"}\nrequire={field="a",op=">=",value=1}\nmessage="m"\nsource={unit_id="42ef05f36314f96d",quote="không có trong điều khoản"}\n', encoding="utf-8")
    with pytest.raises(ValueError):
        load_procedures(tmp_path, service_kinds=set(SERVICE_KINDS), unit_text=UNITS.text)


def test_state_machine_edges():
    assert advance("COLLECTING", "READY_FOR_PREVIEW") == "READY_FOR_PREVIEW"
    for bad in (("SUBMITTED", "CANCELLED"), ("CANCELLED", "COLLECTING"), ("COLLECTING", "SUBMITTED"), ("STARTED", "PREVIEWED")):
        with pytest.raises(StateError):
            advance(*bad)


def test_check_blocks_only_when_known_and_failing():
    p = PROCS["leave-of-absence"]
    assert run_checks(p, {"reason_kind": "PERSONAL", "completed_semesters": 0})[0]["source"]["unit_id"] == "42ef05f36314f96d"
    assert run_checks(p, {"reason_kind": "PERSONAL", "completed_semesters": 1}) == []
    assert run_checks(p, {"reason_kind": "MEDICAL", "completed_semesters": 0}) == []
    assert run_checks(p, {"reason_kind": "PERSONAL"}) == []  # unknown: ask, do not block


def test_extraction_keeps_only_values_found_in_the_sentence():
    p = PROCS["grade-appeal"]
    text = "Em muốn phúc khảo môn MAT101 vì điểm thi thấp bất thường"
    kept, dropped = verbatim_extraction(text, {"course_code": "MAT101", "reason": "điểm thi bị sai hoàn toàn", "semester": "HK1"}, p)
    assert list(kept) == ["course_code"] and kept["course_code"]["span"] == [text.casefold().find("mat101"), text.casefold().find("mat101") + 6]
    assert {d["field"]: d["code"] for d in dropped} == {"reason": "NOT_IN_TEXT", "semester": "NOT_EXTRACTABLE"}
    clean, errors = validate_fields(p, {"course_code": "!!", "reason": "ngắn"})
    assert {(e["field"], e["code"]) for e in errors} == {("course_code", "BAD_FORMAT"), ("reason", "TOO_SHORT")}


def test_full_run_creates_exactly_one_ticket_after_explicit_confirmation(svc):
    s, store, clock = svc
    me = student(1)
    base = store.query("SELECT COUNT(*) n FROM ops_tickets")[0]["n"]
    run = s.start(me, "student-certificate")
    assert run["state"] == "STARTED" and run["next_step"] == "fill"
    with pytest.raises(OpsError) as e:
        s.submit_preview(me, run["id"])
    assert e.value.code == "PROCEDURE_STATE"
    run = s.put_fields(me, run["id"], {"purpose": "Vay vốn"}, run["row_version"])
    assert run["state"] == "READY_FOR_PREVIEW" and run["fields"] == {"purpose": "Vay vốn"}
    with pytest.raises(OpsError) as e:  # stale row_version
        s.put_fields(me, run["id"], {"copies": 2}, 1)
    assert e.value.code == "PROCEDURE_CONFLICT"
    pv = s.submit_preview(me, run["id"])
    assert pv["ticket_preview"]["title"] == "Giấy xác nhận sinh viên — Vay vốn" and "Số bản: 1" in pv["ticket_preview"]["summary"]
    assert store.query("SELECT COUNT(*) n FROM ops_tickets")[0]["n"] == base  # nothing written yet
    with pytest.raises(OpsError) as e:
        s.submit_confirm(me, pv["preview_id"], "", "k1")
    assert e.value.code == "CONFIRMATION_REQUIRED"
    with pytest.raises(OpsError) as e:
        s.submit_confirm(student(2), pv["preview_id"], pv["confirmation_token"], "k1")  # another student cannot use it
    assert e.value.code == "PREVIEW_EXPIRED"
    done = s.submit_confirm(me, pv["preview_id"], pv["confirmation_token"], "k1")
    assert done["state"] == "SUBMITTED" and done["ticket"]["id"]
    again = s.submit_confirm(me, pv["preview_id"], pv["confirmation_token"], "k2")
    assert again["replayed"] is True
    assert store.query("SELECT COUNT(*) n FROM ops_tickets")[0]["n"] == base + 1
    with pytest.raises(OpsError) as e:
        s.put_fields(me, run["id"], {"copies": 3}, done["row_version"])
    assert e.value.code == "PROCEDURE_STATE"
    with pytest.raises(OpsError):
        s.cancel(me, run["id"])
    actions = [r["action"] for r in store.query("SELECT action FROM ops_audit WHERE action LIKE 'PROCEDURE_%' ORDER BY id")]
    assert actions[0] == "PROCEDURE_STARTED" and actions[-1] == "PROCEDURE_SUBMITTED" and "PROCEDURE_PREVIEWED" in actions


def test_blocked_run_cannot_be_previewed_until_fixed(svc):
    s, _, _ = svc
    me = student(1)
    run = s.start(me, "leave-of-absence")
    run = s.put_fields(me, run["id"], {"reason_kind": "PERSONAL", "completed_semesters": 0, "duration_semesters": 1, "detail": "Cần nghỉ để chăm sóc gia đình"}, run["row_version"])
    assert run["state"] == "BLOCKED" and run["blocked"][0]["check"] == "personal-needs-one-semester"
    with pytest.raises(OpsError) as e:
        s.submit_preview(me, run["id"])
    assert e.value.code == "PROCEDURE_NOT_ELIGIBLE" and e.value.errors
    run = s.put_fields(me, run["id"], {"completed_semesters": 2}, run["row_version"])
    assert run["state"] == "READY_FOR_PREVIEW" and run["blocked"] == []


def test_privacy_and_limits(svc):
    s, store, clock = svc
    run = s.start(student(1), "grade-appeal")
    with pytest.raises(OpsError) as e:
        s.get(student(2), run["id"])
    assert e.value.status == 404
    with pytest.raises(OpsError) as e:
        s.start(person(sid(1000), IdentityRole.SUPPORT_OFFICER), "grade-appeal")
    assert e.value.status == 403
    for _ in range(9):
        s.start(student(1), "grade-appeal")
    with pytest.raises(OpsError) as e:
        s.start(student(1), "grade-appeal")
    assert e.value.code == "PROCEDURE_RATE"
    s.put_fields(student(1), run["id"], {"course_code": "MAT101"}, 1)
    clock.now = NOW + timedelta(days=31)
    assert s.expire_stale() == 10
    gone = store.one("SELECT state, fields FROM proc_runs WHERE id=?", (run["id"],))
    assert gone == {"state": "EXPIRED", "fields": "{}"}


def test_http_flow_and_text_recognition(svc):
    s, _, _ = svc
    app = FastAPI()
    register_ops_errors(app)
    register_procedure_errors(app)
    app.include_router(create_procedures_router(s))

    @app.middleware("http")
    async def ident(request, call_next):
        request.state.identity = student(1)
        return await call_next(request)
    c = TestClient(app)
    assert len(c.get("/v1/procedures").json()["items"]) == 3
    guess = c.post("/v1/procedures/runs:from-text", json={"text": "Mình muốn phúc khảo môn MAT101 vì chấm sai"}).json()
    assert guess["suggestions"][0]["procedure_id"] == "grade-appeal" and [e["field"] for e in guess["extracted"]] == ["course_code"]
    run = c.post("/v1/procedures/runs", json={"procedure_id": "grade-appeal"}).json()
    bad = c.put(f"/v1/procedures/runs/{run['id']}/fields", json={"fields": {"course_code": "??"}, "row_version": 1})
    assert bad.status_code == 422 and bad.json()["errors"][0]["field"] == "course_code"
    ok = c.put(f"/v1/procedures/runs/{run['id']}/fields", json={"fields": {"course_code": "MAT101", "semester": "HK1 2026", "reason": "Điểm thi không khớp bài làm"},
        "confirm_extracted": ["course_code"], "row_version": 1}).json()
    assert ok["state"] == "READY_FOR_PREVIEW" and ok["field_origin"]["course_code"] == "EXTRACTED_CONFIRMED"
    pv = c.post(f"/v1/procedures/runs/{run['id']}:submit-preview").json()
    missing_key = c.post("/v1/procedures/runs:submit-confirm", json={"preview_id": pv["preview_id"], "confirmation_token": pv["confirmation_token"]})
    assert missing_key.status_code == 422
    done = c.post("/v1/procedures/runs:submit-confirm", json={"preview_id": pv["preview_id"], "confirmation_token": pv["confirmation_token"]}, headers={"Idempotency-Key": "abc"})
    assert done.status_code == 200 and done.json()["state"] == "SUBMITTED"
