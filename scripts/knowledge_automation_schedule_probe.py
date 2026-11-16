"""Exercise actual background schedules in the restored prototype only.

Uses the designated local owner at the user's direct implementation request.
Creates observations and a prepared release from already admitted sources;
never reviews sources or confirms publication. Test schedules are cancelled
additively afterwards, retaining every definition, job, artifact and outcome.
"""
import asyncio
from datetime import UTC, datetime, timedelta
import json
from uuid import uuid4

import httpx

from knowledge_platform import ROOT, STATE, checked_path, components, model_budget, retain
from campus247_worker.knowledge import KnowledgeIngestionWorker

MANIFEST = ROOT / "infra/local/knowledge-automation-20261026/schema-rehearsal-bundle-20261026T174106266973.json"
SOURCE = "5c0b7c32-2740-720a-87a5-3db734608d01"


async def main():
    scope = checked_path(ROOT / "infra/local/knowledge-automation-20261026" /
        ("schedule-probe-"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")), ROOT)
    report = {"started_at": datetime.now(UTC), "publication_confirmed": False, "new_reviews": 0,
        "scope": "real source observation and prepared-release readiness only", "native_before": model_budget(), "schedules": []}
    pool, _, platform, runtime = await components(rehearsal=MANIFEST)
    try:
        async with pool.acquire() as conn:
            async with conn.transaction(readonly=True):
                report["pointer_before"] = await platform.repo.pointer(conn)
                source = await conn.fetchrow("""SELECT x.version_id,s.canonical_uri,s.title FROM knowledge_release_member m
                    JOIN knowledge_source s ON s.id=m.source_id JOIN knowledge_ingest_version x ON x.version_id=m.version_id
                    WHERE m.release_id=$1 AND m.source_id=$2 AND x.tenant_id=$3""",
                    report["pointer_before"]["release_id"], SOURCE, platform.repo.tenant)
                if not source:
                    raise ValueError("Exact admitted ready source required")
                await platform._eligible(conn, source["version_id"])
                report["source"] = dict(source)
        worker = KnowledgeIngestionWorker(platform.repo, platform.storage, runtime.embedding,
            owner="scoped-live-schedule-"+uuid4().hex, platform=platform,
            parser_python=checked_path(ROOT / ".venv/Scripts/python.exe", ROOT))
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8018", trust_env=False, follow_redirects=False, timeout=90) as client:
            credentials = json.loads((STATE / "owner-credentials.json").read_bytes())
            login = await client.post("/v1/knowledge/platform/session", json={key:credentials[key] for key in ("username", "password")})
            credentials = None
            login.raise_for_status()
            async def post(path, body=None):
                response = await client.post("/v1/knowledge/platform"+path, json=body, headers={"Idempotency-Key": uuid4().hex})
                if response.status_code >= 400:
                    report.setdefault("http_failures", []).append({"path":path, "status":response.status_code, "body":response.json()})
                response.raise_for_status()
                return response.json()
            try:
                accepted = await post("/url-intakes", {"url":source["canonical_uri"], "title_hint":source["title"]})
                report["initial_intake"] = accepted
                report["initial_worker_outcome"] = await worker.run_once(target_job_id=accepted["job_id"])
                listing = await client.get("/v1/knowledge/platform/intakes"); listing.raise_for_status()
                observed = next(item for item in listing.json()["items"] if item["id"] == accepted["intake_id"])
                report["initial_state"] = observed
                now = datetime.now(UTC)
                if observed.get("can_refresh_url"):
                    schedule = await post("/schedules", {"kind":"URL_REFRESH", "target_id":accepted["intake_id"],
                        "not_before":(now-timedelta(seconds=1)).isoformat(), "expires_at":(now+timedelta(minutes=20)).isoformat(),
                        "interval_seconds":900, "expected_original_sha256":observed["original_sha256"], "confirmed":True})
                    report["schedules"].append(schedule)
                # Reuses precisely the reviewed members. Build does not activate.
                prepared = await post(f"/versions/{source['version_id']}/releases")
                report["prepared_release"] = prepared
                release_schedule = await post("/schedules", {"kind":"RELEASE_DUE", "target_id":prepared["release_id"],
                    "not_before":(now-timedelta(seconds=1)).isoformat(), "expires_at":(now+timedelta(minutes=20)).isoformat(),
                    "interval_seconds":900, "expected_generation":report["pointer_before"]["generation"], "confirmed":True})
                report["schedules"].append(release_schedule)
                # Observe the actual lifespan loop; do not call the manual tick endpoint.
                for _ in range(20):
                    listing = await client.get("/v1/knowledge/platform/schedules"); listing.raise_for_status()
                    items = {item["id"]:item for item in listing.json()["items"]}
                    if all(items.get(item["id"],{}).get("last_outcome") for item in report["schedules"]):
                        break
                    await asyncio.sleep(2)
                report["background_outcomes"] = [items[item["id"]] for item in report["schedules"]]
                for item in report["background_outcomes"]:
                    outcome = item["last_outcome"]
                    if item["kind"] == "URL_REFRESH" and outcome and outcome["state"] == "QUEUED":
                        report["refresh_worker_outcome"] = await worker.run_once(target_job_id=outcome["job_id"])
                        async with pool.acquire() as conn:
                            report["observations"] = [dict(row) for row in await conn.fetch("""SELECT f.intake_id,a.sha256,f.acquisition
                                FROM knowledge_intake_fetch f JOIN knowledge_artifact a ON a.id=f.original_id AND a.tenant_id=f.tenant_id
                                WHERE f.tenant_id=$1 AND f.intake_id=ANY($2::uuid[]) ORDER BY f.recorded_at""",
                                platform.repo.tenant, [accepted["intake_id"], outcome["intake_id"]])]
                report["release_readiness_passed"] = any(item["kind"] == "RELEASE_DUE" and item["last_outcome"]
                    and item["last_outcome"]["state"] == "AWAITING_CONFIRMATION" for item in report["background_outcomes"])
                report["url_background_passed"] = len(report.get("observations", [])) == 2
            finally:
                report["cancellations"] = [await post(f"/schedules/{item['id']}/cancel") for item in report["schedules"]]
                await client.post("/v1/auth/logout")
        async with pool.acquire() as conn:
            report["pointer_after"] = await platform.repo.pointer(conn)
            report["pointer_unchanged"] = report["pointer_after"] == report["pointer_before"]
    except Exception as error:
        report["error_type"] = type(error).__name__
        raise
    finally:
        await pool.close()
        report.update(finished_at=datetime.now(UTC), native_after=model_budget())
        retain(scope / "receipt.json", report)
        print(json.dumps({"receipt":str(scope / "receipt.json"), "url_background_passed":report.get("url_background_passed"),
            "release_readiness_passed":report.get("release_readiness_passed"), "pointer_unchanged":report.get("pointer_unchanged")}))


if __name__ == "__main__":
    asyncio.run(main())
