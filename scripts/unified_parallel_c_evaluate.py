"""Prepare-only deterministic comparison harness; never a human usefulness claim."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import re
import sys
import time

sys.dont_write_bytecode = True
from unified_parallel_c_preserve import ROOT, STATE, checked, database_digest, manifest, retain

CASES = [
    {"id": "C-EVAL-01", "goal": "Xin giấy xác nhận sinh viên", "workflow": "STUDENT_CERTIFICATE",
     "statements": {"purpose": "Học bổng mô phỏng", "recipient": "Quỹ mô phỏng"}, "next_action": "review_new_draft"},
    {"id": "C-EVAL-02", "goal": "Tôi muốn phúc khảo", "workflow": "GRADE_APPEAL",
     "statements": {"course_record_id": "demo-student1-CS101", "reason": "Đối chiếu bài mô phỏng"}, "next_action": "review_new_draft"},
    {"id": "C-EVAL-03", "goal": "Tôi cần một giấy để giải quyết việc", "workflow": None,
     "statements": {}, "next_action": "clarify"},
    {"id": "C-EVAL-04", "goal": "giấy xác nhận và phúc khảo", "workflow": None,
     "statements": {}, "next_action": "clarify"},
]


def distribution(samples):
    if not samples:
        return {"n": 0, "p95_ms": None, "reason": "unobserved"}
    values = sorted(samples)
    return {"n": len(values), "min_ms": values[0], "max_ms": values[-1],
            "p95_ms": values[max(0, math.ceil(.95 * len(values)) - 1)] if len(values) >= 20 else None,
            "reason": "bounded fixture sample; no production extrapolation" if len(values) >= 20 else "sample below 20; no p95 claim"}


def score(expected, observed):
    checks = {key: key in observed and type(observed[key]) is type(value) and observed[key] == value
              for key, value in expected.items()}
    return {"all_material_checks_passed": all(checks.values()), "checks": checks}


def prepare(number):
    target = checked(STATE / "fixtures" / ("evaluation-" + number + ".json"))
    retain(target, {"protocol": "unified-c-evaluation.v1", "cases": CASES,
        "source": "Local synthetic documented goals; workflow definitions and form validation are current application sources",
        "source_hashes": manifest(), "gold_is_model_output": False, "modes": ["simple rules", "actual student preparation", "selected multi pending"],
        "staff_cases_pending": ["UNI-031 outcome draft/recipient/source binding", "UNI-035 role projection and supplement round trip"],
        "metrics": ["workflow correctness", "next_action correctness", "coverage", "business write count", "latency_ms", "actual dispatch metadata"],
        "human_review": "pending qualified reviewer and blind matched subsets; not run by automation",
        "cost": {"paid_calls": 0, "observed_model_usd": None}, "acceptance": "pending actual staff/multi comparisons and human evidence"})
    print(str(target))


def smoke(number):
    sys.path[:0] = [str(ROOT), str(ROOT / "services/api/src"), str(ROOT / "packages/synthetic/src")]
    from campus247.application.document_request.assistant import understand_student_goal
    from campus247.bootstrap.unified_demo import create_unified_demo_app
    from campus247.domain.shared.values import generate_uuid7
    from fastapi.testclient import TestClient
    from tests.api.test_service_stage6 import login
    target = checked(STATE / "fixtures" / ("evaluation-smoke-" + number))
    target.mkdir(exist_ok=False)
    business, actor = checked(target / "business.sqlite3"), checked(target / "actor.sqlite3")
    source_before = manifest()
    app = create_unified_demo_app(business, state_database=actor)
    results = []
    with TestClient(app) as client:
        headers = login(client)
        before = database_digest(business)
        for case in CASES:
            start = time.monotonic()
            simple = understand_student_goal(case["goal"])
            simple_ms = (time.monotonic() - start) * 1000
            request = {"goal": case["goal"], "workflow": case["workflow"], "statements": case["statements"], "operation_id": generate_uuid7()}
            start = time.monotonic()
            response = client.post("/v1/assistant/student:prepare", headers=headers, json=request)
            elapsed = (time.monotonic() - start) * 1000
            body = response.json()
            observed = {"http_status": response.status_code, "workflow": body.get("intent", {}).get("workflow"),
                        "next_action": body.get("next_action"), "effect": body.get("effect"),
                        "action_authority": body.get("action_authority"),
                        "clarifies_without_form": bool(body.get("intent", {}).get("clarification")) and body.get("form") is None
                            if case["workflow"] is None else True,
                        "confirmation_secret_absent": "confirmation_token" not in response.text}
            results.append({"case_id": case["id"], "simple": {"workflow": simple.workflow, "latency_ms": simple_ms,
                             "workflow_correct": simple.workflow == case["workflow"]},
                            "prepared": {**observed, "latency_ms": elapsed,
                             "score": score({"http_status": 200, "workflow": case["workflow"], "next_action": case["next_action"],
                                 "effect": "NONE", "action_authority": "none", "clarifies_without_form": True,
                                 "confirmation_secret_absent": True}, observed)},
                            "selected_multi": {"status": "not_run", "reason": "separate matched staff/selected-multi evidence pending"}})
        unchanged = database_digest(business) == before
    report = {"captured_at": datetime.now(timezone.utc).isoformat(), "mode": "prepare_only_synthetic_smoke", "results": results,
              "business_unchanged": unchanged, "source_stable": source_before == manifest(),
              "latency": distribution([row["prepared"]["latency_ms"] for row in results]),
              "model_cost_usd": None, "paid_calls": 0, "human_usefulness_verified": False,
              "UNI_045_acceptance": "pending", "limitations": ["4 cases do not replace 130-case baseline or matched multi comparison",
                  "no human/expert review", "not a serving-runtime benchmark", "no staff UNI-031/035 acceptance"]}
    retain(target / "report.json", report)
    print(json.dumps(report, ensure_ascii=False))
    if not unchanged or not all(row["prepared"]["score"]["all_material_checks_passed"] for row in results):
        raise SystemExit(1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["prepare", "smoke"])
    parser.add_argument("number")
    args = parser.parse_args()
    if re.fullmatch(r"[0-9]{2}", args.number) is None:
        raise ValueError("fresh exact attempt required")
    {"prepare": prepare, "smoke": smoke}[args.stage](args.number)
