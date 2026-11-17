"""Source-bound, independently verified edition decisions; no publication.

All revisions remain queryable by knowledge time. Proposals do not supply an
independent reviewer, and a document saying 'approved' cannot create authority.
"""
from datetime import UTC, datetime
import json
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from campus247.application.knowledge.document_identity import EditionIdentity, EffectiveInterval, SourceWitness, StrictModel
from campus247.application.knowledge.platform_models import PlatformError, digest
from campus247.application.knowledge.version_resolver import EditionRelation
from campus247.domain.shared.values import generate_uuid7
from campus247.application.knowledge.platform_models import json_value


class EditionDecisionInput(StrictModel):
    expected_revision: int = Field(ge=0)
    identity: EditionIdentity
    basis_note: str = Field(min_length=10, max_length=2000)
    confirmed_source_basis: bool = False


class RelationDecisionInput(StrictModel):
    relation_id: UUID | None = None
    expected_revision: int = Field(ge=0)
    from_edition: UUID
    to_edition: UUID
    kind: Literal["REPLACES", "PARTIAL_AMEND", "SUPPLEMENTS", "ALIAS"]
    effective: EffectiveInterval
    witness: SourceWitness
    target_unit_ids: frozenset[str] = frozenset()
    decision_state: Literal["PROPOSED", "VERIFIED", "REJECTED"] = "PROPOSED"
    basis_note: str = Field(min_length=10, max_length=2000)
    confirmed_source_basis: bool = False

    @model_validator(mode="after")
    def validate_relation(self):
        if self.from_edition == self.to_edition or self.expected_revision and self.relation_id is None:
            raise ValueError("Exact distinct editions and existing revision required")
        if self.kind == "PARTIAL_AMEND" and not self.target_unit_ids:
            raise ValueError("Partial amendment requires exact unit occurrences")
        return self


class EditionDecisions:
    def __init__(self, platform):
        self.platform, self.repo, self.storage = platform, platform.repo, platform.storage

    async def ready(self, conn):
        if not await conn.fetchval("SELECT to_regclass('knowledge_edition_decision') IS NOT NULL"):
            raise PlatformError(503, "EDITION_DECISION_SCHEMA_NOT_READY", "Chưa có schema lịch sử quyết định phiên bản.")

    async def edition(self, conn, identifier):
        row = await conn.fetchrow("""SELECT e.*,l.observation_id,x.original_id,x.revoked_at FROM knowledge_document_edition e
            JOIN knowledge_version_lineage l ON l.edition_id=e.id AND l.tenant_id=e.tenant_id
            JOIN knowledge_ingest_version x ON x.version_id=l.version_id AND x.tenant_id=l.tenant_id
            WHERE e.id=$1 AND e.tenant_id=$2 ORDER BY l.recorded_at DESC LIMIT 1""", identifier, self.repo.tenant)
        if not row:
            raise PlatformError(404, "EDITION_NOT_FOUND", "Không tìm thấy phiên bản nghiệp vụ trong phạm vi hiện tại.")
        return row

    @staticmethod
    def independent(actor, editions, previous=None):
        if any(str(row["created_by"]) == str(actor.subject_id) for row in editions) or previous and str(previous["created_by"]) == str(actor.subject_id):
            raise PlatformError(403, "SEPARATION_OF_DUTIES", "Người tạo hồ sơ hoặc đề xuất không được tự xác minh quyết định này.")

    async def witness(self, conn, edition, witness):
        original = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", edition["original_id"], self.repo.tenant)
        if witness.artifact_id != original["id"] or witness.artifact_sha256 != original["sha256"]:
            raise PlatformError(409, "WITNESS_SOURCE_MISMATCH", "Căn cứ phải thuộc bản gốc của đúng phiên bản.")
        self.storage.read(original)
        step = await conn.fetchrow("""SELECT step.* FROM knowledge_ingestion_job job JOIN knowledge_job_step step ON step.job_id=job.id
            WHERE job.intake_id=$1 AND job.tenant_id=$2 AND step.stage='EXTRACT' AND step.input_sha256=$3
            AND step.output_sha256=$4 ORDER BY step.completed_at DESC LIMIT 1""", edition["observation_id"], self.repo.tenant,
            original["sha256"], witness.locator.get("extraction_sha256"))
        if not step:
            raise PlatformError(409, "WITNESS_EXTRACTION_REQUIRED", "Chưa có bản trích xuất gắn với nguồn để đối chiếu.")
        artifact = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", step["artifact_id"], self.repo.tenant)
        raw = self.storage.read(artifact)
        if digest(raw) != step["output_sha256"]:
            raise PlatformError(409, "WITNESS_INTEGRITY", "Bản trích xuất không khớp checkpoint.")
        import json
        locator = witness.locator
        page_index, start, end = (locator.get(name) for name in ("page_index", "char_start", "char_end"))
        pages = json.loads(raw)["pages"]
        if (locator.get("extraction_sha256") != step["output_sha256"] or type(page_index) is not int or not 0 <= page_index < len(pages)
            or type(start) is not int or type(end) is not int or not 0 <= start < end <= len(pages[page_index]["text"])
            or locator.get("page") != pages[page_index]["page"] or pages[page_index]["text"][start:end] != witness.verbatim):
            raise PlatformError(409, "WITNESS_LOCATOR_MISMATCH", "Đoạn căn cứ hoặc vị trí không khớp nguồn đã gắn hash.")

    async def workspace(self, actor, version_id, page_index=0):
        """Current decisions and one exact source page for an admin to compare.

        No inferred dates, scope, semantics, reviewer, or serving authority.
        Historical extraction witnesses remain separately addressable by hash.
        """
        self.platform.admin(actor)
        if type(page_index) is not int or page_index < 0:
            raise PlatformError(422, "INVALID_PAGE_INDEX", "Chọn trang/khối hợp lệ.")
        from campus247.application.knowledge.values import public_row
        async with self.repo.transaction() as conn:
            await self.ready(conn)
            version = await self.repo.version(conn, version_id)
            lineage = await conn.fetchrow("SELECT * FROM knowledge_version_lineage WHERE version_id=$1 AND tenant_id=$2", version_id, self.repo.tenant)
            if not lineage:
                return {"state": "UNMAPPED", "reason": "LEGACY_IDENTITY_NOT_MAPPED", "admission_granted": False}
            edition = await self.edition(conn, lineage["edition_id"])
            previous = await conn.fetchrow("SELECT * FROM knowledge_edition_decision WHERE edition_id=$1 AND tenant_id=$2 ORDER BY revision DESC LIMIT 1", edition["id"], self.repo.tenant)
            decision = previous or edition
            payload = json_value(decision["identity"])
            if digest(payload) != decision["identity_sha256"]:
                raise PlatformError(409, "IDENTITY_INTEGRITY", "Định danh không khớp binding.")
            identity = EditionIdentity.model_validate(payload)
            if identity.tenant_id != self.repo.tenant or identity.family_id != version["source_id"]:
                raise PlatformError(409, "IDENTITY_INTEGRITY", "Định danh không thuộc nguồn hiện tại.")
            original = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", version["original_id"], self.repo.tenant)
            self.storage.read(original)
            step = await conn.fetchrow("""SELECT step.* FROM knowledge_ingestion_job job JOIN knowledge_job_step step ON step.job_id=job.id
                WHERE job.intake_id=$1 AND job.tenant_id=$2 AND step.stage='EXTRACT' AND step.input_sha256=$3
                ORDER BY step.completed_at DESC LIMIT 1""", lineage["observation_id"], self.repo.tenant, original["sha256"])
            page, total_pages, witness = None, 0, None
            if step:
                artifact = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", step["artifact_id"], self.repo.tenant)
                raw = self.storage.read(artifact)
                if digest(raw) != step["output_sha256"]:
                    raise PlatformError(409, "WITNESS_INTEGRITY", "Bản trích xuất không khớp checkpoint.")
                pages = json.loads(raw)["pages"]
                total_pages = len(pages)
                if not 0 <= page_index < total_pages:
                    raise PlatformError(422, "INVALID_PAGE_INDEX", "Trang/khối nằm ngoài bản trích xuất.")
                page = {"page_index": page_index, "page": pages[page_index]["page"], "text": pages[page_index]["text"]}
                if page["text"]:
                    witness = SourceWitness(artifact_id=original["id"], artifact_sha256=original["sha256"],
                        locator={"page_index": page_index, "page": page["page"], "char_start": 0,
                            "char_end": len(page["text"]), "extraction_sha256": step["output_sha256"]},
                        verbatim=page["text"], text_sha256=digest(page["text"].encode())).model_dump(mode="json")
            related = await conn.fetch("""SELECT e.id,e.created_by,e.recorded_at FROM knowledge_document_edition e
                JOIN knowledge_source_scope scope ON scope.source_id=e.source_id AND scope.tenant_id=e.tenant_id
                WHERE e.tenant_id=$1 AND e.source_id=$2 ORDER BY e.recorded_at,e.id LIMIT 100""", self.repo.tenant, version["source_id"])
            relations = await conn.fetch("""SELECT DISTINCT ON (relation_id) relation_id,revision,decision_state,relation,relation_sha256,created_by,basis_note
                FROM knowledge_edition_relation_decision WHERE tenant_id=$1 AND (from_edition=$2 OR to_edition=$2)
                ORDER BY relation_id,revision DESC""", self.repo.tenant, edition["id"])
            for relation in relations:
                if digest(json_value(relation["relation"])) != relation["relation_sha256"]:
                    raise PlatformError(409, "RELATION_INTEGRITY", "Quan hệ không khớp binding.")
            can_verify = not version["revoked_at"] and all(str(row["created_by"]) != actor.subject_id for row in [edition, *([previous] if previous else [])])
            return {"state": "MAPPED", "version_id": str(version_id), "edition_id": str(edition["id"]),
                "source_id": str(version["source_id"]), "identity": identity.model_dump(mode="json"),
                "expected_revision": previous["revision"] if previous else 0, "can_verify": can_verify,
                "recorded_at": str(decision["recorded_at"]), "basis_note": previous["basis_note"] if previous else None,
                "total_pages": total_pages, "page": page, "page_witness": witness,
                "related_editions": [public_row(row) for row in related],
                "relations": [{**public_row(row), "relation": json_value(row["relation"])} for row in relations],
                "admission_granted": False, "release_changed": False}

    async def identity(self, actor, edition_id, body, key):
        self.platform.admin(actor)
        fingerprint = digest({"edition_id": edition_id, **body.model_dump(mode="json")})
        async with self.repo.transaction() as conn:
            await self.ready(conn)
            replay = await self.repo.replay(conn, actor.subject_id, "edition-decision:"+key, fingerprint)
            if replay:
                return {**replay, "is_replay": True}
            from campus247.application.knowledge.edition_release import lock_decisions
            await lock_decisions(self.platform, conn)
            edition = await self.edition(conn, edition_id)
            await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1,0))", "edition-decision:"+self.repo.tenant+":"+str(edition_id))
            previous = await conn.fetchrow("SELECT * FROM knowledge_edition_decision WHERE edition_id=$1 AND tenant_id=$2 ORDER BY revision DESC LIMIT 1", edition_id, self.repo.tenant)
            current = previous["revision"] if previous else 0
            if body.expected_revision != current:
                raise PlatformError(409, "EDITION_REVISION_CHANGED", "Quyết định phiên bản đã đổi; cần đối chiếu lại.")
            if body.identity.tenant_id != self.repo.tenant or body.identity.family_id != edition["source_id"]:
                raise PlatformError(409, "EDITION_SCOPE_MISMATCH", "Định danh phải thuộc đúng nguồn và tenant.")
            if body.identity.verification == "VERIFIED":
                self.independent(actor, [edition], previous)
                if not body.confirmed_source_basis:
                    raise PlatformError(422, "SOURCE_BASIS_CONFIRMATION_REQUIRED", "Cần xác nhận đã đối chiếu căn cứ nguồn.")
                if edition["revoked_at"]:
                    raise PlatformError(409, "EDITION_REVOKED", "Nguồn đã bị thu hồi; quyết định metadata không phục hồi quyền sử dụng.")
            for witness in (body.identity.identity_basis, body.identity.effective.basis):
                if witness:
                    await self.witness(conn, edition, witness)
            identifier = generate_uuid7()
            await conn.execute("""INSERT INTO knowledge_edition_decision(id,tenant_id,edition_id,revision,identity,identity_sha256,basis_note,created_by)
                VALUES($1,$2,$3,$4,$5::jsonb,$6,$7,$8)""", identifier, self.repo.tenant, edition_id, current+1,
                body.identity.model_dump_json(), digest(body.identity.model_dump(mode="json")), body.basis_note, actor.subject_id)
            result = {"decision_id": identifier, "edition_id": str(edition_id), "revision": current+1, "admission_granted": False, "release_changed": False, "is_replay": False}
            await self.repo.audit(conn, actor.subject_id, "knowledge.edition.decision", identifier, {"edition_id": str(edition_id), "revision": current+1, "verification": body.identity.verification})
            await self.repo.remember(conn, actor.subject_id, "edition-decision:"+key, fingerprint, result)
            return result

    async def relation(self, actor, body, key):
        self.platform.admin(actor)
        request_payload = body.model_dump(mode="json")
        request_payload["target_unit_ids"] = sorted(body.target_unit_ids)
        fingerprint = digest(request_payload)
        async with self.repo.transaction() as conn:
            await self.ready(conn)
            replay = await self.repo.replay(conn, actor.subject_id, "edition-relation:"+key, fingerprint)
            if replay:
                return {**replay, "is_replay": True}
            from campus247.application.knowledge.edition_release import lock_decisions
            await lock_decisions(self.platform, conn)
            source, target = await self.edition(conn, body.from_edition), await self.edition(conn, body.to_edition)
            relation_id = str(body.relation_id or generate_uuid7())
            await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1,0))", "edition-relation:"+self.repo.tenant+":"+relation_id)
            previous = await conn.fetchrow("SELECT * FROM knowledge_edition_relation_decision WHERE relation_id=$1 AND tenant_id=$2 ORDER BY revision DESC LIMIT 1", relation_id, self.repo.tenant)
            current = previous["revision"] if previous else 0
            if body.expected_revision != current:
                raise PlatformError(409, "RELATION_REVISION_CHANGED", "Quan hệ đã có quyết định mới; cần đối chiếu lại.")
            if previous and (previous["from_edition"] != body.from_edition or previous["to_edition"] != body.to_edition):
                raise PlatformError(409, "RELATION_TARGET_CHANGED", "Quan hệ có định danh riêng; không chuyển sang cặp văn bản khác.")
            if body.decision_state in {"VERIFIED", "REJECTED"}:
                self.independent(actor, [source, target], previous)
                if not body.confirmed_source_basis:
                    raise PlatformError(422, "SOURCE_BASIS_CONFIRMATION_REQUIRED", "Cần xác nhận đã đối chiếu căn cứ nguồn.")
            await self.witness(conn, source, body.witness)
            if body.effective.basis:
                await self.witness(conn, source, body.effective.basis)
            relation = EditionRelation(from_edition=body.from_edition, to_edition=body.to_edition, kind=body.kind,
                effective=body.effective, recorded_at=datetime.now(UTC), witness=body.witness, target_unit_ids=body.target_unit_ids,
                decision_state="VERIFIED" if body.decision_state == "VERIFIED" else "PROPOSED", revision=current+1)
            identifier = generate_uuid7()
            relation_payload = relation.model_dump(mode="json")
            relation_payload["target_unit_ids"] = sorted(relation.target_unit_ids)
            await conn.execute("""INSERT INTO knowledge_edition_relation_decision(id,tenant_id,relation_id,revision,from_edition,to_edition,decision_state,
                relation,relation_sha256,basis_note,created_by) VALUES($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9,$10,$11)""",
                identifier, self.repo.tenant, relation_id, current+1, body.from_edition, body.to_edition, body.decision_state,
                json.dumps(relation_payload), digest(relation_payload), body.basis_note, actor.subject_id)
            result = {"decision_id": identifier, "relation_id": relation_id, "revision": current+1, "admission_granted": False, "release_changed": False, "is_replay": False}
            await self.repo.audit(conn, actor.subject_id, "knowledge.edition.relation", identifier, {"relation_id": relation_id, "revision": current+1, "decision_state": body.decision_state})
            await self.repo.remember(conn, actor.subject_id, "edition-relation:"+key, fingerprint, result)
            return result
