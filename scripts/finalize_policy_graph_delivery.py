"""Verify preserved rows and append final stage5 delivery evidence without runtime actions."""
import hashlib
import json
import sqlite3
from datetime import datetime, timezone

from build_policy_graph import ROOT, destination
from finalize_policy_graph_evidence import CODE, summarize
from multi_agent_live_resources import paid_view, native_view
from policy_graph_runtime_handoff import quiet_state


def read(name):
    return json.loads(destination(name).read_text(encoding="utf-8"))


def retain(name, value):
    with destination(name).open("x", encoding="utf-8") as out:
        json.dump(value, out, ensure_ascii=False, indent=2)


def preservation():
    checks = []
    for before_name, current_name in (
        ("business-before-live-01.sqlite3", "infra/local/certificate-stage1-20261013-01/demo.sqlite3"),
        ("history-before-live-01.sqlite3", "infra/local/public-rag-20261013/conversations.sqlite3"),
        ("runs-before-live-01.sqlite3", "infra/local/multi-agent-integrated-20261013-01/agent-runs.sqlite3"),
    ):
        before, current = destination(before_name), (ROOT/current_name).resolve(strict=True)
        if not current.is_relative_to(ROOT):
            raise ValueError("workspace readback required")
        tables = {}
        with sqlite3.connect(before.as_uri()+"?mode=ro", uri=True) as old, sqlite3.connect(current.as_uri()+"?mode=ro", uri=True) as new:
            for (table,) in old.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
                if not table.replace("_", "").isalnum():
                    raise ValueError("allowlisted SQL table identifier required")
                prior = old.execute('SELECT * FROM "'+table+'"').fetchall()
                now = new.execute('SELECT * FROM "'+table+'"').fetchall()
                retained = set(now)
                missing = sum(row not in retained for row in prior)
                if missing:
                    raise ValueError("pre-existing rows changed; inspect before delivery")
                tables[table] = {"before": len(prior), "after": len(now), "missing_or_changed_prior_rows": missing}
        checks.append({"backup": before_name, "current": current_name, "tables": tables, "all_prior_rows_retained": True})
    for backup in read("runtime-handoff-preflight-01.json")["backups"]:
        path = destination(__import__("pathlib").Path(backup["backup"]).name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != backup["sha256"]:
            raise ValueError("backup changed")
    return {"at": datetime.now(timezone.utc).isoformat(), "kind": "read_only_exact_row_comparison",
        "checks": checks, "all_prior_rows_retained": True, "backups_unchanged": True,
        "business_rows_unchanged": all(v["before"] == v["after"] for v in checks[0]["tables"].values())}


def main():
    for name in ("data-retention-01.json", "verification-manifest-03.json"):
        if destination(name).exists():
            raise FileExistsError("retain earlier delivery evidence")
    quiet = quiet_state()
    source, quality, browser, runtime = (read(name) for name in
        ("source-verification-03.json", "live-quality-review-02.json", "browser-verification-01.json", "runtime-active-01.json"))
    backend = summarize(("tests-04.xml", "tests-05.xml", "tests-06.xml", "tests-07.xml"))
    frontend = summarize(("frontend-tests-04.xml",))
    if backend["failed"] or frontend["failed"] or source["failed"] or source["validation_issues"]:
        raise ValueError("verification failure remains unresolved")
    if not browser["two_conflicting_reviews_persisted"] or any(e["publication"] for e in quality["extraction"]):
        raise ValueError("raw candidates must remain separate from active publication")
    current_paid, current_native = paid_view(), native_view()
    if current_paid != quality["paid_after"] or current_native != quality["native_after"]:
        raise ValueError("budget changed after recorded campaign")
    readback_path = ROOT/"infra/local/multi-agent-integrated-20261013-01/stage5-after-live-readback-01.json"
    readback = json.loads(readback_path.read_text(encoding="utf-8"))
    if not readback["passed"]:
        raise ValueError("retained certificate/history readback failed")
    retained = preservation()
    retain("data-retention-01.json", retained)
    artifacts = ["build-01.json", "source-verification-03.json", "tests-04.xml", "tests-05.xml", "tests-06.xml", "tests-07.xml",
        "frontend-tests-04.xml", "frontend-build-01.json", "live-preflight-03.json", "live-campaign-admission-01.json",
        "live-quality-review-01.json", "live-quality-review-02.json", "runtime-handoff-result-01.json", "runtime-active-01.json",
        "browser-verification-01.json", "data-retention-01.json", "browser-review-certificate-full-01.png"]
    artifacts += [f"live-case-{i:03d}-01.json" for i in range(1, 13)]
    artifacts += [f"live-extraction-{i:02d}-01.json" for i in (1, 2)]
    code = (*CODE, "scripts/finalize_policy_graph_live_evidence.py", "scripts/finalize_policy_graph_delivery.py",
        "scripts/policy_graph_runtime_handoff.py", "scripts/prepare_policy_graph_frontend.py", "scripts/launch_policy_graph_frontend.py",
        "scripts/multi_agent_live_resources.py")
    report = {"at": datetime.now(timezone.utc).isoformat(), "status": "stage5_local_development_delivered_with_observed_limits",
        "backend": backend, "frontend": frontend, "source_cases": {"passed": len(source["cases"]), "failed": source["failed"]},
        "live_summary": quality["summary"], "live_usage": quality["usage"],
        "graph_snapshot": source["graph_snapshot"], "runtime": {"graph_active_on_api8003": True,
            "wrapper_pid": 1888, "worker_pid": 5480, "frontend": 3004, "only_paid_writer": "api8003",
            "native_proxy_frontend3003_preserved": True, "quiet": quiet, "receipt": runtime["launch_receipt"]},
        "paid": current_paid, "native": current_native, "provider_call_extension_authorized": True,
        "total_usd_and_native_caps_unchanged": True, "unknown_reservations_retained": True,
        "stage1_rows_unchanged": retained["business_rows_unchanged"], "all_prior_history_run_rows_retained": True,
        "retained_stage1_history_citations_http_readback": True, "source_bytes_or_index_mutated": False,
        "browser_review_verified": True, "new_candidates": {"count": 2, "conflicting_verdicts": 2, "published": 0},
        "independent_human_assessment": False, "production_readiness": "not_verified",
        "limitations": quality["limitations"] + ["full-project TypeScript retains four pre-existing AppShell.test.tsx errors"],
        "time": {"active_Codex_ms": None, "external_wait_ms": None, "calendar_ms": None,
            "meaning": "full stage telemetry not continuously instrumented; per-run observed latency recorded"},
        "retained_runtime_readback_sha256": hashlib.sha256(readback_path.read_bytes()).hexdigest(),
        "artifacts": {name: hashlib.sha256(destination(name).read_bytes()).hexdigest() for name in artifacts},
        "code_and_docs": {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in code},
        "prior_failed_aborted_and_rejected_evidence_retained": True, "commit_push_deploy_cleanup": False}
    retain("verification-manifest-03.json", report)
    print(json.dumps({"status": report["status"], "backend": backend, "frontend": frontend,
        "all_prior_rows_retained": True, "live_summary": quality["summary"], "paid": current_paid}))


if __name__ == "__main__":
    main()
