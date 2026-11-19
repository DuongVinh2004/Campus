"""New isolated SQLite fixtures; no retained runtime writes or model dispatch."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import sqlite3

from fastapi.testclient import TestClient
import pytest

from campus247.bootstrap.unified_demo import create_unified_demo_app
from campus247.application.knowledge.operations import digest
from tests.api.test_certificate_stage1 import login, draft, preview, confirm, action, FORM
from tests.api.test_service_stage6 import sent, candidate, kp, kc, act, read, APPEAL, preview as service_preview, confirm as service_confirm

PATH = "/v1/assistant/workflows/resolve"


@pytest.fixture
def runtime(tmp_path):
    database = tmp_path / "continuation.sqlite3"
    app = create_unified_demo_app(database)
    with TestClient(app) as client:
        yield app, client, database


def resolve(c, headers, record, kind="certificate_request", **extra):
    return c.post(PATH, headers=headers, json={"resource": {
        "kind": kind, "id": record["id"], "expected_version": record["version"]}, **extra})


def rows(database):
    with sqlite3.connect(database.as_uri()+"?mode=ro",uri=True) as connection:
        return {table:digest(list(connection.execute('SELECT * FROM "'+table+'" ORDER BY rowid'))) for table in
            ["certificate_request", "certificate_audit", "certificate_replay", "service_request", "service_request_audit", "service_operations_record"]}


def submitted_certificate(c):
    h = login(c)
    record = draft(c, h)
    p = preview(c, h, record)
    assert confirm(c, h, p, key="workflow-cert:"+record["id"]).status_code == 201
    return h, c.get(f"/v1/document-requests/{record['id']}",headers=h).json(), p


def test_certificate_source_template_binding_is_shared_minimal_read_only_and_unknown_institutionally(runtime):
    _, c, db = runtime
    h, record, _ = submitted_certificate(c)
    before = rows(db)
    a, b = resolve(c, h, record), resolve(c, login(c,"OF001"), record)
    assert a.status_code == b.status_code == 200
    left, right = a.json(), b.json()
    assert left["binding"] == right["binding"] and left["resource"]["view"] == "student"
    assert right["resource"]["view"] == "staff" and a.headers["cache-control"] == "no-store"
    source = left["binding"]["source"]
    assert source["classification"] == "public_snapshot" and source["effective_status"] == "unknown"
    assert source["effective_from"] is None and source["effective_until"] is None
    assert len(left["binding"]["supporting_sources"]) == 1
    assert left["institutional_rules_verified"] is False and all(r["status"]=="required" for r in left["mandatory_reviews"])
    binding = dict(left["binding"]); checksum = binding.pop("sha256")
    assert digest(binding) == checksum and rows(db) == before
    assert not {"profile", "payload", "preview", "internal_notes", "token"} & left.keys()


@pytest.mark.parametrize("account,status",[("SV024",404),("OF002",403),("KA001",403)])
def test_certificate_scope_remains_concealed_or_role_denied(runtime, account, status):
    _,c,_ = runtime
    _,record,_ = submitted_certificate(c)
    r=resolve(c,login(c,account),record)
    assert r.status_code==status and "binding" not in r.json()


def test_private_draft_and_injected_source_or_confirmation_are_rejected(runtime):
    _,c,_ = runtime
    h=login(c);record=draft(c,h)
    assert resolve(c,login(c,"OF001"),record).status_code==404
    for extra in [{"guidance_snapshot":{}},{"confirmed":True},{"institutional_rules_verified":True},{"source":{"verified":True}}]:
        assert resolve(c,h,record,**extra).status_code==422
    assert resolve(c,h,{**record,"version":record["version"]+1}).status_code==409


def test_source_changed_after_preview_blocks_commit_and_preserves_work(runtime):
    app,c,db=runtime
    h=login(c);record=draft(c,h);p=preview(c,h,record)
    original=app.state.certificate_service.guidance_reader()
    changed=deepcopy(original);changed["sources"][0]["content_sha256"]="0"*64
    app.state.certificate_service.guidance_reader=lambda:changed
    before=rows(db)
    r=confirm(c,h,p,key="changed-source")
    assert r.status_code==409 and r.json()["code"]=="PUBLIC_SOURCE_CHANGED_OR_UNAVAILABLE"
    assert rows(db)==before
    package=resolve(c,h,p["document_request"]).json()
    assert package["binding_status"]=="unresolved" and package["template"] is None
    assert package["current_source_differs"] and package["readiness"]=="undetermined"


def test_legacy_missing_capture_is_never_backfilled_by_read_or_preview(runtime):
    app,c,db=runtime
    h=login(c);record=draft(c,h)
    with app.state.certificate_repository.transaction() as tx:
        raw=tx.get(record["id"]);raw["guidance_snapshot"]=None;tx.save(raw)
    before=rows(db)
    package=resolve(c,h,record).json()
    assert package["binding_status"]=="unresolved" and package["reasons"]==["SOURCE_SNAPSHOT_MISSING"]
    r=c.post(f"/v1/document-requests/{record['id']}/preview",headers=h,json={"expected_version":record["version"]})
    assert r.status_code==409 and r.json()["code"]=="WORKFLOW_BINDING_UNRECORDED"
    assert rows(db)==before


def test_result_records_template_source_and_replay_survives_restart(runtime):
    _,c,db=runtime
    h,record,p=submitted_certificate(c)
    officer=login(c,"OF001")
    accepted=action(c,officer,record["id"],"accept",record["version"],"workflow-accept")
    assert accepted.status_code == 200, accepted.text
    record=accepted.json()["document_request"]
    approved=action(c,officer,record["id"],"approve",record["version"],"workflow-approve","Đối chiếu fixture")
    assert approved.status_code == 200, approved.text
    record=approved.json()["document_request"]
    package=resolve(c,officer,record).json()
    assert record["result"]["template_version"]==package["template"]["version"]
    assert record["result"]["source_fingerprint"]==record["guidance_snapshot"]["fingerprint"]
    assert record["result"]["institutional_rules_verified"] is False
    before=rows(db)
    with TestClient(create_unified_demo_app(db)) as restarted:
        r=restarted.get(f"/v1/document-requests/{record['id']}",headers=h)
        assert r.json()==record
        assert resolve(restarted,officer,record).json()["binding"]==package["binding"]
        r=confirm(restarted,h,p,key="workflow-cert:"+record["id"])
        assert r.status_code==201 and r.json()["is_replay"]
    assert rows(db)==before


def test_service_supplement_captures_new_source_without_rebinding_initial_submission(runtime):
    _,c,db=runtime
    h,record,_=sent(c)
    old=resolve(c,h,record,"service_request").json()["binding"]
    officer=login(c,"OF002")
    record=act(c,officer,record,"claim").json()["document_request"]
    record=act(c,officer,record,"request_information").json()["document_request"]
    editor,reviewer=login(c,"KA001"),login(c,"KA002")
    _,version=candidate(c,editor,reviewer)
    assert kc(c,reviewer,version,kp(c,reviewer,version)).status_code==200
    form={**APPEAL,"reason":"Bổ sung fixture mới"}
    p=service_preview(c,h,record,form=form,note="Đã bổ sung fixture")
    response=service_confirm(c,h,p);assert response.status_code==201
    record=read(c,h,record["id"])
    before=rows(db)
    package=resolve(c,h,record,"service_request").json()
    assert package["binding"]==old
    extra=package["supplements"][0]
    assert extra["binding_status"]=="bound" and extra["source"]["version_id"]==version["id"]
    assert extra["source_changed_from_submission"] and package["readiness"]=="requires_officer_review"
    assert record["snapshot"]["guidance"]["version_id"]==old["source"]["version_id"]
    assert record["supplements"][0]["source_snapshot"]["version_id"]==version["id"]
    assert rows(db)==before
    with TestClient(create_unified_demo_app(db)) as restarted:
        assert resolve(restarted,h,record,"service_request").json()==package


def test_old_supplement_without_source_is_reported_unknown_not_current(runtime):
    app,c,db=runtime
    h,record,_=sent(c)
    with app.state.service_requests.repository.transaction() as tx:
        raw=tx.get(record["id"])
        raw["supplements"]=[{"before":raw["payload"],"form":raw["payload"],"note":"Legacy fixture"}]
        raw["internal_notes"]="PRIVATE-SENTINEL"
        tx.save(raw)
    before=rows(db)
    response=resolve(c,h,record,"service_request");package=response.json()
    assert package["binding_status"]=="bound" and package["readiness"]=="undetermined"
    extra=package["supplements"][0]
    assert extra["source"] is None and extra["at"] is None and extra["source_changed_from_submission"] is None
    assert extra["reasons"]==["SUPPLEMENT_SOURCE_UNRECORDED"]
    assert "PRIVATE-SENTINEL" not in response.text and "Legacy fixture" not in response.text
    assert rows(db)==before


def test_certificate_supplement_has_separate_source_time_and_prior_payload(runtime):
    _,c,_=runtime
    h,record,_=submitted_certificate(c);old=resolve(c,h,record).json()["binding"]
    officer=login(c,"OF001")
    record=action(c,officer,record["id"],"accept",record["version"],"accept-supp").json()["document_request"]
    record=action(c,officer,record["id"],"request_supplement",record["version"],"request-supp","Bổ sung nơi nhận").json()["document_request"]
    updated={**FORM,"recipient":"Đơn vị fixture mới"}
    response=action(c,h,record["id"],"supplement",record["version"],"workflow-supp","Đã bổ sung",updated)
    assert response.status_code == 200, response.text
    record=response.json()["document_request"]
    package=resolve(c,h,record).json()
    assert package["binding"]==old
    assert package["supplements"][0]["binding_status"]=="bound"
    assert package["supplements"][0]["source_changed_from_submission"] is False
    assert record["supplements"][0]["before"]["recipient"]==FORM["recipient"]
    assert record["supplements"][0]["payload"]["recipient"]==updated["recipient"]


@pytest.mark.parametrize("change,reason",[
    ({"at":"2026-10-13T00:00:00+00:00"},"SUPPLEMENT_PROVENANCE_INCONSISTENT"),
    ({"committed_version":999},"SUPPLEMENT_PROVENANCE_INCONSISTENT"),
    ({"template_version":"invented"},"SUPPLEMENT_WORKFLOW_VERSION_MISMATCH"),
    ({"source_snapshot":{"version_id":"missing"}},"SOURCE_SNAPSHOT_MISMATCH"),
])
def test_supplement_provenance_cannot_invent_a_valid_binding(runtime,change,reason):
    app,c,db=runtime
    h,record,_=sent(c);officer=login(c,"OF002")
    record=act(c,officer,record,"claim").json()["document_request"]
    record=act(c,officer,record,"request_information").json()["document_request"]
    p=service_preview(c,h,record,form=APPEAL,note="Fixture supplement")
    assert service_confirm(c,h,p).status_code==201
    record=read(c,h,record["id"])
    with app.state.service_requests.repository.transaction() as tx:
        raw=tx.get(record["id"])
        if "source_snapshot" in change:
            raw["supplements"][0]["source_snapshot"]["source_sha256"]="0"*64
        else:
            raw["supplements"][0].update(change)
        tx.save(raw)
    before=rows(db)
    r=resolve(c,h,record,"service_request");assert r.status_code==200,r.text
    package=r.json();extra=package["supplements"][0]
    assert package["readiness"]=="undetermined" and extra["binding_status"]=="unresolved"
    assert extra["source"] is None and extra["source_changed_from_submission"] is None
    assert reason in extra["reasons"] and rows(db)==before
