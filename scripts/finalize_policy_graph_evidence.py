"""Exclusive stage5 manifest from completed reports; no runtime or provider actions."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree

from build_policy_graph import ROOT, destination

CODE = (
    "services/api/src/campus247/domain/policy_graph.py",
    "services/api/src/campus247/application/policy_graph/service.py",
    "services/api/src/campus247/application/policy_graph/source_mapping.py",
    "services/api/src/campus247/application/policy_graph/extraction.py",
    "services/api/src/campus247/infrastructure/repositories/sqlite_policy_graph.py",
    "services/api/src/campus247/presentation/policy_graph.py",
    "services/api/src/campus247/bootstrap/app.py",
    "services/api/src/campus247/bootstrap/certificate_demo.py",
    "services/api/src/campus247/agent/multi_rag.py",
    "services/api/src/campus247/application/multi_agent/orchestrator.py",
    "services/api/src/campus247/application/multi_agent/contracts.py",
    "services/api/src/campus247/infrastructure/retrieval/public_hybrid.py",
    "scripts/build_policy_graph.py", "scripts/verify_policy_graph.py",
    "scripts/evaluate_policy_graph_live.py", "scripts/run_multi_agent.py", "scripts/launch_multi_agent_live.py",
    "apps/web/src/app/knowledge/policy-graph/page.tsx",
    "apps/web/src/features/knowledge/PolicyGraphReview.tsx",
    "apps/web/src/features/documents/CertificateWorkspace.tsx",
    "apps/web/src/features/knowledge/policy-graph.test-setup.ts",
    "apps/web/vitest.policy-graph.config.ts", "apps/web/tsconfig.policy-graph-20261014.json",
    "evals/datasets/policy-graph-development-20261014.json",
    "docs/POLICY_GRAPH_STAGE5_DELIVERY_20261014.md", "docs/POLICY_GRAPH_STAGE5_RUNBOOK_20261014.md",
)


def summarize(paths):
    cases = {}
    for name in paths:
        tree = ElementTree.parse(destination(name))
        for case in tree.iter("testcase"):
            key = (case.get("classname"), case.get("name"))
            cases[key] = "failed" if case.find("failure") is not None or case.find("error") is not None else "skipped" if case.find("skipped") is not None else "passed"
    return {"distinct_cases": len(cases), **{status: sum(v == status for v in cases.values()) for status in ("passed", "failed", "skipped")}}


def main():
    paths = ["build-01.json", "source-verification-02.json", "tests-04.xml", "tests-05.xml",
        "frontend-tests-02.xml", "frontend-tests-03.xml", "frontend-tests-04.xml", "live-preflight-01.json"]
    source = json.loads(destination("source-verification-02.json").read_text(encoding="utf-8"))
    preflight = json.loads(destination("live-preflight-01.json").read_text(encoding="utf-8"))
    backend = summarize(("tests-04.xml", "tests-05.xml"))
    frontend = summarize(("frontend-tests-04.xml",))
    if backend["failed"] or frontend["failed"] or source["failed"] or source["validation_issues"]:
        raise ValueError("verification failures must remain explicit")
    report = {"at": datetime.now(timezone(timedelta(hours=7))).isoformat(), "timezone": "Asia/Bangkok",
        "status": "implemented_offline_verified_live_not_verified", "backend": backend, "frontend": frontend,
        "source_cases": {"passed": len(source["cases"]), "failed": source["failed"]},
        "graph_snapshot": source["graph_snapshot"], "new_provider_calls": source["provider_calls_delta"],
        "new_native_counts": source["native_delta"], "conservative_new_provider_cost_usd": source["conservative_provider_cost_delta_usd"],
        "live_admitted": preflight["admitted"], "call_extension_applied": False,
        "live_query_cases_not_verified": 12, "live_extraction_cases_not_verified": 2,
        "runtime_transition_executed": False, "new_paid_writer": False,
        "stage1_business_database_mutated": False, "retained_history_database_mutated": False,
        "source_bytes_or_index_mutated": False, "independent_human_assessment": False, "production_readiness": "not_verified",
        "time": {"active_Codex_ms": None, "external_wait_ms": None, "calendar_ms": None,
            "source_verification_elapsed_ms": source["elapsed_ms"], "meaning": "unknown fields were not continuously instrumented"},
        "limitations": ["live headroom below admission", "legal dates unknown", "detailed certificate form version unknown",
            "phuc-khao multi-column OCR interpretation not verified", "active frontend graph build/browser QA not verified",
            "full-project TypeScript four pre-existing AppShell.test.tsx ByRoleOptions.exact errors"],
        "prior_attempts": {"default_sandbox_build_and_backend": "aborted_not_verified",
            "frontend_localStorage": "three failed runs retained in terminal/XML; final scoped harness passed"},
        "artifacts": {name: hashlib.sha256(destination(name).read_bytes()).hexdigest() for name in paths},
        "code_and_docs": {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in CODE}}
    with destination("verification-manifest-01.json").open("x", encoding="utf-8") as out:
        json.dump(report, out, indent=2, ensure_ascii=False)
    print(json.dumps({"status": report["status"], "backend": backend, "frontend": frontend,
        "source_cases": report["source_cases"], "new_provider_calls": report["new_provider_calls"]}))


if __name__ == "__main__":
    main()
