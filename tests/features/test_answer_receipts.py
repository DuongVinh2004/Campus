"""F4.2: receipts are stored without text, readable only by the owner, re-checked against the current release, and removed with the conversation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from campus247.application.answer_evidence.receipts import AnswerReceiptService
from campus247.infrastructure.repositories.sqlite_answer_receipts import AnswerReceiptStore
from campus247.ports.campus_ops import OpsError
from campus247.ports.identity import IdentityContext, IdentityRole
from campus247.presentation.answer_receipts import create_answer_receipts_router
from campus247.presentation.campus_ops import register_ops_errors

NOW = datetime(2026, 11, 26, 3, 0, tzinfo=timezone.utc)
OWNER, OTHER = "01900000-0000-7000-8000-00000000000a", "01900000-0000-7000-8000-00000000000b"
UNITS = {"u1": "hash-1", "u2": "hash-2-new"}  # u2 changed, u3 removed


def make(tmp_path, enabled=True):
    store = AnswerReceiptStore(tmp_path / "r.sqlite3")
    service = AnswerReceiptService(store, current_unit_sha=UNITS.get, current_release=lambda: "rel-2", enabled=lambda: enabled, clock=lambda: NOW,
                                   impact_run_for=lambda units: "run-1" if units else None)
    return store, service


def record(service, **over):
    args = dict(owner=OWNER, conversation_id="c1", message_id="m1", release_id="rel-1", binding_sha256="b", outcome_kind="answer",
                statements=["Học phí 580.500 đồng", "Hạn nộp 15/09"],
                sources=[{"unit_id": "u1", "text_sha256": "hash-1", "path": "Điều 10", "doc_title": "Quy chế", "page": 4},
                         {"unit_id": "u2", "text_sha256": "hash-2", "path": "Điều 11", "doc_title": "Quy chế", "page": 5},
                         {"unit_id": "u3", "text_sha256": "hash-3", "path": "Điều 12", "doc_title": "Quy chế", "page": 6}],
                checks=[{"deterministic": "PASSED", "verbatim": True, "semantic": "SKIPPED_VERBATIM", "unit_ids": ["u1"]},
                        {"deterministic": "PASSED", "verbatim": False, "semantic": "PASSED", "unit_ids": ["u2", "u3"]}],
                rejected_counts={"NUMBER_NOT_IN_SOURCE": 1}, expires_at=(NOW + timedelta(days=30)).isoformat(timespec="seconds"))
    args.update(over)
    return service.record(**args)


def test_record_open_and_status_now(tmp_path):
    store, service = make(tmp_path)
    rid = record(service)
    opened = service.open(OWNER, rid)
    assert [s["status_now"] for s in opened["sources"]] == ["UNCHANGED", "CHANGED", "REMOVED"]
    assert opened["now"] == {"release_id": "rel-2", "sources_changed": 1, "sources_removed": 1, "impact_run_id": "run-1"}
    assert opened["statements"][1]["sources"][0]["unit_id"] == "u2" and "unit_ids" not in opened["statements"][1]["checks"]
    assert opened["rejected_counts"] == {"NUMBER_NOT_IN_SOURCE": 1}
    raw = store.get(rid)
    assert "Học phí" not in str(raw) and len(raw["statements_sha256"]) == 64  # no statement text is kept


def test_only_the_owner_can_open_and_expired_receipts_are_gone(tmp_path):
    store, service = make(tmp_path)
    rid = record(service)
    for who in (OTHER, "x"):
        try:
            service.open(who, rid)
            raise AssertionError("opened by another person")
        except OpsError as error:
            assert error.status == 404
    expired = record(service, message_id="m2", expires_at=(NOW - timedelta(seconds=1)).isoformat(timespec="seconds"))
    try:
        service.open(OWNER, expired)
        raise AssertionError("expired")
    except OpsError as error:
        assert error.code == "RECEIPT_NOT_FOUND"
    assert store.purge_expired(NOW.isoformat(timespec="seconds")) == 1


def test_deleting_the_conversation_deletes_its_receipts(tmp_path):
    store, service = make(tmp_path)
    record(service)
    record(service, message_id="m2")
    record(service, conversation_id="c2")
    assert store.delete_conversation("c1") == 2 and store.for_message("c1", "m1") is None and store.for_message("c2", "m1")


def test_flag_off_writes_nothing_and_a_failing_store_never_breaks_the_answer(tmp_path):
    store, off = make(tmp_path, enabled=False)
    assert record(off) is None and store.for_message("c1", "m1") is None
    errors = []
    broken = AnswerReceiptService(type("Broken", (), {"save": lambda self, row: (_ for _ in ()).throw(RuntimeError("disk"))})(), current_unit_sha=UNITS.get,
                                  current_release=lambda: "r", on_error=errors.append, clock=lambda: NOW)
    assert record(broken) is None and len(errors) == 1


def test_route_returns_404_for_a_stranger(tmp_path):
    _, service = make(tmp_path)
    rid = record(service)
    app = FastAPI()
    register_ops_errors(app)
    app.include_router(create_answer_receipts_router(service))

    @app.middleware("http")
    async def who(request, call_next):
        name = request.headers.get("x-user")
        if name:
            request.state.identity = IdentityContext(subject_id=name, external_subject="x", issuer="l", roles=(IdentityRole.STUDENT,), display_name="x",
                                                     auth_time=NOW, expires_at=NOW + timedelta(hours=1), student_code="S1")
        return await call_next(request)

    c = TestClient(app)
    ok = c.get(f"/v1/answer-receipts/{rid}", headers={"x-user": OWNER})
    assert ok.status_code == 200 and ok.headers["cache-control"] == "no-store" and ok.json()["now"]["sources_changed"] == 1
    assert c.get(f"/v1/answer-receipts/{rid}", headers={"x-user": OTHER}).status_code == 404


def test_record_receipt_binds_sources_by_hash_and_by_message_route_is_owner_only(tmp_path):
    import json
    from types import SimpleNamespace
    from campus247.application.answer_evidence.record import record_receipt
    store, service = make(tmp_path)
    cite = SimpleNamespace(citation_json=json.dumps({"unit_id": "u1", "source_title": "Quy chế", "release_id": "rel-1", "locator": {"section_path": "Điều 10", "page_start": 4}}))
    message = SimpleNamespace(id="m9", citations=(cite,))
    result = SimpleNamespace(response_class="grounded_answer", evidence={
        "statements": ["Học phí 580.500 đồng"], "rejected_counts": {"NUMBER_NOT_IN_SOURCE": 1},
        "checks": [{"deterministic": "PASSED", "verbatim": True, "semantic": "PASSED", "unit_ids": ["u1"]}]})
    expires = (NOW + timedelta(days=30)).isoformat(timespec="seconds")
    rid = record_receipt(service, owner=OWNER, conversation_id="c9", message=message, result=result, expires_at=expires, release_id="rel-1")
    assert rid
    opened = service.open_for_message(OWNER, "c9", "m9")
    assert opened["receipt_id"] == rid and opened["sources"][0]["status_now"] == "UNCHANGED"
    # a statement citing a unit missing from the index cannot be bound: no receipt rather than a wrong one
    result.evidence["checks"][0]["unit_ids"] = ["gone"]
    assert record_receipt(service, owner=OWNER, conversation_id="c9", message=SimpleNamespace(id="m10", citations=()), result=result, expires_at=expires, release_id="rel-1") is None
    app = FastAPI()
    register_ops_errors(app)
    app.include_router(create_answer_receipts_router(service))

    @app.middleware("http")
    async def who(request, call_next):
        request.state.identity = IdentityContext(subject_id=request.headers["x-user"], external_subject="x", issuer="l", roles=(IdentityRole.STUDENT,),
                                                 display_name="x", auth_time=NOW, expires_at=NOW + timedelta(hours=1), student_code="S1")
        return await call_next(request)

    c = TestClient(app)
    assert c.get("/v1/answer-receipts/by-message/c9/m9", headers={"x-user": OWNER}).json()["receipt_id"] == rid
    assert c.get("/v1/answer-receipts/by-message/c9/m9", headers={"x-user": OTHER}).status_code == 404


def test_receipts_of_chunk_level_citations_are_bound_by_evidence_hash_and_document_version(tmp_path):
    import json
    from types import SimpleNamespace
    from campus247.application.answer_evidence.record import record_receipt
    served = {"versions": {"ver-new"}, "documents": {"doc-a", "doc-b"}}
    state = lambda version, document: "UNCHANGED" if version in served["versions"] else "CHANGED" if document in served["documents"] else "REMOVED"
    store = AnswerReceiptStore(tmp_path / "r.sqlite3")
    service = AnswerReceiptService(store, current_unit_sha=lambda unit_id: None, current_release=lambda: "rel-2", clock=lambda: NOW, version_state=state)
    cites = [{"unit_id": "chunk-unit-1", "evidence_sha256": "e" * 64, "document_version_id": "ver-new", "source_id": "doc-a", "source_title": "Quy chế", "release_id": "rel-1", "locator": {"section_path": "Điều 3", "page_start": 2}},
             {"unit_id": "chunk-unit-2", "evidence_sha256": "f" * 64, "document_version_id": "ver-old", "source_id": "doc-b", "source_title": "Học phí", "release_id": "rel-1", "locator": {"page_start": 1}},
             {"unit_id": "chunk-unit-3", "evidence_sha256": "d" * 64, "document_version_id": "ver-gone", "source_id": "doc-z", "source_title": "Cũ", "release_id": "rel-1", "locator": {"page_start": 1}}]
    message = SimpleNamespace(id="m1", citations=tuple(SimpleNamespace(citation_json=json.dumps(c)) for c in cites))
    result = SimpleNamespace(response_class="grounded_answer", evidence={"statements": ["a", "b", "c"], "rejected_counts": {},
        "checks": [{"deterministic": "PASSED", "verbatim": False, "semantic": "PASSED", "unit_ids": [c["unit_id"]]} for c in cites]})
    rid = record_receipt(service, owner=OWNER, conversation_id="c1", message=message, result=result, expires_at=(NOW + timedelta(days=30)).isoformat(timespec="seconds"), release_id="rel-1")
    assert rid and store.get(rid)["sources"][0]["text_sha256"] == "e" * 64
    opened = service.open(OWNER, rid)
    assert [s["status_now"] for s in opened["sources"]] == ["UNCHANGED", "CHANGED", "REMOVED"]
    assert opened["now"]["sources_changed"] == 1 and opened["now"]["sources_removed"] == 1
