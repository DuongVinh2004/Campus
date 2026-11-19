"""Typed supplement transport must preserve strict certificate form semantics."""
import pytest

from campus247.domain.shared.values import generate_uuid7
from tests.integration.test_unified_storage_completion import tables
from tests.unified_workflow13a.test_certificate import certificate as certificate_fixture, body
from tests.unified_workflow13a.test_case_workflow import post, prepare, preview, confirmation

certificate = certificate_fixture


@pytest.mark.parametrize("invalid_integer", [True, 2.0, "2"])
def test_supplement_transport_cannot_coerce_bool_float_or_text_into_strict_quantity(certificate, tmp_path, invalid_integer):
    _, client, student, staff, record = certificate
    draft = body(client, staff, record, operation="request_supplement", outcome="SUPPLEMENT_REQUIRED", supplement_items=[{
        "id": "quantity", "criterion_id": "evidence_review", "source_ids": ["payload:quantity"], "field": "quantity",
        "public_reason": "C synthetic confirmation of quantity", "accepted_format": "integer"}])
    prepare(client, staff, draft)
    candidate = preview(client, staff, draft)
    assert post(client, staff, ":confirm", confirmation(candidate)).status_code == 200
    route = "/v1/document-requests/" + record["id"]
    waiting = client.get(route, headers=student).json()
    target = {**draft["resource"], "expected_version": waiting["version"]}
    request = post(client, student, "/supplement:read", {"resource": target}).json()["current_request"]
    payload = {"resource": target, "request_id": request["id"], "request_version": request["version"], "client_id": generate_uuid7(),
        "responses": [{"item_id": "quantity", "field": "quantity", "value": invalid_integer}], "note": "C typed quantity response"}
    before = tables(tmp_path / "business.sqlite3")
    response = post(client, student, "/supplement:preview", payload)
    assert response.status_code == 422, response.text
    assert tables(tmp_path / "business.sqlite3") == before
    assert client.get(route, headers=student).json() == waiting
    valid = {**payload, "responses": [{"item_id": "quantity", "field": "quantity", "value": 2}]}
    accepted = post(client, student, "/supplement:preview", valid)
    assert accepted.status_code == 200 and accepted.json()["form"]["quantity"] == 2
