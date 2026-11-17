"""Append verified development observations; no model dispatch or mutations."""
import hashlib
import argparse
import json
import math
import subprocess
import sys
import xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts"), str(ROOT / "services/api/src"), str(ROOT / "packages/synthetic/src")]
from service_stage6_workspace import STATE, destination, retain, checked

CODE = [
    "services/api/src/campus247/domain/service_request.py",
    "services/api/src/campus247/application/document_request/service_requests.py",
    "services/api/src/campus247/application/knowledge/operations.py",
    "services/api/src/campus247/infrastructure/repositories/sqlite_service_operations.py",
    "services/api/src/campus247/presentation/service_operations.py",
    "services/api/src/campus247/bootstrap/service_demo.py",
    "services/api/src/campus247/bootstrap/certificate_demo.py",
    "services/api/src/campus247/application/document_request/certificates.py",
    "apps/web/src/lib/data/api/service-gateway.ts",
    "apps/web/src/features/documents/ServiceWorkspace.tsx",
    "apps/web/src/features/knowledge/SourceOperations.tsx",
    "apps/web/src/features/documents/CertificateWorkspace.tsx",
    "apps/web/src/components/AppShell.tsx", "apps/web/src/app/chat/page.tsx",
    "apps/web/src/app/services/page.tsx", "apps/web/src/app/knowledge/sources/page.tsx",
    "apps/web/tsconfig.service-stage6-20261014.json", "tests/api/test_service_stage6.py",
    "apps/web/src/features/documents/ServiceWorkspace.test.tsx", "apps/web/src/features/knowledge/SourceOperations.test.tsx",
    "scripts/service_stage6_workspace.py", "scripts/run_service_stage6.py", "scripts/launch_service_stage6.py",
    "scripts/prepare_service_stage6_frontend.py", "scripts/run_service_stage6_restart_worker.py",
    "scripts/verify_service_stage6_restart.py", "scripts/evaluate_service_stage6_live.py",
    "scripts/verify_service_stage6_delivery.py", "scripts/finalize_service_stage6_evidence.py",
    "docs/SERVICE_STAGE6_DELIVERY_20261014.md", "docs/SERVICE_STAGE6_RUNBOOK_20261014.md",
]


def read(name):
    return json.loads(destination(name).read_text(encoding="utf-8"))


def test_count(name):
    tree = ET.parse(destination(name))
    cases = tree.findall(".//testcase")
    if any(case.find("failure") is not None or case.find("error") is not None for case in cases):
        raise ValueError("failure cannot be reported as passing")
    return len(cases)


def main(ordinal="01"):
    verification = read("data-retention-readback-01.json")
    initial = read("live-preflight-01.json")
    after = verification["paid_after"]
    cases = []
    notes = [
        "Portal registration/bank payment,10working days from score announcement and oral/practical exception match retained PDF page61; current institutional applicability is unverified. Extra cancellation sentence is terse but present in that diagram.",
        "Oral/practical exclusion matches retained PDF page61; no LLM grade decision.",
        "No fee amount invented. Generic refusal lacks an explicit explanation that fee amount is missing, so completeness is partial.",
    ]
    for number, note in enumerate(notes, 1):
        r = read(f"live-case-{number:02d}-01.json"); turn = r["turn"]
        assert not turn["failure"] and turn["history_readback_equal"]
        assert all(s["hash_matches"] for s in turn["sources"])
        cases.append({"case": number, "conversation": r["conversation_id"], "artifact": f"live-case-{number:02d}-01.json",
            "response_class": turn["final"]["response_class"], "correctness": 2, "completeness": 1 if number == 3 else 2,
            "source_hash_checks": len(turn["sources"]), "history_equal": True, "provider_calls": turn["provider_calls"],
            "cost_usd_conservative": turn["conservative_cost_usd"], "latency_ms": turn["latency_ms"], "review_note": note})
    latencies = sorted(r["latency_ms"] for r in cases)
    live = {"cases": cases, "review": "Codex authored development questions and source review; not held-out/independent human assessment",
        "provider_calls_guidance": sum(r["provider_calls"] for r in cases), "guidance_system_errors": 0,
        "guidance_history_matches": 3, "guidance_source_hash_matches": 2,
        "latency_p50_ms_three_guidance_cases": latencies[math.ceil(len(latencies)*.5)-1],
        "latency_p95_ms_three_guidance_cases": latencies[math.ceil(len(latencies)*.95)-1],
        "browser_chat": verification["browser_chat"], "provider_calls_stage6_observed": after["calls"]-initial["paid"]["calls"],
        "cost_stage6_conservative_usd": str(Decimal(after["conservative_charged_usd"])-Decimal(initial["paid"]["conservative_charged_usd"])),
        "actual_invoice_usd": None, "total_paid_snapshot": after, "total_native_snapshot": verification["native_after"],
        "initial_runner_aggregation": {"exit_code": 1, "reason": "whole business list changed during concurrent browser/staff actions",
            "business_effect_attribution": "not_verified_in_that_campaign; raw3cases retained and never resent",
            "repair": "runner now retains before/after snapshots and reports concurrency as inconclusive; repaired code not replayed"},
        "new_writer": False, "unknown_reservations_unchanged": initial["paid"]["unsettled_attempts_retained"] == after["unsettled_attempts_retained"]}
    retain(f"live-source-review-{ordinal}.json", live)
    runtime = read("runtime-active-01.json")
    by_port = {r["Port"]: r for r in runtime}
    assert by_port[8003]["ProcessId"] == 5480 and by_port[8003]["ParentProcessId"] == 1888
    assert by_port[3003]["ProcessId"] == 23056 and by_port[3004]["ProcessId"] == 18312
    assert by_port[18081]["ProcessId"] == 21908 and by_port[18082]["ProcessId"] == 21908
    assert read("process-restart-01.json")["passed"] and read("frontend-build-02.json")["exit_code"] == 0
    status = subprocess.run(["git", "status", "--short"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    initial_status = read("initial-discovery-01.json")["git_status"]
    old_deleted = {line[3:] for line in initial_status.splitlines() if "D" in line[:2]}
    final_deleted = {line[3:] for line in status.stdout.splitlines() if "D" in line[:2]}
    assert old_deleted == final_deleted
    scoped_diff = subprocess.run(["git", "diff", "--check", "--", "apps/web/src/components/AppShell.tsx", "apps/web/src/app/chat/page.tsx"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert scoped_diff.returncode == 0
    code = [{"path": name, "sha256": hashlib.sha256(checked(ROOT/name).read_bytes()).hexdigest()} for name in CODE]
    artifacts = [{"path": p.name, "sha256": hashlib.sha256(checked(p, STATE).read_bytes()).hexdigest()}
        for p in sorted(STATE.iterdir()) if p.is_file() and p.suffix in {".json", ".xml", ".png"}]
    backend_reports = ["backend-tests-06.xml"] + (["backend-tests-07.xml"] if ordinal == "02" else [])
    retain(f"verification-manifest-{ordinal}.json", {"scope": "stage6 local/development demo implemented and verified in listed cases",
        "backend_passed": sum(test_count(name) for name in backend_reports), "backend_reports": backend_reports,
        "frontend_passed": test_count("frontend-tests-01.xml"),
        "staff_concurrency_scope": "two sessions of one signed officer viaHTTP; two distinct trusted server contexts with synthetic same-queue grants viaapplication service; app directory/tokens/grants unchanged",
        "production_build": "frontend02", "scoped_typescript": "passed", "scoped_ruff": "passed", "scoped_diff_check": "passed",
        "retention": "all prior business rows match backup; old READY5audit and HTML hash unchanged through8003/8004",
        "runtime": runtime, "existing_runtime_owners_preserved": True, "process_restart": "4newowned test workers; graceful lifecycle; no prior process stopped",
        "live": live, "code": code, "artifacts": artifacts, "git_status": status.stdout, "git_warnings": status.stderr,
        "preexisting_deleted_state_preserved": True,
        "retained_failures": ["pytest01/02 interrupted at sandbox socketpair; fixtures retained", "backend-tests05: invalid test directory, zero tests", "live runner aggregate concurrency mismatch", "first certificate readback assumed wrong owner; verified SV024 then reran read-only"],
        "limitations": ["Service intent/field collection is a deterministic demo adapter; live multi-agent RAG provides source guidance. LLMs cannot confirm/grade/sign/decide.",
            "Source operations support bounded UTF-8 text snapshots and reviewed manual renditions; automatic PDF/OCR ingestion is not newly implemented.",
            "Demo lexical candidates affect service guidance/eligibility snapshots. Retained official hybrid index and stage5 graph publication are separate and unchanged.",
            "Fee amount refusal is generic; browser RAG answer is partial for demo preparation, which has dedicated form guidance.",
            "No real school integration, payment, notification delivery, institutional review or production readiness claim.",
            "Full-project TS previously has4ByRoleOptions.exact errors; scoped TS/fresh build passed. Whole-workspace diffcheck has pre-existing globals.css EOF blank.",
            "Actual invoice, all-stage active/external wait/calendar effort remain unknown."]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--ordinal", choices=["01", "02"], default="01")
    main(parser.parse_args().ordinal)
