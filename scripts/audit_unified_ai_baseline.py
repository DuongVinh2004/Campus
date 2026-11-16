"""Read-only baseline receipt reconciliation, separate from human acceptance.

No runtime initialization, login, model calls, recorder events or business
writes. Export only allowlisted metadata. Read a consistent SQLite transaction;
retain reports exclusively at a fresh exact path in this session's namespace.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from unified_ai_runtime_probe import ROOT, checked, retain

STATE = ROOT / "infra/local/unified-ai-20261014-03"
DATABASE = ROOT / "infra/local/unified-ai-20261014-01/business-candidate01.sqlite3"
DATASET = ROOT / "evals/datasets/unified-ai-baseline-20261014.json"
PROTOCOL = "unified-baseline-measurement.v1"
TRANSITIONS = {"pause": ({"active", "waiting"}, "paused"),
               "wait": ({"active", "paused"}, "waiting"),
               "resume": ({"paused", "waiting"}, "active"),
               "finish": ({"active", "paused", "waiting"}, "finished")}
OPERATIONS = {"field_edit", "correction", "manual_action", "check_source",
              "assistant_request", "preview", "receipt_observed"}
FIELDS = {"reason", "course_record_id", "purpose", "recipient", "staff_note",
          "target", "outcome", "contact_preference"}
METRICS = {"active": "active_ms", "waiting": "wait_ms", "paused": "paused_ms",
           "unattributed": "unattributed_ms"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def timestamp(value):
    result = datetime.fromisoformat(value)
    if result.utcoffset() is None:
        raise ValueError("timezone required")
    return result


def reconcile(row, events, dataset, dataset_sha256):
    """Recompute every measurement from immutable event receipts; emit no data.

    A valid chain proves the recorder's consistency, never identity, attention,
    business completion, first-pass correctness or reduced human effort.
    """
    errors = set()

    def check(condition, code):
        if not condition:
            errors.add(code)

    try:
        record = json.loads(row["record"])
        check(all(record[key] == row[key] for key in ("id", "owner", "tenant", "client_id", "fingerprint")), "session_binding")
        check(record["protocol"] == PROTOCOL, "protocol")
        check(record["dataset_sha256"] == dataset_sha256, "dataset_changed")
        check(record["operator_kind"] in {"automation", "human_declared"}, "operator_kind")
        case = next((case for case in dataset["cases"] if case["id"] == record["case_id"]), None)
        hint = case["actor"].lower() if case else ""
        check(case is not None and (record["role"] == "STUDENT" and ("sv" in hint or "student" in hint)
              or record["role"] == "SUPPORT_OFFICER" and ("of" in hint or "staff" in hint)), "case_role")
        check(record["fingerprint"] == digest({key: record[key] for key in ("client_id", "case_id", "operator_kind")}), "start_fingerprint")
        check(type(record["event_count"]) is int and 0 <= record["event_count"] <= 1000, "event_limit")
        check(len(events) == record["event_count"], "event_count")
        check(type(record["version"]) is int and record["version"] == len(events) + 1, "session_version")
        sums = {metric: 0 for metric in METRICS.values()}
        counts, fields = Counter(), Counter()
        state, previous = "active", timestamp(record["created_at"])
        seen = set()
        for sequence, event in enumerate(events, 1):
            receipt = json.loads(event["receipt"])
            check(event["event_id"] not in seen, "duplicate_event")
            seen.add(event["event_id"])
            check(receipt["event_id"] == event["event_id"], "event_binding")
            check(type(receipt["sequence"]) is int and receipt["sequence"] == event["sequence"] == sequence, "sequence")
            check(type(receipt["version"]) is int and receipt["version"] == sequence + 1, "event_version")
            kind, field = receipt["kind"], receipt["field"]
            check(kind in TRANSITIONS or kind in OPERATIONS, "event_kind")
            check((kind == "field_edit" and field in FIELDS) or (kind != "field_edit" and field is None), "field")
            check(event["fingerprint"] == digest({"event_id": event["event_id"], "expected_version": sequence,
                  "kind": kind, "field": field}), "event_fingerprint")
            check(receipt["previous_state"] == state, "previous_state")
            if kind in TRANSITIONS:
                allowed, next_state = TRANSITIONS[kind]
                check(state in allowed, "transition")
            else:
                check(state == "active", "transition")
                next_state = state
            check(receipt["state"] == next_state, "next_state")
            now = timestamp(receipt["committed_at"])
            elapsed = int((now - previous).total_seconds() * 1000)
            check(elapsed >= 0, "clock")
            check(type(receipt["interval_ms"]) is int and receipt["interval_ms"] == elapsed, "interval")
            classification = "unattributed" if elapsed > 300000 else state
            check(receipt["interval_classification"] == classification, "interval_classification")
            if classification in METRICS:
                sums[METRICS[classification]] += elapsed
            counts[kind] += 1
            if field is not None:
                fields[field] += 1
            state, previous = next_state, now
        check(timestamp(record["last_at"]) == previous, "last_timestamp")
        check(record["state"] == state, "final_state")
        check(all(type(record[key]) is int and record[key] == value for key, value in sums.items()), "metric_sums")
        check(record["counts"] == dict(counts), "operation_counts")
        check(record["fields"] == dict(fields), "field_counts")
        keys = ("id", "case_id", "role", "operator_kind", "state", "version", "created_at", "last_at",
                "active_ms", "wait_ms", "paused_ms", "unattributed_ms", "event_count", "counts", "fields")
        # Invalid chains expose no untrusted strings or potential injected data.
        summary = {key: record[key] for key in keys} if not errors else {"id": row["id"]}
    except (KeyError, TypeError, ValueError, OverflowError):
        errors.add("malformed_record_or_receipt")
        summary = {"id": row["id"]}
    return {**summary, "receipt_chain_valid": not errors, "findings": sorted(errors),
            "human_identity_verified": False, "business_completion_verified": False}


def audit(database=DATABASE):
    database = checked(database)
    if not database.is_file():
        raise FileNotFoundError("existing candidate required; never create a database")
    raw = checked(DATASET).read_bytes()
    dataset, checksum = json.loads(raw), hashlib.sha256(raw).hexdigest()
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        sessions = []
        for row in connection.execute("SELECT id,owner,tenant,client_id,fingerprint,record FROM unified_baseline_session ORDER BY id"):
            events = list(connection.execute("SELECT event_id,sequence,fingerprint,receipt FROM unified_baseline_event WHERE session_id=? ORDER BY sequence", (row["id"],)))
            sessions.append(reconcile(row, events, dataset, checksum))
        orphan_events = connection.execute("SELECT COUNT(*) FROM unified_baseline_event e LEFT JOIN unified_baseline_session s ON s.id=e.session_id WHERE s.id IS NULL").fetchone()[0]
        business_counts = {table: connection.execute('SELECT COUNT(*) FROM "' + table + '"').fetchone()[0]
                           for table in ("service_request", "service_request_audit", "certificate_request", "certificate_replay")}
        connection.rollback()
    human = [s for s in sessions if s.get("operator_kind") == "human_declared"]
    return {"captured_at": datetime.now(timezone.utc).isoformat(), "scope": "read_only_local_recorder_metadata",
            "database": str(database), "dataset_sha256": checksum, "sessions": sessions,
            "session_count": len(sessions), "human_declared_session_count": len(human),
            "finished_human_declared_session_count": sum(s["state"] == "finished" for s in human),
            "orphan_event_count": orphan_events,
            "all_receipt_chains_valid": not orphan_events and all(s["receipt_chain_valid"] for s in sessions),
            "business_table_counts": business_counts, "human_acceptance_verified": False,
            "UNI_003_verified": False,
            "required_user_evidence": ["student/staff session IDs", "business request ID", "completion or blocking error",
                                       "repeated input/search observations", "source and result correctness feedback"],
            "limitations": ["human_declared is self-declared; chain consistency does not prove attention or identity",
                            "Recorder has no business request/receipt binding; correlate user-supplied IDs separately",
                            "Only hooked operations are counted; no completion, correction or benefit inferred from clicks"],
            "business_mutations": 0, "recorder_sessions_started": 0, "model_calls": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = checked(args.output)
    if not output.is_relative_to(checked(STATE)) or output.exists() or not output.parent.is_dir():
        raise ValueError("fresh exact output in the preflighted session03 directory required")
    report = audit()
    retain(output, report)
    print(json.dumps({key: report[key] for key in ("session_count", "human_declared_session_count", "all_receipt_chains_valid", "UNI_003_verified")}))
