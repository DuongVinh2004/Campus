"""Receipt corruption and read-only export checks on new synthetic fixtures."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import uuid

from fastapi.testclient import TestClient
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from audit_unified_ai_baseline import audit, reconcile, digest, DATASET
from campus247.bootstrap.unified_demo import create_unified_demo_app


@pytest.fixture
def recorded(tmp_path):
    database = tmp_path / "evidence.sqlite3"
    app = create_unified_demo_app(database)
    now = [datetime(2026, 10, 14, tzinfo=timezone.utc)]
    app.state.baseline_measurements.clock = lambda: now[0]
    with TestClient(app) as client:
        token = client.post("/v1/auth/demo-login", json={"account": "SV001"}).json()["token"]
        headers = {"Authorization": "Bearer " + token}
        session = client.post("/v1/assistant/baseline/sessions", headers=headers,
            json={"client_id": "baseline:" + str(uuid.uuid4()), "case_id": "UB-04", "operator_kind": "automation"}).json()["session"]
        for kind, field, seconds in [("field_edit", "reason", 4), ("wait", None, 1),
                                     ("resume", None, 2), ("manual_action", None, 300), ("finish", None, 301)]:
            now[0] += timedelta(seconds=seconds)
            response = client.post(f"/v1/assistant/baseline/sessions/{session['id']}/events", headers=headers,
                json={"event_id": "event:" + str(uuid.uuid4()), "expected_version": session["version"], "kind": kind, "field": field})
            assert response.status_code == 200
            session = response.json()["session"]
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        row = dict(connection.execute("SELECT * FROM unified_baseline_session").fetchone())
        events = [dict(e) for e in connection.execute("SELECT * FROM unified_baseline_event ORDER BY sequence")]
    raw = DATASET.read_bytes()
    return database, row, events, json.loads(raw), hashlib.sha256(raw).hexdigest()


def verify(recorded, row=None, events=None, checksum=None):
    _, original, chain, dataset, sha = recorded
    return reconcile(row or original, chain if events is None else events, dataset, checksum or sha)


def test_export_survives_restart_is_read_only_and_does_not_claim_acceptance(recorded):
    database, _, _, _, _ = recorded
    before = database.read_bytes()
    first, reopened = audit(database), audit(database)
    assert database.read_bytes() == before
    assert first["sessions"] == reopened["sessions"]
    assert first["all_receipt_chains_valid"]
    assert first["human_declared_session_count"] == 0
    session = first["sessions"][0]
    assert (session["active_ms"], session["wait_ms"], session["unattributed_ms"]) == (305000, 2000, 301000)
    assert session["counts"]["manual_action"] == 1 and session["fields"] == {"reason": 1}
    assert not first["UNI_003_verified"] and not first["human_acceptance_verified"]
    assert not session["business_completion_verified"] and not session["human_identity_verified"]
    assert set(first["business_table_counts"]) == {"certificate_request", "certificate_replay", "service_request", "service_request_audit"}


@pytest.mark.parametrize("field,value,code", [
    ("active_ms", 305001, "metric_sums"), ("version", 7, "session_version"),
    ("event_count", 6, "event_count"), ("state", "active", "final_state"),
    ("role", "SUPPORT_OFFICER", "case_role"), ("owner", "another-owner", "session_binding"),
    ("counts", {"manual_action": 999}, "operation_counts"),
    ("fields", {"staff_note": 1}, "field_counts"),
    ("last_at", "2026-10-15T00:00:00+00:00", "last_timestamp"),
])
def test_modified_totals_and_binding_fail_closed(recorded, field, value, code):
    row = deepcopy(recorded[1])
    record = json.loads(row["record"])
    record[field] = value
    row["record"] = json.dumps(record)
    report = verify(recorded, row=row)
    assert not report["receipt_chain_valid"] and code in report["findings"]
    assert "counts" not in report and "fields" not in report


@pytest.mark.parametrize("field,value,code", [
    ("sequence", 2, "sequence"), ("version", 8, "event_version"),
    ("interval_ms", 1, "interval"), ("interval_classification", "waiting", "interval_classification"),
    ("previous_state", "paused", "previous_state"), ("state", "finished", "next_state"),
    ("field", "PRIVATE-SENTINEL", "field"), ("event_id", "changed", "event_binding"),
    ("committed_at", "2026-10-13T00:00:00+00:00", "clock"),
])
def test_corrupt_receipt_is_detected_and_untrusted_data_not_exported(recorded, field, value, code):
    events = deepcopy(recorded[2])
    receipt = json.loads(events[0]["receipt"])
    receipt[field] = value
    events[0]["receipt"] = json.dumps(receipt)
    report = verify(recorded, events=events)
    assert not report["receipt_chain_valid"] and code in report["findings"]
    assert "PRIVATE-SENTINEL" not in json.dumps(report)


def test_missing_duplicate_or_reordered_receipts_are_not_accepted(recorded):
    events = recorded[2]
    for damaged in (events[:-1], [events[0], *events], list(reversed(events))):
        report = verify(recorded, events=damaged)
        assert not report["receipt_chain_valid"]
    modified = deepcopy(events)
    modified[0]["fingerprint"] = "0" * 64
    assert "event_fingerprint" in verify(recorded, events=modified)["findings"]
    assert "dataset_changed" in verify(recorded, checksum="0" * 64)["findings"]


def test_orphan_events_fail_export_integrity_without_changing_database(recorded):
    database = recorded[0]
    with sqlite3.connect(database) as connection:
        connection.execute("INSERT INTO unified_baseline_event VALUES(?,?,?,?,?)", (str(uuid.uuid4()), "orphan", 1, "hash", "{}"))
    before = database.read_bytes()
    report = audit(database)
    assert report["orphan_event_count"] == 1 and not report["all_receipt_chains_valid"]
    assert database.read_bytes() == before


def test_private_metadata_and_injected_extra_receipt_fields_are_not_exported(recorded):
    row, events = deepcopy(recorded[1]), deepcopy(recorded[2])
    record = json.loads(row["record"])
    record["internal_notes"] = "PRIVATE-SENTINEL"
    row["record"] = json.dumps(record)
    receipt = json.loads(events[0]["receipt"])
    receipt["content"] = "PRIVATE-SENTINEL"
    events[0]["receipt"] = json.dumps(receipt)
    report = verify(recorded, row=row, events=events)
    assert report["receipt_chain_valid"]
    assert "PRIVATE-SENTINEL" not in json.dumps(report)
    assert not {"owner", "tenant", "client_id", "fingerprint", "internal_notes", "receipt"} & report.keys()


def test_self_declaration_or_unfinished_session_never_proves_completion(recorded):
    row = deepcopy(recorded[1])
    record = json.loads(row["record"])
    record["operator_kind"] = "human_declared"
    record["fingerprint"] = digest({key: record[key] for key in ("client_id", "case_id", "operator_kind")})
    row["fingerprint"] = record["fingerprint"]
    row["record"] = json.dumps(record)
    report = verify(recorded, row=row)
    assert report["receipt_chain_valid"] and not report["human_identity_verified"]
    assert not report["business_completion_verified"]
    record.update(version=1, event_count=0, state="active", last_at=record["created_at"],
                  active_ms=0, wait_ms=0, paused_ms=0, unattributed_ms=0, counts={}, fields={})
    row["record"] = json.dumps(record)
    assert verify(recorded, row=row, events=[])["receipt_chain_valid"]


def test_malformed_data_and_invalid_transition_are_reported(recorded):
    row = deepcopy(recorded[1])
    row["record"] = "not-json"
    assert verify(recorded, row=row)["findings"] == ["malformed_record_or_receipt"]
    events = deepcopy(recorded[2])
    receipt = json.loads(events[1]["receipt"])
    receipt.update(kind="resume", state="active")
    events[1]["receipt"] = json.dumps(receipt)
    events[1]["fingerprint"] = digest({"event_id": events[1]["event_id"], "expected_version": 2, "kind": "resume", "field": None})
    assert "transition" in verify(recorded, events=events)["findings"]


def test_missing_database_is_not_created(tmp_path):
    path = tmp_path / "absent.sqlite3"
    with pytest.raises(FileNotFoundError):
        audit(path)
    assert not path.exists()
