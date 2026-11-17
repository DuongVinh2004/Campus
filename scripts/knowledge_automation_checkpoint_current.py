"""Retain current code/runtime evidence without changing any prior checkpoint."""
import argparse
import asyncio
from datetime import UTC, datetime
import hashlib
import json
import re
import subprocess

from knowledge_platform import ROOT, checked_path, connection, model_budget, rehearsal_connection, retain
from knowledge_automation_checkpoint_20261027 import database

SCOPE = ROOT / "infra/local/knowledge-automation-20261026"
CODE = (
    "services/api/src/campus247/application/knowledge/edition_release.py",
    "services/api/src/campus247/application/knowledge/release_members.py",
    "services/api/src/campus247/application/knowledge/version_resolver.py",
    "services/api/src/campus247/infrastructure/knowledge/runtime.py",
    "tests/knowledge_platform/test_edition_release_postgres.py",
    "tests/knowledge_platform/test_edition_question_scope.py",
    "tests/knowledge_platform/test_relevance.py",
    "services/api/src/campus247/application/knowledge/edition_decisions.py",
    "services/api/src/campus247/application/knowledge/applicability.py",
    "services/api/src/campus247/application/knowledge/document_identity.py",
    "services/api/src/campus247/application/knowledge/evidence_units.py",
    "services/api/src/campus247/application/knowledge/intake.py",
    "services/api/src/campus247/application/knowledge/platform.py",
    "services/api/src/campus247/infrastructure/knowledge/fetch.py",
    "services/api/src/campus247/infrastructure/knowledge/repository.py",
    "services/api/src/campus247/presentation/knowledge_platform.py",
    "services/worker/src/campus247_worker/knowledge.py",
    "services/worker/src/campus247_worker/knowledge_embedding_cache.py",
    "services/worker/src/campus247_worker/knowledge_layout.py",
    "services/worker/src/campus247_worker/knowledge_parse.py",
    "services/worker/src/campus247_worker/knowledge_table_layout.py",
    "apps/web/src/features/knowledge/EditionWorkspace.tsx",
    "apps/web/src/features/knowledge/EditionWorkspace.test.tsx",
    "apps/web/src/features/knowledge/KnowledgeIntake.tsx",
    "apps/web/src/features/knowledge/KnowledgeIntake.test.tsx",
    "apps/web/src/features/knowledge/KnowledgePlatform.tsx",
    "tests/knowledge_platform/test_draft_postgres.py",
    "tests/knowledge_platform/test_edition_decisions.py",
    "tests/knowledge_platform/test_effective_release_postgres.py",
    "tests/knowledge_platform/test_incremental_index.py",
    "tests/knowledge_platform/test_incremental_index_postgres.py",
    "tests/knowledge_platform/test_ingestion_cancellation_postgres.py",
    "tests/knowledge_platform/test_merged_table_layout.py",
    "tests/knowledge_platform/test_document_fetch.py",
    "tests/knowledge_platform/test_url_refresh_postgres.py",
    "scripts/knowledge_automation_verify.py",
    "scripts/knowledge_automation_verify_owned_worker.py",
    "scripts/knowledge_automation_shadow_map.py",
    "scripts/knowledge_automation_prepare_ready_pilot.py",
    "scripts/knowledge_automation_checkpoint_current.py",
)


async def main(args):
    initial = json.loads((SCOPE / "checkpoint-20261026T142917811865.json").read_text(encoding="utf-8"))
    previous = json.loads((SCOPE / "checkpoint-20261026T175836882985.json").read_text(encoding="utf-8"))
    bundle_path = checked_path(SCOPE / "schema-rehearsal-bundle-20261026T174106266973.json", ROOT)
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    verify_dir = checked_path(SCOPE / args.verification, ROOT)
    if verify_dir.parent != SCOPE or not re.fullmatch(r"verify-\d{8}T\d{12}", verify_dir.name):
        raise ValueError("Exact retained verification directory required")
    verification = json.loads((verify_dir / "receipt.json").read_text(encoding="utf-8"))
    backend = (verify_dir / "backend.stdout.log").read_text(encoding="utf-8")
    ui = (verify_dir / "ui.stdout.log").read_text(encoding="utf-8")
    backend_counts = re.findall(r"(\d+) passed, (\d+) skipped", backend)
    ui_counts = re.findall(r"Tests\s+(\d+) passed", ui)
    if not backend_counts or not ui_counts:
        raise ValueError("Use actual complete test summaries, not assumed counts")
    build_root = checked_path(ROOT / "infra/local/knowledge-platform-20261023" / args.build, ROOT)
    if not re.fullmatch(r"frontend-knowledge-automation-20261027-\d{2}", build_root.name):
        raise ValueError("Exact retained immutable build required")
    build = json.loads((build_root.parent / (build_root.name+"-build.json")).read_text(encoding="utf-8"))
    tracked = subprocess.run(["git", "status", "--short", "-uno"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    operational = await database(connection())
    rehearsal = await database(rehearsal_connection(bundle_path))
    ui_names = [name for name in CODE if name.startswith("apps/web/src/")]
    from multi_agent_live_resources import latest_paid_snapshot
    paid = latest_paid_snapshot()
    report = {"at": datetime.now(UTC), "goal_complete": False, "git_head": head,
        "tracked_changes": tracked, "tracked_path_states_match_prior": tracked == initial["tracked_changes"],
        "tracked_change_count": len(tracked), "git_head_unchanged": head == previous["git_head"],
        "operational": operational, "rehearsal": rehearsal,
        "main_pointer_unchanged": all(str(operational["pointer"][key]) == str(bundle["source_pointer"][key]) for key in ("release_id", "generation", "policy_generation")),
        "main_schema_unchanged": operational["schema"] == "0018", "main_counts_unchanged": (operational["source_count"], operational["version_count"], operational["serving_members"]) == (120,330,114),
        "build": args.build, "build_exit_code": build["exit_code"],
        "ui_build_matches_source": all((ROOT / name).read_bytes() == (build_root / name.removeprefix("apps/web/")).read_bytes() for name in ui_names),
        "code_sha256": {name: hashlib.sha256(checked_path(ROOT / name, ROOT).read_bytes()).hexdigest() for name in CODE},
        "verification": {"receipt": str(verify_dir / "receipt.json"), "backend_passed": int(backend_counts[-1][0]), "backend_skipped": int(backend_counts[-1][1]),
            "ui_passed": int(ui_counts[-1]), "local_ocr_enabled": verification["local_ocr_smoke"], "command_exits": {row["name"]:row["exit_code"] for row in verification["commands"]}},
        "human_steering": {"reviewer": "Human will perform independent comparison; none impersonated", "pilot_scope": "Use already-finished sources; leave unfinished sources for later",
            "local_account": "Existing designated owner reused at the human's direct request; no new account, credential, role or reviewer created"},
        "native_shared_snapshot": model_budget(), "paid_gateway_writer_created": False,
        "paid_shared_snapshot": {key: paid[key] for key in ("calls", "input_tokens_charged", "output_tokens_charged", "conservative_charged_usd", "unsettled_attempts_retained")},
        "evidence": {}, "remaining": ["Source-based verified semantic dependencies and structured corrections for unfinished documents",
            "Verified partial-amendment unit graph and historical knowledge-time answer view beyond the typed admin preview", "Actual scoped automation publication authority", "Candidate end-to-end/multiturn answer acceptance",
            "Configured application sync/effective-date scheduler", "Load/long-job measurements beyond the tested cancellation/fencing cases", "Independent review and rollout acceptance"],
        "limits": ["No candidate paid answer acceptance; native embedding/rerank still timed out under the unchanged 3s guard",
            "Business resolver now binds new mapped releases and guards search/citations; unmapped historical members retain their prior independently admitted contract",
            "Additional editions are sealed in immutable profile and full membership checksum; original table, late-insert and update/delete guards remain unchanged",
            "Three actual ready-source UI uploads stopped at explicit source comparison, without new review/publication or source/version creation",
            "Synthetic cache vectors test mechanics only; no semantic-quality or production-SLA claim",
            "No new autonomous scheduler/background worker; main API/frontend/worker never stopped or restarted"]}
    for value in args.evidence:
        path = checked_path(SCOPE / value, ROOT)
        report["evidence"][value] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}
    target = checked_path(SCOPE / ("checkpoint-"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")+".json"), ROOT)
    retain(target, report)
    print(json.dumps({"checkpoint": str(target), "main_schema_pointer_counts_unchanged": all(report[key] for key in ("main_pointer_unchanged", "main_schema_unchanged", "main_counts_unchanged")),
        "tracked_states_match": report["tracked_path_states_match_prior"], "ui_build_matches": report["ui_build_matches_source"], "verification": report["verification"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", required=True)
    parser.add_argument("--verification", required=True)
    parser.add_argument("--evidence", action="append", default=[])
    asyncio.run(main(parser.parse_args()))
