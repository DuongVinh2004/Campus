"""Verify scoped main queue operation without reviewing or publishing sources."""
import argparse
import asyncio
from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from uuid import uuid4

import asyncpg
import httpx

from knowledge_platform import ROOT, STATE, TENANT, checked_path, connection, model_budget, retain
from knowledge_platform_runtime import start, process_inventory, worker_state, matching_processes, api_state
from knowledge_automation_live_eval import paid

SCOPE = ROOT / "infra/local/knowledge-automation-20261026"
SOURCE = "5c0b7c32-2740-720a-87a5-3db734608d01"


async def snapshot():
    conn = await asyncpg.connect(**connection())
    try:
        async with conn.transaction(readonly=True, isolation="repeatable_read"):
            value = {"database": await conn.fetchval("SELECT current_database()"),
                "schema": await conn.fetchval("SELECT version_num FROM alembic_version"),
                "pointer": dict(await conn.fetchrow("SELECT * FROM knowledge_release_pointer WHERE tenant_id=$1", TENANT)),
                "deferred_jobs": [dict(row) for row in await conn.fetch("""SELECT * FROM knowledge_ingestion_job
                    WHERE tenant_id<>$1 AND state IN ('QUEUED','RUNNING','RETRY_WAIT') ORDER BY id""", TENANT)],
                "counts": dict(await conn.fetchrow("""SELECT
                    (SELECT count(*) FROM knowledge_source_scope WHERE tenant_id=$1) AS sources,
                    (SELECT count(*) FROM knowledge_ingest_version WHERE tenant_id=$1) AS versions,
                    (SELECT count(*) FROM knowledge_review r JOIN knowledge_ingest_version x ON x.version_id=r.version_id WHERE x.tenant_id=$1) AS reviews,
                    (SELECT count(*) FROM knowledge_release WHERE tenant_id=$1) AS releases""", TENANT))}
            return json.loads(json.dumps(value, default=str))
    finally:
        await conn.close()


async def main_probe(report):
    before = await snapshot()
    report["before"] = before
    if (before["database"], before["schema"]) != ("campus247_knowledge_local_20261023", "0022"):
        raise ValueError("Exact retained main database required")
    if len(before["deferred_jobs"]) != 11 or not all(row["attempts"] == 0 and row["state"] == "QUEUED" for row in before["deferred_jobs"]):
        raise ValueError("Deferred queue differs; inspect before running")
    report["native_before"], report["paid_before"] = model_budget(), paid()
    conn = await asyncpg.connect(**connection())
    try:
        async with conn.transaction(readonly=True):
            source = dict(await conn.fetchrow("""SELECT s.id,s.title,s.canonical_uri FROM knowledge_source s
                JOIN knowledge_release_member m ON m.source_id=s.id
                WHERE m.release_id=$1 AND s.id=$2""", before["pointer"]["release_id"], SOURCE))
    finally:
        await conn.close()
    report["scheduled_source"] = source
    if "uploaded" not in report:
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8015", trust_env=False, timeout=60) as client:
            credentials = json.loads((STATE / "owner-credentials.json").read_bytes())
            response = await client.post("/v1/knowledge/platform/session", json={k:credentials[k] for k in ("username", "password")})
            credentials = None
            response.raise_for_status()
            prepared = json.loads((SCOPE / "ready-pilot-20261027T013448012440/prepared.json").read_bytes())["sources"][0]
            path = checked_path(Path(prepared["file"]), ROOT)
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != prepared["original_sha256"]:
                raise ValueError("Completed original binding changed")
            response = await client.post("/v1/knowledge/platform/intakes", headers={"Idempotency-Key":uuid4().hex},
                files={"file":(path.name,raw,"application/pdf"),"metadata":(None,"{}","application/json")})
            response.raise_for_status()
            report["uploaded"] = response.json()
            await client.post("/v1/auth/logout")
            # Release the upload connection. Only the background worker consumes it.
    report["runtime_start"] = await asyncio.to_thread(start, "frontend-knowledge-automation-20261027-13")
    async def wait_job(identifier):
        conn = await asyncpg.connect(**connection())
        try:
            for _ in range(45):
                async with conn.transaction(readonly=True):
                    job = dict(await conn.fetchrow("SELECT * FROM knowledge_ingestion_job WHERE id=$1 AND tenant_id=$2", identifier, TENANT))
                if job["state"] not in {"QUEUED","RUNNING","RETRY_WAIT"}:
                    return job
                await asyncio.sleep(1)
            raise TimeoutError("Scoped queue job did not complete within the operational probe")
        finally:
            await conn.close()
    report["upload_job"] = await wait_job(report["uploaded"]["job_id"])
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8015", trust_env=False, timeout=60) as client:
        credentials = json.loads((STATE / "owner-credentials.json").read_bytes())
        response = await client.post("/v1/knowledge/platform/session", json={k:credentials[k] for k in ("username","password")})
        credentials = None
        response.raise_for_status()
        async def post(path, body):
            response = await client.post("/v1/knowledge/platform"+path,json=body,headers={"Idempotency-Key":uuid4().hex})
            response.raise_for_status()
            return response.json()
        report["url_intake"] = await post("/url-intakes", {"url":source["canonical_uri"],"title_hint":source["title"]})
        report["url_job"] = await wait_job(report["url_intake"]["job_id"])
        response = await client.get("/v1/knowledge/platform/intakes"); response.raise_for_status()
        observed = next(row for row in response.json()["items"] if row["id"] == report["url_intake"]["intake_id"])
        report["url_observation"] = observed
        response = await client.get("/v1/knowledge/platform/schedules"); response.raise_for_status()
        now = datetime.now(UTC)
        expires = min(datetime.fromisoformat(response.json()["session_expires_at"])-timedelta(seconds=5),now+timedelta(minutes=45))
        report["schedule"] = await post("/schedules", {"kind":"URL_REFRESH","target_id":observed["id"],
            "not_before":(now-timedelta(seconds=1)).isoformat(),"expires_at":expires.isoformat(),"interval_seconds":900,
            "expected_original_sha256":observed["original_sha256"],"confirmed":True})
        for _ in range(20):
            response = await client.get("/v1/knowledge/platform/schedules"); response.raise_for_status()
            item = next(row for row in response.json()["items"] if row["id"] == report["schedule"]["id"])
            if item["last_outcome"]:
                break
            await asyncio.sleep(1)
        report["background_schedule"] = item
        if item["last_outcome"] and item["last_outcome"]["state"] == "QUEUED":
            report["scheduled_job"] = await wait_job(item["last_outcome"]["job_id"])
        # The exact limited schedule remains configured until signed-session
        # expiry. No publication, human review or unattended authority is added.
    report["after"] = await snapshot()
    report["native_after"], report["paid_after"] = model_budget(), paid()
    report["worker"] = worker_state(process_inventory("frontend-knowledge-automation-20261027-13"))
    assess(report)


def assess(report):
    item = report["background_schedule"]
    report["checks"] = {
        "eleven_deferred_rows_unchanged":report["before"]["deferred_jobs"] == report["after"]["deferred_jobs"],
        "content_review_release_counts_unchanged":report["before"]["counts"] == report["after"]["counts"],
        "pointer_unchanged":report["before"]["pointer"] == report["after"]["pointer"],
        "upload_consumed_after_connection_closed":report["upload_job"]["state"] == "NEEDS_INFORMATION"
            and report["upload_job"]["stage"] == "DUPLICATE_REVIEW" and report["upload_job"]["attempts"] == 1,
        "real_background_schedule":bool(report.get("scheduled_job")) and item["last_outcome"]["publication_authority"] is False,
        "no_paid_generation":report["paid_before"] == report["paid_after"],
    }
    report["passed"] = all(report["checks"].values())
    if not report["passed"]:
        raise RuntimeError("Operational probe has failed checks; preserve evidence")


async def restart_probe(report):
    """Restart only verified idle main processes; reuse every stored observation."""
    report["before"] = await snapshot()
    report["paid_before"] = paid()
    rows = process_inventory("frontend-knowledge-automation-20261027-13")
    health = worker_state(rows)
    report["old_worker"] = health
    db = sqlite3.connect((STATE / "conversations.sqlite3").as_uri()+"?mode=ro",uri=True)
    try:
        pending = [json.loads(row[0]) for row in db.execute("SELECT receipt FROM conversation_turn") if json.loads(row[0])["state"] == "pending"]
        if pending:
            raise RuntimeError("Pending conversation turn; preserve running API")
    finally:
        db.close()
    conn = await asyncpg.connect(**connection())
    try:
        async with conn.transaction(readonly=True):
            if await conn.fetchval("SELECT EXISTS(SELECT 1 FROM knowledge_ingestion_job WHERE state='RUNNING' AND lease_until>clock_timestamp())"):
                raise RuntimeError("A worker owns a live job; preserve it")
            report["old_ack"] = dict(await conn.fetchrow("SELECT boot_id,release_id,generation,policy_generation FROM knowledge_runtime_ack WHERE tenant_id=$1 AND instance_id='knowledge-local-api'",TENANT))
    finally:
        await conn.close()
    query = "Get-NetTCPConnection -State Listen -LocalPort 8015 | Select-Object -ExpandProperty OwningProcess | ConvertTo-Json -Compress"
    result = subprocess.run(["powershell.exe","-NoProfile","-Command",query],capture_output=True,text=True,check=True,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    pid = json.loads(result.stdout)
    if not isinstance(pid,int) or pid not in matching_processes(rows,"api"):
        raise RuntimeError("Exact main API listener identity required")
    report["stopped_exact_idle_processes"] = {"api":pid,"worker":health["pid"]}
    for target in (health["pid"],pid):
        subprocess.run(["powershell.exe","-NoProfile","-Command",f"Stop-Process -Id {int(target)} -ErrorAction Stop"],
            capture_output=True,check=True,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    report["runtime_start"] = await asyncio.to_thread(start,"frontend-knowledge-automation-20261027-13")
    report["new_worker"] = worker_state(process_inventory("frontend-knowledge-automation-20261027-13"))
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8015",trust_env=False,timeout=60) as client:
        credentials = json.loads((STATE / "owner-credentials.json").read_bytes())
        response = await client.post("/v1/knowledge/platform/session",json={k:credentials[k] for k in ("username","password")})
        credentials = None
        response.raise_for_status()
        old_schedule = report["schedule"]
        response = await client.get("/v1/knowledge/platform/schedules"); response.raise_for_status()
        old = next(item for item in response.json()["items"] if item["id"] == old_schedule["id"])
        report["restored_schedule_without_invented_authority"] = old["state"]
        response = await client.post("/v1/knowledge/platform/schedules/"+old_schedule["id"]+"/cancel")
        response.raise_for_status()
        report["old_schedule_cancelled_additively"] = response.json()
        # Replace only this task's own limited schedule under the new real session.
        response = await client.get("/v1/knowledge/platform/intakes"); response.raise_for_status()
        observed = next(item for item in response.json()["items"] if item["id"] == report["scheduled_job"]["intake_id"])
        response = await client.get("/v1/knowledge/platform/schedules"); response.raise_for_status()
        now = datetime.now(UTC)
        expires = min(datetime.fromisoformat(response.json()["session_expires_at"])-timedelta(seconds=5),now+timedelta(minutes=45))
        response = await client.post("/v1/knowledge/platform/schedules",headers={"Idempotency-Key":uuid4().hex},json={
            "kind":"URL_REFRESH","target_id":observed["id"],"not_before":(now-timedelta(seconds=1)).isoformat(),
            "expires_at":expires.isoformat(),"interval_seconds":900,"expected_original_sha256":observed["original_sha256"],"confirmed":True})
        response.raise_for_status()
        report["replacement_schedule"] = response.json()
        for _ in range(25):
            response = await client.get("/v1/knowledge/platform/schedules"); response.raise_for_status()
            entry = next(item for item in response.json()["items"] if item["id"] == report["replacement_schedule"]["id"])
            if entry["last_outcome"]:
                break
            await asyncio.sleep(1)
        report["background_after_restart"] = entry
    conn = await asyncpg.connect(**connection())
    try:
        async with conn.transaction(readonly=True):
            report["new_ack"] = dict(await conn.fetchrow("SELECT boot_id,release_id,generation,policy_generation,valid_until>clock_timestamp() AS live FROM knowledge_runtime_ack WHERE tenant_id=$1 AND instance_id='knowledge-local-api'",TENANT))
    finally:
        await conn.close()
    report["after"] = await snapshot()
    report["paid_after"] = paid()
    report["checks"] = {
        "data_and_deferred_jobs_unchanged":report["before"] == report["after"],
        "fresh_ack":report["old_ack"]["boot_id"] != report["new_ack"]["boot_id"] and report["new_ack"]["live"],
        "fresh_worker_loop":report["old_worker"]["owner"] != report["new_worker"]["owner"],
        "schedule_requires_real_session_after_restart":old["state"] == "SESSION_REQUIRED",
        "background_resumed":bool(entry["last_outcome"]) and entry["last_outcome"]["state"] == "QUEUED",
        "no_paid_calls":report["paid_before"] == report["paid_after"],
    }
    report["passed"] = all(report["checks"].values())
    if not report["passed"]:
        raise RuntimeError("Restart probe has failed checks; preserve all evidence")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("verify","run","recheck","restart"))
    parser.add_argument("--resume-receipt", help="Exact failed operations run; reuse its already accepted upload")
    args = parser.parse_args()
    target = checked_path(SCOPE / ("operations-"+args.command+"-"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")),ROOT)
    target.mkdir()
    report = {"started_at":datetime.now(UTC),"publication_confirmed":False,"source_review_created":False}
    if args.resume_receipt:
        path = checked_path(ROOT / args.resume_receipt, ROOT)
        if path.parent.parent != SCOPE or not path.parent.name.startswith("operations-run-") or path.name != "receipt.json":
            raise ValueError("Exact retained operations run required")
        prior = json.loads(path.read_bytes())
        if args.command in {"recheck","restart"}:
            report.update({key:value for key,value in prior.items() if key not in {"started_at","finished_at","checks","passed","error_type"}})
        report.update(resumed_from=str(path),uploaded=prior["uploaded"])
    try:
        if args.command == "verify":
            env = dict(os.environ,PYTHONDONTWRITEBYTECODE="1",KNOWLEDGE_AUTOMATION_CORRECTIONS="infra/local/knowledge-automation-20261026/schema-rehearsal-20261026T133349385686.json",
                KNOWLEDGE_AUTOMATION_REHEARSAL=str(ROOT / "infra/local/knowledge-automation-20261026/schema-rehearsal-20261026T090926324751.json"))
            command = [sys.executable,"-B","-m","pytest","tests/operations/test_knowledge_platform_runtime.py",
                "tests/operations/test_knowledge_worker_loop.py","tests/knowledge_platform/test_ingestion_cancellation_postgres.py",
                "tests/knowledge_platform/test_schedules.py","tests/knowledge_platform/test_schedules_postgres.py","-q","-p","no:cacheprovider"]
            with (target / "pytest.log").open("xb") as stream:
                child = subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0),check=False)
            report.update(command=command,exit_code=child.returncode,passed=child.returncode == 0)
        elif args.command == "restart":
            asyncio.run(restart_probe(report))
        elif args.command == "recheck":
            current = asyncio.run(snapshot())
            report["after"] = current
            report["worker"] = worker_state(process_inventory("frontend-knowledge-automation-20261027-13"))
            report["paid_after"] = paid()
            report["native_after"] = model_budget()
            assess(report)
        else:
            asyncio.run(main_probe(report))
    except Exception as error:
        report["error_type"] = type(error).__name__
        raise
    finally:
        report["finished_at"] = datetime.now(UTC)
        retain(target / "receipt.json",report)
        print(json.dumps({"receipt":str(target / "receipt.json"),"passed":report.get("passed",False)}),flush=True)
    if not report.get("passed"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
