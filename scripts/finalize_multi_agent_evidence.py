"""Exclusive verification manifest with per-case verdicts, fingerprints and limits."""
from __future__ import annotations

import ast
import hashlib
import json
import sqlite3
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from multi_agent_workspace import ROOT, STATE, checked, retain

sys.path[:0] = [str(ROOT / "services/api/src"), str(ROOT)]
from campus247.application.multi_agent.contracts import MultiAgentPolicy
from evaluate_certificate_rag import paid_snapshot, native_snapshot


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = checked(STATE / "verification-manifest-01.json", STATE)
    if output.exists():
        raise FileExistsError("retain prior manifest; choose a new name")
    paths = [
        "services/api/src/campus247/agent/graph.py", "services/api/src/campus247/agent/state.py",
        "services/api/src/campus247/agent/multi_rag.py", "services/api/src/campus247/bootstrap/app.py",
        "services/api/src/campus247/bootstrap/certificate_demo.py",
        "services/api/src/campus247/application/conversation/followup.py",
        "services/api/src/campus247/application/conversation/messages.py",
        "services/api/src/campus247/application/conversation/read.py",
        "services/api/src/campus247/application/conversation/stream_result.py",
        "services/api/src/campus247/infrastructure/repositories/sqlite_agent_runs.py",
        "services/api/src/campus247/presentation/agent_runs.py", "services/api/src/campus247/presentation/chat.py",
        "services/api/src/campus247/presentation/identity.py",
        "apps/web/src/app/chat/page.tsx", "apps/web/src/features/chat/ChatPanel.tsx", "apps/web/src/features/chat/sse.ts",
        "contracts/json-schema/chat/stream-event.schema.json", "tests/unit/agent/test_multi_agent_integrated.py",
        "tests/unit/agent/test_multi_agent_admission.py", "tests/api/test_multi_agent_api.py",
        "apps/web/src/features/chat/agent-progress.test.tsx", "apps/web/src/app/chat/page.resume.test.tsx",
        "scripts/multi_agent_workspace.py", "scripts/run_multi_agent.py", "scripts/launch_multi_agent.py",
        "scripts/prepare_multi_agent_frontend.py", "scripts/evaluate_multi_agent_sources.py",
        "scripts/verify_multi_agent_runtime.py", "scripts/finalize_multi_agent_evidence.py",
        "docs/MULTI_AGENT_INTEGRATED_RUNBOOK_20261013.md", "docs/MULTI_AGENT_INTEGRATED_DELIVERY_20261013.md",
    ]
    paths.extend(str(p.relative_to(ROOT)).replace("\\", "/") for folder in ("single_agent", "multi_agent")
                 for p in (ROOT / f"services/api/src/campus247/application/{folder}").glob("*.py"))
    code = []
    for name in sorted(set(paths)):
        path = checked(ROOT / name)
        if path.suffix == ".py":
            ast.parse(path.read_text(encoding="utf-8"))
        code.append({"path": name, "sha256": sha(path), "python_ast_checked": path.suffix == ".py"})
    tests = []
    for path in sorted(STATE.glob("backend-*.xml")):
        document = ET.parse(path).getroot()
        cases = []
        for case in document.iter("testcase"):
            failure = case.find("failure")
            error = case.find("error")
            skipped = case.find("skipped")
            cases.append({"name": case.attrib["name"], "class": case.attrib.get("classname"),
                "duration_seconds": float(case.attrib.get("time", 0)),
                "verdict": "failed" if failure is not None or error is not None else "skipped" if skipped is not None else "passed"})
        tests.append({"artifact": path.name, "sha256": sha(path), "cases": cases,
            "passed": sum(case["verdict"] == "passed" for case in cases),
            "failed": sum(case["verdict"] == "failed" for case in cases),
            "exit_code": 1 if any(case["verdict"] == "failed" for case in cases) else 0,
            "method": "offline/scripted models unless explicit actual canonical source readback testcase"})
    frontend = []
    for path in sorted(STATE.glob("frontend-*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        if "testResults" in value:
            frontend.append({"artifact": path.name, "sha256": sha(path), "passed": value["numPassedTests"],
                "failed": value["numFailedTests"], "cases": [{"name": case["fullName"], "verdict": case["status"]}
                    for test_file in value["testResults"] for case in test_file["assertionResults"]]})
        elif "exit_code" in value:
            frontend.append({"artifact": path.name, "sha256": sha(path), "exit_code": value["exit_code"], "command": value.get("command")})
    # Safe structured trace from the dedicated actual-source corrective test.
    db = next((STATE / "pytest-13").rglob("real-source-runs.sqlite3"))
    checked(db, STATE)
    with sqlite3.connect(db.resolve().as_uri()+"?mode=ro", uri=True) as conn:
        trace = [json.loads(row[0]) for row in conn.execute("SELECT record FROM agent_event ORDER BY run_id,seq")]
        task_rows = [{"task_id": row[0], "status": row[1], "record": json.loads(row[2])}
            for row in conn.execute("SELECT id,status,record FROM agent_task ORDER BY id")]
    corrective_path = checked(STATE / "corrective-source-trace-01.json", STATE)
    retain(corrective_path, {"mode": "actual_lexical_search_and_original_source_reader_with_scripted_agents",
        "fresh_live_generation": False, "trace": trace, "tasks": task_rows,
        "paid_provider_calls": 0, "native_inference": 0,
        "limits": "Scripted planner/generation/verdict token usage is not live provider telemetry or quality."})
    preservation = []
    stage1 = ROOT / "infra/local/certificate-stage1-20261013-01"
    for name in ("backend-04.xml", "frontend-tests-03.json", "frontend-build-03.json", "process-restart-01.json",
                 "delivery-readback-01.json", "generation-review-03.json", "verification-manifest-01.json"):
        path = checked(stage1 / name)
        preservation.append({"path": str(path.relative_to(ROOT)), "sha256": sha(path), "task_writes": 0})
    guards = [ROOT / "infra/local/rag-fixture/m1_source_guard_20261012_58-repair1.mjs",
              STATE / "frontend02/acceptance-20261012-58-frontend-repair1-local-repair2/preserve-build.mjs"]
    assert sha(guards[0]) == sha(guards[1]) == "8f0886295da2214205cf257dd9e1d9476993ed1a7fb0ac67434909fa4af2eae6"
    git = subprocess.run(["git", "--no-optional-locks", "status", "--porcelain=v1"], cwd=ROOT,
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    diff = subprocess.run(["git", "--no-optional-locks", "diff", "--name-only"], cwd=ROOT,
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    now = datetime.now(timezone.utc)
    start = datetime(2026, 10, 13, 11, 56, 33, tzinfo=timezone.utc)
    sources = json.loads((STATE / "source-regression-01.json").read_text(encoding="utf-8"))
    paid, native = paid_snapshot(), native_snapshot()
    artifacts = [{"path": str(path.relative_to(STATE)), "sha256": sha(path)} for path in sorted(STATE.glob("*.json"))
                 if path != output]
    retain(output, {"stage": "integrated_2_3_4", "implementation": "local_guarded_available", "acceptance": "not_verified_live_quality",
        "comparison_required": False, "created_at_utc": now.isoformat(), "workspace": str(ROOT),
        "code": code, "policy": __import__("dataclasses").asdict(MultiAgentPolicy()),
        "policy_fingerprint": MultiAgentPolicy().fingerprint, "index_fingerprint": sources["index_fingerprint"],
        "dataset_sha256": sources["dataset_sha256"], "test_reports": tests, "frontend_reports": frontend,
        "preserved_stage1_evidence": preservation, "guard_sha256": sha(guards[0]), "artifacts": artifacts,
        "paid_snapshot": paid, "native_snapshot": native, "task_live_provider_calls": 0, "task_native_inference": 0,
        "live_generation": {"status": "not_verified", "reason": "paid/native headroom insufficient; no second writer/cap reset",
            "minimum_simple_control_flow_model_calls": 8, "profile_max_model_calls": 12,
            "paid_calls_remaining": paid["call_cap"]-paid["calls"],
            "native_inference_remaining": native["caps"]["inference"]-native["counts"]["inference"],
            "cost_usd": None, "latency_ms": None, "answers_correctness": None, "answers_completeness": None},
        "source_regression": {"mode": sources["mode"], "source_covered": sources["source_covered"], "source_cases": sources["source_cases"],
            "misses": [row["id"] for row in sources["results"] if row["required_source_coverage"] is False]},
        "time": {"started_at_utc": start.isoformat(), "finished_at_utc": now.isoformat(),
            "calendar_elapsed_minutes": round((now-start).total_seconds()/60, 2),
            "active_elapsed_minutes": None, "external_wait_minutes": None,
            "measurement_basis": "Tool UTC observations; no complete separate active/wait telemetry. No calendar-to-active inference."},
        "git": {"status_exit": git.returncode, "status": git.stdout, "warnings": git.stderr,
            "diff_exit": diff.returncode, "diff_names": diff.stdout,
            "scope_note": "Many dirty/untracked/deleted changes predate this task. Whole HEAD diff is not attributable to this task. No cleanup/staging/commit/push or protection edits."},
        "limits": ["Scripted ports prove controls, not fresh live quality.", "Lexical source readback is not neural retrieval or answer correctness.",
            "Actual guarded HTTP/UI restart preserved history and stage1 result; no provider-in-flight crash was executed.",
            "Current app requires resource and single-writer ownership authority before live activation."]})
    print(json.dumps({"manifest": str(output), "acceptance": "not_verified_live_quality",
                      "source_corrective_trace_saved": True, "guard_preserved": True}))


if __name__ == "__main__":
    main()
