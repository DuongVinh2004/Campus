"""Read-only continuation checkpoint; retained receipts are never rewritten."""
import asyncio
import hashlib
import json
import subprocess
from datetime import UTC, datetime

import asyncpg

from knowledge_platform import ROOT, TENANT, checked_path, connection, model_budget, rehearsal_connection, retain

SCOPE = ROOT / "infra/local/knowledge-automation-20261026"
BUNDLE = SCOPE / "schema-rehearsal-bundle-20261026T174106266973.json"
CODE = [
    "services/api/src/campus247/agent/nodes/intent.py",
    "services/api/src/campus247/application/retrieval/candidate_selection.py",
    "services/api/src/campus247/infrastructure/knowledge/runtime.py",
    "services/api/src/campus247/application/knowledge/ocr_evidence.py",
    "services/api/src/campus247/application/knowledge/platform.py",
    "services/api/src/campus247/application/knowledge/intake.py",
    "services/api/src/campus247/presentation/knowledge_platform.py",
    "services/worker/src/campus247_worker/knowledge.py",
    "apps/web/src/features/knowledge/KnowledgeIntake.tsx",
    "apps/web/src/features/knowledge/KnowledgePlatform.tsx",
    "apps/web/src/features/knowledge/KnowledgeIntake.test.tsx",
    "apps/web/src/features/knowledge/KnowledgePlatform.test.tsx",
    "tests/knowledge_platform/test_text_baseline_repairs.py",
    "tests/knowledge_platform/test_ocr_evidence.py",
    "tests/knowledge_platform/test_ocr_evidence_postgres.py",
    "tests/knowledge_platform/test_local_ocr.py",
    "scripts/knowledge_automation_retrieval_diagnostic.py",
    "scripts/knowledge_automation_restore_bundle.py",
    "scripts/knowledge_automation_ui_fixture.py",
]
RECEIPTS = [
    "verify-20261026T173717202658/receipt.json", "verify-20261026T175145111249/receipt.json",
    "verify-20261026T175322261141/receipt.json", "retrieval-diagnostic-20261026T175537123294/receipt.json",
    "retrieval-diagnostic-20261026T173908425771/receipt.json", "schema-rehearsal-bundle-20261026T174106266973.json",
    "ui-fixture-20261026T174736838124/receipt.json", "ui-fixture-20261026T174718771305/receipt.json",
    "ui-ocr-evidence-20261027-01.png", "ui-correction-image-20261027-01.png", "ui-correction-waiting-20261027-01.png",
]


async def database(parameters):
    conn = await asyncpg.connect(**parameters)
    try:
        async with conn.transaction(readonly=True, isolation="repeatable_read"):
            pointer = dict(await conn.fetchrow("SELECT * FROM knowledge_release_pointer WHERE tenant_id=$1 AND campus_id='HUCE'", TENANT))
            result = {"database": await conn.fetchval("SELECT current_database()"),
                "schema": await conn.fetchval("SELECT version_num FROM alembic_version"), "pointer": pointer,
                "source_count": await conn.fetchval("SELECT count(*) FROM knowledge_source_scope WHERE tenant_id=$1", TENANT),
                "version_count": await conn.fetchval("SELECT count(*) FROM knowledge_ingest_version WHERE tenant_id=$1", TENANT),
                "serving_members": await conn.fetchval("SELECT count(*) FROM knowledge_release_member WHERE release_id=$1", pointer["release_id"])}
            if await conn.fetchval("SELECT to_regclass('knowledge_rendition_correction') IS NOT NULL"):
                result["corrections"] = [dict(row) for row in await conn.fetch("""SELECT c.id,c.source_version_id,c.proposal_sha256,
                    (SELECT count(*) FROM knowledge_rendition_correction_review r WHERE r.correction_id=c.id AND r.tenant_id=c.tenant_id) AS review_count,
                    (SELECT count(*) FROM knowledge_rendition_correction_result r WHERE r.correction_id=c.id AND r.tenant_id=c.tenant_id) AS materialized_count
                    FROM knowledge_rendition_correction c WHERE c.tenant_id=$1 ORDER BY c.recorded_at,c.id""", TENANT)]
            return result
    finally:
        await conn.close()


async def main():
    initial = json.loads((SCOPE / "checkpoint-20261026T142917811865.json").read_text(encoding="utf-8"))
    tracked = subprocess.run(["git", "status", "--short", "-uno"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True).stdout.splitlines()
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    bundle = json.loads(BUNDLE.read_text(encoding="utf-8"))
    operational = await database(connection())
    rehearsal = await database(rehearsal_connection(BUNDLE))
    build_name = "frontend-knowledge-automation-20261027-09"
    build_root = ROOT / "infra/local/knowledge-platform-20261023" / build_name
    ui_names = [name for name in CODE if name.startswith("apps/web/src/")]
    report = {"at": datetime.now(UTC), "goal_complete": False,
        "tracked_path_state_matches_prior": tracked == initial["tracked_changes"], "tracked_change_count": len(tracked),
        "git_head": head, "git_head_unchanged": head == "c18e2d1741361e7852511a2200fb2595bc6e47b9",
        "operational": operational, "rehearsal": rehearsal,
        "main_pointer_unchanged": all(str(operational["pointer"][k]) == str(bundle["source_pointer"][k]) for k in ("release_id", "generation", "policy_generation")),
        "main_schema_unchanged": operational["schema"] == "0018",
        "code_sha256": {name: hashlib.sha256(checked_path(ROOT / name, ROOT).read_bytes()).hexdigest() for name in CODE},
        "new_rehearsal": "8018/3018, schema0022, generation disabled; one scoped synthetic fixture, no background queue worker",
        "existing_rehearsal": "8016/3016 still schema0020/snapshot07; only its verified worker was paused for full tests and then resumed",
        "build": build_name, "ui_build_matches_source": all((ROOT / name).read_bytes() == checked_path(build_root / name.removeprefix("apps/web/"), ROOT).read_bytes() for name in ui_names),
        "verification": {"latest": "verify-20261026T175322261141/receipt.json", "backend_passed": 356, "backend_skipped": 7,
            "ui_passed": 13, "typescript_exit": 0, "build_exit": 0,
            "real_local_ocr": "Both opt-in tests ran in verify-20261026T173717202658; additional actual OCR in the scoped UI fixture. Latest full run skips both."},
        "retrieval_limits": "Both clauses reach the bounded lexical preselection with unchanged source hashes. Full native hybrid recheck retained timeout/503 failures; no candidate paid answer acceptance.",
        "ocr_limits": "11 actual OCR occurrences exposed with pixel locators and candidate context. Final glyph is clipped in the synthetic rendered line; semantics remain unverified.",
        "correction_limits": "UI proposal normalizes trailing whitespace only. No independent reviewer impersonated, no review/materialization/publication.",
        "remaining": ["P07 verified semantic dependencies and structured table/diagram corrections", "P08 serving resolver and business-decision UI",
            "P10 unit/page incremental indexing", "P11 real scoped automation authority", "P12 candidate end-to-end/multiturn validation",
            "P13 application sync/effective scheduling", "P14 load/cancel/long-job verification", "P15 real three-type/novel-source pilot and46-source shadow map", "P16 rollout/acceptance"],
        "native_shared_snapshot": model_budget(), "paid_gateway_writer_created": False,
        "evidence": {name: {"sha256": hashlib.sha256(checked_path(SCOPE / name, ROOT).read_bytes()).hexdigest(),
            "bytes": (SCOPE / name).stat().st_size} for name in RECEIPTS}}
    from multi_agent_live_resources import latest_paid_snapshot
    paid = latest_paid_snapshot()
    report["paid_shared_snapshot"] = {key: paid[key] for key in ("calls", "input_tokens_charged", "output_tokens_charged", "conservative_charged_usd", "unsettled_attempts_retained")}
    path = checked_path(SCOPE / ("checkpoint-"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")+".json"), ROOT)
    retain(path, report)
    print(json.dumps({"checkpoint": str(path), "main_schema_unchanged": report["main_schema_unchanged"],
        "main_pointer_unchanged": report["main_pointer_unchanged"], "tracked_states_unchanged": report["tracked_path_state_matches_prior"],
        "ui_build_matches_source": report["ui_build_matches_source"], "goal_complete": False}))


if __name__ == "__main__":
    asyncio.run(main())
