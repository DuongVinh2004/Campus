"""Real intake/review/publication with independent review and signed previews."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import PurePath

from campus247.application.document_request.certificates import preview_entity, serial
from campus247.application.knowledge.platform_models import (
    EMBED_ARTIFACT, IntakeMetadata, PROCESSOR, PlatformError, digest, metadata_binding,
)
from campus247.application.retrieval.profile import load_retrieval_profile
from campus247.application.knowledge.release_members import canonical_members, member_reads, merge_members, split_members
from campus247.domain.action.preview import create_action_preview
from campus247.domain.shared.values import generate_uuid7
from campus247.application.knowledge.platform_models import json_value
from campus247.application.knowledge.values import public_row
from campus247.ports.identity import IdentityRole


class KnowledgePlatform:
    def __init__(self, repository, storage, tokens):
        self.repo, self.storage, self.tokens = repository, storage, tokens

    def admin(self, actor):
        if (not actor.is_active or actor.expires_at <= datetime.now(UTC)
            or actor.tenant_id != self.repo.tenant or not actor.session_id
            or not any(actor.has_role(r) for r in (IdentityRole.KNOWLEDGE_ADMIN, IdentityRole.SYSTEM_ADMIN))):
            raise PlatformError(403, "KNOWLEDGE_FORBIDDEN", "Cần phiên quản trị tri thức đúng tenant.")

    def reader(self, actor):
        if (not actor.is_active or actor.expires_at <= datetime.now(UTC)
            or actor.tenant_id != self.repo.tenant or not actor.session_id
            or not any(actor.has_role(r) for r in (IdentityRole.STUDENT, IdentityRole.KNOWLEDGE_ADMIN, IdentityRole.SYSTEM_ADMIN))):
            raise PlatformError(403, "KNOWLEDGE_FORBIDDEN", "Cần phiên đọc tri thức đúng tenant.")

    async def upload(self, actor, metadata: IntakeMetadata, upload, key: str, *, artifact=None, _connection=None):
        self.admin(actor)
        if not key or len(key) > 128:
            raise PlatformError(422, "IDEMPOTENCY_REQUIRED", "Cần mã yêu cầu upload.")
        filename = upload.filename or ""
        if filename != PurePath(filename).name or any(c in filename for c in "\\/\r\n\x00") or len(filename) > 200:
            raise PlatformError(422, "INVALID_FILENAME", "Tên tệp không hợp lệ.")
        media = {".pdf": "application/pdf", ".txt": "text/plain"}.get(PurePath(filename.lower()).suffix)
        if not media or upload.content_type not in {media, "application/octet-stream"}:
            raise PlatformError(415, "UNSUPPORTED_MEDIA", "Hỗ trợ PDF và TXT UTF-8 với MIME phù hợp.")
        artifact = artifact or await self.storage.receive(upload, media)
        content = metadata.model_dump(mode="json", exclude={"source_id"})
        fingerprint = digest({"metadata": content, "source_id": metadata.source_id,
                              "sha256": artifact.sha256, "filename": filename, "processor": PROCESSOR})
        async with self.repo.transaction(_connection) as conn:
            replay = await self.repo.replay(conn, actor.subject_id, "upload:" + key, fingerprint)
            if replay:
                return {**replay, "is_replay": True}
            source_id = metadata.source_id or generate_uuid7()
            if metadata.source_id:
                source = await conn.fetchrow("""SELECT s.* FROM knowledge_source s
                    JOIN knowledge_source_scope x ON x.source_id=s.id
                    WHERE s.id=$1 AND x.tenant_id=$2 FOR UPDATE OF s""", source_id, self.repo.tenant)
                if not source:
                    raise PlatformError(404, "SOURCE_NOT_FOUND", "Không tìm thấy nguồn.")
                expected = (metadata.title, metadata.owner_unit, metadata.canonical_uri, metadata.authority_level,
                            metadata.campus, metadata.faculties, metadata.programs, metadata.audiences)
                actual = tuple(source[k] for k in ("title", "owner_unit", "canonical_uri", "authority_level",
                                                   "campus_scope", "faculty_scope", "program_scope", "audiences"))
                if actual != expected:
                    raise PlatformError(409, "SOURCE_SCOPE_CHANGED", "Nguồn mới cần giữ metadata/phạm vi của nguồn đã chọn.")
            else:
                # Global legacy URI uniqueness is retained. Never reveal another tenant's row.
                inserted = await conn.fetchval("""INSERT INTO knowledge_source
                    (id,source_type,canonical_uri,title,owner_unit,authority_level,approval_status,is_synthetic,
                     campus_scope,faculty_scope,program_scope,audiences)
                    VALUES ($1,'OFFICIAL_DOCUMENT',$2,$3,$4,$5,'DRAFT',false,$6,$7,$8,$9)
                    ON CONFLICT(canonical_uri) DO NOTHING RETURNING id""", source_id, metadata.canonical_uri,
                    metadata.title, metadata.owner_unit, metadata.authority_level, metadata.campus,
                    metadata.faculties, metadata.programs, metadata.audiences)
                if not inserted:
                    raise PlatformError(409, "SOURCE_URI_CONFLICT", "URI đã đăng ký; chọn nguồn hiện có trong phạm vi được cấp.")
                await conn.execute("INSERT INTO knowledge_source_scope(source_id,tenant_id,created_by) VALUES ($1,$2,$3)",
                                   source_id, self.repo.tenant, actor.subject_id)
            version_id, job_id = generate_uuid7(), generate_uuid7()
            registered = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", artifact.id, self.repo.tenant)
            if registered:
                if any(registered[k] != getattr(artifact, k) for k in ("object_key", "sha256", "byte_size", "media_type", "kind")):
                    raise PlatformError(409, "ARTIFACT_INTEGRITY", "Artifact tiếp nhận không khớp binding.")
                self.storage.read(registered)
            else:
                await self.repo.artifact(conn, artifact)
            await conn.execute("""INSERT INTO document_version
                (id,knowledge_source_id,version_label,content_checksum,effective_from,effective_until,status,storage_object_key)
                VALUES ($1,$2,$3,$4,$5,$6,'DRAFT',$7)""", version_id, source_id, version_id,
                artifact.sha256, metadata.effective_from, metadata.effective_until, artifact.object_key)
            await conn.execute("""INSERT INTO knowledge_ingest_version
                (version_id,tenant_id,original_id,filename,created_by,metadata_sha256,processor_profile)
                VALUES ($1,$2,$3,$4,$5,$6,$7)""", version_id, self.repo.tenant, artifact.id, filename,
                actor.subject_id, digest(content), PROCESSOR)
            await conn.execute("INSERT INTO knowledge_ingestion_job(id,tenant_id,version_id) VALUES ($1,$2,$3)",
                               job_id, self.repo.tenant, version_id)
            result = {"source_id": source_id, "version_id": version_id, "job_id": job_id,
                      "state": "QUEUED", "original_sha256": artifact.sha256, "is_replay": False}
            await self.repo.audit(conn, actor.subject_id, "knowledge.upload", version_id,
                                  {"sha256": artifact.sha256, "job_id": job_id})
            await self.repo.outbox(conn, "knowledge.upload.accepted", version_id, result)
            await self.repo.remember(conn, actor.subject_id, "upload:" + key, fingerprint, result)
            return result

    async def state(self, actor):
        self.admin(actor)
        async with self.repo.transaction() as conn:
            sources = await conn.fetch("""SELECT s.id,s.title,s.owner_unit,s.canonical_uri,s.approval_status,
                s.source_type,s.authority_level,s.version
                FROM knowledge_source s JOIN knowledge_source_scope x ON x.source_id=s.id
                WHERE x.tenant_id=$1 ORDER BY s.created_at DESC LIMIT 200""", self.repo.tenant)
            versions = await conn.fetch(member_reads("""SELECT x.version_id,x.filename,x.created_by,x.review_state,x.revision,
                x.rendition_sha256,x.metadata_sha256,x.revoked_at,v.knowledge_source_id AS source_id,
                v.effective_from,v.effective_until,v.status AS publication_state,v.index_version,v.created_at,
                (SELECT rv.note FROM knowledge_review rv WHERE rv.version_id=x.version_id
                    ORDER BY rv.created_at DESC,rv.id DESC LIMIT 1) AS review_note,
                a.sha256 AS original_sha256,a.byte_size,
                EXISTS(SELECT 1 FROM knowledge_release_member member JOIN knowledge_release_pointer pointer
                    ON pointer.release_id=member.release_id WHERE member.version_id=x.version_id
                    AND pointer.tenant_id=x.tenant_id AND pointer.campus_id='HUCE') AS is_in_desired_release,
                (SELECT step.result->>'applicability_basis' FROM knowledge_job_step step
                    JOIN knowledge_ingestion_job job ON job.id=step.job_id
                    WHERE job.version_id=x.version_id AND step.stage='METADATA' LIMIT 1) AS applicability_basis
                FROM knowledge_ingest_version x JOIN document_version v ON v.id=x.version_id
                JOIN knowledge_artifact a ON a.id=x.original_id
                WHERE x.tenant_id=$1 ORDER BY v.created_at DESC LIMIT 500"""), self.repo.tenant)
            jobs = await conn.fetch("""SELECT id,version_id,state,stage,progress,attempts,error_code,
                cancel_requested,heartbeat_at,updated_at FROM knowledge_ingestion_job
                WHERE tenant_id=$1 ORDER BY created_at DESC LIMIT 200""", self.repo.tenant)
            releases = await conn.fetch(member_reads("""SELECT r.id,r.predecessor_id,r.membership_sha256,r.created_at,
                count(m.version_id) AS document_count FROM knowledge_release r
                JOIN knowledge_release_seal seal ON seal.release_id=r.id
                LEFT JOIN knowledge_release_member m ON m.release_id=r.id
                WHERE r.tenant_id=$1 GROUP BY r.id ORDER BY r.created_at DESC LIMIT 50"""), self.repo.tenant)
            desired = await self.repo.pointer(conn)
            acks = await conn.fetch("""SELECT instance_id,boot_id,release_id,generation,policy_generation,
                valid_until,error_code,heartbeat_at,valid_until>clock_timestamp() AS live
                FROM knowledge_runtime_ack WHERE tenant_id=$1 AND campus_id=$2""", self.repo.tenant, self.repo.campus)
            serving = [public_row(a) for a in acks if a["live"] and not a["error_code"]
                       and str(a["release_id"]) == desired["release_id"] and a["generation"] == desired["generation"]
                       and a["policy_generation"] == desired["policy_generation"]]
            version_items=[public_row(r) for r in versions]
            source_items=[public_row(r) for r in sources]
            dispositions = []
            if await conn.fetchval("SELECT to_regclass('knowledge_source_disposition') IS NOT NULL"):
                dispositions = await conn.fetch("""SELECT DISTINCT ON (source_id) source_id,original_sha256,category,
                    related_source_id,note,created_at FROM knowledge_source_disposition WHERE tenant_id=$1
                    ORDER BY source_id,created_at DESC,id DESC""", self.repo.tenant)
            by_source = {str(item["source_id"]): public_row(item) for item in dispositions}
            for source in source_items:
                if source["id"] in by_source:
                    source["disposition"] = by_source[source["id"]]
            active_versions = {version["source_id"]: version for version in version_items if version["is_in_desired_release"]}
            for version in version_items:
                active = active_versions.get(version["source_id"])
                version["is_historical"] = bool(not version["is_in_desired_release"] and active and active["version_id"] != version["version_id"]
                    and active["created_at"] > version["created_at"])
            if getattr(self, "operational", False):
                # HUCE acquisition receipts also bind originals hosted on Drive/CDN.
                # A newly received draft may have an explicit URN while its
                # publisher is unresolved. Keep its own tenant-bound intake
                # visible for admin comparison; this grants no serving status.
                intake_sources = set()
                if await conn.fetchval("SELECT to_regclass('knowledge_intake_resolution') IS NOT NULL"):
                    intake_sources = {str(row["source_id"]) for row in await conn.fetch("""SELECT DISTINCT v.knowledge_source_id AS source_id
                        FROM knowledge_intake_resolution r JOIN document_version v ON v.id=r.version_id
                        JOIN knowledge_source_scope scope ON scope.source_id=v.knowledge_source_id AND scope.tenant_id=r.tenant_id
                        WHERE r.tenant_id=$1""", self.repo.tenant)}
                source_items = [s for s in source_items if s["canonical_uri"].startswith("https://") or s["id"] in intake_sources]
                source_ids = {s["id"] for s in source_items}
                version_items = [v for v in version_items if v["source_id"] in source_ids]
                version_ids = {v["version_id"] for v in version_items}
                jobs = [j for j in jobs if str(j["version_id"]) in version_ids]
                real_releases = await conn.fetch(member_reads("""SELECT r.id FROM knowledge_release r WHERE r.tenant_id=$1
                    AND EXISTS(SELECT 1 FROM knowledge_release_member m WHERE m.release_id=r.id)
                    AND NOT EXISTS(SELECT 1 FROM knowledge_release_member m JOIN knowledge_source s ON s.id=m.source_id
                        WHERE m.release_id=r.id AND s.canonical_uri NOT LIKE 'https://%')"""), self.repo.tenant)
                real_ids = {str(r["id"]) for r in real_releases}
                releases = [r for r in releases if str(r["id"]) in real_ids]
            at=datetime.now(UTC)
            for source in source_items:
                source["has_serving_version"]=bool(serving) and any(
                    v["source_id"]==source["id"] and v["is_in_desired_release"] and not v["revoked_at"]
                    and v["review_state"]=="APPROVED" and v["publication_state"]=="PUBLISHED"
                    and v["effective_from"] and datetime.fromisoformat(v["effective_from"])<=at
                    and (not v["effective_until"] or datetime.fromisoformat(v["effective_until"])>at) for v in version_items)
            return {"mode": "postgres_bge", "environment": getattr(self, "runtime_environment", "operational"),
                "session_schedules_available": hasattr(self, "schedules"),
                "edition_decisions_available":await conn.fetchval("SELECT to_regclass('knowledge_edition_decision') IS NOT NULL"),
                "correction_history_available":await conn.fetchval("SELECT to_regclass('knowledge_rendition_correction') IS NOT NULL"),"sources": source_items,
                    "versions": version_items, "jobs": [public_row(r) for r in jobs],
                    "releases": [public_row(r) for r in releases], "desired": desired,
                    "serving": serving, "runtime": [public_row(r) for r in acks],
                    "release_prepared": bool(serving) and desired["release_id"] is not None,
                    "is_serving": any(s["has_serving_version"] for s in source_items)}

    async def availability(self):
        """Public counts only; an acknowledgement alone is not usable knowledge."""
        async with self.repo.transaction() as conn:
            pointer = await self.repo.pointer(conn)
            prepared = await conn.fetchval("""SELECT EXISTS(SELECT 1 FROM knowledge_runtime_ack
                WHERE tenant_id=$1 AND campus_id=$2 AND release_id=$3 AND generation=$4
                AND policy_generation=$5 AND valid_until>clock_timestamp() AND error_code IS NULL)""",
                self.repo.tenant, self.repo.campus, pointer["release_id"], pointer["generation"], pointer["policy_generation"])
            counts = await conn.fetchrow(member_reads("""SELECT count(DISTINCT s.id) AS sources,
                count(*) FILTER (WHERE x.review_state='NEEDS_REVIEW') AS pending,
                count(*) FILTER (WHERE x.review_state='NEEDS_REVIEW' AND EXISTS(
                    SELECT 1 FROM knowledge_release_member historical
                    JOIN knowledge_ingest_version current_version ON current_version.version_id=historical.version_id
                    JOIN document_version current_document ON current_document.id=current_version.version_id
                    WHERE historical.release_id=$2 AND historical.source_id=s.id
                    AND current_version.review_state='APPROVED' AND current_version.revoked_at IS NULL
                    AND current_document.created_at>v.created_at)) AS historical_pending,
                count(*) FILTER (WHERE x.revoked_at IS NOT NULL) AS withdrawn,
                count(*) FILTER (WHERE x.revoked_at IS NULL AND x.review_state='APPROVED'
                    AND v.status='PUBLISHED' AND s.approval_status='APPROVED'
                    AND v.effective_from<=clock_timestamp()
                    AND (v.effective_until IS NULL OR v.effective_until>clock_timestamp())
                    AND EXISTS(SELECT 1 FROM knowledge_release_member m WHERE m.release_id=$2 AND m.version_id=x.version_id)
                    AND EXISTS(SELECT 1 FROM knowledge_review rv WHERE rv.version_id=x.version_id
                        AND rv.verdict='APPROVED' AND rv.reviewer_id<>x.created_by
                        AND rv.rendition_sha256=x.rendition_sha256 AND rv.metadata_sha256=x.metadata_sha256)) AS eligible
                FROM knowledge_ingest_version x JOIN document_version v ON v.id=x.version_id
                JOIN knowledge_source s ON s.id=v.knowledge_source_id
                WHERE x.tenant_id=$1 AND NOT s.is_synthetic
                AND s.canonical_uri LIKE 'https://%'"""), self.repo.tenant, pointer["release_id"])
            ready = bool(prepared and counts["eligible"])
            equivalents = 0
            equivalent_pending = 0
            limited_sources = 0
            scope_unresolved_sources = 0
            if prepared and await conn.fetchval("SELECT to_regclass('knowledge_source_disposition') IS NOT NULL"):
                aliases = await conn.fetchrow(member_reads("""WITH latest AS (
                    SELECT DISTINCT ON (source_id) source_id,category,related_source_id
                    FROM knowledge_source_disposition WHERE tenant_id=$1 ORDER BY source_id,created_at DESC,id DESC),
                    covered AS (SELECT d.source_id FROM latest d
                    JOIN knowledge_release_member m ON m.source_id=d.related_source_id AND m.release_id=$2
                    JOIN knowledge_ingest_version current ON current.version_id=m.version_id
                    JOIN document_version current_document ON current_document.id=m.version_id
                    WHERE d.category='EQUIVALENT_SOURCE_ALIAS' AND current.review_state='APPROVED'
                    AND current.revoked_at IS NULL AND current_document.status='PUBLISHED'
                    AND current_document.effective_from<=clock_timestamp()
                    AND (current_document.effective_until IS NULL OR current_document.effective_until>clock_timestamp())
                    AND NOT EXISTS(SELECT 1 FROM knowledge_release_member own WHERE own.release_id=$2 AND own.source_id=d.source_id))
                    SELECT (SELECT count(*) FROM covered) AS sources,
                    (SELECT count(*) FROM covered c JOIN document_version v ON v.knowledge_source_id=c.source_id
                        JOIN knowledge_ingest_version x ON x.version_id=v.id WHERE x.tenant_id=$1 AND x.review_state='NEEDS_REVIEW') AS pending"""),
                    self.repo.tenant, pointer["release_id"])
                equivalents, equivalent_pending = aliases["sources"], aliases["pending"]
                limits = await conn.fetchrow(member_reads("""WITH latest AS (
                    SELECT DISTINCT ON (source_id) source_id,category FROM knowledge_source_disposition
                    WHERE tenant_id=$1 ORDER BY source_id,created_at DESC,id DESC)
                    SELECT count(*) FILTER (WHERE category IN ('PARTIAL_SOURCE_TEXT','SOURCE_SCOPE_UNRESOLVED')) AS limited,
                    count(*) FILTER (WHERE category='SOURCE_SCOPE_UNRESOLVED') AS unresolved
                    FROM latest d JOIN knowledge_release_member m ON m.source_id=d.source_id AND m.release_id=$2"""),
                    self.repo.tenant, pointer["release_id"])
                limited_sources, scope_unresolved_sources = limits["limited"], limits["unresolved"]
            budget=getattr(self,"model_budget",None)
            budget=budget() if budget is not None else None
            remaining=budget["remaining_inferences"] if budget is not None else None
            answering_available=ready and (remaining is None or remaining>=4)
            return {"ready": ready, "serving_documents": counts["eligible"] if prepared else 0,
                "answering_available":answering_available,"model_budget":budget,
                "pending_versions": counts["pending"], "generation": pointer["generation"],
                "total_sources": counts["sources"],
                "unserved_sources": counts["sources"] - (counts["eligible"] if prepared else 0),
                "historical_pending_versions": counts["historical_pending"],
                "equivalent_sources": equivalents, "equivalent_pending_versions": equivalent_pending,
                "limited_sources": limited_sources, "scope_unresolved_sources": scope_unresolved_sources,
                "unresolved_sources": counts["sources"] - (counts["eligible"] if prepared else 0) - equivalents,
                "actionable_pending_versions": counts["pending"] - counts["historical_pending"] - equivalent_pending,
                "message": ("Nguồn HUCE đã lưu và release còn hiệu lực, nhưng dịch vụ trả lời tạm dừng vì ngân sách mô hình hiện tại không đủ."
                    if ready and not answering_available else f"Đang phục vụ {counts['eligible']} tài liệu HUCE; kho còn nguồn chờ xử lý và ngân sách mô hình còn rất ít. Chưa sẵn sàng vận hành liên tục."
                    if ready and remaining is not None and remaining<20 else "Nguồn HUCE đã phục vụ trong phạm vi ghi trên từng tài liệu; kho chưa bao phủ mọi câu hỏi."
                    if ready else "Kho HUCE chưa sẵn sàng: chưa có tài liệu HUCE đủ điều kiện đang phục vụ. Chatbot chưa thể trả lời từ nguồn HUCE."),
                "identity": "Tài khoản local do chủ hệ thống chỉ định; chưa kết nối SSO HUCE."}

    async def artifact(self, actor, version_id, kind):
        self.admin(actor)
        async with self.repo.transaction() as conn:
            version = await self.repo.version(conn, version_id)
            identifier = version["original_id"] if kind == "original" else version["rendition_id"]
            row = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", identifier, self.repo.tenant)
            if not row:
                raise PlatformError(404, "ARTIFACT_NOT_FOUND", "Chưa có artifact này.")
        return self.storage.read(row), row["media_type"], version["filename"]

    async def review(self, actor, version_id, body):
        self.admin(actor)
        async with self.repo.transaction() as conn:
            from campus247.application.knowledge.edition_release import lock_decisions
            await lock_decisions(self, conn)
            row = await self.repo.version(conn, version_id, lock=True)
            if str(row["created_by"]) == actor.subject_id:
                raise PlatformError(403, "SEPARATION_OF_DUTIES", "Tác giả không được tự duyệt.")
            if row["revision"] != body.expected_revision:
                raise PlatformError(409, "STALE_VERSION", "Phiên bản đã đổi; tải lại.")
            if (not row["index_version"] or row["revoked_at"] or row["publication_state"] != "DRAFT"
                or row["metadata_sha256"] != metadata_binding(row) or not body.note.strip()):
                raise PlatformError(409, "NOT_REVIEWABLE", "Cần build đầy đủ, metadata khớp và ghi chú đối chiếu nguồn.")
            # Verifies both immutable originals and the exact rendition before binding review.
            for identifier in (row["original_id"], row["rendition_id"]):
                artifact = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", identifier, self.repo.tenant)
                self.storage.read(artifact)
            await conn.execute("""INSERT INTO knowledge_review
                (id,version_id,reviewer_id,verdict,rendition_sha256,metadata_sha256,note)
                VALUES ($1,$2,$3,$4,$5,$6,$7)""", generate_uuid7(), version_id, actor.subject_id, body.verdict,
                row["rendition_sha256"], row["metadata_sha256"], body.note)
            await conn.execute("UPDATE knowledge_ingest_version SET review_state=$2,revision=revision+1 WHERE version_id=$1", version_id, body.verdict)
            await self.repo.audit(conn, actor.subject_id, "knowledge.review", version_id,
                                  {"verdict": body.verdict, "rendition_sha256": row["rendition_sha256"], "metadata_sha256": row["metadata_sha256"],
                                   "identity_issuer":actor.issuer,"is_synthetic_identity":actor.is_synthetic})
            return {"version_id": version_id, "review_state": body.verdict, "revision": row["revision"] + 1}

    async def _eligible(self, conn, version_id, *, publisher=None, allow_revoked=False):
        row = await self.repo.version(conn, version_id)
        from campus247.application.knowledge.source_snapshot import read_snapshot
        snapshot_scope = await read_snapshot(self, conn, row)
        if snapshot_scope is not None:
            hashes = await conn.fetch("SELECT DISTINCT content_checksum FROM knowledge_chunk WHERE document_version_id=$1", version_id)
            if not hashes or any(item["content_checksum"] not in snapshot_scope["_evidence_hashes"] for item in hashes):
                raise PlatformError(409, "SOURCE_SPAN_MISMATCH", "Chỉ mục không khớp các đoạn gốc đã đối chiếu.")
        if getattr(self,"operational",False) and not row["canonical_uri"].startswith("https://"):
            raise PlatformError(409,"NON_OPERATIONAL_SOURCE","Nguồn fixture/local verification không được xuất bản trong phiên vận hành.")
        if row["processor_profile"].startswith("verified-original-span-v1:"):
            raise PlatformError(409,"PROCESSOR_SUPERSEDED","Bản này chưa có mapping rerank đạt envelope; dùng bản trích nguyên bản v2 đã đối chiếu.")
        reviewed = await conn.fetchrow("""SELECT * FROM knowledge_review WHERE version_id=$1
            ORDER BY created_at DESC,id DESC LIMIT 1""", version_id)
        if (row["review_state"] != "APPROVED" or not row["index_version"] or not reviewed
            or reviewed["verdict"] != "APPROVED" or str(reviewed["reviewer_id"]) == str(row["created_by"])
            or reviewed["rendition_sha256"] != row["rendition_sha256"]
            or reviewed["metadata_sha256"] != row["metadata_sha256"] or metadata_binding(row) != row["metadata_sha256"]
            or not row["effective_from"] or row["revoked_at"] and not allow_revoked):
            raise PlatformError(409, "REVIEW_BINDING_REQUIRED", "Cần review hợp lệ và metadata hiệu lực/phạm vi đã xác minh.")
        if publisher and str(row["created_by"]) == publisher:
            raise PlatformError(403, "SEPARATION_OF_DUTIES", "Tác giả không được tự xuất bản/thu hồi.")
        manifest = await conn.fetchrow("SELECT * FROM embedding_index_manifest WHERE index_version=$1", row["index_version"])
        profile = load_retrieval_profile()
        if (not manifest or manifest["build_status"] != "READY" or not manifest["validated_at"]
            or manifest["embedding_model_id"] != profile.embedding_model_id
            or manifest["embedding_model_revision"] != profile.embedding_model_revision or manifest["dimension"] != 1024
            or manifest["normalization"] != profile.normalization or manifest["distance_metric"] != profile.distance_metric
            or manifest["artifact_sha256"] != EMBED_ARTIFACT or manifest["profile_version"] != profile.profile_version):
            raise PlatformError(409, "INDEX_NOT_READY", "Chỉ mục BGE chưa hợp lệ.")
        return row

    async def build_release(self, actor, version_id, key):
        self.admin(actor)
        async with self.repo.transaction() as conn:
            fingerprint = digest({"build_version": version_id})
            replay = await self.repo.replay(conn, actor.subject_id, "release:" + key, fingerprint)
            if replay:
                return replay
            from campus247.application.knowledge.edition_release import lock_decisions, prepared_members, release_profile
            await lock_decisions(self, conn)
            pointer = await self.repo.pointer(conn, lock=True)
            version = await self._eligible(conn, version_id)
            members = [dict(r) for r in await conn.fetch(member_reads("""SELECT m.source_id,m.version_id,m.index_version,
                m.rendition_sha256,m.metadata_sha256 FROM knowledge_release_member m
                JOIN knowledge_ingest_version x ON x.version_id=m.version_id
                WHERE m.release_id=$1 AND x.tenant_id=$2 AND x.revoked_at IS NULL"""),
                pointer["release_id"], self.repo.tenant)]
            members = await merge_members(self, conn, members, [version])
            members = await prepared_members(self, conn, members, [version_id])
            for member in members:
                await self._eligible(conn, member["version_id"])
            identifier = generate_uuid7()
            profile = await release_profile(self, conn, members, requested=[version_id])
            checksum = digest(members)
            await conn.execute("""INSERT INTO knowledge_release
                (id,tenant_id,campus_id,predecessor_id,profile,membership_sha256,created_by)
                VALUES ($1,$2,$3,$4,$5::jsonb,$6,$7)""", identifier, self.repo.tenant, self.repo.campus,
                pointer["release_id"], json.dumps(profile), checksum, actor.subject_id)
            anchors, _ = split_members(members, [version_id])
            for member in anchors:
                await conn.execute("""INSERT INTO knowledge_release_member
                    (release_id,source_id,version_id,index_version,rendition_sha256,metadata_sha256)
                    VALUES ($1,$2,$3,$4,$5,$6)""", identifier, *(member[k] for k in
                        ("source_id", "version_id", "index_version", "rendition_sha256", "metadata_sha256")))
            await conn.execute("INSERT INTO knowledge_release_seal(release_id) VALUES ($1)", identifier)
            result = {"release_id": identifier, "membership_sha256": checksum, "members": members, "expected_generation": pointer["generation"]}
            await self.repo.remember(conn, actor.subject_id, "release:" + key, fingerprint, result)
            await self.repo.audit(conn, actor.subject_id, "knowledge.release.ready", identifier, {"membership_sha256": checksum})
            return result

    async def build_batch_release(self, actor, version_ids, key):
        """One sealed candidate retaining current members; normal confirmation follows."""
        self.admin(actor)
        if (not isinstance(version_ids, list) or not 1 <= len(version_ids) <= 200
                or any(not isinstance(value, str) or len(value) != 36 for value in version_ids)
                or len(set(version_ids)) != len(version_ids)):
            raise PlatformError(422, "INVALID_RELEASE_MEMBERS", "Cần danh sách phiên bản rõ ràng, không trùng.")
        async with self.repo.transaction() as conn:
            fingerprint = digest({"build_versions": sorted(version_ids)})
            replay = await self.repo.replay(conn, actor.subject_id, "release-batch:" + key, fingerprint)
            if replay:
                return replay
            from campus247.application.knowledge.edition_release import lock_decisions, prepared_members, release_profile
            await lock_decisions(self, conn)
            pointer = await self.repo.pointer(conn, lock=True)
            versions = [await self._eligible(conn, identifier) for identifier in sorted(version_ids)]
            previous = await conn.fetch(member_reads("""SELECT m.source_id,m.version_id,m.index_version,m.rendition_sha256,m.metadata_sha256
                FROM knowledge_release_member m JOIN knowledge_ingest_version x ON x.version_id=m.version_id
                WHERE m.release_id=$1 AND x.tenant_id=$2 AND x.revoked_at IS NULL"""), pointer["release_id"], self.repo.tenant)
            keys = ("source_id", "version_id", "index_version", "rendition_sha256", "metadata_sha256")
            members = await merge_members(self, conn, previous, versions)
            members = await prepared_members(self, conn, members, version_ids)
            for member in members:
                await self._eligible(conn, member["version_id"])
            identifier = generate_uuid7()
            checksum = digest(members)
            await conn.execute("""INSERT INTO knowledge_release(id,tenant_id,campus_id,predecessor_id,profile,membership_sha256,created_by)
                VALUES($1,$2,$3,$4,$5::jsonb,$6,$7)""", identifier, self.repo.tenant, self.repo.campus,
                pointer["release_id"], json.dumps(await release_profile(self, conn, members, requested=version_ids)), checksum, actor.subject_id)
            anchors, _ = split_members(members, version_ids)
            for member in anchors:
                await conn.execute("""INSERT INTO knowledge_release_member(release_id,source_id,version_id,index_version,rendition_sha256,metadata_sha256)
                    VALUES($1,$2,$3,$4,$5,$6)""", identifier, *(member[name] for name in keys))
            await conn.execute("INSERT INTO knowledge_release_seal(release_id) VALUES($1)", identifier)
            result = {"release_id": identifier, "membership_sha256": checksum, "members": members,
                "expected_generation": pointer["generation"]}
            await self.repo.remember(conn, actor.subject_id, "release-batch:" + key, fingerprint, result)
            await self.repo.audit(conn, actor.subject_id, "knowledge.release.ready", identifier,
                {"membership_sha256": checksum, "batch_versions": len(version_ids)})
            return result

    async def _release(self, conn, identifier):
        row = await conn.fetchrow("""SELECT r.* FROM knowledge_release r JOIN knowledge_release_seal s ON s.release_id=r.id
            WHERE r.id=$1 AND r.tenant_id=$2 AND r.campus_id=$3""", identifier, self.repo.tenant, self.repo.campus)
        if not row:
            raise PlatformError(404, "RELEASE_NOT_FOUND", "Không tìm thấy release hoàn chỉnh.")
        members = canonical_members(await conn.fetch(member_reads("""SELECT source_id,version_id,index_version,rendition_sha256,
            metadata_sha256 FROM knowledge_release_member member WHERE release_id=$1 ORDER BY source_id,version_id"""), identifier))
        if len({member["version_id"] for member in members}) != len(members):
            raise PlatformError(409, "RELEASE_INTEGRITY", "Release chứa rendition trùng lặp.")
        if digest(members) != row["membership_sha256"]:
            raise PlatformError(409, "RELEASE_INTEGRITY", "Release không khớp membership/profile.")
        from campus247.application.knowledge.edition_release import check_profile
        state = await check_profile(self, conn, row["profile"], members)
        return dict(row) | {"_edition_state": state}, members

    @staticmethod
    def activation_time(versions, *, at_time=None):
        at_time = at_time or datetime.now(UTC)
        future = [row for row in versions if row["effective_from"] and row["effective_from"] > at_time and not row["revoked_at"]]
        if future:
            raise PlatformError(409, "RELEASE_NOT_YET_EFFECTIVE", "Release có bản chưa tới ngày áp dụng; giữ bản đang dùng và xem trước lại khi đủ điều kiện hiệu lực.")

    async def preview(self, actor, body):
        self.admin(actor)
        async with self.repo.transaction() as conn:
            from campus247.application.knowledge.edition_release import activation_resolution, lock_decisions
            await lock_decisions(self, conn)
            pointer = await self.repo.pointer(conn)
            if pointer["generation"] != body.expected_generation:
                raise PlatformError(409, "STALE_GENERATION", "Release đã đổi; tải lại.")
            if body.operation == "revoke":
                version = await self._eligible(conn, body.target_id, publisher=actor.subject_id)
                target_hash = digest({"rendition": version["rendition_sha256"], "metadata": version["metadata_sha256"]})
                members = [{"version_id": body.target_id, "title": version["title"]}]
            else:
                release, members = await self._release(conn, body.target_id)
                target_hash = release["membership_sha256"]
                versions = []
                for member in members:
                    versions.append(await self._eligible(conn, member["version_id"], publisher=actor.subject_id, allow_revoked=body.operation == "rollback"))
                self.activation_time(versions)
                activation_resolution(*release["_edition_state"])
                if body.operation == "activate" and str(release["predecessor_id"] or "") != str(pointer["release_id"] or ""):
                    raise PlatformError(409, "STALE_RELEASE_BASE", "Release cần dựng lại trên membership hiện tại.")
            payload = {"operation": body.operation, "target_id": body.target_id,
                "target_sha256": target_hash, "generation": pointer["generation"],
                "policy_generation": pointer["policy_generation"], "previous_release_id": pointer["release_id"],
                "members": members}
            value = create_action_preview(actor.subject_id, "KNOWLEDGE_" + body.operation.upper(), payload, session_id=actor.session_id)
            await conn.execute("""INSERT INTO knowledge_release_preview(id,tenant_id,actor_id,session_id,preview)
                VALUES ($1,$2,$3,$4,$5::jsonb)""", value.id, self.repo.tenant, actor.subject_id, actor.session_id,
                json.dumps(serial(asdict(value))))
            return {"preview_id": value.id, "confirmation_token": self.tokens.mint_token(value),
                    "expires_at": value.expires_at.isoformat(), "payload": payload}

    async def confirm(self, actor, body, key):
        self.admin(actor)
        async with self.repo.transaction() as conn:
            from campus247.application.knowledge.edition_release import activation_resolution, lock_decisions
            await lock_decisions(self, conn)
            raw = await conn.fetchrow("""SELECT * FROM knowledge_release_preview WHERE id=$1 AND tenant_id=$2
                AND actor_id=$3 AND session_id=$4 FOR UPDATE""", body.preview_id, self.repo.tenant, actor.subject_id, actor.session_id)
            if not raw:
                raise PlatformError(404, "PREVIEW_NOT_FOUND", "Không có preview trong phiên này.")
            preview = preview_entity(json_value(raw["preview"]))
            payload = json.loads(preview.normalized_payload)
            fingerprint = digest({"preview": body.preview_id, "payload_hash": preview.payload_hash})
            replay = await self.repo.replay(conn, actor.subject_id, "confirm:" + key, fingerprint)
            valid = self.tokens.validate_token(body.confirmation_token, preview.id, actor.subject_id, actor.session_id,
                "none", preview.action_type, "1.0", "1.0", preview.payload_hash,
                at_time=preview.created_at if replay else None)
            if not valid.is_valid:
                raise PlatformError(422, "INVALID_CONFIRMATION", "Xác nhận không hợp lệ hoặc đã hết hạn.")
            if replay:
                return {**replay, "is_replay": True}
            if raw["consumed_at"] or not preview.is_active(datetime.now(UTC)):
                raise PlatformError(409, "PREVIEW_CONSUMED", "Preview không còn hoạt động.")
            pointer = await self.repo.pointer(conn, lock=True)
            if (pointer["generation"], pointer["policy_generation"], pointer["release_id"]) != (
                payload["generation"], payload["policy_generation"], payload["previous_release_id"]):
                raise PlatformError(409, "STALE_GENERATION", "Trạng thái đã thay đổi; xem trước lại.")
            target, operation = payload["target_id"], payload["operation"]
            if operation == "revoke":
                row = await self._eligible(conn, target, publisher=actor.subject_id)
                if digest({"rendition": row["rendition_sha256"], "metadata": row["metadata_sha256"]}) != payload["target_sha256"]:
                    raise PlatformError(409, "REVIEW_CHANGED", "Nội dung đã thay đổi.")
                await conn.execute("UPDATE knowledge_ingest_version SET revoked_at=clock_timestamp(),revision=revision+1 WHERE version_id=$1", target)
                await conn.execute("UPDATE document_version SET status='ARCHIVED' WHERE id=$1", target)
                pointer["policy_generation"] += 1
            else:
                release, members = await self._release(conn, target)
                if release["membership_sha256"] != payload["target_sha256"]:
                    raise PlatformError(409, "RELEASE_CHANGED", "Release đã thay đổi.")
                versions = []
                for member in members:
                    versions.append(await self._eligible(conn, member["version_id"], publisher=actor.subject_id, allow_revoked=operation == "rollback"))
                self.activation_time(versions)  # Revalidate after preview and before any publication write.
                activation_resolution(*release["_edition_state"])
                for member, version in zip(members, versions, strict=True):
                    # Revocation is independent; rollback never changes it or archived status.
                    if not version["revoked_at"]:
                        await conn.execute("UPDATE document_version SET status='PUBLISHED',published_at=clock_timestamp(),applicability_reviewed_at=clock_timestamp() WHERE id=$1", member["version_id"])
                        await conn.execute("UPDATE knowledge_source SET approval_status='APPROVED' WHERE id=$1", member["source_id"])
                pointer["release_id"] = target
            pointer["generation"] += 1
            await conn.execute("""UPDATE knowledge_release_pointer SET release_id=$3,generation=$4,
                policy_generation=$5,updated_at=clock_timestamp() WHERE tenant_id=$1 AND campus_id=$2""",
                self.repo.tenant, self.repo.campus, pointer["release_id"], pointer["generation"], pointer["policy_generation"])
            await conn.execute("UPDATE knowledge_release_preview SET consumed_at=clock_timestamp() WHERE id=$1", body.preview_id)
            result = {"desired": pointer, "is_replay": False, "serving_confirmed": False}
            await self.repo.audit(conn, actor.subject_id, "knowledge." + operation, target, pointer)
            await self.repo.outbox(conn, "knowledge.release.changed", target, pointer)
            await self.repo.remember(conn, actor.subject_id, "confirm:" + key, fingerprint, result)
            return result

    async def job_action(self, actor, job_id, action):
        self.admin(actor)
        async with self.repo.transaction() as conn:
            job = await conn.fetchrow("SELECT * FROM knowledge_ingestion_job WHERE id=$1 AND tenant_id=$2 FOR UPDATE", job_id, self.repo.tenant)
            if not job:
                raise PlatformError(404, "JOB_NOT_FOUND", "Không có job này.")
            if action == "cancel" and job["state"] in {"QUEUED", "RETRY_WAIT", "RUNNING"}:
                await conn.execute("""UPDATE knowledge_ingestion_job SET cancel_requested=true,
                    state=CASE WHEN state='RUNNING' THEN state ELSE 'CANCELLED' END WHERE id=$1""", job_id)
            elif action == "retry" and job["state"] in {"FAILED", "CANCELLED"}:
                if job["attempts"] >= 3:
                    raise PlatformError(409, "ATTEMPTS_EXHAUSTED", "Job đã dùng hết ba lần xử lý; giữ checkpoint và đối chiếu nguyên nhân trước khi tạo rendition/run mới phù hợp.")
                if job["version_id"]:
                    version = await self.repo.version(conn, job["version_id"])
                    if version["revoked_at"] or version["publication_state"] != "DRAFT" or version["review_state"] == "APPROVED":
                        raise PlatformError(409, "IMMUTABLE_VERSION", "Không xử lý lại phiên bản đã duyệt/xuất bản.")
                elif await conn.fetchval("SELECT EXISTS(SELECT 1 FROM knowledge_intake_resolution WHERE intake_id=$1 AND tenant_id=$2)", job["intake_id"], self.repo.tenant):
                    raise PlatformError(409, "INTAKE_REVISION_CHANGED", "Hồ sơ đã chuyển sang phiên bản để duyệt.")
                await conn.execute("""UPDATE knowledge_ingestion_job SET state='QUEUED',cancel_requested=false,
                    error_code=NULL,next_attempt_at=clock_timestamp(),fencing_token=fencing_token+1 WHERE id=$1""", job_id)
            else:
                raise PlatformError(409, "INVALID_JOB_STATE", "Job không thể thực hiện thao tác này.")
            await self.repo.audit(conn, actor.subject_id, "knowledge.job." + action, job_id, {})
            return {"job_id": job_id, "action": action}
