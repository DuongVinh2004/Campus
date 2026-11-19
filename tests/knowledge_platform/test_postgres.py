"""Real DB tests in new retained tenant namespaces. No reset/drop/truncate.

Enable explicitly against the task-owned local DB. Model smoke is separate;
these tests create no vectors pretending to be BGE embeddings.
"""
import asyncio
import io
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from campus247.application.knowledge.platform_models import IntakeMetadata, PlatformError
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.knowledge.repository import KnowledgeRepository, LeaseLost
from campus247.infrastructure.knowledge.storage import FileKnowledgeStorage
from campus247.application.knowledge.platform import KnowledgePlatform
from campus247.domain.action.confirmation import ConfirmationTokenService
from campus247.ports.identity import IdentityContext, IdentityRole
from starlette.datastructures import Headers, UploadFile

from .conftest import ROOT

pytestmark = pytest.mark.skipif(os.environ.get("KNOWLEDGE_PLATFORM_LIVE_TESTS") != "1", reason="Explicit task-owned PostgreSQL opt-in required")


async def setup(path):
    import asyncpg
    from knowledge_platform import connection
    pool = await asyncpg.create_pool(**connection(), min_size=1,max_size=3)
    tenant = "knowledge-test-" + uuid4().hex
    repository = KnowledgeRepository(pool,tenant)
    storage = FileKnowledgeStorage(ROOT,path / "artifacts")
    service = KnowledgePlatform(repository,storage,ConfirmationTokenService("test-only-confirmation-key"))
    at = datetime.now(UTC)
    actor = IdentityContext(generate_uuid7(),"editor","test",(IdentityRole.KNOWLEDGE_ADMIN,),"Editor",at,at+timedelta(hours=1),
                            tenant_id=tenant,session_id="test-session")
    metadata = IntakeMetadata(title="Synthetic queue contract",owner_unit="Local test",canonical_uri="urn:queue:"+uuid4().hex,
                              programs=["PUBLIC"],audiences=["STUDENT"],effective_from=at-timedelta(days=1))
    return pool,repository,service,actor,metadata


def file():
    return UploadFile(io.BytesIO(b"Synthetic local queue contract, no institutional facts."),filename="contract.txt",headers=Headers({"content-type":"text/plain"}))


def test_idempotency_scope_and_authorization(retained_directory):
    async def run():
        pool, repo, service, actor, metadata = await setup(retained_directory)
        try:
            first = await service.upload(actor,metadata,file(),"same-request")
            replay = await service.upload(actor,metadata,file(),"same-request")
            assert first["version_id"] == replay["version_id"] and replay["is_replay"]
            with pytest.raises(PlatformError,match="IDEMPOTENCY_CONFLICT"):
                await service.upload(actor,metadata.model_copy(update={"title":"Different title"}),file(),"same-request")
            student = replace(actor,roles=(IdentityRole.STUDENT,),student_code="SYN001")
            count = len(list(service.storage.root.iterdir()))
            with pytest.raises(PlatformError,match="KNOWLEDGE_FORBIDDEN"):
                await service.upload(student,metadata,file(),"denied")
            assert len(list(service.storage.root.iterdir())) == count
            async with pool.acquire() as conn:
                assert await conn.fetchval("SELECT count(*) FROM knowledge_ingestion_job WHERE tenant_id=$1",repo.tenant) == 1
            state = await service.state(actor)
            assert len(state["versions"]) == 1 and not state["is_serving"]
            assert "object_key" not in str(state) and "storage_object_key" not in str(state)
        finally:
            await pool.close()
    asyncio.run(run())


def test_expired_owner_fenced_and_job_recoverable(retained_directory):
    async def run():
        pool, repo, service, actor, metadata = await setup(retained_directory)
        try:
            result = await service.upload(actor,metadata,file(),"lease-test")
            first = await repo.claim("process-A")
            assert await repo.claim("process-B") is None
            async with repo.transaction() as conn:
                await conn.execute("UPDATE knowledge_ingestion_job SET lease_until=clock_timestamp()-interval '1 second' WHERE id=$1",result["job_id"])
            second = await repo.claim("process-B")
            assert second["fencing_token"] == first["fencing_token"]+1
            assert not await repo.heartbeat(first)
            with pytest.raises(LeaseLost):
                async with repo.fenced(first):
                    pytest.fail("Old process was allowed to commit")
            async with repo.fenced(second) as conn:
                await repo.save_step(conn,second,"EXTRACT","a"*64,"b"*64,"c"*64,None,{"retained_contract_checkpoint":True})
            await service.job_action(actor,str(second["id"]),"cancel")
            with pytest.raises(LeaseLost):
                async with repo.fenced(second):
                    pytest.fail("Cancelled job was allowed to commit")
            await repo.finish(second,"CANCELLED")
            await service.job_action(actor,str(second["id"]),"retry")
            third = await repo.claim("process-C")
            checkpoint = await repo.checkpoint(third,"EXTRACT","a"*64,"b"*64)
            assert checkpoint and third["fencing_token"] > second["fencing_token"]
            await repo.finish(third,"FAILED","RETAINED_TEST_END")
        finally:
            await pool.close()
    asyncio.run(run())


def test_heavy_admission_serializes_different_tenants(retained_directory):
    async def run():
        first_pool, first_repo, first_service, first_actor, first_metadata = await setup(retained_directory)
        second_pool, second_repo, second_service, second_actor, second_metadata = await setup(retained_directory)
        claimed = []
        try:
            await first_service.upload(first_actor, first_metadata, file(), "first-tenant")
            await second_service.upload(second_actor, second_metadata, file(), "second-tenant")
            first = await first_repo.claim("tenant-A")
            assert first is not None
            claimed.append((first_repo, first))
            assert await second_repo.claim("tenant-B") is None
            await first_repo.finish(first, "FAILED", "RETAINED_ADMISSION_TEST_END")
            claimed.clear()
            second = await second_repo.claim("tenant-B")
            assert second is not None
            claimed.append((second_repo, second))
        finally:
            for repository, job in claimed:
                await repository.finish(job, "FAILED", "RETAINED_ADMISSION_TEST_END")
            await first_pool.close()
            await second_pool.close()
    asyncio.run(run())


def test_real_bge_release_membership_and_immutability(retained_directory):
    async def run():
        import asyncpg
        from knowledge_platform import models
        from campus247_worker.knowledge import KnowledgeIngestionWorker
        from campus247.application.knowledge.platform_models import ReviewInput,PreviewInput,ConfirmInput
        pool,repo,service,actor,metadata=await setup(retained_directory)
        reviewer=replace(actor,subject_id=generate_uuid7(),external_subject="reviewer",session_id="reviewer-session")
        try:
            embedding,_=models()
            worker=KnowledgeIngestionWorker(repo,service.storage,embedding,owner="real-bge-test")
            async def candidate(body,key):
                accepted=await service.upload(actor,body,file(),key)
                assert await worker.run_once()=="PROCESSED"
                state=await service.state(actor)
                job=next(j for j in state["jobs"] if j["id"]==accepted["job_id"])
                assert job["state"]=="SUCCEEDED",job
                version=next(v for v in state["versions"] if v["version_id"]==accepted["version_id"])
                await service.review(reviewer,version["version_id"],ReviewInput(expected_revision=version["revision"],verdict="APPROVED",note="Synthetic contract fixture, real BGE; not human source approval."))
                return accepted,await service.build_release(reviewer,version["version_id"],key)
            first,release=await candidate(metadata,"first")
            preview=await service.preview(reviewer,PreviewInput(operation="activate",target_id=release["release_id"],expected_generation=0))
            await service.confirm(reviewer,ConfirmInput(preview_id=preview["preview_id"],confirmation_token=preview["confirmation_token"],confirmed=True),"first-confirm")
            second_metadata=metadata.model_copy(update={"canonical_uri":"urn:second:"+uuid4().hex,"title":"Second retained source"})
            second,next_release=await candidate(second_metadata,"second")
            assert {m["version_id"] for m in next_release["members"]} == {first["version_id"],second["version_id"]}
            from campus247.application.knowledge.applicability import applicability_version
            from campus247.application.knowledge.platform_models import ApplicabilityInput
            updated=await applicability_version(service,actor,first["version_id"],ApplicabilityInput(expected_revision=2,
                effective_from=datetime.now(UTC)-timedelta(days=2),basis="Synthetic metadata-version contract; no institutional approval."),"metadata-copy")
            assert updated["new_model_calls"]==0 and updated["vectors_reused"]==1
            state=await service.state(actor)
            original=next(v for v in state["versions"] if v["version_id"]==first["version_id"])
            fresh=next(v for v in state["versions"] if v["version_id"]==updated["version_id"])
            assert original["review_state"]=="APPROVED" and fresh["review_state"]=="NEEDS_REVIEW"
            assert fresh["applicability_basis"].startswith("Synthetic metadata-version contract")
            with pytest.raises(PlatformError,match="REVIEW_BINDING_REQUIRED"):
                await service.build_release(reviewer,fresh["version_id"],"metadata-not-approved")
            async with pool.acquire() as conn:
                before=await conn.fetchval("SELECT title FROM knowledge_source WHERE id=$1",first["source_id"])
                with pytest.raises(asyncpg.CheckViolationError):
                    async with conn.transaction():
                        await conn.execute("UPDATE knowledge_source SET title='unexpected change' WHERE id=$1",first["source_id"])
                assert await conn.fetchval("SELECT title FROM knowledge_source WHERE id=$1",first["source_id"])==before
                assert await conn.fetchval("""SELECT old.embedding_rag_v1::text=new.embedding_rag_v1::text
                    FROM knowledge_chunk old JOIN knowledge_chunk new ON new.document_version_id=$2
                    WHERE old.document_version_id=$1""",first["version_id"],updated["version_id"])
                with pytest.raises(asyncpg.CheckViolationError):
                    async with conn.transaction():
                        await conn.execute("UPDATE knowledge_ingest_version SET original_id=$2 WHERE version_id=$1",first["version_id"],generate_uuid7())
                with pytest.raises(asyncpg.CheckViolationError):
                    async with conn.transaction():
                        await conn.execute("UPDATE knowledge_chunk SET content_text='unexpected change' WHERE document_version_id=$1",first["version_id"])
                member=next_release["members"][0]
                with pytest.raises(asyncpg.CheckViolationError):
                    async with conn.transaction():
                        await conn.execute("""INSERT INTO knowledge_release_member
                            (release_id,source_id,version_id,index_version,rendition_sha256,metadata_sha256)
                            VALUES ($1,$2,$3,$4,$5,$6)""",next_release["release_id"],*(member[k] for k in
                                ("source_id","version_id","index_version","rendition_sha256","metadata_sha256")))
        finally:
            await pool.close()
    asyncio.run(run())
