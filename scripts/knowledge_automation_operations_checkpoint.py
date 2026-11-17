"""Final read-only operational reconciliation; old rows and receipts are retained."""
import asyncio
from collections import Counter
from datetime import UTC, datetime
import hashlib
import json
import subprocess

import asyncpg

from knowledge_platform import ROOT, STATE, TENANT, checked_path, connection, rehearsal_connection, retain
from knowledge_platform_runtime import api_state, frontend_ready, process_inventory, worker_state
from knowledge_automation_checkpoint_20261027 import database
from knowledge_automation_live_eval import paid

SCOPE = ROOT / "infra/local/knowledge-automation-20261026"
EVIDENCE = ["operations-verify-20261027T114049142697/receipt.json", "operations-recheck-20261027T113741093639/receipt.json",
    "operations-restart-20261027T114314164611/receipt.json", "main-rollout-check-20261027T114439803565/receipt.json",
    "schema-rehearsal-bundle-20261027T114458600701.json", "schedule-recurring-20261027T115951589140.json"]
FILES = ["scripts/knowledge_platform.py", "scripts/knowledge_platform_runtime.py", "scripts/knowledge_worker_loop.py",
    "scripts/knowledge_automation_operations_probe.py", "scripts/knowledge_automation_operations_checkpoint.py",
    "services/api/src/campus247/application/knowledge/schedules.py", "tests/operations/test_knowledge_worker_loop.py",
    "tests/operations/test_knowledge_platform_runtime.py", "tests/knowledge_platform/test_ingestion_cancellation_postgres.py",
    "tests/knowledge_platform/test_schedules_postgres.py", "docs/DOCUMENT_KNOWLEDGE_AUTOMATION_HANDOFF_20261027.md",
    "docs/DOCUMENT_KNOWLEDGE_AUTOMATION_ROLLOUT_20261027.md"]


def read(name):
    return json.loads(checked_path(SCOPE / name, ROOT).read_bytes())


async def main():
    original = await asyncpg.connect(**rehearsal_connection(SCOPE / "schema-rehearsal-bundle-20261027T085621179427.json"))
    current = await asyncpg.connect(**connection())
    report = {"started_at":datetime.now(UTC), "overall_P00_P16_complete":False,
        "baseline_bundle":"schema-rehearsal-bundle-20261027T085621179427.json", "tables":{}}
    try:
        async with original.transaction(readonly=True,isolation="repeatable_read"), current.transaction(readonly=True,isolation="repeatable_read"):
            for table in ("knowledge_source_scope","document_version","knowledge_ingest_version","knowledge_artifact",
                "knowledge_review","knowledge_release","knowledge_release_member","knowledge_release_pointer","knowledge_ingestion_job"):
                columns = await original.fetch("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=$1 ORDER BY ordinal_position",table)
                query = 'SELECT '+','.join('"'+row["column_name"]+'"' for row in columns)+' FROM "'+table+'"'
                def fingerprints(rows):
                    return Counter(hashlib.sha256(json.dumps(dict(row),sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest() for row in rows)
                before, after = fingerprints(await original.fetch(query)),fingerprints(await current.fetch(query))
                report["tables"][table] = {"before_count":sum(before.values()),"current_count":sum(after.values()),
                    "all_preexisting_rows_identical":not bool(before-after),"new_rows":sum((after-before).values())}
            report["mapping_counts"] = {table:await current.fetchval('SELECT count(*) FROM "'+table+'" WHERE tenant_id=$1',TENANT)
                for table in ("knowledge_document_edition","knowledge_version_lineage","knowledge_edition_decision","knowledge_edition_relation_decision")}
            report["live_ack"] = dict(await current.fetchrow("SELECT boot_id,release_id,generation,policy_generation,valid_until>clock_timestamp() AS live FROM knowledge_runtime_ack WHERE tenant_id=$1 AND instance_id='knowledge-local-api'",TENANT))
            report["own_pending_jobs"] = [dict(row) for row in await current.fetch("SELECT id,state,stage,attempts FROM knowledge_ingestion_job WHERE tenant_id=$1 AND state IN ('QUEUED','RUNNING','RETRY_WAIT')",TENANT)]
    finally:
        await original.close(); await current.close()
    report["main"] = await database(connection())
    report["worker"] = worker_state(process_inventory("frontend-knowledge-automation-20261027-13"))
    report["api"] = api_state()
    report["frontend"] = frontend_ready()
    report["paid"] = paid()
    report["code_sha256"] = {name:hashlib.sha256(checked_path(ROOT / name, ROOT).read_bytes()).hexdigest() for name in FILES}
    report["evidence"] = {name:{"sha256":hashlib.sha256(checked_path(SCOPE / name,ROOT).read_bytes()).hexdigest(),
        "passed":read(name).get("passed",read(name).get("all_passed",read(name).get("status") == "passed"))} for name in EVIDENCE}
    git = subprocess.run(["git","status","--short","-uno"],capture_output=True,text=True,check=True,cwd=ROOT)
    report["tracked_states_preserved"] = git.stdout.splitlines() == read("checkpoint-deployed-20261027T085929068688.json")["tracked_changes"]
    report["git_head"] = subprocess.run(["git","rev-parse","HEAD"],capture_output=True,text=True,check=True,cwd=ROOT).stdout.strip()
    baseline = read("checkpoint-deployed-20261027T085929068688.json")
    report["build"] = "frontend-knowledge-automation-20261027-13"
    report["frontend_source_matches_build"] = all(checked_path(ROOT / name,ROOT).read_bytes() ==
        checked_path(STATE / report["build"] / name.removeprefix("apps/web/"),ROOT).read_bytes()
        for name in baseline["code_sha256"] if name.startswith("apps/web/src/"))
    recurrence = read("schedule-recurring-20261027T115951589140.json")
    first, second = recurrence["outcomes"][:2]
    report["schedule_recurrence_elapsed_seconds"] = (datetime.fromisoformat(second["at"])-datetime.fromisoformat(first["at"])).total_seconds()
    report["checks"] = {"all_nine_preexisting_tables_preserved":all(item["all_preexisting_rows_identical"] for item in report["tables"].values()),
        "evidence_passed":all(item["passed"] for item in report["evidence"].values()),
        "main_schema_counts":(report["main"]["schema"],report["main"]["source_count"],report["main"]["version_count"],report["main"]["serving_members"]) == ("0022",120,330,114),
        "live_ack":report["live_ack"]["live"],"own_queue_drained":not report["own_pending_jobs"],
        "preexisting_tracked_states_preserved":report["tracked_states_preserved"],
        "git_head_preserved":report["git_head"] == baseline["git_head"],
        "frontend_source_matches_build":report["frontend_source_matches_build"],
        "real_recurring_interval_at_least_900_seconds":report["schedule_recurrence_elapsed_seconds"] >= 900,
        "paid_calls_unchanged":report["paid"] == read("operations-run-20261027T113601381612/receipt.json")["paid_before"]}
    report["operational_work_verified"] = all(report["checks"].values())
    report["remaining"] = ["Deferred source/semantic graph/partial amendments and independent review/pilots",
        "Natural-language historical knowledge-time acceptance has no verified edition/lineage corpus; typed resolver preview exists",
        "Session schedule expires normally; no unattended service identity or publication authority",
        "HUCE SSO/personal data APIs absent; no production SLA claim"]
    report["finished_at"] = datetime.now(UTC)
    target = SCOPE / ("operations-final-"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")+".json")
    retain(target,report)
    print(json.dumps({"receipt":str(target),"operational_work_verified":report["operational_work_verified"],"checks":report["checks"]}))
    if not report["operational_work_verified"]:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
