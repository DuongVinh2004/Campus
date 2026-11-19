"""Real 0021 PostgreSQL decision history; synthetic actors never publish."""
import asyncio
import io
import json
import os
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from starlette.datastructures import Headers, UploadFile

from campus247.application.knowledge.document_identity import ApplicabilityScope, DraftIntakeInput, EditionIdentity, EffectiveInterval, ScopeAxis, SourceWitness
from campus247.application.knowledge.edition_decisions import EditionDecisions, EditionDecisionInput, RelationDecisionInput
from campus247.application.knowledge.intake import KnowledgeIntake
from campus247.application.knowledge.platform import KnowledgePlatform
from campus247.application.knowledge.platform_models import IntakeMetadata, PlatformError, digest
from campus247.application.knowledge.version_resolver import ResolutionQuery, preview_resolution
from campus247.domain.action.confirmation import ConfirmationTokenService
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.knowledge.repository import KnowledgeRepository
from campus247.infrastructure.knowledge.storage import FileKnowledgeStorage
from campus247.ports.identity import IdentityContext, IdentityRole
from campus247_worker.knowledge import KnowledgeIngestionWorker
from .test_draft_postgres import NoModel
from .conftest import ROOT

pytestmark = pytest.mark.skipif(not os.environ.get("KNOWLEDGE_AUTOMATION_RELATIONS"), reason="Exact fresh 0021 rehearsal manifest required")


async def fixture(path):
    from knowledge_platform import components
    receipt = json.loads((ROOT / os.environ["KNOWLEDGE_AUTOMATION_RELATIONS"]).read_text(encoding="utf-8"))
    assert receipt["status"] == "passed" and receipt["revision"] == "0021"
    pool, _, _, _ = await components(rehearsal=ROOT / os.environ["KNOWLEDGE_AUTOMATION_RELATIONS"])
    tenant = "edition-test-"+uuid4().hex
    platform = KnowledgePlatform(KnowledgeRepository(pool, tenant), FileKnowledgeStorage(ROOT, path / "artifacts"), ConfirmationTokenService("edition-test-only-key"))
    now = datetime.now(UTC)
    creator = IdentityContext(generate_uuid7(), "synthetic-creator", "test", (IdentityRole.KNOWLEDGE_ADMIN,), "Synthetic creator", now, now+timedelta(hours=1), tenant_id=tenant, session_id="synthetic-test")
    reviewer = replace(creator, subject_id=generate_uuid7(), external_subject="synthetic-independent-reviewer")
    worker = KnowledgeIngestionWorker(platform.repo, platform.storage, NoModel(), owner="edition-test", low_watermark=0)
    return pool, platform, creator, reviewer, worker


async def edition(platform, creator, worker, metadata=None, *, source_text=None):
    intake = KnowledgeIntake(platform)
    text = source_text or "Synthetic issuer. Effective from 01/01/2026 with no stated end. This replaces the earlier synthetic edition."
    accepted = await intake.accept(creator, UploadFile(io.BytesIO(text.encode()), filename="synthetic-edition.txt", headers=Headers({"content-type":"text/plain"})), DraftIntakeInput(), uuid4().hex)
    job = await platform.repo.claim(worker.owner, target_job_id=accepted["job_id"])
    assert job is not None
    await platform.repo.finish(job, await worker._process(job))
    metadata = metadata or IntakeMetadata(title="Synthetic edition history", owner_unit="Synthetic issuer", canonical_uri="urn:edition:"+uuid4().hex, programs=["PUBLIC"], audiences=["STUDENT"])
    result = await intake.resolve(creator, accepted["intake_id"], 1, metadata, uuid4().hex)
    async with platform.repo.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM knowledge_version_lineage WHERE version_id=$1", result["version_id"])
        original = await conn.fetchval("SELECT original_id FROM knowledge_intake WHERE id=$1", accepted["intake_id"])
        extraction_hash = await conn.fetchval("SELECT output_sha256 FROM knowledge_job_step WHERE job_id=$1 AND stage='EXTRACT'", accepted["job_id"])
    witness = SourceWitness(artifact_id=original, artifact_sha256=accepted["original_sha256"], locator={"page_index":0,"page":None,
        "char_start":0,"char_end":len(text),"extraction_sha256":extraction_hash}, verbatim=text, text_sha256=digest(text.encode()))
    identity = EditionIdentity(tenant_id=platform.repo.tenant, family_id=result["source_id"], issuer="Synthetic issuer", identity_basis=witness,
        verification="VERIFIED", scope=ApplicabilityScope(programmes=ScopeAxis(kind="ALL"),cohorts=ScopeAxis(kind="ALL"),academic_years=ScopeAxis(kind="ALL")),
        effective=EffectiveInterval(from_day=date(2026,1,1),end_kind="OPEN",basis=witness))
    return row["edition_id"], identity, result, metadata


def test_identity_history_requires_independent_source_bound_decision_and_preserves_known_at(retained_directory):
    async def run():
        pool, platform, creator, reviewer, worker = await fixture(retained_directory)
        try:
            identifier, identity, result, _ = await edition(platform, creator, worker)
            service = EditionDecisions(platform)
            before = datetime.now(UTC)
            body = EditionDecisionInput(expected_revision=0, identity=identity, basis_note="Synthetic source checked in isolated test only.", confirmed_source_basis=True)
            with pytest.raises(PlatformError, match="SEPARATION_OF_DUTIES"):
                await service.identity(creator, identifier, body, "self")
            with pytest.raises(PlatformError, match="SOURCE_BASIS_CONFIRMATION_REQUIRED"):
                await service.identity(reviewer, identifier, body.model_copy(update={"confirmed_source_basis":False}), "unconfirmed")
            bad_witness = identity.identity_basis.model_copy(update={"locator": identity.identity_basis.locator | {"char_start":1}})
            with pytest.raises(PlatformError, match="WITNESS_LOCATOR_MISMATCH"):
                await service.identity(reviewer, identifier, body.model_copy(update={"identity": identity.model_copy(update={"identity_basis":bad_witness})}), "wrong-offset")
            with pytest.raises(PlatformError, match="KNOWLEDGE_FORBIDDEN"):
                await service.identity(replace(reviewer, tenant_id="other"), identifier, body, "other")
            saved = await service.identity(reviewer, identifier, body, "verify")
            assert saved["revision"] == 1 and not saved["admission_granted"] and not saved["release_changed"]
            assert (await service.identity(reviewer, identifier, body, "verify"))["is_replay"]
            with pytest.raises(PlatformError, match="EDITION_REVISION_CHANGED"):
                await service.identity(reviewer, identifier, body, "stale")
            query = ResolutionQuery(family_ids=(identity.family_id,), at_day=date(2026,10,26))
            past = await preview_resolution(platform, reviewer, query.model_copy(update={"known_at":before}))
            assert past["state"] == "NEEDS_INFORMATION"
            current = await preview_resolution(platform, reviewer, query)
            assert current["state"] == "RESOLVED" and not current["admission_granted"]
            async with pool.acquire() as conn:
                assert await conn.fetchval("SELECT count(*) FROM knowledge_review WHERE version_id=$1", result["version_id"]) == 0
                assert await conn.fetchval("SELECT count(*) FROM knowledge_release WHERE tenant_id=$1", platform.repo.tenant) == 0
                import asyncpg
                with pytest.raises(asyncpg.CheckViolationError):
                    async with conn.transaction():
                        await conn.execute("UPDATE knowledge_edition_decision SET basis_note='Altered evidence' WHERE id=$1", saved["decision_id"])
        finally:
            await pool.close()
    asyncio.run(run())


def test_relation_proposal_review_rejection_and_revision_history_never_publish(retained_directory):
    async def run():
        pool, platform, creator, reviewer, worker = await fixture(retained_directory)
        try:
            old, old_identity, old_result, metadata = await edition(platform, creator, worker)
            new, new_identity, _, _ = await edition(platform, creator, worker, metadata.model_copy(update={"source_id":old_result["source_id"]}))
            service = EditionDecisions(platform)
            for identifier, identity in ((old, old_identity), (new, new_identity)):
                await service.identity(reviewer, identifier, EditionDecisionInput(expected_revision=0,identity=identity,
                    basis_note="Independent synthetic identity assertion, no publication.",confirmed_source_basis=True), uuid4().hex)
            body = RelationDecisionInput(expected_revision=0, from_edition=new,to_edition=old,kind="REPLACES",effective=new_identity.effective,
                witness=new_identity.identity_basis,basis_note="Propose explicit replacement from retained synthetic source.")
            proposed = await service.relation(creator, body, "propose")
            assert (await service.relation(creator, body, "propose"))["is_replay"]
            revision = body.model_copy(update={"relation_id":UUID(proposed["relation_id"]),"expected_revision":1,"decision_state":"VERIFIED","confirmed_source_basis":True})
            with pytest.raises(PlatformError, match="SEPARATION_OF_DUTIES"):
                await service.relation(creator, revision, "self-verify")
            at_proposal = datetime.now(UTC)
            verified = await service.relation(reviewer, revision, "independent-verify")
            query = ResolutionQuery(family_ids=(old_identity.family_id,),at_day=date(2026,10,26))
            past = await preview_resolution(platform, reviewer, query.model_copy(update={"known_at":at_proposal}))
            assert past["state"] == "NEEDS_INFORMATION"
            current = await preview_resolution(platform,reviewer,query)
            assert [row["edition_id"] for row in current["segments"][0]["selected"]] == [str(new)]
            assert not current["admission_granted"]
            third = replace(reviewer,subject_id=generate_uuid7())
            rejected = revision.model_copy(update={"expected_revision":2,"decision_state":"REJECTED"})
            await service.relation(third,rejected,"reject-relation")
            current = await preview_resolution(platform,third,ResolutionQuery(family_ids=(old_identity.family_id,),at_day=date(2026,10,26)))
            assert current["state"] == "NEEDS_INFORMATION"  # Two editions now conflict; no latest-upload winner.
            async with pool.acquire() as conn:
                assert await conn.fetchval("SELECT count(*) FROM knowledge_edition_relation_decision WHERE relation_id=$1", proposed["relation_id"]) == 3
                assert await conn.fetchval("SELECT count(*) FROM knowledge_release WHERE tenant_id=$1", platform.repo.tenant) == 0
        finally:
            await pool.close()
    asyncio.run(run())


def test_workspace_is_source_bound_and_old_witness_survives_new_extraction(retained_directory):
    async def run():
        pool, platform, creator, reviewer, worker = await fixture(retained_directory)
        try:
            identifier, identity, result, _ = await edition(platform, creator, worker)
            service = EditionDecisions(platform)
            workspace = await service.workspace(creator, result["version_id"])
            assert workspace["state"] == "MAPPED" and workspace["expected_revision"] == 0
            assert workspace["identity"]["scope"]["cohorts"]["kind"] == "UNKNOWN"
            assert workspace["identity"]["effective"]["from_day"] is None
            assert workspace["page_witness"] == identity.identity_basis.model_dump(mode="json")
            assert not workspace["can_verify"] and not workspace["admission_granted"]
            assert (await service.workspace(reviewer, result["version_id"]))["can_verify"]
            with pytest.raises(PlatformError, match="INVALID_PAGE_INDEX"):
                await service.workspace(reviewer, result["version_id"], 999)
            with pytest.raises(PlatformError, match="KNOWLEDGE_FORBIDDEN"):
                await service.workspace(replace(reviewer, tenant_id="other"), result["version_id"])
            async with platform.repo.transaction() as conn:
                row = await service.edition(conn, identifier)
                job = await conn.fetchrow("SELECT * FROM knowledge_ingestion_job WHERE intake_id=$1 AND tenant_id=$2", row["observation_id"], platform.repo.tenant)
                extraction = {"pages": [{"page": None, "text": "New technical extraction retained separately."}], "page_count": 1, "issues": []}
                artifact = platform.storage.write_json(json.dumps(extraction).encode(), "synthetic-new-extraction")
                await platform.repo.save_step(conn, job, "EXTRACT", identity.identity_basis.artifact_sha256, "e"*64,
                    artifact.sha256, artifact, {"synthetic_fixture": True})
                # The new latest extraction is not substituted for the exact
                # hash/offsets held by the old immutable decision witness.
                await service.witness(conn, row, identity.identity_basis)
            newer = await service.workspace(reviewer, result["version_id"])
            assert newer["page_witness"]["locator"]["extraction_sha256"] == artifact.sha256
            assert newer["page_witness"]["verbatim"] != identity.identity_basis.verbatim
            saved = await service.identity(reviewer, identifier, EditionDecisionInput(expected_revision=0, identity=identity,
                basis_note="Old exact source witness remains addressable after re-extraction.", confirmed_source_basis=True), "old-witness")
            assert saved["revision"] == 1
        finally:
            await pool.close()
    asyncio.run(run())
