"""Explicit local-engine smoke only; no paid model or synthetic BGE vectors."""
import asyncio
import io
import os
import subprocess
from dataclasses import replace

import pytest
from starlette.datastructures import Headers, UploadFile

from campus247.application.knowledge.document_identity import DraftIntakeInput
from campus247.application.knowledge.platform_models import PlatformError
from campus247_worker.knowledge import KnowledgeIngestionWorker, available_memory
from campus247_worker.knowledge_ocr import LocalOcrAdapter
from .conftest import ROOT
from .test_draft_postgres import setup, NoModel
from .test_layout_intake import synthetic_pdf

pytestmark = pytest.mark.skipif(os.environ.get("KNOWLEDGE_AUTOMATION_LOCAL_OCR_TESTS")!="1",reason="Explicit retained local OCR smoke opt-in required")


def test_local_network_guard_applies_before_socket_connect(retained_directory):
    from advanced_rag_frontend import NODE
    guard = ROOT / "services/worker/src/campus247_worker/knowledge_ocr_network_guard.cjs"
    result = subprocess.run([str(NODE),"--require",str(guard),"-e","require('node:net').connect(1,'127.0.0.1')"],cwd=retained_directory,
        capture_output=True,check=False,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    assert result.returncode != 0 and b"LOCAL_OCR_NETWORK_OR_PROCESS_DENIED" in result.stderr


def test_real_local_ocr_checkpoint_reuses_image_profile_without_inventing_semantics(retained_directory):
    memory = available_memory()
    if memory is not None and memory<2*1024**3:
        pytest.skip("Retained 2 GiB resource guard requires waiting; no cap reduction")
    async def run():
        from advanced_rag_frontend import NODE
        pool,repo,platform,actor,intake,_ = await setup(retained_directory)
        adapter = LocalOcrAdapter(platform.storage,node=NODE,package_root=NODE.parents[1] / "package.json")
        worker = KnowledgeIngestionWorker(repo,platform.storage,NoModel(),owner="local-ocr-smoke",parser_python=ROOT / ".venv/Scripts/python.exe",ocr_adapter=adapter)
        job = None
        try:
            accepted = await intake.accept(actor,UploadFile(io.BytesIO(synthetic_pdf("image")),filename="synthetic-image-with-native-heading.pdf",
                headers=Headers({"content-type":"application/pdf"})),DraftIntakeInput(),"local-ocr-smoke")
            job = await repo.claim(worker.owner,target_job_id=accepted["job_id"])
            assert job is not None
            assert await worker._process(job)=="NEEDS_INFORMATION"
            first = await intake.ocr(actor,accepted["intake_id"],1)
            assert first["source_sha256"]==accepted["original_sha256"] and first["semantics_verified"] is False and first["admission_granted"] is False
            assert first["profile"]["language"]=="vie" and first["profile"]["engine"]=="tesseract.js"
            async with pool.acquire() as conn:
                before = await conn.fetch("SELECT stage,artifact_id,output_sha256,completed_at FROM knowledge_job_step WHERE job_id=$1 ORDER BY stage",job["id"])
                assert {row["stage"] for row in before}=={"EXTRACT","EVIDENCE","RENDER:1","OCR:1","OCR_EVIDENCE:1"}
                assert first["evidence"]["unit_count"] > 0 and not first["evidence"]["admission_granted"]
                assert await conn.fetchval("SELECT count(*) FROM knowledge_ingest_version WHERE tenant_id=$1",repo.tenant)==0
            async def forbidden(*args): raise AssertionError("Committed parse/render/OCR checkpoint must be reused")
            worker._parse=forbidden; worker.renderer.render=forbidden; adapter.recognize=forbidden
            assert await worker._process(job)=="NEEDS_INFORMATION"
            assert (await intake.ocr(actor,accepted["intake_id"],1))["ocr_sha256"]==first["ocr_sha256"]
            with pytest.raises(PlatformError,match="KNOWLEDGE_FORBIDDEN"):
                await intake.ocr(replace(actor,tenant_id="other"),accepted["intake_id"],1)
            async with pool.acquire() as conn:
                assert await conn.fetch("SELECT stage,artifact_id,output_sha256,completed_at FROM knowledge_job_step WHERE job_id=$1 ORDER BY stage",job["id"])==before
            await repo.finish(job,"NEEDS_INFORMATION")
        finally:
            if job is not None:
                from campus247.infrastructure.knowledge.repository import LeaseLost
                try:
                    await repo.finish(job,"FAILED","TEST_FAILURE_IF_STILL_RUNNING")
                except LeaseLost:
                    pass  # A finished/stale job must not be changed by teardown.
            await pool.close()
    asyncio.run(run())
