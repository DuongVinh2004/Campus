"""Independent C faults against the actual A case workflow consumer."""
from concurrent.futures import ThreadPoolExecutor

import pytest

from campus247.application.document_request.certificates import CertificateError
from campus247.domain.shared.values import generate_uuid7
from tests.api.test_service_stage6 import act, read, sent
from tests.unified_final.test_security_c import runtime as runtime_fixture
from tests.unified_workflow13a.test_case_workflow import confirmation, draft_body, post, prepare, preview
from tests.integration.test_unified_storage_completion import tables

runtime = runtime_fixture


@pytest.mark.parametrize("not_boolean", [1, 1.0, "true", None, False])
def test_explicit_staff_confirmation_must_be_json_boolean_true(runtime, not_boolean):
    _, client, _, staff, record, path = runtime
    body = draft_body(client, staff, record)
    prepare(client, staff, body)
    candidate = preview(client, staff, body)
    before = tables(path / "business.sqlite3")
    response = post(client, staff, ":confirm", {**confirmation(candidate), "confirmed": not_boolean})
    assert response.status_code == 422, response.text
    assert tables(path / "business.sqlite3") == before


def test_receipt_storage_failure_rolls_back_business_event_and_result(runtime, monkeypatch):
    app, client, student, staff, record, path = runtime
    body = draft_body(client, staff, record)
    prepare(client, staff, body)
    candidate = preview(client, staff, body)
    before = tables(path / "business.sqlite3")
    original = app.state.case_workflow.repository.insert
    def fail_receipt(tx, kind, value):
        if kind == "receipt":
            raise CertificateError(503, "C_FIXTURE_RECEIPT_UNAVAILABLE", "Synthetic receipt write failed")
        return original(tx, kind, value)
    monkeypatch.setattr(app.state.case_workflow.repository, "insert", fail_receipt)
    response = post(client, staff, ":confirm", confirmation(candidate))
    assert response.status_code == 503, response.text
    assert tables(path / "business.sqlite3") == before
    assert read(client, student, record["id"])["version"] == record["version"]
    monkeypatch.setattr(app.state.case_workflow.repository, "insert", original)
    recovered = post(client, staff, ":confirm", confirmation(candidate))
    assert recovered.status_code == 200 and recovered.json()["state"] == "committed"
    assert read(client, student, record["id"])["version"] == record["version"] + 1


def test_competing_confirmations_have_one_business_effect_and_one_receipt(runtime):
    _, client, student, staff, record, _ = runtime
    body = draft_body(client, staff, record)
    prepare(client, staff, body)
    candidate = preview(client, staff, body)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: post(client, staff, ":confirm", confirmation(candidate)), range(2)))
    assert [r.status_code for r in responses] == [200, 200]
    assert len({r.json()["receipt_id"] for r in responses}) == 1
    assert sorted(r.json()["is_replay"] for r in responses) == [False, True]
    assert read(client, student, record["id"])["version"] == record["version"] + 1


def test_batch_hash_drift_and_stale_item_cannot_expand_or_duplicate_targets(runtime):
    _, client, student, staff, first, path = runtime
    _, second, _ = sent(client)
    second = act(client, staff, second, "claim").json()["document_request"]
    items = []
    for record in [first, second]:
        body = draft_body(client, staff, record)
        prepare(client, staff, body)
        items.append({"resource": body["resource"], "draft_version": 1, "client_id": generate_uuid7()})
    batch = post(client, staff, "/batch:prepare", {"client_id": generate_uuid7(), "items": items})
    assert batch.status_code == 200, batch.text
    batch = batch.json()
    before = tables(path / "business.sqlite3")
    rejected = post(client, staff, "/batch:confirm", {"batch_id": batch["batch_id"], "target_hash": "0" * 64, "confirmed": True})
    assert rejected.status_code == 409 and tables(path / "business.sqlite3") == before
    changed = act(client, staff, second, "respond", note="Manual response after batch preview")
    assert changed.status_code == 200
    second_before = read(client, student, second["id"])
    request = {"batch_id": batch["batch_id"], "target_hash": batch["target_hash"], "confirmed": True}
    response = post(client, staff, "/batch:confirm", request)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["state"] == "partial"
    assert [r["state"] for r in result["results"]] == ["committed", "blocked"]
    first_after = read(client, student, first["id"])
    assert first_after["version"] == first["version"] + 1
    assert read(client, student, second["id"]) == second_before
    retry = post(client, staff, "/batch:confirm", request)
    assert retry.status_code == 200 and retry.json()["results"][0]["is_replay"]
    assert retry.json()["results"][0]["receipt"]["receipt_id"] == result["results"][0]["receipt"]["receipt_id"]
    assert read(client, student, first["id"]) == first_after
    assert read(client, student, second["id"]) == second_before
