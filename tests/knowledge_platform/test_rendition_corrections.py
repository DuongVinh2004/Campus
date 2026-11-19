"""Real 0022 prose-correction history; no fake vectors or real-user approval."""
import asyncio
import io
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from starlette.datastructures import Headers, UploadFile

from campus247.application.knowledge.document_identity import DraftIntakeInput
from campus247.application.knowledge.intake import KnowledgeIntake
from campus247.application.knowledge.platform import KnowledgePlatform
from campus247.application.knowledge.platform_models import IntakeMetadata, PlatformError
from campus247.application.knowledge.rendition_corrections import CorrectionInput, CorrectionReviewInput, PageCorrection, RenditionCorrections
from campus247.domain.action.confirmation import ConfirmationTokenService
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.knowledge.repository import KnowledgeRepository
from campus247.infrastructure.knowledge.storage import FileKnowledgeStorage
from campus247.ports.identity import IdentityContext, IdentityRole
from campus247_worker.knowledge import KnowledgeIngestionWorker
from .conftest import ROOT
from .test_draft_postgres import NoModel
from .test_layout_intake import synthetic_pdf

pytestmark=pytest.mark.skipif(not os.environ.get("KNOWLEDGE_AUTOMATION_CORRECTIONS"),reason="Exact fresh 0022 rehearsal required")


async def setup(path,kind):
    from knowledge_platform import components
    pool,_,_,_=await components(rehearsal=ROOT / os.environ["KNOWLEDGE_AUTOMATION_CORRECTIONS"])
    repo=KnowledgeRepository(pool,"correction-test-"+uuid4().hex)
    platform=KnowledgePlatform(repo,FileKnowledgeStorage(ROOT,path / "artifacts"),ConfirmationTokenService("correction-test-key"))
    at=datetime.now(UTC)
    author=IdentityContext(generate_uuid7(),"synthetic-author","test",(IdentityRole.KNOWLEDGE_ADMIN,),"Synthetic author",at,at+timedelta(hours=1),tenant_id=repo.tenant,session_id="synthetic-correction")
    reviewer=replace(author,subject_id=generate_uuid7(),external_subject="synthetic-independent-reviewer")
    worker=KnowledgeIngestionWorker(repo,platform.storage,NoModel(),owner="correction-test",low_watermark=0,parser_python=ROOT / ".venv/Scripts/python.exe")
    intake=KnowledgeIntake(platform)
    accepted=await intake.accept(author,UploadFile(io.BytesIO(synthetic_pdf(kind)),filename="synthetic-prose.pdf",headers=Headers({"content-type":"application/pdf"})),DraftIntakeInput(),"draft")
    job=await repo.claim(worker.owner,target_job_id=accepted["job_id"])
    assert job is not None
    await repo.finish(job,await worker._process(job))
    resolved=await intake.resolve(author,accepted["intake_id"],1,IntakeMetadata(title="Synthetic prose correction",owner_unit="Synthetic publisher",canonical_uri="urn:correction:"+uuid4().hex,
        programs=["PUBLIC"],audiences=["STUDENT"]),"resolve")
    job=await repo.claim(worker.owner,target_job_id=resolved["job_id"])
    assert job is not None
    with pytest.raises(PlatformError,match="EXTRACTION_NEEDS_REVIEW"):
        await worker._process(job)
    await repo.finish(job,"FAILED","EXTRACTION_NEEDS_REVIEW")
    return pool,platform,author,reviewer,worker,resolved


def test_prose_correction_creates_new_rendition_of_same_edition_after_independent_review(retained_directory):
    async def run():
        pool,platform,author,reviewer,worker,resolved=await setup(retained_directory,"image")
        service=RenditionCorrections(platform)
        try:
            preview=await service.preview(author,resolved["version_id"])
            assert preview["pages"]
            page=preview["pages"][0]
            correction=CorrectionInput(expected_revision=preview["expected_revision"],expected_rendition_sha256=preview["expected_rendition_sha256"],
                pages=(PageCorrection(**page),),note="Synthetic exact native heading confirmed against the retained blank-image fixture.",confirmed_source_comparison=True)
            with pytest.raises(PlatformError,match="CORRECTION_AUTHOR_REQUIRED"):
                await service.propose(reviewer,resolved["version_id"],correction,"not-author")
            bad=correction.model_copy(update={"pages":(correction.pages[0].model_copy(update={"preview_image_sha256":"f"*64}),)})
            with pytest.raises(PlatformError,match="CORRECTION_IMAGE_CHANGED"):
                await service.propose(author,resolved["version_id"],bad,"wrong-image")
            proposed=await service.propose(author,resolved["version_id"],correction,"propose")
            assert (await service.history(reviewer,resolved["version_id"]))["items"][0]["revision"]==0
            detail=await service.detail(reviewer,proposed["correction_id"])
            assert detail["proposal_sha256"]==proposed["proposal_sha256"] and detail["pages"][0]["preview_image_sha256"]==page["preview_image_sha256"]
            assert (await service.propose(author,resolved["version_id"],correction,"propose"))["is_replay"]
            body=CorrectionReviewInput(expected_revision=0,expected_proposal_sha256=proposed["proposal_sha256"],verdict="APPROVED",coverage="PROSE_ONLY",
                note="Independent synthetic source-image comparison only; no public HUCE approval.",confirmed_full_page_and_conditions=True)
            with pytest.raises(PlatformError,match="SEPARATION_OF_DUTIES"):
                await service.review(author,proposed["correction_id"],body,"self")
            with pytest.raises(PlatformError,match="KNOWLEDGE_FORBIDDEN"):
                await service.review(replace(reviewer,tenant_id="other"),proposed["correction_id"],body,"other")
            approved=await service.review(reviewer,proposed["correction_id"],body,"review")
            history=(await service.history(reviewer,resolved["version_id"]))["items"][0]
            assert history["latest_verdict"]=="APPROVED" and history["version_id"]==approved["version_id"]
            assert approved["version_id"]!=resolved["version_id"] and not approved["admission_granted"] and not approved["release_changed"]
            assert (await service.review(reviewer,proposed["correction_id"],body,"review"))["is_replay"]
            async with pool.acquire() as conn:
                old=await platform.repo.version(conn,resolved["version_id"])
                new=await platform.repo.version(conn,approved["version_id"])
                assert old["original_id"]==new["original_id"] and old["rendition_id"]!=new["rendition_id"]
                assert old["effective_from"] is new["effective_from"] is None and old["effective_until"] is new["effective_until"] is None
                assert str(new["created_by"])==author.subject_id and new["review_state"]=="NEEDS_REVIEW"
                old_lineage=await conn.fetchrow("SELECT * FROM knowledge_version_lineage WHERE version_id=$1",resolved["version_id"])
                new_lineage=await conn.fetchrow("SELECT * FROM knowledge_version_lineage WHERE version_id=$1",approved["version_id"])
                assert old_lineage["edition_id"]==new_lineage["edition_id"] and old_lineage["observation_id"]==new_lineage["observation_id"]
                assert await conn.fetchval("SELECT count(*) FROM knowledge_review WHERE version_id=$1",approved["version_id"])==0
                assert await conn.fetchval("SELECT count(*) FROM knowledge_release WHERE tenant_id=$1",platform.repo.tenant)==0
            job=await platform.repo.claim(worker.owner,target_job_id=approved["job_id"])
            assert job is not None
            async def forbidden(*args): raise AssertionError("Verified correction must not reparse the original")
            worker._parse=forbidden
            try:
                with pytest.raises(AssertionError,match="embedding/model"):
                    await worker._process(job)
            finally:
                await platform.repo.finish(job,"FAILED","TEST_EMBEDDING_NOT_CALLED")
        finally:
            await pool.close()
    asyncio.run(run())


def test_prose_correction_cannot_clear_a_native_table_uncertainty(retained_directory):
    async def run():
        pool,platform,author,_,_,resolved=await setup(retained_directory,"table")
        try:
            service=RenditionCorrections(platform)
            preview=await service.preview(author,resolved["version_id"])
            body=CorrectionInput(expected_revision=preview["expected_revision"],expected_rendition_sha256=preview["expected_rendition_sha256"],
                pages=(PageCorrection(**preview["pages"][0]),),note="Must retain unknown table headers, units and cell relationships.",confirmed_source_comparison=True)
            with pytest.raises(PlatformError,match="STRUCTURED_CORRECTION_REQUIRED"):
                await service.propose(author,resolved["version_id"],body,"not-a-table-review")
            async with pool.acquire() as conn:
                assert await conn.fetchval("SELECT count(*) FROM knowledge_rendition_correction WHERE tenant_id=$1",platform.repo.tenant)==0
        finally:
            await pool.close()
    asyncio.run(run())
