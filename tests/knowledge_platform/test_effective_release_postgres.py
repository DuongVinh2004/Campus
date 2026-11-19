"""Future preparation is allowed; activation/rollback still revalidate time."""
import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from campus247.application.knowledge.platform import KnowledgePlatform
from campus247.application.knowledge.platform_models import ConfirmInput, PlatformError, PreviewInput, ReviewInput
from campus247.domain.shared.values import generate_uuid7
from .test_incremental_index_postgres import add, setup, pytestmark


def test_future_release_can_prepare_but_neither_activate_nor_rollback_early(monkeypatch, retained_directory):
    async def run():
        pool, platform, author, worker, _, metadata = await setup(retained_directory)
        try:
            future = datetime.now(UTC)+timedelta(days=10)
            result, _, _ = await add(platform, author, worker, metadata.model_copy(update={"effective_from": future}),
                ["Synthetic future policy fixture; no institutional applicability asserted."], "future")
            reviewer = replace(author, subject_id=generate_uuid7(), external_subject="synthetic-future-review")
            await platform.review(reviewer, result["version_id"], ReviewInput(expected_revision=1, verdict="APPROVED", note="Synthetic mechanical review fixture, never institutional approval."))
            release = await platform.build_release(author, result["version_id"], "prepared")
            assert release["release_id"]
            for operation in ("activate", "rollback"):
                with pytest.raises(PlatformError, match="RELEASE_NOT_YET_EFFECTIVE"):
                    await platform.preview(reviewer, PreviewInput(operation=operation, target_id=release["release_id"], expected_generation=0))
            # Simulate a preview at a later business time, then clock correction
            # before confirmation. All auth/review/token checks remain real.
            check = KnowledgePlatform.activation_time
            monkeypatch.setattr(platform, "activation_time", lambda rows: check(rows, at_time=future+timedelta(days=1)))
            preview = await platform.preview(reviewer, PreviewInput(operation="activate", target_id=release["release_id"], expected_generation=0))
            monkeypatch.setattr(platform, "activation_time", check)
            with pytest.raises(PlatformError, match="RELEASE_NOT_YET_EFFECTIVE"):
                await platform.confirm(reviewer, ConfirmInput(preview_id=preview["preview_id"], confirmation_token=preview["confirmation_token"], confirmed=True), "early-confirm")
            async with pool.acquire() as conn:
                pointer = await platform.repo.pointer(conn)
                assert pointer["generation"] == 0 and pointer["release_id"] is None
                assert (await platform.repo.version(conn, result["version_id"]))["publication_state"] == "DRAFT"
                assert await conn.fetchval("SELECT consumed_at FROM knowledge_release_preview WHERE id=$1", preview["preview_id"]) is None
        finally:
            await pool.close()
    asyncio.run(run())


def test_metadata_copy_preserves_the_same_business_edition_and_observation(retained_directory):
    async def run():
        from campus247.application.knowledge.applicability import applicability_version
        from campus247.application.knowledge.platform_models import ApplicabilityInput
        from .test_edition_decisions import edition
        pool, platform, author, worker, _, metadata = await setup(retained_directory)
        try:
            _, _, result, _ = await edition(platform, author, worker, metadata)
            job = await platform.repo.claim(worker.owner, target_job_id=result["job_id"])
            assert job
            await worker._process(job)
            await platform.repo.finish(job, "SUCCEEDED")
            changed = await applicability_version(platform, author, result["version_id"], ApplicabilityInput(expected_revision=1,
                effective_from=datetime.now(UTC)+timedelta(days=1), basis="Synthetic metadata-copy fixture; independent publication review still required."), "metadata-copy")
            async with pool.acquire() as conn:
                original = await conn.fetchrow("SELECT * FROM knowledge_version_lineage WHERE version_id=$1 AND tenant_id=$2", result["version_id"], platform.repo.tenant)
                copied = await conn.fetchrow("SELECT * FROM knowledge_version_lineage WHERE version_id=$1 AND tenant_id=$2", changed["version_id"], platform.repo.tenant)
                assert copied and all(copied[field] == original[field] for field in ("edition_id", "observation_id", "rendition_identity"))
                assert (await platform.repo.version(conn, changed["version_id"]))["review_state"] == "NEEDS_REVIEW"
                assert await conn.fetchval("SELECT count(*) FROM knowledge_review WHERE version_id=$1", changed["version_id"]) == 0
        finally:
            await pool.close()
    asyncio.run(run())
