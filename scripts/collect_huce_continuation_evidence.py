"""Append-only evidence for this session's synthetic temporary conversation."""
import argparse
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from huce_source_registry import checked, save, norm

CONVERSATION = "01a15a32-a304-782b-96a8-01f4f6bd4d52"
WITHDRAWAL_CONVERSATION = "01a15a60-28cd-7872-bc4b-2a166fed79c1"
OUTPUT = ROOT / ".tooling/huce-continuation-20261020-01"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", choices=("before-units", "after-units", "final"), required=True)
    args = parser.parse_args()
    runtime = checked(ROOT / ".tooling/campus-single-entry-20261015-01/runtime")
    cases, failures = [], []
    with sqlite3.connect((runtime / "coordination.sqlite3").as_uri() + "?mode=ro", uri=True) as connection:
        for run_id, status, encoded in connection.execute("SELECT id,status,record FROM agent_run WHERE conversation IN (?,?) ORDER BY rowid", (CONVERSATION, WITHDRAWAL_CONVERSATION)):
            record = json.loads(encoded)
            cases.append({"run_id": run_id, "status": status, "question": record.get("original_goal", record.get("goal")),
                          "final": record.get("final_result"), "errors": record.get("error_codes"),
                          "verification_requests": record.get("verification_requests"), "claim_attempts": record.get("claim_attempts"),
                          "usage": record.get("usage"), "snapshot": record.get("snapshot")})
        for run_id, status, encoded in connection.execute("SELECT id,status,record FROM agent_run ORDER BY rowid DESC LIMIT 500"):
            record = json.loads(encoded)
            question = record.get("original_goal", record.get("goal", ""))
            if not any(term in norm(question) for term in ("rut hoc phan", "bao luu")):
                continue
            events = [json.loads(row[0]) for row in connection.execute("SELECT record FROM agent_event WHERE run_id=? ORDER BY seq", (run_id,))]
            failures.append({"run_id": run_id, "status": status, "errors": record.get("error_codes"),
                "usage": record.get("usage"), "events": events,
                "evidence_refs": record.get("controller", {}).get("evidence_refs", [])})
            if len(failures) == 4:
                break
    consents = []
    with sqlite3.connect((runtime / "actor.sqlite3").as_uri() + "?mode=ro", uri=True) as connection:
        for purpose, version, encoded in connection.execute("SELECT key,version,record FROM unified_actor_state WHERE namespace='consent'"):
            record = json.loads(encoded)
            payload = record.get("payload", {})
            consents.append({"purpose": purpose, "version": version, "decision": payload.get("decision"),
                             "notice_version": payload.get("notice_version")})
    report = {"collected_at": datetime.now(UTC).isoformat(), "conversations": [CONVERSATION, WITHDRAWAL_CONVERSATION],
              "cases": cases, "historical_procedure_diagnostics": failures, "consents": consents,
              "limitations": ["Persisted runtime classes require manual content/source review", "UI captures are separate evidence"]}
    target = OUTPUT / ("e2e-" + args.label + "-" + datetime.now(UTC).strftime("%H%M%S%f") + ".json")
    save(target, report)
    print(json.dumps({"report": str(target), "cases": [{"question": c["question"], "status": c["status"],
        "response_class": (c.get("final") or {}).get("response_class"), "errors": c["errors"]} for c in cases],
        "consents": consents}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
