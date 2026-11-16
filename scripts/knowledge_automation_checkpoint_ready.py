"""Retain current live facts and scoped completion evidence; preserve old reports."""
import asyncio
from datetime import UTC, datetime
import hashlib
import json
import re

import httpx

from knowledge_platform import ROOT, STATE, checked_path, connection, model_budget, rehearsal_connection, retain
from knowledge_automation_checkpoint_20261027 import database
from knowledge_automation_checkpoint_blocked import command
from knowledge_automation_live_eval import paid

SCOPE = ROOT / "infra/local/knowledge-automation-20261026"
BUNDLE = SCOPE / "schema-rehearsal-bundle-20261026T174106266973.json"
VERIFY = SCOPE / "verify-20261027T073302095623"
BUILD = "frontend-knowledge-automation-20261027-13"
EXTRA = [
    "scripts/knowledge_platform_runtime.py", "scripts/knowledge_automation_checkpoint_ready.py",
    "scripts/knowledge_automation_conversation_probe.py", "scripts/knowledge_automation_load_probe.py",
    "scripts/knowledge_automation_schedule_probe.py", "scripts/knowledge_automation_live_eval.py",
    "scripts/knowledge_automation_retrieval_diagnostic.py", "scripts/knowledge_automation_verify_restore.py",
    "services/api/src/campus247/application/conversation/followup.py",
    "services/api/src/campus247/application/knowledge/document_reference.py",
    "services/api/src/campus247/application/retrieval/candidate_selection.py",
    "services/api/src/campus247/application/retrieval/question_facets.py",
    "tests/knowledge_platform/test_document_reference.py", "tests/knowledge_platform/test_document_fairness.py",
    "tests/knowledge_platform/test_question_facets.py", "tests/unit/conversation/test_followup_question_m2.py",
    "tests/operations/test_knowledge_platform_runtime.py",
    "docs/DOCUMENT_KNOWLEDGE_AUTOMATION_ROLLOUT_20261027.md",
    "docs/DOCUMENT_KNOWLEDGE_AUTOMATION_HANDOFF_20261027.md",
    "docs/DOCUMENT_KNOWLEDGE_AUTOMATION_PROGRESS_20261027.md",
]
EVIDENCE = [
    "verify-20261027T071310584464/receipt.json", "verify-20261027T073302095623/receipt.json",
    "verify-20261027T073302095623/backend.stdout.log", "verify-20261027T073302095623/ui.stdout.log",
    "live-independent-20261027T071521803644/receipt.json", "candidate-material-20261027-01.json",
    "conversation-probe-20261027T072140717220/receipt.json", "conversation-probe-20261027T073342900434/receipt.json",
    "application-load-20261027T074634045889/receipt.json", "schedule-probe-20261027T073929376851/receipt.json",
    "schema-rehearsal-bundle-20261027T072224263352.json", "restore-runtime-20261027T073301641623.json",
    "ui-candidate-citation-20261027-14.png", "ui-history-citation-20261027-15.png",
]


def read(name):
    return json.loads(checked_path(SCOPE / name, ROOT).read_bytes())


def runtime_state(port):
    # Only this fresh checker session is logged out; the human browser remains signed in.
    with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False, timeout=15) as client:
        credentials = json.loads((STATE / "owner-credentials.json").read_bytes())
        response = client.post("/v1/knowledge/platform/session", json={key: credentials[key] for key in ("username", "password")})
        credentials = None
        response.raise_for_status()
        try:
            response = client.get("/v1/knowledge/platform/state"); response.raise_for_status()
            state = response.json()
            return {"port": port, **{key: state[key] for key in ("environment", "desired", "is_serving")},
                "live_acks": [ack for ack in state["serving"] if ack.get("live")]}
        finally:
            client.post("/v1/auth/logout").raise_for_status()


async def main():
    previous = read("checkpoint-blocked-20261027T070638137908.json")
    names = sorted(set(previous["code_sha256"]) | set(EXTRA))
    names += [str(path.relative_to(ROOT)).replace("\\", "/") for path in
        sorted((ROOT / "services/api/migrations/versions").glob("00[12][0-9]_*.py"))
        if path.name[:4] in {"0019", "0020", "0021", "0022"}]
    names = sorted(set(names))
    verification = json.loads((VERIFY / "receipt.json").read_bytes())
    if any(row["exit_code"] for row in verification["commands"]) or not verification["database_tests_enabled"]:
        raise ValueError("Actual complete database verification required")
    backend = re.findall(r"(\d+) passed, (\d+) skipped", (VERIFY / "backend.stdout.log").read_text(encoding="utf-8"))[-1]
    ui = re.findall(r"Tests\s+(\d+) passed", (VERIFY / "ui.stdout.log").read_text(encoding="utf-8"))[-1]
    material = read("candidate-material-20261027-01.json")
    conversations = read("conversation-probe-20261027T073342900434/receipt.json")
    load = read("application-load-20261027T074634045889/receipt.json")
    schedule = read("schedule-probe-20261027T073929376851/receipt.json")
    restore = read("restore-runtime-20261027T073301641623.json")
    if not (material["material_failures"] == 0 and conversations["all_passed"] and load["all_passed"]
            and schedule["url_background_passed"] and schedule["release_readiness_passed"]
            and schedule["pointer_unchanged"] and restore["runtime_checks_passed"]):
        raise ValueError("Do not summarize failed evidence as ready")
    tracked = command(["git", "status", "--short", "-uno"]).splitlines()
    main_db = await database(connection())
    prototype = await database(rehearsal_connection(BUNDLE))
    main_unchanged = (main_db["schema"], main_db["source_count"], main_db["version_count"], main_db["serving_members"]) == ("0018", 120, 330, 114)
    pointer = json.loads(BUNDLE.read_bytes())["source_pointer"]
    main_unchanged &= all(str(main_db["pointer"][key]) == str(pointer[key]) for key in ("release_id", "generation", "policy_generation"))
    build = json.loads((STATE / (BUILD+"-build.json")).read_bytes())
    policy = json.loads((STATE / "model-accounting.json").read_bytes())
    before = read("native-binding-before-20261027-01.json")
    controls_unchanged = all(policy[key] == value for key, value in before.items() if key not in {"native_namespace", "retained_predecessor"})
    listeners = command(["powershell.exe", "-NoProfile", "-Command",
        "Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in 55437,8015,3015,8017,8018,3018,18081,18082 } | Select-Object LocalPort,OwningProcess | ConvertTo-Json -Compress"])
    sac = command(["powershell.exe", "-NoProfile", "-Command",
        "Get-ItemPropertyValue -LiteralPath 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\CI\\Policy' -Name VerifiedAndReputablePolicyState"])
    shared_paid = paid()
    report = {"at": datetime.now(UTC), "goal_complete": False, "status": "prototype_verified_main_rollout_pending",
        "historical_windows_block_resolved": {"same_postgres_executable_started": True, "security_policy_changed": False, "smart_app_control_state": int(sac.strip())},
        "git_head": command(["git", "rev-parse", "HEAD"]).strip(), "tracked_changes": tracked,
        "tracked_path_states_match_prior": tracked == previous["tracked_changes"],
        "main": main_db, "prototype": prototype, "main_schema_counts_pointer_unchanged": main_unchanged,
        "listeners": json.loads(listeners), "prototype_runtime": runtime_state(8018), "restored_runtime": runtime_state(8017),
        "build": BUILD, "build_exit_code": build["exit_code"],
        "ui_build_matches_source": all((ROOT / name).read_bytes() == (STATE / BUILD / name.removeprefix("apps/web/")).read_bytes()
            for name in names if name.startswith("apps/web/src/")),
        "code_sha256": {name: hashlib.sha256(checked_path(ROOT / name, ROOT).read_bytes()).hexdigest() for name in names},
        "evidence": {name: {"sha256": hashlib.sha256(checked_path(SCOPE / name, ROOT).read_bytes()).hexdigest(),
            "bytes": (SCOPE / name).stat().st_size} for name in EVIDENCE},
        "verification": {"receipt": str(VERIFY / "receipt.json"), "backend_passed": int(backend[0]), "backend_skipped": int(backend[1]),
            "ui_passed": int(ui), "local_ocr_ran": verification["local_ocr_smoke"],
            "commands": verification["commands"], "launcher_and_followup": {"passed": 31, "exit_code": 0,
                "basis": "Observed tool output on 2026-10-27 after final launcher patch; no additional run inferred",
                "command": "python -B -X utf8 -m pytest tests/operations/test_knowledge_platform_runtime.py tests/unit/conversation/test_followup_question_m2.py -q -p no:cacheprovider"}},
        "native": {"namespace": policy["native_namespace"], "accounting_controls_unchanged": controls_unchanged, "shared_usage": model_budget()},
        "paid_shared_snapshot": shared_paid, "paid_writer": "prototype8018 acquired retained OS lease normally; no reset/bypass",
        "source_review_or_publication_created": False, "main_process_started_stopped_or_deployed": False,
        "observations": {"bounded_material_failures": material["material_failures"], "multiturn_multisource_corrected": conversations["all_passed"],
            "application_concurrency_two": load["all_passed"], "real_url_background": schedule["url_background_passed"],
            "release_background_readiness": schedule["release_readiness_passed"], "restore_runtime": restore["runtime_checks_passed"]},
        "remaining": ["Exact main rollout permission under prior scope; concrete package prepared",
            "Human independent source comparison and unfinished documents deferred by user",
            "Unattended publication requires real scoped service authority; schedules currently session-bound readiness only",
            "HUCE personal/SSO integrations unavailable; retain truthful abstention",
            "Unfinished verified semantic graph/partial amendments and broad production SLA are not established"],
        "rollout_package": "docs/DOCUMENT_KNOWLEDGE_AUTOMATION_ROLLOUT_20261027.md"}
    target = checked_path(SCOPE / ("checkpoint-ready-"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")+".json"), ROOT)
    retain(target, report)
    print(json.dumps({"checkpoint": str(target), "main_unchanged": main_unchanged,
        "tracked_states_match": report["tracked_path_states_match_prior"], "ui_build_matches": report["ui_build_matches_source"],
        "controls_unchanged": controls_unchanged, "prototype_serving": report["prototype_runtime"]["is_serving"]}))


if __name__ == "__main__":
    asyncio.run(main())
