"""Real isolated PostgreSQL release/resolver/citation guards, synthetic content.

Unit vectors check mechanics only. No operational review or HUCE applicability
is asserted by these synthetic actors and source witnesses.
"""
import asyncio
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from campus247.application.knowledge.document_identity import ScopeAxis
from campus247.application.knowledge.edition_decisions import EditionDecisions, EditionDecisionInput, RelationDecisionInput
from campus247.application.knowledge.release_members import MULTI_SCHEMA
from campus247.application.knowledge.platform_models import ConfirmInput, PlatformError, PreviewInput, ReviewInput
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.knowledge.repository import json_value
from campus247.infrastructure.knowledge.runtime import KnowledgeReleaseRuntime
from .test_edition_decisions import edition
from .test_incremental_index_postgres import setup, pytestmark


def decision(identity, revision=0):
    return EditionDecisionInput(expected_revision=revision, identity=identity,
        basis_note="Independent source-bound mechanical assertion in synthetic namespace only.", confirmed_source_basis=True)


async def prepared(platform, author, worker, metadata, reviewer, *, cohort=None, source_id=None, from_day=date(2026, 1, 1)):
    metadata = metadata.model_copy(update={"effective_from": datetime(2026, 1, 1, tzinfo=UTC), **({"source_id": source_id} if source_id else {})})
    text = f"Synthetic issuer. Effective from {from_day.strftime('%d/%m/%Y')} with no stated end. Cohort {cohort or 'ALL'}. This replaces the earlier synthetic edition."
    identifier, identity, result, _ = await edition(platform, author, worker, metadata, source_text=text)
    identity = identity.model_copy(update={"effective": identity.effective.model_copy(update={"from_day": from_day})})
    job = await platform.repo.claim(worker.owner, target_job_id=result["job_id"])
    assert job
    try:
        await worker._process(job)
    except Exception:
        await platform.repo.finish(job, "FAILED", "RETAINED_EDITION_RELEASE_FIXTURE")
        raise
    else:
        await platform.repo.finish(job, "SUCCEEDED")
    await platform.review(reviewer, result["version_id"], ReviewInput(expected_revision=1, verdict="APPROVED",
        note="Synthetic content mechanics only, never institutional publication approval."))
    if cohort:
        identity = identity.model_copy(update={"scope": identity.scope.model_copy(update={"cohorts": ScopeAxis(kind="VALUES", values=(cohort,))})})
    await EditionDecisions(platform).identity(reviewer, identifier, decision(identity), uuid4().hex)
    return identifier, identity, result


def context(platform, actor):
    return RetrievalContext(AuthorizedScope(platform.repo.tenant, "HUCE", actor.subject_id,
        frozenset({"STUDENT"}), frozenset({"STUDENT"}), frozenset({"FIT"}), frozenset({"PUBLIC"})),
        "vi", datetime.now(UTC), SimulationPolicy.DENY, "synthetic-edition-release")


async def publish(platform, publisher, release, generation=0):
    value = await platform.preview(publisher, PreviewInput(operation="activate", target_id=release["release_id"], expected_generation=generation))
    return await platform.confirm(publisher, ConfirmInput(preview_id=value["preview_id"], confirmation_token=value["confirmation_token"], confirmed=True), uuid4().hex)


def test_sealed_decision_applies_before_search_limit_and_citation_has_explicit_scope(retained_directory):
    async def run():
        pool, platform, author, worker, model, metadata = await setup(retained_directory)
        reviewer = replace(author, subject_id=generate_uuid7(), external_subject="synthetic-independent")
        try:
            identifier, identity, result = await prepared(platform, author, worker, metadata, reviewer, cohort="K68")
            release = await platform.build_release(author, result["version_id"], "bound-release")
            async with pool.acquire() as conn:
                profile = json_value(await conn.fetchval("SELECT profile FROM knowledge_release WHERE id=$1", release["release_id"]))
                assert profile["schema"] == MULTI_SCHEMA and profile["edition_binding"]["members"][0]["edition_id"] == str(identifier)
            await publish(platform, reviewer, release)
            runtime = KnowledgeReleaseRuntime(platform, None, None, instance_id="synthetic-resolver-test")
            ctx = context(platform, reviewer)
            async with pool.acquire() as conn:
                ids = [str(row["id"]) for row in await conn.fetch("SELECT id FROM knowledge_chunk WHERE document_version_id=$1", result["version_id"])]
                # Missing required cohort, even though the authorization scope
                # is valid, cannot supply a source to either search branch.
                assert await runtime._rows(conn, "Synthetic issuer", ctx, release["release_id"]) == []
                assert await runtime._rows(conn, "K69 Synthetic issuer", ctx, release["release_id"]) == []
                rows = await runtime._rows(conn, "K68 Synthetic issuer", ctx, release["release_id"])
                assert rows and all(str(row["document_version_id"]) == str(result["version_id"]) for row in rows)
                assert "cohorts=K68" in rows[0]["applicability_note"]
                citation = await runtime._rows(conn, "source", ctx, release["release_id"], ids=ids)
                assert citation and "cohorts=K68" in citation[0]["applicability_note"]
            runtime.current = None
            async def snapshot():
                async with pool.acquire() as conn:
                    return await platform.repo.pointer(conn)
            runtime.snapshot = snapshot
            excerpt = await runtime.read(str(result["source_id"]), str(result["version_id"]), ids[0], context=ctx)
            assert excerpt and "cohorts=K68" in excerpt.applicability_note
            # A new decision invalidates the seal despite unchanged pointer
            # generation. Current citation read must fail, not show stale proof.
            third = replace(reviewer, subject_id=generate_uuid7())
            changed = identity.model_copy(update={"scope": identity.scope.model_copy(update={"cohorts": ScopeAxis(kind="VALUES", values=("K69",))})})
            await EditionDecisions(platform).identity(third, identifier, decision(changed, 1), "changed-scope")
            with pytest.raises(PlatformError, match="EDITION_DECISIONS_CHANGED"):
                await runtime.read(str(result["source_id"]), str(result["version_id"]), ids[0], context=ctx)
            assert len(model.inputs) == 1  # No query-model calls in guard tests.
            async with pool.acquire() as conn:
                assert (await platform.repo.pointer(conn))["generation"] == 1
        finally:
            await pool.close()
    asyncio.run(run())


def test_decision_change_between_preview_and_confirmation_is_atomic_and_recoverable(retained_directory):
    async def run():
        pool, platform, author, worker, _, metadata = await setup(retained_directory)
        reviewer = replace(author, subject_id=generate_uuid7())
        try:
            identifier, identity, result = await prepared(platform, author, worker, metadata, reviewer)
            release = await platform.build_release(author, result["version_id"], "prepared")
            preview = await platform.preview(reviewer, PreviewInput(operation="activate", target_id=release["release_id"], expected_generation=0))
            third = replace(reviewer, subject_id=generate_uuid7())
            await EditionDecisions(platform).identity(third, identifier, decision(identity.model_copy(update={"verification": "CANDIDATE"}), 1), "withdraw-verification")
            with pytest.raises(PlatformError, match="EDITION_SOURCE_DECISION_REQUIRED"):
                await platform.confirm(reviewer, ConfirmInput(preview_id=preview["preview_id"], confirmation_token=preview["confirmation_token"], confirmed=True), "stale-confirm")
            async with pool.acquire() as conn:
                assert (await platform.repo.pointer(conn))["release_id"] is None
                assert (await platform.repo.version(conn, result["version_id"]))["publication_state"] == "DRAFT"
                assert await conn.fetchval("SELECT consumed_at FROM knowledge_release_preview WHERE id=$1", preview["preview_id"]) is None
                assert await conn.fetchval("SELECT count(*) FROM knowledge_edition_decision WHERE edition_id=$1", identifier) == 2
        finally:
            await pool.close()
    asyncio.run(run())


def test_distinct_cohorts_coexist_in_one_seal_and_original_table_protections_remain(retained_directory):
    async def run():
        pool, platform, author, worker, _, metadata = await setup(retained_directory)
        reviewer = replace(author, subject_id=generate_uuid7())
        try:
            _, _, first = await prepared(platform, author, worker, metadata, reviewer, cohort="K68")
            release = await platform.build_release(author, first["version_id"], "first")
            await publish(platform, reviewer, release)
            _, _, second = await prepared(platform, author, worker, metadata, reviewer, cohort="K69", source_id=str(first["source_id"]))
            candidate = await platform.build_release(author, second["version_id"], "second")
            assert len(candidate["members"]) == 2
            await publish(platform, reviewer, candidate, generation=1)
            runtime = KnowledgeReleaseRuntime(platform, None, None, instance_id="synthetic-multi-edition")
            ctx = context(platform, reviewer)
            async with pool.acquire() as conn:
                assert (await platform.repo.pointer(conn))["release_id"] == str(candidate["release_id"])
                assert len(await platform.repo.release_versions(conn, candidate["release_id"])) == 2
                assert await conn.fetchval("SELECT count(*) FROM knowledge_release_member WHERE release_id=$1", candidate["release_id"]) == 1
                profile = json_value(await conn.fetchval("SELECT profile FROM knowledge_release WHERE id=$1", candidate["release_id"]))
                assert len(profile["additional_members"]) == 1
                for cohort, target in (("K68", first), ("K69", second)):
                    rows = await runtime._rows(conn, cohort+" Synthetic issuer", ctx, candidate["release_id"])
                    assert rows and {str(row["document_version_id"]) for row in rows} == {str(target["version_id"])}
                import asyncpg
                with pytest.raises(asyncpg.CheckViolationError):
                    async with conn.transaction():
                        await conn.execute("UPDATE knowledge_release SET profile=profile WHERE id=$1", candidate["release_id"])
            state = await platform.state(reviewer)
            assert next(row for row in state["releases"] if row["id"] == str(candidate["release_id"]))["document_count"] == 2
            active = [row for row in state["versions"] if row["is_in_desired_release"]]
            assert len(active) == 2 and all(not row["is_historical"] for row in active)
        finally:
            await pool.close()
    asyncio.run(run())


def test_explicit_verified_replacement_is_bound_and_rejection_invalidates_serving(retained_directory):
    async def run():
        pool, platform, author, worker, _, metadata = await setup(retained_directory)
        reviewer = replace(author, subject_id=generate_uuid7())
        try:
            old, _, first = await prepared(platform, author, worker, metadata, reviewer)
            release = await platform.build_release(author, first["version_id"], "old")
            await publish(platform, reviewer, release)
            new, identity, second = await prepared(platform, author, worker, metadata, reviewer, source_id=str(first["source_id"]))
            candidate = await platform.build_release(author, second["version_id"], "unresolved")
            with pytest.raises(PlatformError, match="EDITION_RESOLUTION_REQUIRED"):
                await platform.preview(reviewer, PreviewInput(operation="activate", target_id=candidate["release_id"], expected_generation=1))
            service = EditionDecisions(platform)
            relation = RelationDecisionInput(expected_revision=0, from_edition=new, to_edition=old, kind="REPLACES",
                effective=identity.effective, witness=identity.identity_basis, basis_note="Synthetic source explicitly replaces earlier synthetic policy.")
            proposal = await service.relation(author, relation, "propose")
            verified = relation.model_copy(update={"relation_id": UUID(proposal["relation_id"]), "expected_revision": 1, "decision_state": "VERIFIED", "confirmed_source_basis": True})
            await service.relation(reviewer, verified, "verify")
            # Build a fresh immutable candidate; the earlier seal stays intact.
            resolved = await platform.build_release(author, second["version_id"], "resolved")
            await publish(platform, reviewer, resolved, generation=1)
            async with pool.acquire() as conn:
                await platform._release(conn, resolved["release_id"])
            await service.relation(replace(reviewer, subject_id=generate_uuid7()), verified.model_copy(update={"expected_revision": 2, "decision_state": "REJECTED"}), "reject")
            async with pool.acquire() as conn:
                with pytest.raises(PlatformError, match="EDITION_DECISIONS_CHANGED"):
                    await platform._release(conn, resolved["release_id"])
                assert await conn.fetchval("SELECT count(*) FROM knowledge_release WHERE tenant_id=$1", platform.repo.tenant) == 3
        finally:
            await pool.close()
    asyncio.run(run())


def test_future_preparation_keeps_current_seal_and_checks_business_day_at_activation(retained_directory):
    async def run():
        pool, platform, author, worker, _, metadata = await setup(retained_directory)
        reviewer = replace(author, subject_id=generate_uuid7())
        try:
            old, _, first = await prepared(platform, author, worker, metadata, reviewer)
            release = await platform.build_release(author, first["version_id"], "current")
            await publish(platform, reviewer, release)
            future_day = (datetime.now(UTC)+timedelta(days=10)).date()
            new, identity, second = await prepared(platform, author, worker, metadata, reviewer,
                source_id=str(first["source_id"]), from_day=future_day)
            relation = RelationDecisionInput(expected_revision=0, from_edition=new, to_edition=old, kind="REPLACES",
                effective=identity.effective, witness=identity.identity_basis, basis_note="Synthetic future replacement with date printed in retained source.")
            service = EditionDecisions(platform)
            proposed = await service.relation(author, relation, "future-proposal")
            await service.relation(reviewer, relation.model_copy(update={"relation_id": UUID(proposed["relation_id"]),
                "expected_revision": 1, "decision_state": "VERIFIED", "confirmed_source_basis": True}), "future-verify")
            candidate = await platform.build_release(author, second["version_id"], "future-prepared")
            assert {row["version_id"] for row in candidate["members"]} == {str(second["version_id"])}
            async with pool.acquire() as conn:
                await platform._release(conn, release["release_id"])
                assert (await platform.repo.pointer(conn))["release_id"] == str(release["release_id"])
            # Technical metadata was already effective; the business source
            # decision independently blocks premature activation and rollback.
            for operation in ("activate", "rollback"):
                with pytest.raises(PlatformError, match="EDITION_NOT_YET_EFFECTIVE"):
                    await platform.preview(reviewer, PreviewInput(operation=operation, target_id=candidate["release_id"], expected_generation=1))
            runtime = KnowledgeReleaseRuntime(platform, None, None, instance_id="synthetic-future")
            async with pool.acquire() as conn:
                rows = await runtime._rows(conn, "Synthetic issuer", context(platform, reviewer), release["release_id"])
                assert rows and {str(row["document_version_id"]) for row in rows} == {str(first["version_id"])}
                future_context = replace(context(platform, reviewer), effective_at=datetime.combine(future_day, datetime.min.time(), tzinfo=UTC))
                # A future view must not label the old edition current merely
                # because the new one has not been confirmed into membership.
                assert await runtime._rows(conn, "Synthetic issuer", future_context, release["release_id"]) == []
        finally:
            await pool.close()
    asyncio.run(run())


def test_batch_can_include_distinct_editions_but_rejects_two_renditions_of_one_edition(retained_directory):
    async def run():
        from campus247.application.knowledge.applicability import applicability_version
        from campus247.application.knowledge.platform_models import ApplicabilityInput
        pool, platform, author, worker, _, metadata = await setup(retained_directory)
        reviewer = replace(author, subject_id=generate_uuid7())
        try:
            _, _, first = await prepared(platform, author, worker, metadata, reviewer, cohort="K68")
            _, _, second = await prepared(platform, author, worker, metadata, reviewer, cohort="K69", source_id=str(first["source_id"]))
            targets = [str(first["version_id"]), str(second["version_id"])]
            release = await platform.build_batch_release(author, targets, "two-editions")
            assert len(release["members"]) == 2
            replay = await platform.build_batch_release(author, list(reversed(targets)), "two-editions")
            assert str(replay["release_id"]) == str(release["release_id"])
            await publish(platform, reviewer, release)
            copied = await applicability_version(platform, author, first["version_id"], ApplicabilityInput(expected_revision=2,
                effective_from=datetime(2026,1,1,tzinfo=UTC), basis="Synthetic same-edition rendition for duplicate-membership guard."), "copy")
            await platform.review(reviewer, copied["version_id"], ReviewInput(expected_revision=1, verdict="APPROVED", note="Synthetic copied-rendition review only."))
            with pytest.raises(PlatformError, match="DUPLICATE_RELEASE_EDITION"):
                await platform.build_batch_release(author, [str(first["version_id"]), str(copied["version_id"])], "duplicate-edition")
        finally:
            await pool.close()
    asyncio.run(run())
