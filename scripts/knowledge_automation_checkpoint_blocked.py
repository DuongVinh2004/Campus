"""Capture a truthful offline checkpoint; never infer database state from old data."""
from datetime import UTC, datetime
import hashlib
import json
import re
import subprocess

from knowledge_platform import ROOT, STATE, checked_path, model_budget, retain

SCOPE = ROOT / "infra/local/knowledge-automation-20261026"
EXTRA = (
    "services/api/src/campus247/application/knowledge/schedules.py",
    "services/api/src/campus247/application/retrieval/conditional_query.py",
    "apps/web/src/features/knowledge/KnowledgeSchedules.tsx",
    "apps/web/src/features/knowledge/KnowledgeSchedules.test.tsx",
    "tests/knowledge_platform/test_schedules.py",
    "tests/knowledge_platform/test_schedules_postgres.py",
    "tests/knowledge_platform/test_schedule_transport.py",
    "tests/knowledge_platform/test_conditional_query.py",
    "scripts/knowledge_platform.py",
    "scripts/knowledge_automation_native_probe.py",
    "scripts/knowledge_automation_checkpoint_blocked.py",
    "scripts/serve_rag_models.py",
    "infra/local/rag-fixture/m2-20261012-74/runtime-config.json",
)


def command(args):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return result.stdout


def main():
    previous = json.loads(checked_path(SCOPE / "checkpoint-20261027T024747917187.json", ROOT).read_bytes())
    verify = checked_path(SCOPE / "verify-20261027T070322297540", ROOT)
    receipt = json.loads((verify / "receipt.json").read_bytes())
    if receipt["database_tests_enabled"] or any(row["exit_code"] for row in receipt["commands"]):
        raise ValueError("Use the actual completed offline verification receipt")
    backend = re.findall(r"(\d+) passed, (\d+) skipped", (verify / "backend.stdout.log").read_text(encoding="utf-8"))[-1]
    ui = re.findall(r"Tests\s+(\d+) passed", (verify / "ui.stdout.log").read_text(encoding="utf-8"))[-1]
    policy = json.loads((STATE / "model-accounting.json").read_bytes())
    policy_before = json.loads((SCOPE / "native-binding-before-20261027-01.json").read_bytes())
    if any(policy[key] != value for key, value in policy_before.items() if key not in {"native_namespace", "retained_predecessor"}):
        raise ValueError("Only accounting namespace routing may change; all controls must remain identical")
    native = checked_path(ROOT / policy["native_namespace"], ROOT)
    launch = json.loads((native / "launch.json").read_bytes())
    predecessor = json.loads((native / "predecessor.json").read_bytes())
    build_name = "frontend-knowledge-automation-20261027-13"
    build_root = checked_path(STATE / build_name, ROOT)
    build = json.loads((STATE / (build_name+"-build.json")).read_bytes())
    names = sorted(set(previous["code_sha256"]) | set(EXTRA))
    hashes = {name: hashlib.sha256(checked_path(ROOT / name, ROOT).read_bytes()).hexdigest() for name in names}
    tracked = command(["git", "status", "--short", "-uno"]).splitlines()
    inventory = command(["powershell", "-NoProfile", "-Command",
        "Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in 55437,8015,3015,8018,3018,18081,18082 } | Select-Object LocalPort,OwningProcess | ConvertTo-Json -Compress"])
    block = command(["powershell", "-NoProfile", "-Command",
        "Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-CodeIntegrity/Operational';Id=3077} -MaxEvents 12 | Where-Object { $_.Message -like '*knowledge-postgres-20261023*postgres.exe*' } | Select-Object -First 1 TimeCreated,Id,Message | ConvertTo-Json -Compress"])
    from multi_agent_live_resources import latest_paid_snapshot
    paid = latest_paid_snapshot()
    report = {"at": datetime.now(UTC), "goal_complete": False, "status": "environment_blocked",
        "blocker": json.loads(block), "listeners": json.loads(inventory), "main_process_action": False,
        "database_rechecked": False, "database_state": "UNKNOWN_CURRENT_STATE; only the historical checkpoint is available",
        "historical_database_checkpoint": "checkpoint-20261027T024747917187.json", "source_review_or_publication_created": False,
        "git_head": command(["git", "rev-parse", "HEAD"]).strip(), "tracked_changes": tracked,
        "tracked_path_states_match_prior": tracked == previous["tracked_changes"], "code_sha256": hashes,
        "changed_previous_code": [name for name, value in previous["code_sha256"].items() if hashes[name] != value],
        "verification": {"receipt": str(verify / "receipt.json"), "backend_passed": int(backend[0]),
            "backend_skipped": int(backend[1]), "ui_passed": int(ui), "database_tests_enabled": False,
            "command_exits": {row["name"]: row["exit_code"] for row in receipt["commands"]}},
        "build": build_name, "build_exit_code": build["exit_code"], "build_deployed": False,
        "ui_build_matches_source": all((ROOT / name).read_bytes() == (build_root / name.removeprefix("apps/web/")).read_bytes()
            for name in names if name.startswith("apps/web/src/")),
        "native": {"namespace": policy["native_namespace"], "retained_predecessor": predecessor,
            "controls": launch["controls"], "accounting_controls_unchanged": True, "shared_usage": model_budget()},
        "paid_gateway_writer_created": False, "paid_generation_calls": 0,
        "paid_shared_snapshot": {key: paid[key] for key in ("calls", "input_tokens_charged", "output_tokens_charged",
            "conservative_charged_usd", "unsettled_attempts_retained")}, "evidence": {},
        "remaining": ["Real PostgreSQL scheduler transactions and fresh runtime end-to-end/citation/multiturn acceptance",
            "Real scoped service publication authority, independent comparisons and release confirmation",
            "Application recovery/load/rollout acceptance in an approved runnable PostgreSQL environment",
            "Deferred unfinished-document semantic/partial-amendment graph and historical answer view"],
        "limits": ["Offline tests are not a replacement for the prior full PostgreSQL suite; 39 tests skipped",
            "Native probes use retained actual source inputs without current DB authorization or answer-quality acceptance",
            "Conditional-query probe is a development regression observation, not a new independent acceptance set",
            "Two concurrent embeddings are a bounded native observation, not a campus workload or SLA",
            "Session schedules do not confer unattended service identity, review or publication authority",
            "Main/prototype APIs and frontends are absent; no API was deployed and no main runtime restarted"]}
    for relative in ("native-probe-20261027T064711977954/receipt.json", "native-probe-20261027T070204538904/receipt.json",
            "native-probe-20261027T070321403287/receipt.json", "native-binding-before-20261027-01.json"):
        path = checked_path(SCOPE / relative, ROOT)
        report["evidence"][relative] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}
    target = checked_path(SCOPE / ("checkpoint-blocked-"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")+".json"), ROOT)
    retain(target, report)
    print(json.dumps({"checkpoint": str(target), "status": report["status"], "verification": report["verification"],
        "ui_build_matches_source": report["ui_build_matches_source"], "tracked_states_match": report["tracked_path_states_match_prior"]}))


if __name__ == "__main__":
    main()
