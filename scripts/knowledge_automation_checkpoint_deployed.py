"""Capture the completed approved rollout without rewriting historical evidence."""
import asyncio
from datetime import UTC, datetime
import hashlib
import json

import asyncpg

from knowledge_platform import ROOT, STATE, checked_path, connection, model_budget, retain
from knowledge_automation_checkpoint_20261027 import database
from knowledge_automation_checkpoint_blocked import command
from knowledge_automation_live_eval import paid


async def main():
    scope = ROOT / "infra/local/knowledge-automation-20261026"
    def read(name):
        return json.loads(checked_path(scope / name,ROOT).read_bytes())
    before = read("checkpoint-ready-20261027T075315423548.json")
    smoke_name = "main-rollout-check-20261027T085538074526/receipt.json"
    migration_name = "rollout-migration-20261027T085839389847.json"
    smoke,migration = read(smoke_name),read(migration_name)
    backups = ["schema-rehearsal-bundle-20261027T084928784392.json","schema-rehearsal-bundle-20261027T085621179427.json"]
    manifests = [read(name) for name in backups]
    current = await database(connection())
    conn = await asyncpg.connect(**connection())
    try:
        async with conn.transaction(readonly=True):
            ack = dict(await conn.fetchrow("SELECT boot_id,release_id,generation,policy_generation,valid_until>clock_timestamp() AS live FROM knowledge_runtime_ack WHERE tenant_id=$1 AND instance_id='knowledge-local-api'", "huce-local-public"))
            jobs = [dict(row) for row in await conn.fetch("SELECT id,state,attempts FROM knowledge_ingestion_job WHERE state IN ('QUEUED','RUNNING','RETRY_WAIT') ORDER BY id")]
    finally:
        await conn.close()
    checks = {"smoke13":smoke["all_passed"] and len(smoke["checks"]) == 13,
        "old_content_unchanged":migration["passed"] and migration["all_existing_content_rows_unchanged"],
        "schema_counts":(current["schema"],current["source_count"],current["version_count"],current["serving_members"]) == ("0022",120,330,114),
        "live_main_ack":ack["live"],"pointer_unchanged":all(str(current["pointer"][key]) == str(before["main"]["pointer"][key]) for key in ("release_id","generation","policy_generation")),
        "backup_before_after":all(m["status"] == "passed" and m["cross_store_capture_verified"] and m["postgres_fingerprints_equal"] for m in manifests),
        "deferred_jobs_retained":len(jobs) == 11 and all(row["state"] == "QUEUED" and row["attempts"] == 0 for row in jobs)}
    names = sorted(set(before["code_sha256"]) | {
        "scripts/knowledge_automation_rollout_preflight.py","scripts/knowledge_automation_rollout_migration_check.py",
        "scripts/knowledge_automation_main_check.py","scripts/knowledge_automation_checkpoint_deployed.py",
        "scripts/knowledge_automation_restore.py","scripts/knowledge_automation_restore_bundle.py"})
    tracked = command(["git","status","--short","-uno"]).splitlines()
    checks["tracked_states_preserved"] = tracked == before["tracked_changes"]
    checks["ui_build_source_matches"] = all((ROOT / name).read_bytes() == (STATE / before["build"] / name.removeprefix("apps/web/")).read_bytes() for name in names if name.startswith("apps/web/src/"))
    evidence = [smoke_name,migration_name,*backups,"rollout-preflight-20261027T084915271098.json",
        "rollout-migration-20261027T085136157308.json","rollout-migration-20261027T085214082149.json",
        "main-rollout-check-20261027T085405885806/receipt.json","ui-main-answer-20261027-16.png"]
    report = {"at":datetime.now(UTC),"authorized_rollout_complete":all(checks.values()),"overall_P00_P16_complete":False,
        "authorization":"Direct human answer: Cho phép triển khai gói lên bản chính",
        "checks":checks,"main":current,"main_live_ack":ack,"main_ports":"8015/3015","build":before["build"],
        "paid_writer":"main8015; prototype8018 restarted without generation; OS lease transferred normally",
        "runtime_receipt":"infra/local/knowledge-platform-20261023/resume-20261027T085226306869/receipt.json",
        "worker_deferred":True,"deferred_jobs":jobs,"source_review_or_publication_created":False,
        "native_shared_snapshot":model_budget(),"paid_shared_snapshot":paid(),
        "git_head":command(["git","rev-parse","HEAD"]).strip(),"tracked_changes":tracked,
        "code_sha256":{name:hashlib.sha256(checked_path(ROOT / name,ROOT).read_bytes()).hexdigest() for name in names},
        "evidence":{name:{"sha256":hashlib.sha256(checked_path(scope / name,ROOT).read_bytes()).hexdigest(),"bytes":(scope / name).stat().st_size} for name in evidence},
        "verification":"436backend/5skipped,20UI,TypeScript0,realOCR before rollout;18launcher passed after defer-worker change;13live main checks",
        "remaining_limits":["Deferred unfinished documents/semantic graph/partial amendments and independent source review",
            "No general ingestion worker while11legacy DRAFT jobs remain deferred; new uploads remain queued until scoped processing",
            "Unattended publication authority and HUCE SSO/personal APIs not supplied","No production throughput/SLA claim"],
        "failed_checkers_retained":"Typed UUID/datetime-to-JSON comparison and duplicate-SSE expectation corrected in checker only; original receipts retained"}
    target = scope / ("checkpoint-deployed-"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")+".json")
    retain(target,report)
    print(json.dumps({"checkpoint":str(target),"authorized_rollout_complete":report["authorized_rollout_complete"],"checks":checks}))
    if not report["authorized_rollout_complete"]:
        raise RuntimeError("Deployment checkpoint incomplete")


if __name__ == "__main__":
    asyncio.run(main())
