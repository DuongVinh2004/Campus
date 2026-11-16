"""Bounded fixture outcome/receipt instrumentation, no serving-runtime workload."""
import argparse
import json
import re
import sys
import time

sys.dont_write_bytecode = True
from unified_parallel_c_preserve import ROOT, STATE, checked, manifest, retain
from unified_parallel_c_evaluate import distribution


def run(number):
    sys.path[:0] = [str(ROOT), str(ROOT / "services/api/src"), str(ROOT / "packages/synthetic/src")]
    from fastapi.testclient import TestClient
    from campus247.bootstrap.unified_demo import create_unified_demo_app
    from tests.api.test_service_stage6 import sent, login, act, read
    from tests.unified_workflow13a.test_case_workflow import draft_body, post, prepare, preview, confirmation
    target = checked(STATE / "fixtures" / ("case-measure-" + number))
    target.mkdir(exist_ok=False)
    before = manifest()
    latencies = {"prepare_after_officer_review": [], "first_confirm_to_public_readback": [], "receipt_restore": []}
    results = []
    begin = time.monotonic()
    for index in range(3):
        if time.monotonic() - begin > 20:
            break
        fixture = checked(target / ("case-" + str(index)))
        fixture.mkdir(exist_ok=False)
        app = create_unified_demo_app(fixture / "business.sqlite3", state_database=fixture / "actor.sqlite3")
        with TestClient(app) as client:
            student, record, _ = sent(client)
            staff = login(client, "OF002")
            claimed = act(client, staff, record, "claim")
            assert claimed.status_code == 200
            record = claimed.json()["document_request"]
            body = draft_body(client, staff, record)
            started = time.monotonic()
            prepared = prepare(client, staff, body)
            latencies["prepare_after_officer_review"].append((time.monotonic() - started) * 1000)
            candidate = preview(client, staff, body, version=prepared["version"])
            started = time.monotonic()
            response = post(client, staff, ":confirm", confirmation(candidate))
            public = read(client, student, record["id"])
            latencies["first_confirm_to_public_readback"].append((time.monotonic() - started) * 1000)
            assert response.status_code == 200 and response.json()["state"] == "committed"
            assert public["status"] == "READY" and public["version"] == record["version"] + 1
            assert "PRIVATE SENTINEL" not in str(public)
            receipt_id = response.json()["receipt_id"]
            for _ in range(8):
                started = time.monotonic()
                restored = post(client, staff, "/receipt:read", {"client_id": candidate["client_id"]})
                latencies["receipt_restore"].append((time.monotonic() - started) * 1000)
                assert restored.status_code == 200 and restored.json()["receipt"]["receipt_id"] == receipt_id
            replay = post(client, staff, ":confirm", confirmation(candidate))
            assert replay.status_code == 200 and replay.json()["is_replay"]
            assert replay.json()["receipt_id"] == receipt_id
            assert read(client, student, record["id"]) == public
            results.append({"case": index, "state": "committed", "exactly_one_version_transition": True,
                            "receipt_readbacks": 8, "retry_duplicate_effect": False, "private_leak": False})
    report = {"scope": "new C synthetic per-case fixture; sequential in-process HTTP", "source_stable": before == manifest(),
              "bounds": {"first_commits_max": 3, "receipt_reads_per_case_max": 8, "admission_seconds_max": 20, "concurrency": 1},
              "latencies": {k: distribution(v) for k, v in latencies.items()}, "outcomes": results,
              "duration_seconds": time.monotonic() - begin, "model_cost_usd": None, "paid_provider_calls": 0,
              "queue_cache_fault_load": "not_measured_here; separate fault tests are correctness only",
              "acceptance": "UNI046 pending full workload/dependencies; UNI048 pending pilot/full rehearsal",
              "limitations": ["Only3 first commits: p95 unavailable", "24 warm receipt reads are clustered over3 cases, not24 independent user sessions",
                  "No production throughput/SLO, active-labor or user usefulness conclusion", "No distributed cross-store crash atomicity claim"]}
    retain(target / "report.json", report)
    print(json.dumps(report))
    if len(results) != 3:
        raise SystemExit(1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("number")
    args = parser.parse_args()
    if re.fullmatch(r"[0-9]{2}", args.number) is None:
        raise ValueError("fresh exact attempt required")
    run(args.number)
