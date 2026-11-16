"""Generic retained intake pilot in a fresh test DB namespace; never publishes.

Accepts any bounded public HUCE URL or workspace PDF/TXT, without a recipe for
that document. The actor is explicitly synthetic and supplies no reviewer grant.
"""
import argparse
import asyncio
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import asyncpg
from starlette.datastructures import UploadFile, Headers

from knowledge_platform import ROOT, checked_path, connection, model_budget, retain
from campus247.application.knowledge.document_identity import DraftIntakeInput, UrlIntakeInput
from campus247.application.knowledge.intake import KnowledgeIntake
from campus247.application.knowledge.platform import KnowledgePlatform
from campus247.application.knowledge.platform_models import EMBED_MODEL, EMBED_REVISION
from campus247.domain.action.confirmation import ConfirmationTokenService
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.knowledge.repository import KnowledgeRepository, json_value, public_row
from campus247.infrastructure.knowledge.storage import FileKnowledgeStorage
from campus247.ports.embedding import EmbeddingProfile
from campus247.ports.identity import IdentityContext, IdentityRole
from campus247_worker.knowledge import KnowledgeIngestionWorker


class DraftOnly:
    profile = EmbeddingProfile(EMBED_MODEL, EMBED_REVISION, 1024, batch_limit=1, timeout_ms=30000)
    async def _embed(self, inputs):
        raise RuntimeError("Draft intake cannot spend an embedding call or publish")


async def run(args):
    manifest = checked_path(args.rehearsal.absolute(), ROOT)
    rehearsal = json.loads(manifest.read_text(encoding="utf-8"))
    database = rehearsal["database"]
    if (rehearsal["status"] != "passed" or rehearsal["revision"] != "0020"
            or manifest.parent != ROOT / "infra/local/knowledge-automation-20261026"
            or not re.fullmatch(r"campus247_automation_20261026_[0-9a-f]{12}", database)):
        raise ValueError("An exact successful local rehearsal manifest is required")
    at = datetime.now(UTC)
    output = checked_path(ROOT / "infra/local/knowledge-automation-20261026" / ("pilot-" + at.strftime("%Y%m%dT%H%M%S%f")), ROOT)
    output.mkdir(exist_ok=False)
    tenant = "knowledge-pilot-" + uuid4().hex
    pool = await asyncpg.create_pool(**(connection() | {"database": database}), min_size=1, max_size=4)
    report = {"started_at": at.isoformat(), "database": database, "tenant": tenant,
        "actor": "synthetic intake test actor; no human or reviewer impersonation",
        "ui_journey_verified": False, "publication_attempted": False, "serving_database_changed": False,
        "native_before": model_budget(), "intakes": []}
    try:
        async with pool.acquire() as conn:
            if await conn.fetchval("SELECT version_num FROM alembic_version") != "0020":
                raise RuntimeError("Rehearsal schema mismatch")
        repo = KnowledgeRepository(pool, tenant)
        storage = FileKnowledgeStorage(ROOT, output / "artifacts")
        platform = KnowledgePlatform(repo, storage, ConfirmationTokenService("synthetic-pilot-no-confirmations"))
        intake = KnowledgeIntake(platform)
        actor = IdentityContext(generate_uuid7(), "pilot-fixture", "test", (IdentityRole.KNOWLEDGE_ADMIN,),
            "Synthetic intake test", at, at+timedelta(hours=1), tenant_id=tenant, session_id="pilot-fixture")
        parser = checked_path(ROOT / ".venv/Scripts/python.exe", ROOT)
        worker = KnowledgeIngestionWorker(repo, storage, DraftOnly(), owner="pilot-"+uuid4().hex,
            parser_python=parser, low_watermark=2*1024**3, platform=platform)
        report["parser_identity"] = worker.parser_identity
        for index, url in enumerate(args.url or []):
            accepted = await intake.accept_url(actor, UrlIntakeInput(url=url), "pilot-url-"+str(index))
            report["intakes"].append(accepted)
        for index, path in enumerate(args.file or []):
            path = checked_path(path.absolute(), ROOT)
            with path.open("rb") as source:
                prefix = source.read(8); source.seek(0)
                media, suffix = ("application/pdf", ".pdf") if prefix.startswith(b"%PDF-") else ("text/plain", ".txt")
                accepted = await intake.accept(actor, UploadFile(source, filename="source"+suffix,
                    headers=Headers({"content-type": media})), DraftIntakeInput(), "pilot-file-"+str(index))
            report["intakes"].append(accepted)
        for _ in report["intakes"]:
            report.setdefault("worker_outcomes", []).append(await worker.run_once())
        report["state"] = await intake.list(actor)
        # Instantiate the service again and compare persisted progress after the caller leaves.
        report["read_after_reopen_equal"] = report["state"] == await KnowledgeIntake(platform).list(actor)
        async with pool.acquire() as conn:
            report["steps"] = [public_row(row) for row in await conn.fetch("""SELECT j.id AS job_id,s.stage,s.input_sha256,
                s.config_sha256,s.output_sha256,s.artifact_id,s.result FROM knowledge_job_step s
                JOIN knowledge_ingestion_job j ON j.id=s.job_id WHERE j.tenant_id=$1 ORDER BY j.created_at,s.completed_at""", tenant)]
            report["previews"] = []
            for item in report["state"]["items"]:
                for issue in item["issues"]:
                    for page in issue["evidence"].get("preview_pages", []):
                        await intake.preview(actor, item["id"], page)
            artifacts = await conn.fetch("SELECT * FROM knowledge_artifact WHERE tenant_id=$1 AND kind='review-preview'", tenant)
            report["previews"] = [{"artifact_id": str(a["id"]), "path": str(storage.path(a["object_key"])), "sha256": a["sha256"]} for a in artifacts]
            report["source_versions_created"] = await conn.fetchval("SELECT count(*) FROM knowledge_ingest_version WHERE tenant_id=$1", tenant)
        report["status"] = "intake_extraction_checked" if all(i["state"] == "NEEDS_INFORMATION" for i in report["state"]["items"]) else "incomplete"
        report["no_auto_effectivity_or_admission"] = True
        # Novelty is checked against the serving catalog, without writing to it.
        serving = await asyncpg.connect(**connection())
        try:
            async with serving.transaction(readonly=True):
                report["novelty"] = [{"intake_id": item["id"],
                    "uri_present_in_serving_catalog": await serving.fetchval("SELECT EXISTS(SELECT 1 FROM knowledge_source WHERE canonical_uri=$1)", item["hints"].get("source_uri")),
                    "bytes_present_in_serving_artifacts": await serving.fetchval("SELECT EXISTS(SELECT 1 FROM knowledge_artifact WHERE sha256=$1)", item["original_sha256"])} for item in report["state"]["items"]]
        finally:
            await serving.close()
    except Exception as error:
        report.update(status="failed", error_type=type(error).__name__)
        raise
    finally:
        report.update(finished_at=datetime.now(UTC).isoformat(), native_after=model_budget())
        retain(output / "receipt.json", report)
        await pool.close()
        print(json.dumps({"receipt": str(output / "receipt.json"), "status": report["status"],
            "intakes": len(report["intakes"]), "previews": report.get("previews", [])}, default=str))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rehearsal", type=Path, required=True)
    parser.add_argument("--file", type=Path, action="append")
    parser.add_argument("--url", action="append")
    arguments = parser.parse_args()
    if not (arguments.file or arguments.url):
        parser.error("At least one exact file/URL is required")
    asyncio.run(run(arguments))
