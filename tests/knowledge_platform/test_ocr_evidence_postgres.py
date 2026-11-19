"""Checkpoint/API upgrade from a synthetic cached OCR result; no engine calls."""
import asyncio
from dataclasses import asdict, replace
import json
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest

from campus247.application.knowledge.platform_models import PlatformError, digest
from campus247.application.knowledge.document_identity import DraftIntakeInput
from .test_draft_postgres import setup, upload
from .test_ocr_evidence import fixture

pytestmark = pytest.mark.skipif(not os.environ.get("KNOWLEDGE_AUTOMATION_REHEARSAL"), reason="Explicit retained rehearsal required")


def test_cached_ocr_adds_a_separate_fenced_checkpoint_and_reuses_it(retained_directory):
    async def run():
        pool, repo, platform, actor, intake, worker = await setup(retained_directory)
        job = None
        try:
            accepted = await intake.accept(actor, upload(), DraftIntakeInput(), "cached-ocr-upgrade")
            job = await repo.claim(worker.owner, target_job_id=accepted["job_id"])
            assert await worker._process(job) == "NEEDS_INFORMATION"
            async with pool.acquire() as conn:
                original = await conn.fetchrow("""SELECT a.* FROM knowledge_intake i JOIN knowledge_artifact a
                    ON a.id=i.original_id AND a.tenant_id=i.tenant_id WHERE i.id=$1 AND i.tenant_id=$2""", accepted["intake_id"], repo.tenant)
            image_bytes, payload = fixture(page=1)
            image = platform.storage.write_bytes(image_bytes, "synthetic-image-header", "image/png")
            payload.update(source_sha256=original["sha256"], confidence=1)
            raw = json.dumps(payload).encode()
            ocr = platform.storage.write_json(raw, "synthetic-cached-ocr")
            worker.ocr = SimpleNamespace(profile=payload["automation_profile"], config_hash=digest(payload["automation_profile"]))
            binding = digest({"tenant_id": repo.tenant, "source_sha256": original["sha256"], "image_sha256": image.sha256, "page": 1})
            async with repo.fenced(job) as conn:
                await repo.save_step(conn, job, "RENDER:1", original["sha256"], "b"*64, image.sha256, image, {"synthetic_header_only": True})
                await repo.save_step(conn, job, "OCR:1", binding, worker.ocr.config_hash, ocr.sha256, ocr, {"synthetic_cached_output": True})
            old = await intake.ocr(actor, accepted["intake_id"], 1)
            assert old["evidence"] is None  # Existing OCR remains readable before the new stage.
            first = await worker._ocr_evidence(job, original, asdict(image), raw)
            view = await intake.ocr(actor, accepted["intake_id"], 1, limit=2)
            assert view["ocr_sha256"] == ocr.sha256 and view["evidence"]["manifest_sha256"] == first["sha256"]
            assert len(view["evidence"]["units"]) == 2 and view["evidence"]["next_offset"] == 2
            assert not view["evidence"]["admission_granted"] and not view["evidence"]["dependency_graph_verified"]
            async with pool.acquire() as conn:
                before = await conn.fetch("SELECT stage,artifact_id,output_sha256,completed_at FROM knowledge_job_step WHERE job_id=$1 ORDER BY stage", job["id"])
            assert await worker._ocr_evidence(job, original, asdict(image), raw) == first
            next_view = await intake.ocr(actor, accepted["intake_id"], 1, offset=2, limit=2)
            assert not {u["id"] for u in view["evidence"]["units"]} & {u["id"] for u in next_view["evidence"]["units"]}
            with pytest.raises(PlatformError, match="KNOWLEDGE_FORBIDDEN"):
                await intake.ocr(replace(actor, tenant_id="other"), accepted["intake_id"], 1)
            with pytest.raises(PlatformError, match="EVIDENCE_PAGE_INVALID"):
                await intake.ocr(actor, accepted["intake_id"], 1, limit=101)
            async with pool.acquire() as conn:
                assert await conn.fetch("SELECT stage,artifact_id,output_sha256,completed_at FROM knowledge_job_step WHERE job_id=$1 ORDER BY stage", job["id"]) == before
                assert await conn.fetchval("SELECT count(*) FROM knowledge_ingest_version WHERE tenant_id=$1", repo.tenant) == 0
            await repo.finish(job, "NEEDS_INFORMATION")
            from campus247.application.knowledge.platform_models import IntakeMetadata
            uri = "urn:synthetic:unresolved-publisher:"+uuid4().hex
            resolved = await intake.resolve(actor, accepted["intake_id"], 1, IntakeMetadata(
                title="Synthetic URN intake draft", owner_unit="Synthetic test fixture", canonical_uri=uri,
                programs=["SYNTHETIC_TEST_ONLY"], audiences=["KNOWLEDGE_ADMIN"]), "resolve-urn-fixture")
            platform.operational = True
            state = await platform.state(actor)
            assert any(v["version_id"] == resolved["version_id"] for v in state["versions"])
            source = next(s for s in state["sources"] if s["id"] == resolved["source_id"])
            assert source["canonical_uri"] == uri and not source["has_serving_version"]
            assert not state["is_serving"]
        finally:
            if job is not None:
                from campus247.infrastructure.knowledge.repository import LeaseLost
                try:
                    await repo.finish(job, "FAILED", "TEST_FAILURE_IF_STILL_RUNNING")
                except LeaseLost:
                    pass
            await pool.close()
    asyncio.run(run())
