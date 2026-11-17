"""Freeze current evidence without rewriting any run, test or ledger artifact."""
import argparse
import ast
import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from multi_agent_workspace import ROOT, STATE, checked, retain
from multi_agent_live_resources import paid_view, native_view


def sha(path):
    value = hashlib.sha256()
    with checked(path).open("rb") as source:
        for block in iter(lambda: source.read(1_048_576), b""):
            value.update(block)
    return value.hexdigest()


def main(output, quality):
    output, quality = checked(output, STATE), checked(quality, STATE)
    if output.exists():
        raise FileExistsError("retain previous manifest")
    baseline = json.loads((STATE / "verification-manifest-01.json").read_text("utf-8"))
    review = json.loads(quality.read_text("utf-8"))
    names = {entry["path"] for entry in baseline["code"]}
    names.update([
        "scripts/evaluate_multi_agent_live.py", "scripts/multi_agent_live_resources.py",
        "scripts/run_public_rag.py", "scripts/run_public_multi_proxy.py", "scripts/serve_rag_models.py",
        "scripts/public_rag_retrieval.py", "scripts/launch_multi_agent_live.py", "scripts/launch_multi_agent.py",
        "scripts/probe_multi_agent_live_crash.py", "scripts/verify_multi_agent_live_runtime.py",
        "scripts/probe_multi_agent_corrective_live.py", "tests/unit/conversation/test_stream_result.py",
        "scripts/finalize_multi_agent_live_evidence.py",
        "services/api/src/campus247/infrastructure/streaming_asgi.py",
        "services/api/src/campus247/infrastructure/llm/openai_adapter.py",
        "services/api/src/campus247/infrastructure/llm/egress_policy.py",
        "services/api/src/campus247/application/retrieval/semantic_support.py",
        "services/api/src/campus247/application/retrieval/procedure_scope.py",
        "services/api/src/campus247/application/retrieval/question_scope.py",
        "services/api/src/campus247/application/multi_agent/query_aliases.py",
        "tests/unit/retrieval/test_semantic_question_scope.py",
        "tests/unit/retrieval/test_procedure_scope.py", "tests/unit/agent/test_natural_public_questions.py",
        "services/api/src/campus247/presentation/certificates.py",
        "services/api/src/campus247/agent/state.py",
        "services/api/src/campus247/agent/nodes/definitions.py",
        "services/api/src/campus247/agent/nodes/intent.py",
        "services/api/src/campus247/application/conversation/stream_result.py",
        "services/api/src/campus247/application/conversation/followup.py",
        "services/api/src/campus247/application/conversation/understanding.py",
        "tests/api/test_certificate_stage1.py", "tests/unit/conversation/test_followup_question_m2.py",
        "tests/contract/ai/test_deepseek_non_thinking.py", "tests/contract/ai/test_openai_adapter_limits.py",
        "tests/evals/test_multi_agent_live_runner.py", "tests/evals/test_multi_agent_resources.py",
        "tests/unit/agent/test_streaming_asgi.py", "tests/api/test_citation_source.py",
        "docs/MULTI_AGENT_LIVE_RUNBOOK_20261013.md", "docs/MULTI_AGENT_LIVE_DELIVERY_20261013.md",
        "docs/MULTI_AGENT_JSON_TOOL_PROPOSAL_20261013.md",
        "docs/MULTI_AGENT_STAGE5_HANDOFF_20261014.md",
    ])
    code = []
    for name in sorted(names):
        path = checked(ROOT / name)
        if path.suffix == ".py":
            ast.parse(path.read_text("utf-8"))
        code.append({"path": name, "sha256": sha(path), "python_ast_checked": path.suffix == ".py"})
    # Overlapping test runs are retained; unique latest testcase results are
    # reported separately rather than summing reruns into a success count.
    tests, latest = [], {}
    for path in sorted(STATE.glob("backend-*.xml")):
        root = ET.parse(path).getroot()
        suite = next(root.iter("testsuite"))
        rows = []
        for case in root.iter("testcase"):
            verdict = "failed" if case.find("failure") is not None or case.find("error") is not None else (
                "skipped" if case.find("skipped") is not None else "passed")
            row = {"id": case.attrib.get("classname", "")+"::"+case.attrib["name"], "verdict": verdict}
            rows.append(row)
            latest[row["id"]] = {**row, "artifact": path.name}
        tests.append({"artifact": path.name, "sha256": sha(path), "tests": int(suite.attrib["tests"]),
            "failures": int(suite.attrib["failures"]), "errors": int(suite.attrib["errors"]),
            "skipped": int(suite.attrib["skipped"]), "duration_seconds": float(suite.attrib["time"]),
            "exit_code_inferred_from_junit": 1 if any(r["verdict"] == "failed" for r in rows) else 0})
    preservation = []
    for entry in baseline["preserved_stage1_evidence"]:
        actual = sha(ROOT / entry["path"])
        assert actual == entry["sha256"]
        preservation.append({**entry, "unchanged_from_guarded_handoff": True})
    guard = checked(ROOT / "infra/local/rag-fixture/m1_source_guard_20261012_58-repair1.mjs")
    assert sha(guard) == baseline["guard_sha256"]
    dataset = checked(ROOT / "evals/datasets/certificate-development-20261013.json")
    assert sha(dataset) == baseline["dataset_sha256"]
    index = checked(ROOT / f"infra/local/rag-advanced-20261013/index-{baseline['index_fingerprint']}.json")
    # Compare unchanged frontend code with the prior successful build/test
    # bindings; no redundant build is claimed for backend-only changes.
    frontend_unchanged = all(sha(ROOT / entry["path"]) == entry["sha256"] for entry in baseline["code"]
                             if entry["path"].startswith("apps/web/"))
    artifacts = [{"path": path.name, "sha256": sha(path)} for path in sorted(STATE.iterdir())
                 if path.is_file() and path.suffix in {".json", ".xml", ".jpg"} and path != output]
    sys.path.insert(0, str(ROOT / "services/api/src"))
    from campus247.application.multi_agent.contracts import MultiAgentPolicy
    policy = MultiAgentPolicy()
    auth = json.loads((STATE / "resource-authorization-02.json").read_text("utf-8"))
    paid, native = paid_view(), native_view()
    now = datetime.now(timezone.utc)
    start = datetime(2026, 10, 13, 11, 56, 33, tzinfo=timezone.utc)
    turn_start = datetime(2026, 10, 13, 13, 43, 49, tzinfo=timezone.utc)
    git = subprocess.run(["git", "--no-optional-locks", "status", "--porcelain=v1"], cwd=ROOT,
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    diff = subprocess.run(["git", "--no-optional-locks", "diff", "--name-only"], cwd=ROOT,
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    retain(output, {"stage": "integrated_2_3_4", "implementation": "local_live_available",
        "acceptance": review["acceptance"], "comparison_required": False, "created_at_utc": now.isoformat(),
        "workspace": str(ROOT), "code": code, "policy": asdict(policy), "policy_fingerprint": policy.fingerprint,
        "index_fingerprint": baseline["index_fingerprint"], "index_sha256": sha(index), "dataset_sha256": sha(dataset),
        "backend_reports": tests, "unique_latest_testcases": list(latest.values()),
        "unique_latest_passed": sum(r["verdict"] == "passed" for r in latest.values()),
        "unique_latest_failed": [r for r in latest.values() if r["verdict"] == "failed"],
        "frontend_unchanged_from_prior_build": frontend_unchanged,
        "frontend_evidence": {"tests": "frontend-04.json", "build": "frontend-build-02.json"},
        "preserved_stage1_evidence": preservation, "guard_sha256": sha(guard), "artifacts": artifacts,
        "quality_review": {"path": quality.name, "sha256": sha(quality), "summary": review["summary"],
            "assessor": review["assessor"], "independent_human_review": False, "split": "development"},
        "paid_snapshot": paid, "native_snapshot": native,
        "calls_since_authorized_transition": paid["calls"]-auth["paid_before"]["calls"],
        "cost_basis": "conservative cumulative reservation ledger; actual invoice unknown",
        "time": {"task_started_at_utc": start.isoformat(), "continuation_started_at_utc": turn_start.isoformat(),
            "finished_at_utc": now.isoformat(), "task_calendar_minutes": round((now-start).total_seconds()/60, 2),
            "continuation_calendar_minutes": round((now-turn_start).total_seconds()/60, 2),
            "active_minutes": None, "external_wait_minutes": None, "calendar_is_not_active_time": True},
        "git": {"status_exit": git.returncode, "status": git.stdout, "warnings": git.stderr,
            "diff_exit": diff.returncode, "diff_names": diff.stdout,
            "scope_note": "Pre-existing dirty, untracked and deleted state retained. Entire HEAD diff is not attributable to this task. No cleanup, staging, commit, push or destructive data operation."}})
    print(json.dumps({"manifest": str(output), "acceptance": review["acceptance"], "frontend_unchanged": frontend_unchanged}))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--quality", type=Path, required=True)
    args = parser.parse_args()
    main(args.output, args.quality)
