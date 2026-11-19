"""Automatic pipeline from "document added" to "chatbot can use it".

Human gates are kept where the product requires them (a contributor's document needs a second person's approval; a
direct publisher attests the document); everything else is done by this module in the ingestion worker:

    upload -> processing -> automatic checks -> [approval | attestation] -> batched release -> index build -> usable

The release itself is built and confirmed through the existing KnowledgePlatform commands (separation of duties,
signed preview, idempotency, audit and the SQL serving gate are unchanged), by a service identity that is never the author.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from campus247.application.knowledge.platform_models import (
    ConfirmInput, IntakeMetadata, PlatformError, PreviewInput, ReviewInput, digest,
)
from campus247.domain.shared.values import generate_uuid7
from campus247.ports.identity import IdentityContext, IdentityRole

LOGGER = logging.getLogger("campus247.auto_publication")

ATTEST_TEXT = "Tôi xác nhận đây là văn bản chính thức, đúng nguồn và đúng phạm vi áp dụng."
TRANSIENT = {"STALE_GENERATION", "STALE_RELEASE_BASE", "PREVIEW_CONSUMED", "MODEL_BUDGET_UNAVAILABLE"}
STATE_LABELS = {
    "PROCESSING": "Đang xử lý tài liệu", "AWAITING_REVIEW": "Chờ người duyệt", "READY_TO_PUBLISH": "Đang phát hành",
    "WAITING_EFFECTIVE": "Chờ ngày hiệu lực", "INDEXING": "Đang cập nhật chỉ mục chatbot",
    "ACTIVE": "Chatbot đã dùng được", "NEEDS_ATTENTION": "Cần xử lý", "REJECTED": "Đã từ chối", "REVOKED": "Đã thu hồi",
}
CHECK_LABELS = {
    "processed": "Xử lý và nhúng thành công", "chunks": "Đủ đoạn trích đã nhúng", "text": "Có nội dung chữ",
    "metadata": "Thông tin nguồn đầy đủ", "duplicate": "Không trùng văn bản đang phát hành",
    "injection": "Không có chỉ thị lạ trong nội dung", "personal_data": "Không chứa dữ liệu cá nhân",
}


class AutoPublicationService:
    def __init__(self, platform, store, *, scan_text=None, index_builder=None, baseline_index=None,
                 quiet_seconds=30, max_wait_seconds=300, index_retry_seconds=120):
        self.platform, self.store, self.repo = platform, store, platform.repo
        self.scan_text, self.index_builder, self.baseline_index = scan_text, index_builder, baseline_index
        self.quiet_seconds, self.max_wait_seconds, self.index_retry_seconds = quiet_seconds, max_wait_seconds, index_retry_seconds
        self._build_task = None

    # ------------------------------------------------------------------ identities
    async def system_actor(self, name="auto-publisher") -> IdentityContext:
        async with self.repo.pool.acquire() as conn:
            subject = await self.store.service_identity(conn, name)
        now = datetime.now(UTC)
        return IdentityContext(subject, "system:" + name, "internal:" + name, (IdentityRole.KNOWLEDGE_ADMIN,), name,
                               now, now + timedelta(minutes=10), tenant_id=self.repo.tenant, session_id=generate_uuid7(),
                               is_synthetic=False)

    # ------------------------------------------------------------------ entry points
    async def submit(self, actor, file, metadata: IntakeMetadata, key, *, publish_directly=False, attested=False, artifact=None):
        """One call for every role: contributors always go through approval, administrators may publish directly."""
        self.platform.contributor(actor)
        await self.store.ensure()
        admin = self.platform.is_admin(actor)
        if publish_directly and not admin:
            raise PlatformError(403, "DIRECT_PUBLISH_FORBIDDEN", "Vai trò của bạn chỉ được gửi duyệt, không đăng trực tiếp.")
        if publish_directly and not attested:
            raise PlatformError(422, "ATTESTATION_REQUIRED", "Cần tick xác nhận văn bản chính thức trước khi đăng trực tiếp.")
        flags = []
        if metadata.effective_from is None:
            metadata = metadata.model_copy(update={"effective_from": datetime.now(UTC) - timedelta(minutes=1)})
            flags.append("EFFECTIVE_FROM_ASSUMED")
        result = await self.platform.upload(actor, metadata, file, key, artifact=artifact)
        mode = "DIRECT" if publish_directly else "REVIEW"
        attestation = None
        if publish_directly:
            attestation = {"text": ATTEST_TEXT, "by": actor.subject_id, "role": [r.value for r in actor.roles],
                           "at": datetime.now(UTC).isoformat(), "original_sha256": result["original_sha256"],
                           "metadata_sha256": digest(metadata.model_dump(mode="json", exclude={"source_id"}))}
        async with self.repo.transaction() as conn:
            await self.store.create(conn, version_id=result["version_id"], source_id=result["source_id"], mode=mode,
                state="PROCESSING", author_id=actor.subject_id, author_role=",".join(r.value for r in actor.roles),
                attestation=attestation, flags=flags)
        return {**result, "mode": mode, "pipeline_state": "PROCESSING", "pipeline_label": STATE_LABELS["PROCESSING"]}

    async def register(self, conn, *, version_id, source_id, author_id, author_role, mode="REVIEW", origin="UPLOAD", flags=(), attestation=None):
        """Attach an already created version (for example from the crawler) to the pipeline."""
        await self.store.ensure()
        return await self.store.create(conn, version_id=version_id, source_id=source_id, mode=mode, state="PROCESSING",
            author_id=author_id, author_role=author_role, origin=origin, flags=flags, attestation=attestation)

    async def approve(self, actor, version_id, note=None):
        self.platform.admin(actor)
        await self.store.ensure()
        async with self.repo.pool.acquire() as conn:
            row = await self.store.get(conn, version_id)
            if not row or row["state"] != "AWAITING_REVIEW":
                raise PlatformError(409, "NOT_AWAITING_REVIEW", "Tài liệu không ở trạng thái chờ duyệt.")
            if str(row["author_id"]) == actor.subject_id:
                raise PlatformError(403, "SEPARATION_OF_DUTIES", "Tác giả không được tự duyệt.")
            version = await self.repo.version(conn, version_id)
        note = (note or "").strip() or "Đã đối chiếu bản trích với văn bản nguồn."
        await self.platform.review(actor, version_id, ReviewInput(expected_revision=version["revision"], verdict="APPROVED", note=note))
        async with self.repo.transaction() as conn:
            await self._after_acceptance(conn, row, actor_id=actor.subject_id, reviewer_id=actor.subject_id, review_note=note)
        return {"version_id": version_id, "pipeline_state": "READY_TO_PUBLISH"}

    async def reject(self, actor, version_id, note):
        self.platform.admin(actor)
        await self.store.ensure()
        async with self.repo.pool.acquire() as conn:
            row = await self.store.get(conn, version_id)
            if not row or row["state"] not in {"AWAITING_REVIEW", "NEEDS_ATTENTION"}:
                raise PlatformError(409, "NOT_REJECTABLE", "Tài liệu không ở trạng thái có thể từ chối.")
            if str(row["author_id"]) == actor.subject_id and row["state"] == "AWAITING_REVIEW":
                raise PlatformError(403, "SEPARATION_OF_DUTIES", "Tác giả không tự xử lý bản của mình ở bước duyệt.")
            version = await self.repo.version(conn, version_id)
        if version["review_state"] != "REJECTED" and version.get("index_version"):
            await self.platform.review(actor, version_id, ReviewInput(expected_revision=version["revision"], verdict="REJECTED", note=note))
        async with self.repo.transaction() as conn:
            await self.store.transition(conn, version_id, "REJECTED", actor_id=actor.subject_id,
                detail={"note": note}, reviewer_id=actor.subject_id, review_note=note)
        return {"version_id": version_id, "pipeline_state": "REJECTED"}

    async def revoke(self, actor, version_id, note):
        """Immediate withdrawal of a published document. Serving stops at once (the SQL gate runs on every question);
        the index is rebuilt in the background. Carried out by the service identity, the requesting administrator is recorded."""
        self.platform.admin(actor)
        await self.store.ensure()
        note = (note or "").strip()
        if len(note) < 5:
            raise PlatformError(422, "REVOCATION_NOTE_REQUIRED", "Cần ghi lý do thu hồi (ít nhất 5 ký tự).")
        async with self.repo.pool.acquire() as conn:
            row = await self.store.get(conn, version_id)
            pointer = await self.repo.pointer(conn)
        if not row or row["state"] not in {"INDEXING", "ACTIVE"}:
            raise PlatformError(409, "NOT_REVOCABLE", "Chỉ thu hồi được tài liệu đã phát hành.")
        system = await self.system_actor("auto-publisher")
        preview = await self.platform.preview(system, PreviewInput(operation="revoke", target_id=version_id, expected_generation=pointer["generation"]))
        await self.platform.confirm(system, ConfirmInput(preview_id=preview["preview_id"], confirmation_token=preview["confirmation_token"], confirmed=True),
                                    "revoke-" + digest({"v": version_id, "g": pointer["generation"]})[:40])
        async with self.repo.transaction() as conn:
            await self.store.transition(conn, version_id, "REVOKED", actor_id=actor.subject_id, detail={"requested_by": actor.subject_id, "note": note},
                                        review_note=note)
            await self.repo.audit(conn, actor.subject_id, "knowledge.auto_publication.revoke", version_id, {"note": note})
        return {"version_id": version_id, "pipeline_state": "REVOKED"}

    async def retry(self, actor, version_id):
        self.platform.admin(actor)
        await self.store.ensure()
        async with self.repo.pool.acquire() as conn:
            row = await self.store.get(conn, version_id)
            if not row or row["state"] != "NEEDS_ATTENTION":
                raise PlatformError(409, "NOT_RETRYABLE", "Tài liệu không ở trạng thái cần xử lý.")
            job = await conn.fetchrow("SELECT id,state FROM knowledge_ingestion_job WHERE tenant_id=$1 AND version_id=$2 ORDER BY created_at DESC LIMIT 1",
                                      self.repo.tenant, version_id)
        if (row["error_code"] or "").startswith("JOB_") and job and job["state"] in {"FAILED", "CANCELLED"}:
            await self.platform.job_action(actor, str(job["id"]), "retry")
        async with self.repo.transaction() as conn:
            await self.store.transition(conn, version_id, row["resume_state"] or "PROCESSING", from_states={"NEEDS_ATTENTION"},
                actor_id=actor.subject_id, detail={"retry": True}, error_code=None, error_detail=None, attempts=0)
        return {"version_id": version_id, "pipeline_state": row["resume_state"] or "PROCESSING"}

    async def listing(self, actor):
        self.platform.contributor(actor)
        await self.store.ensure()
        admin = self.platform.is_admin(actor)
        async with self.repo.pool.acquire() as conn:
            rows = await self.store.listing(conn, author_id=None if admin else actor.subject_id)
            pointer = await self.repo.pointer(conn)
        items = []
        for row in rows:
            items.append({
                "version_id": str(row["version_id"]), "source_id": str(row["source_id"]), "title": row["title"], "filename": row["filename"],
                "canonical_uri": row["canonical_uri"], "mode": row["mode"], "origin": row["origin"], "state": row["state"],
                "label": STATE_LABELS.get(row["state"], row["state"]), "flags": row["flags"] if isinstance(row["flags"], list) else [],
                "checks": _checks_view(row["checks"]), "error_code": row["error_code"], "error_detail": row["error_detail"],
                "created_at": row["created_at"].isoformat(), "state_changed_at": row["state_changed_at"].isoformat(),
                "published_at": row["published_at"].isoformat() if row["published_at"] else None,
                "usable_at": row["usable_at"].isoformat() if row["usable_at"] else None,
                "effective_from": row["effective_from"].isoformat() if row["effective_from"] else None,
                "author_id": str(row["author_id"]), "review_note": row["review_note"],
                "can_approve": admin and row["state"] == "AWAITING_REVIEW" and str(row["author_id"]) != actor.subject_id,
                "can_retry": admin and row["state"] == "NEEDS_ATTENTION",
                "can_revoke": admin and row["state"] in {"INDEXING", "ACTIVE"},
                "can_reject": admin and row["state"] in {"AWAITING_REVIEW", "NEEDS_ATTENTION"} and not (
                    row["state"] == "AWAITING_REVIEW" and str(row["author_id"]) == actor.subject_id)})
        return {"items": items, "generation": pointer["generation"], "can_publish_directly": admin}

    # ------------------------------------------------------------------ the worker loop
    async def tick(self):
        await self.store.ensure()
        key = self.repo.tenant + ":auto-publication-leader"
        async with self.repo.pool.acquire() as lock:
            if not await lock.fetchval("SELECT pg_try_advisory_lock(hashtextextended($1,0))", key):
                return {"leader": False}
            try:
                report = {"leader": True}
                for name, step in (("processed", self._advance_processing), ("released", self._release_waiting),
                                   ("published", self._publish_ready), ("indexing", self._advance_indexing)):
                    try:
                        report[name] = await step()
                    except PlatformError as error:
                        report[name] = "error:" + error.code
                    except Exception as error:  # noqa: BLE001 -- one failing step must not stop the others
                        LOGGER.warning("auto_publication_step_failed step=%s kind=%s", name, type(error).__name__)
                        report[name] = "error:" + type(error).__name__
                return report
            finally:
                await lock.execute("SELECT pg_advisory_unlock(hashtextextended($1,0))", key)

    async def _attention(self, conn, row, code, detail, *, resume, checks=None):
        extra = {"checks": checks} if checks is not None else {}
        await self.store.transition(conn, row["version_id"], "NEEDS_ATTENTION", actor_id="system:auto-publisher",
            detail={"code": code}, error_code=code, error_detail=str(detail)[:500], resume_state=resume, **extra)

    async def _after_acceptance(self, conn, row, *, actor_id, **fields):
        version = await self.repo.version(conn, str(row["version_id"]))
        future = version["effective_from"] and version["effective_from"] > datetime.now(UTC)
        await self.store.transition(conn, row["version_id"], "WAITING_EFFECTIVE" if future else "READY_TO_PUBLISH",
            actor_id=actor_id, error_code=None, error_detail=None,
            not_before=version["effective_from"] if future else None, **fields)

    async def _advance_processing(self):
        async with self.repo.pool.acquire() as conn:
            rows = await self.store.in_states(conn, ["PROCESSING"])
        moved = 0
        for row in rows:
            async with self.repo.transaction() as conn:
                job = await conn.fetchrow("""SELECT state,error_code FROM knowledge_ingestion_job
                    WHERE tenant_id=$1 AND version_id=$2 ORDER BY created_at DESC LIMIT 1""", self.repo.tenant, row["version_id"])
                if not job or job["state"] in {"QUEUED", "RUNNING", "RETRY_WAIT"}:
                    continue
                if job["state"] != "SUCCEEDED":
                    await self._attention(conn, row, "JOB_" + job["state"], job["error_code"] or "Xử lý tài liệu không hoàn tất.", resume="PROCESSING")
                    moved += 1
                    continue
                checks = await self._auto_checks(conn, row)
                failed = [name for name, check in checks.items() if not check["ok"]]
                if failed:
                    await self._attention(conn, row, "CHECK_FAILED", "; ".join(CHECK_LABELS[n] + ": " + str(checks[n]["detail"]) for n in failed),
                                          resume="PROCESSING", checks=checks)
                elif row["mode"] == "REVIEW":
                    await self.store.transition(conn, row["version_id"], "AWAITING_REVIEW", actor_id="system:auto-publisher", checks=checks)
                else:
                    await self._after_acceptance(conn, row, actor_id="system:auto-publisher", checks=checks)
                moved += 1
        return moved

    async def _auto_checks(self, conn, row):
        version = await self.repo.version(conn, str(row["version_id"]))
        chunks = await conn.fetch("""SELECT content_text, embedding_rag_v1 IS NOT NULL AS embedded FROM knowledge_chunk
            WHERE document_version_id=$1""", row["version_id"])
        expected = await conn.fetchval("SELECT chunk_count FROM embedding_index_manifest WHERE index_version=$1", version.get("index_version")) \
            if version.get("index_version") else None
        embedded = [c for c in chunks if c["embedded"]]
        text = sum(len((c["content_text"] or "").strip()) for c in chunks)
        operational = getattr(self.platform, "operational", False)
        uri = version["canonical_uri"] or ""
        duplicate = await conn.fetchrow("""SELECT s.title FROM knowledge_ingest_version x
            JOIN knowledge_artifact a ON a.id=x.original_id AND a.tenant_id=x.tenant_id
            JOIN document_version v ON v.id=x.version_id JOIN knowledge_source s ON s.id=v.knowledge_source_id
            WHERE x.tenant_id=$1 AND a.sha256=$2 AND x.version_id<>$3 AND s.id<>$4 AND x.revoked_at IS NULL AND v.status='PUBLISHED' LIMIT 1""",
            self.repo.tenant, version["original_sha256"], row["version_id"], row["source_id"])
        flagged = 0
        if self.scan_text is not None:
            for chunk in chunks[:500]:
                if self.scan_text(chunk["content_text"] or ""):
                    flagged += 1
        from campus247.application.knowledge.crawl.pii import scan_personal_data
        personal = scan_personal_data("\n".join((c["content_text"] or "") for c in chunks[:500]))
        # An administrator's reviewer decides for an ordinary upload; crawled and directly published documents have no second look.
        personal_blocks = bool(personal) and not (row["mode"] == "REVIEW" and row["origin"] == "UPLOAD")
        return {
            "processed": {"ok": bool(version.get("index_version")), "detail": "chưa có chỉ mục nhúng" if not version.get("index_version") else ""},
            "chunks": {"ok": bool(chunks) and len(embedded) == len(chunks) and (expected is None or expected == len(embedded)),
                       "detail": f"{len(embedded)}/{len(chunks)} đoạn đã nhúng" + (f", cần {expected}" if expected is not None else "")},
            "text": {"ok": text >= 20, "detail": f"{text} ký tự"},
            "metadata": {"ok": len((version["title"] or "").strip()) >= 3 and bool((version["owner_unit"] or "").strip())
                         and (uri.startswith("https://") or (not operational and uri.startswith("urn:"))),
                         "detail": "thiếu tiêu đề/đơn vị ban hành hoặc URI nguồn không hợp lệ" if not uri.startswith(("https://", "urn:")) else ""},
            "duplicate": {"ok": duplicate is None, "detail": f"trùng nội dung với «{duplicate['title']}»" if duplicate else ""},
            "injection": {"ok": flagged == 0, "detail": f"{flagged} đoạn có dấu hiệu chỉ thị lạ" if flagged else ""},
            "personal_data": {"ok": not personal_blocks, "detail": ("; ".join(f"{f.note} ({f.count})" for f in personal)
                              + (" — cảnh báo cho người duyệt" if personal and not personal_blocks else "")) if personal else ""},
        }

    async def _release_waiting(self):
        async with self.repo.pool.acquire() as conn:
            rows = await self.store.in_states(conn, ["WAITING_EFFECTIVE"])
        moved = 0
        for row in rows:
            if row["not_before"] and row["not_before"] <= datetime.now(UTC):
                async with self.repo.transaction() as conn:
                    moved += bool(await self.store.transition(conn, row["version_id"], "READY_TO_PUBLISH", from_states={"WAITING_EFFECTIVE"},
                                                              actor_id="system:auto-publisher", detail={"effective": True}))
        return moved

    async def _publish_ready(self):
        async with self.repo.pool.acquire() as conn:
            rows = await self.store.in_states(conn, ["READY_TO_PUBLISH"])
        if not rows:
            return 0
        now = datetime.now(UTC)
        if (now - max(r["state_changed_at"] for r in rows)).total_seconds() < self.quiet_seconds \
                and (now - min(r["state_changed_at"] for r in rows)).total_seconds() < self.max_wait_seconds:
            return 0  # still gathering a batch
        system = await self.system_actor("auto-publisher")
        batch = []
        for row in rows:
            try:
                if row["mode"] == "DIRECT":
                    await self._direct_review(system, row)
                batch.append(row)
            except PlatformError as error:
                async with self.repo.transaction() as conn:
                    await self._attention(conn, row, error.code, error.detail, resume="READY_TO_PUBLISH")
        return await self._publish(system, batch) if batch else 0

    async def _direct_review(self, system, row):
        async with self.repo.pool.acquire() as conn:
            version = await self.repo.version(conn, str(row["version_id"]))
        if version["review_state"] == "APPROVED":
            return
        attestation = row["attestation"] if isinstance(row["attestation"], dict) else {}
        note = ("Đăng trực tiếp: người đăng (quản trị tri thức) đã xác nhận «" + ATTEST_TEXT + "» lúc " + str(attestation.get("at", "?"))
                + "; kiểm tra tự động đạt. Bản duyệt do dịch vụ tự động ghi nhận.")[:1990]
        await self.platform.review(system, str(row["version_id"]), ReviewInput(expected_revision=version["revision"], verdict="APPROVED", note=note))

    async def _publish(self, system, rows):
        ids = sorted(str(r["version_id"]) for r in rows)
        async with self.repo.pool.acquire() as conn:
            pointer = await self.repo.pointer(conn)
        key = "auto-" + digest({"ids": ids, "generation": pointer["generation"], "policy": pointer["policy_generation"]})[:40]
        try:
            release = await self.platform.build_batch_release(system, ids, key)
            preview = await self.platform.preview(system, PreviewInput(operation="activate", target_id=release["release_id"],
                                                                       expected_generation=release["expected_generation"]))
            await self.platform.confirm(system, ConfirmInput(preview_id=preview["preview_id"],
                confirmation_token=preview["confirmation_token"], confirmed=True), key + ":confirm")
        except PlatformError as error:
            if error.code in TRANSIENT:
                return 0
            if len(rows) > 1:  # one bad document must not block the others
                return sum([await self._publish(system, [row]) for row in rows])
            async with self.repo.transaction() as conn:
                await self._attention(conn, rows[0], error.code, error.detail, resume="READY_TO_PUBLISH")
            return 0
        async with self.repo.transaction() as conn:
            for row in rows:
                await self.store.transition(conn, row["version_id"], "INDEXING", from_states={"READY_TO_PUBLISH"},
                    actor_id=system.subject_id, detail={"release_id": release["release_id"]},
                    release_id=release["release_id"], published_at=datetime.now(UTC))
        return len(rows)

    # ------------------------------------------------------------------ index: build, then wait for every API process
    async def _advance_indexing(self):
        async with self.repo.pool.acquire() as conn:
            rows = await self.store.in_states(conn, ["INDEXING"])
            pointer = await self.repo.pointer(conn)
            if not pointer["release_id"]:
                return 0
            if self.baseline_index is not None and self._baseline_matches(pointer):
                await self.store.registry_adopt_baseline(conn, release_id=pointer["release_id"], generation=pointer["generation"],
                    policy_generation=pointer["policy_generation"], path=str(self.baseline_index))
            ready = await self.store.registry_for(conn, pointer["release_id"], pointer["generation"], pointer["policy_generation"])
            building = await self.store.registry_building(conn)
            known = await self.store.registry_latest_ready(conn)
        if self._build_task is not None and self._build_task.done():
            self._build_task.exception()  # logged by the task itself; never raised here
            self._build_task = None
        if not rows:
            # A release change nobody queued here (a revocation, a manual publication) also leaves the index stale:
            # once the runtime has a known-good index, keep it current.
            if ready is None and known is not None:
                await self._maybe_build(pointer, building)
            return 0
        if ready is None:
            await self._maybe_build(pointer, building)
            return 0
        async with self.repo.pool.acquire() as conn:
            acks = await self.store.acks(conn)
        live = [a for a in acks if a["live"]]
        if acks and (not live or any(str(a["registry_id"]) != str(ready["id"]) for a in live)):
            return 0  # an API process has not loaded the new index yet
        moved = 0
        async with self.repo.transaction() as conn:
            for row in rows:
                moved += bool(await self.store.transition(conn, row["version_id"], "ACTIVE", from_states={"INDEXING"},
                    actor_id="system:auto-publisher", detail={"registry_id": str(ready["id"])}, usable_at=datetime.now(UTC)))
        return moved

    def _baseline_matches(self, pointer):
        """The index the runtime started with counts as a baseline only if its manifest names the serving release."""
        import json
        from pathlib import Path
        try:
            manifest = json.loads((Path(self.baseline_index) / "manifest.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        return (str(manifest.get("release_id")) == str(pointer["release_id"]) and manifest.get("generation") == pointer["generation"]
                and manifest.get("policy_generation") == pointer["policy_generation"])

    async def _maybe_build(self, pointer, building):
        if self.index_builder is None or building is not None or (self._build_task is not None and not self._build_task.done()):
            return
        async with self.repo.pool.acquire() as conn:
            if await self.store.registry_recent_failures(conn, pointer["release_id"], pointer["generation"], pointer["policy_generation"],
                                                         within_seconds=self.index_retry_seconds):
                return
            latest = await self.store.registry_latest_ready(conn)
            identifier = await self.store.registry_start(conn, release_id=pointer["release_id"], generation=pointer["generation"],
                policy_generation=pointer["policy_generation"], path="(building)")
        base = latest["path"] if latest else self.baseline_index
        self._build_task = asyncio.create_task(self._build(identifier, pointer, base), name="auto-publication-index-build")

    async def _build(self, identifier, pointer, base):
        try:
            built = await self.index_builder.build(base, tag=str(identifier)[:13])
            if (str(built["release_id"]) != str(pointer["release_id"]) or built["generation"] != pointer["generation"]
                    or built["policy_generation"] != pointer["policy_generation"]):
                raise ValueError("INDEX_BUILT_FOR_ANOTHER_RELEASE")
            async with self.repo.pool.acquire() as conn:
                await self.store.registry_finish(conn, identifier, "READY", "built", path=built["candidate_index"])
        except Exception as error:  # noqa: BLE001 -- recorded; the next tick retries after the back-off
            LOGGER.warning("auto_publication_index_build_failed kind=%s", type(error).__name__)
            async with self.repo.pool.acquire() as conn:
                await self.store.registry_finish(conn, identifier, "FAILED", type(error).__name__ + ": " + str(error)[:300])


def _checks_view(value):
    import json
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        return []
    return [{"name": name, "label": CHECK_LABELS.get(name, name), "ok": bool(check.get("ok")), "detail": check.get("detail", "")}
            for name, check in value.items()]
