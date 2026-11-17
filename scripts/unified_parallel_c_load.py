"""Bounded local-fixture instrumentation, pending final dependency acceptance."""
import argparse
import json
import re
import sys
import time

sys.dont_write_bytecode = True
from unified_parallel_c_preserve import ROOT, STATE, checked, database_digest, manifest, retain
from unified_parallel_c_evaluate import CASES, distribution


def run(number, samples):
    if not 20 <= samples <= 32:
        raise ValueError("fixed bounded sample range20..32 required")
    sys.path[:0] = [str(ROOT), str(ROOT / "services/api/src"), str(ROOT / "packages/synthetic/src")]
    from campus247.bootstrap.unified_demo import create_unified_demo_app
    from campus247.domain.shared.values import generate_uuid7
    from fastapi.testclient import TestClient
    from tests.api.test_service_stage6 import login
    target = checked(STATE / "fixtures" / ("load-" + number))
    target.mkdir(exist_ok=False)
    business, actor = checked(target / "business.sqlite3"), checked(target / "actor.sqlite3")
    app = create_unified_demo_app(business, state_database=actor)
    source_before = manifest()
    measurements, outcomes = {"restore": [], "prepare": []}, []
    begin = time.monotonic()
    with TestClient(app) as client:
        headers = login(client)
        original = database_digest(business)
        for _ in range(samples):
            if time.monotonic() - begin > 15:
                break
            started = time.monotonic()
            restored = client.get("/v1/assistant/preferences", headers=headers)
            measurements["restore"].append((time.monotonic() - started) * 1000)
            case = CASES[0]
            started = time.monotonic()
            prepared = client.post("/v1/assistant/student:prepare", headers=headers,
                json={"goal": case["goal"], "workflow": case["workflow"], "statements": case["statements"], "operation_id": generate_uuid7()})
            measurements["prepare"].append((time.monotonic() - started) * 1000)
            body = prepared.json()
            outcomes.append(restored.status_code == prepared.status_code == 200 and body.get("effect") == "NONE"
                            and body.get("action_authority") == "none" and body.get("next_action") == "review_new_draft")
        unchanged = database_digest(business) == original
    elapsed = time.monotonic() - begin
    report = {"scope": "single-process sequential in-process synthetic fixture", "concurrency": 1,
              "bounds": {"samples_max": 32, "elapsed_admission_seconds_max": 15, "automatic_retries": 0},
              "requested_samples": samples, "observed_samples": len(outcomes), "duration_seconds": elapsed,
              "fixture_prepare_operations_per_second": len(outcomes) / elapsed,
              "latencies": {k: distribution(v) for k, v in measurements.items()},
              "valid_outcomes": sum(outcomes), "invalid_outcomes": len(outcomes) - sum(outcomes),
              "business_unchanged": unchanged, "source_stable": source_before == manifest(),
              "complete_to_business_receipt": {"n": 0, "p95_ms": None, "reason": "prepare-only; unobserved"},
              "queue_cache_faults": "unobserved; A036/038/B039/041/final043 checks pending",
              "model_cost_usd": None, "paid_dispatches": 0, "production_slo_verified": False,
              "UNI_046_acceptance": "pending full dependencies, concurrent queue/cache/fault/outcome measurements"}
    retain(target / "report.json", report)
    print(json.dumps(report))
    if not unchanged or not all(outcomes) or not outcomes:
        raise SystemExit(1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("number")
    parser.add_argument("--samples", type=int, default=24)
    args = parser.parse_args()
    if re.fullmatch(r"[0-9]{2}", args.number) is None:
        raise ValueError("fresh exact attempt required")
    run(args.number, args.samples)
