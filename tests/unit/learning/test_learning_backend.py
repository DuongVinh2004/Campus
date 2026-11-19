"""Learning R1 lifecycle, isolation and restart evidence on fresh explicit stores."""
import asyncio
import hashlib
import os
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from campus247.application.learning.service import LearningService
from campus247.domain.learning import LearningError, select_bytes
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.learning.blob import (
    FixtureHashScanner,
    LearningBlobStore,
    UnavailableScanner,
)
from campus247.infrastructure.learning.repository import SQLiteLearningRepository
from campus247.ports.identity import IdentityContext, IdentityRole
from campus247.presentation.learning import create_learning_router
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


class LearningTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        configured = os.environ.get("LEARNING_TEST_ROOT")
        if not configured:
            raise RuntimeError("Set LEARNING_TEST_ROOT to an authorized existing evidence directory")
        root = Path(configured).resolve(strict=True)
        self.root = root / ("case-" + uuid4().hex)
        self.root.mkdir()
        self.objects = self.root / "objects"
        self.objects.mkdir()
        writer = PdfWriter()
        writer.add_blank_page(width=600, height=800)
        content = BytesIO()
        writer.write(content)
        self.pdf = content.getvalue()
        self.scanner = FixtureHashScanner([hashlib.sha256(self.pdf).hexdigest()])
        self.tenant = "learning-test"
        def actor(role):
            current = datetime.now(UTC)
            return IdentityContext(subject_id=generate_uuid7(), external_subject="test", issuer="test", roles=(IdentityRole(role),), display_name=role, auth_time=current, expires_at=current + timedelta(hours=1), tenant_id=self.tenant, session_id=generate_uuid7(), student_code="SYN1" if role == "STUDENT" else None)
        self.admin, self.teacher, self.student, self.outsider = (actor(role) for role in ("SYSTEM_ADMIN", "LECTURER", "STUDENT", "STUDENT"))
        self.directory = [{"subject_id": a.subject_id, "display_name": a.display_name, "roles": [r.value for r in a.roles], "is_synthetic": True} for a in (self.teacher, self.student, self.outsider)]
        self.repo = SQLiteLearningRepository(self.root / "learning.sqlite3", workspace=root, tenant_id=self.tenant, create=True)
        self.service = LearningService(self.repo, LearningBlobStore(self.objects, workspace=root), tenant_id=self.tenant, signing_key="synthetic-signing-key", scanner=self.scanner, directory=lambda: self.directory)
        self.term = await self.cmd(self.admin, "term-create", None, {"name": "Synthetic", "start_date": "2026-01-01", "end_date": "2026-12-31"})
        self.course = await self.cmd(self.admin, "course-create", None, {"code": "SYN101", "name": "Synthetic course"})
        self.offering = await self.cmd(self.admin, "offering-create", None, {"term_id": self.term["id"], "course_id": self.course["id"], "section_code": "A"})
        self.teacher_member = await self.cmd(self.admin, "member-create", self.offering["id"], {"actor_subject_id": self.teacher.subject_id, "role": "INSTRUCTOR"})
        self.student_member = await self.cmd(self.admin, "member-create", self.offering["id"], {"actor_subject_id": self.student.subject_id, "role": "STUDENT"})
        self.session = await self.cmd(self.teacher, "session-create", self.offering["id"], {"title": "Buổi tổng hợp"})
        self.material = await self.cmd(self.teacher, "material-create", self.offering["id"], {"title": "Bài tổng hợp", "session_id": self.session["id"]})

    async def cmd(self, actor, action, target, payload, key=None):
        if action in {"term-create", "course-create", "offering-create", "member-create"} and "preview_id" not in payload:
            preview = await self.service.preview(actor, action, target, payload)
            payload = dict(payload) | {"preview_id": preview["preview_id"], "confirmation_token": preview["confirmation_token"]}
        return await self.service.command(actor, action, target, payload, key=key or uuid4().hex)

    async def upload(self):
        intent = await self.cmd(self.teacher, "upload-create", self.material["id"], {"filename": "bai.pdf", "byte_size": len(self.pdf), "content_type": "application/pdf"})
        async def chunks():
            yield self.pdf[:17]
            yield self.pdf[17:]
        await self.service.receive(self.teacher, intent["id"], chunks())
        version = await self.service.complete(self.teacher, intent["id"])
        self.assertEqual(version["processing_state"], "QUEUED")
        await self.service.tick()
        return await self.service.query(self.teacher, "version", version["id"])

    async def publish(self, version, action="publish", **payload):
        preview = await self.service.preview(self.teacher, action, version["id"], payload)
        return await self.cmd(self.teacher, action, version["id"], dict(payload) | {"preview_id": preview["preview_id"], "confirmation_token": preview["confirmation_token"]})

    async def test_upload_draft_publication_and_restart(self):
        version = await self.upload()
        self.assertEqual(version["processing_state"], "READY")
        with self.assertRaises(LearningError):
            await self.service.query(self.student, "content", version["id"])
        await self.publish(version)
        content = await self.service.query(self.student, "content", version["id"])
        self.assertEqual(content["sha256"], hashlib.sha256(self.pdf).hexdigest())
        repo = SQLiteLearningRepository(self.root / "learning.sqlite3", workspace=self.root.parent, tenant_id=self.tenant)
        reopened = LearningService(repo, self.service.blobs, tenant_id=self.tenant, signing_key="synthetic-signing-key", directory=self.directory)
        self.assertEqual((await reopened.query(self.student, "version", version["id"]))["publication_state"], "PUBLISHED")

    async def test_outsider_admin_and_changed_membership_cannot_read(self):
        version = await self.upload()
        await self.publish(version)
        for actor in (self.outsider, self.admin):
            with self.subTest(actor=actor.display_name), self.assertRaises(LearningError):
                await self.service.query(actor, "content", version["id"])
        payload = {"status": "INACTIVE", "revision": 1}
        preview = await self.service.preview(self.admin, "member-update", self.student_member["id"], payload)
        await self.cmd(self.admin, "member-update", self.student_member["id"], payload | {"preview_id": preview["preview_id"], "confirmation_token": preview["confirmation_token"]})
        with self.assertRaises(LearningError):
            await self.service.query(self.student, "content", version["id"])
        self.assertEqual(await self.service.query(self.student, "notifications"), [])

    async def test_file_versions_immutable_and_retract(self):
        first = await self.upload()
        await self.publish(first)
        second = await self.upload()
        await self.publish(second)
        self.assertEqual(second["version_no"], 2)
        await self.service.query(self.student, "content", first["id"])
        await self.publish(first, "retract")
        with self.assertRaises(LearningError):
            await self.service.query(self.student, "content", first["id"])
        self.assertEqual(len(list(self.objects.iterdir())), 2)

    async def test_retraction_preview_binds_published_replacement_of_the_same_material(self):
        first = await self.upload()
        await self.publish(first)
        second = await self.upload()
        await self.publish(second)
        draft = await self.upload()
        selected = {"replacement_version_id": first["id"]}
        preview = await self.service.preview(self.teacher, "retract", second["id"], selected)
        self.assertEqual(preview["retraction"], {
            "is_current": True, "candidates": [{"id": first["id"], "version_no": 1}],
        })
        proof = {key: preview[key] for key in ("preview_id", "confirmation_token")}
        with self.assertRaises(LearningError) as changed:
            await self.cmd(self.teacher, "retract", second["id"], proof)
        self.assertEqual(changed.exception.code, "STALE_PREVIEW")
        with self.assertRaises(LearningError) as invalid:
            await self.service.preview(self.teacher, "retract", second["id"], {"replacement_version_id": draft["id"]})
        self.assertEqual(invalid.exception.code, "INVALID_REPLACEMENT")
        before = await self.service.query(self.student, "version", first["id"])
        key = uuid4().hex
        reverted = await self.cmd(self.teacher, "retract", second["id"], selected | proof, key)
        self.assertEqual(reverted, await self.cmd(self.teacher, "retract", second["id"], selected | proof, key))
        self.assertEqual(reverted["current_published_version_id"], first["id"])
        self.assertEqual(reverted["publication_state"], "RETRACTED")
        after = await self.service.query(self.student, "version", first["id"])
        self.assertEqual((after["revision"], after["published_at"]), (before["revision"], before["published_at"]))
        with self.assertRaises(LearningError):
            await self.service.query(self.student, "content", second["id"])
        self.assertEqual(len(await self.service.query(self.student, "notifications")), 1)
        self.assertEqual(len(list(self.objects.iterdir())), 3)

    async def test_upload_expiry_keeps_received_blob_and_releases_only_unstarted_reservation(self):
        payload = {"filename": "expiry.pdf", "byte_size": len(self.pdf), "content_type": "application/pdf"}
        unused, received = [
            await self.cmd(self.teacher, "upload-create", self.material["id"], payload) for _ in range(2)
        ]

        async def chunks():
            yield self.pdf

        await self.service.receive(self.teacher, received["id"], chunks())
        with self.assertRaises(LearningError) as limit:
            await self.cmd(self.teacher, "upload-create", self.material["id"], payload)
        self.assertEqual(limit.exception.code, "UPLOAD_LIMIT")
        past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
        async with self.repo.transaction() as state:
            for intent in (unused, received):
                state["uploads"][intent["id"]]["expires_at"] = past
        self.assertEqual((await self.service.query(self.teacher, "upload", received["id"]))["state"], "EXPIRED")
        await self.service.tick()
        async with self.repo.transaction() as state:
            untouched, retained = (state["uploads"][intent["id"]] for intent in (unused, received))
            self.assertEqual((untouched["state"], retained["state"]), ("EXPIRED", "EXPIRED"))
            self.assertTrue(untouched["reservation_released"])
            self.assertFalse(retained.get("reservation_released"))
            self.assertEqual((self.objects / retained["storage_key"]).read_bytes(), self.pdf)
        with self.assertRaises(LearningError) as failure:
            await self.service.complete(self.teacher, received["id"])
        self.assertEqual(failure.exception.code, "UPLOAD_EXPIRED")
        self.assertEqual((await self.cmd(self.teacher, "upload-create", self.material["id"], payload))["state"], "CREATED")

    async def test_upload_abort_wins_when_inflight_body_finishes(self):
        payload = {"filename": "aborted.pdf", "byte_size": len(self.pdf), "content_type": "application/pdf"}
        intent = await self.cmd(self.teacher, "upload-create", self.material["id"], payload)

        async def chunks():
            yield self.pdf
            await self.service.abort(self.teacher, intent["id"])

        with self.assertRaises(LearningError) as error:
            await self.service.receive(self.teacher, intent["id"], chunks())
        self.assertEqual(error.exception.code, "UPLOAD_NOT_WRITABLE")
        with self.assertRaises(LearningError):
            await self.service.complete(self.teacher, intent["id"])
        async with self.repo.transaction() as state:
            upload = state["uploads"][intent["id"]]
            self.assertEqual(upload["state"], "ABORTED")
            self.assertFalse(upload.get("version_id"))
            self.assertEqual((self.objects / upload["storage_key"]).read_bytes(), self.pdf)

    async def test_upload_completion_key_cannot_bind_two_intents(self):
        payload = {"filename": "idempotent.pdf", "byte_size": len(self.pdf), "content_type": "application/pdf"}
        intents = [await self.cmd(self.teacher, "upload-create", self.material["id"], payload) for _ in range(2)]

        async def chunks():
            yield self.pdf

        for intent in intents:
            await self.service.receive(self.teacher, intent["id"], chunks())
        key = uuid4().hex
        first = await self.service.complete(self.teacher, intents[0]["id"], key=key)
        self.assertEqual(first["id"], (await self.service.complete(self.teacher, intents[0]["id"], key=key))["id"])
        with self.assertRaises(LearningError) as conflict:
            await self.service.complete(self.teacher, intents[1]["id"], key=key)
        self.assertEqual(conflict.exception.code, "IDEMPOTENCY_CONFLICT")
        self.assertNotEqual(first["id"], (await self.service.complete(self.teacher, intents[1]["id"], key=uuid4().hex))["id"])

    async def test_preview_stale_and_idempotent_publish(self):
        version = await self.upload()
        preview = await self.service.preview(self.teacher, "publish", version["id"], {})
        payload = {"preview_id": preview["preview_id"], "confirmation_token": preview["confirmation_token"]}
        key = uuid4().hex
        one = await self.cmd(self.teacher, "publish", version["id"], payload, key)
        two = await self.cmd(self.teacher, "publish", version["id"], payload, key)
        self.assertEqual(one, two)
        self.assertEqual(len(await self.service.query(self.student, "notifications")), 1)
        with self.assertRaises(LearningError):
            await self.cmd(self.teacher, "publish", version["id"], payload)

    async def test_unavailable_scanner_never_ready(self):
        self.service.scanner = UnavailableScanner()
        version = await self.upload_without_assert_ready()
        self.assertEqual(version["processing_state"], "FAILED")
        with self.assertRaises(LearningError):
            await self.publish(version)

    async def upload_without_assert_ready(self):
        return await self.upload()

    async def test_reader_state_revision_and_own_bookmarks(self):
        version = await self.upload()
        await self.publish(version)
        state = {"page_no": 1, "revision": 0, "scroll_mode": "horizontal"}
        saved = await self.cmd(self.student, "reader-state", version["id"], state)
        self.assertEqual(saved["revision"], 1)
        with self.assertRaises(LearningError):
            await self.cmd(self.student, "reader-state", version["id"], state)
        await self.cmd(self.student, "bookmark-create", version["id"], {"version_id": version["id"], "page_no": 1, "label": "Đọc tiếp"})
        self.assertEqual(len(await self.service.query(self.student, "bookmarks")), 1)
        self.assertEqual(await self.service.query(self.teacher, "bookmarks"), [])

    async def test_cross_class_link_rollback_and_hidden_material(self):
        version = await self.upload()
        await self.publish(version)
        payload = {"visibility": "HIDDEN", "revision": 2}
        preview = await self.service.preview(self.teacher, "material-update", self.material["id"], payload)
        await self.cmd(self.teacher, "material-update", self.material["id"], payload | {"preview_id": preview["preview_id"], "confirmation_token": preview["confirmation_token"]})
        self.assertEqual(await self.service.query(self.student, "materials", self.session["id"]), [])
        with self.assertRaises(LearningError):
            await self.cmd(self.teacher, "material-links", self.session["id"], {"material_ids": [generate_uuid7()]})

    async def test_offering_timezone_follows_term_and_defaults_for_old_records(self):
        target = self.offering["id"]
        self.assertEqual((await self.service.query(self.student, "offering", target))["timezone"], "Asia/Bangkok")
        async with self.repo.transaction() as state:
            state["terms"][self.term["id"]]["timezone"] = "Asia/Tokyo"
        joined, = await self.service.query(self.student, "offerings")
        administered, = await self.service.query(self.admin, "admin_offerings")
        self.assertEqual((joined["timezone"], administered["timezone"]), ("Asia/Tokyo", "Asia/Tokyo"))
        with self.assertRaises(LearningError):
            await self.service.query(self.outsider, "offering", target)

    async def test_http_range_head_and_permission(self):
        version = await self.upload()
        await self.publish(version)
        app = FastAPI()
        actors = {"student": self.student, "teacher": self.teacher, "outsider": self.outsider}
        @app.middleware("http")
        async def identity(request, call_next):
            request.state.identity = actors.get(request.headers.get("X-Test-Actor", "student"))
            return await call_next(request)
        app.include_router(create_learning_router(self.service))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            url = f'/v1/learning/versions/{version["id"]}/content'
            partial = await client.get(url, headers={"Range": "bytes=0-4"})
            self.assertEqual((partial.status_code, partial.content), (206, b"%PDF-"))
            self.assertEqual(partial.headers["Content-Length"], "5")
            head = await client.head(url, headers={"Range": "bytes=0-4"})
            self.assertEqual((head.status_code, head.content), (200, b""))
            self.assertEqual(int(head.headers["Content-Length"]), len(self.pdf))
            bad = await client.get(url, headers={"Range": "bytes=999999-"})
            self.assertEqual(bad.status_code, 416)
            denied = await client.get(url, headers={"X-Test-Actor": "outsider", "Range": "bytes=0-4"})
            self.assertEqual(denied.status_code, 404)
            unknown = await client.post("/v1/learning/offerings", json={"actor_id": self.admin.subject_id}, headers={"X-Test-Actor": "teacher", "Idempotency-Key": uuid4().hex})
            self.assertEqual(unknown.status_code, 422)

    async def test_expired_identity_and_scanner_hash_boundary(self):
        object.__setattr__(self.outsider, "expires_at", datetime.now(UTC) - timedelta(seconds=1))
        with self.assertRaises(LearningError) as result:
            await self.service.query(self.outsider, "offerings")
        self.assertEqual(result.exception.status, 401)
        self.service.scanner = FixtureHashScanner([])
        version = await self.upload()
        self.assertEqual(version["processing_state"], "FAILED")

    async def test_private_annotations_and_private_questions(self):
        version = await self.upload()
        await self.publish(version)
        payload = {"version_id": version["id"], "page_no": 1, "anchor": {"kind": "REGION", "x": .1, "y": .2, "width": .3, "height": .4}, "body": "Ghi chú riêng"}
        note = await self.cmd(self.student, "annotation-create", version["id"], payload)
        self.assertEqual(len(await self.service.query(self.student, "annotations", version_id=version["id"])), 1)
        self.assertEqual(await self.service.query(self.teacher, "annotations", version_id=version["id"]), [])
        with self.assertRaises(LearningError):
            await self.cmd(self.teacher, "annotation-update", note["id"], {"body": "Không được sửa", "revision": 1})
        question = await self.cmd(self.student, "question-create", version["id"], {"page_no": 1, "anchor": {"kind": "PAGE"}, "body": "Câu hỏi riêng", "visibility": "PRIVATE_TO_INSTRUCTORS"})
        reply = await self.cmd(self.teacher, "reply-create", question["id"], {"body": "Gợi ý", "question_revision": question["revision"]})
        await self.cmd(self.teacher, "reply-endorse", reply["id"], {})
        self.assertTrue((await self.service.query(self.student, "questions", version["id"]))[0]["replies"][0]["endorsed"])
        with self.assertRaises(LearningError):
            await self.cmd(self.student, "question-update", question["id"], {"visibility": "CLASS", "revision": 1})

    async def test_note_share_keeps_original_private_and_rechecks_revision(self):
        version = await self.upload()
        await self.publish(version)
        await self.cmd(self.admin, "member-create", self.offering["id"], {
            "actor_subject_id": self.outsider.subject_id, "role": "STUDENT",
        })
        note = await self.cmd(self.student, "annotation-create", version["id"], {
            "page_no": 1, "body": "Ghi chú để hỏi", "anchor": {"kind": "PAGE"},
        })
        target = note["id"]
        with self.assertRaises(LearningError):
            await self.service.preview(self.teacher, "annotation-share", target, {"revision": 1})
        with self.assertRaises(LearningError) as missing:
            await self.cmd(self.student, "annotation-share", target, {"revision": 1})
        self.assertEqual(missing.exception.code, "CONFIRMATION_REQUIRED")

        async def preview(revision):
            draft = await self.service.preview(self.student, "annotation-share", target, {"revision": revision})
            return draft["sharing"], {"revision": revision, "preview_id": draft["preview_id"],
                                     "confirmation_token": draft["confirmation_token"]}

        _, stale = await preview(1)
        await self.cmd(self.student, "annotation-update", target, {"revision": 1, "body": "Nội dung đã sửa"})
        with self.assertRaises(LearningError) as conflict:
            await self.cmd(self.student, "annotation-share", target, stale)
        self.assertEqual(conflict.exception.code, "REVISION_CONFLICT")
        sharing, confirmation = await preview(2)
        self.assertEqual((sharing["body"], sharing["page_no"]), ("Nội dung đã sửa", 1))
        key = uuid4().hex
        copy = await self.cmd(self.student, "annotation-share", target, confirmation, key)
        self.assertEqual(copy, await self.cmd(self.student, "annotation-share", target, confirmation, key))
        self.assertEqual(await self.service.query(self.teacher, "annotations", version_id=version["id"]), [])
        self.assertEqual(await self.service.query(self.outsider, "questions", version["id"]), [])
        visible, = await self.service.query(self.teacher, "questions", version["id"])
        self.assertEqual((visible["body"], visible["visibility"]), ("Nội dung đã sửa", "PRIVATE_TO_INSTRUCTORS"))
        original, = await self.service.query(self.student, "annotations", version_id=version["id"])
        self.assertEqual((original["id"], original["revision"]), (target, 2))

    async def test_sharing_confirmation_binds_content_author_and_session_and_keeps_replies_private(self):
        version = await self.upload()
        await self.publish(version)
        classmate = await self.cmd(self.admin, "member-create", self.offering["id"], {"actor_subject_id": self.outsider.subject_id, "role": "STUDENT"})
        question = await self.cmd(self.student, "question-create", version["id"], {"page_no": 1, "body": "Tại sao có bước này?"})
        reply = await self.cmd(self.teacher, "reply-create", question["id"], {"body": "Private reply", "question_revision": 1})
        # Legacy replies lack an explicit scope and must inherit their old thread scope.
        async with self.repo.transaction() as state:
            state["replies"][reply["id"]].pop("visibility")
        self.assertEqual(await self.service.query(self.outsider, "questions", version["id"]), [])
        self.assertEqual(await self.service.query(self.outsider, "notifications"), [])
        payload = {"visibility": "CLASS", "revision": 1}
        with self.assertRaises(LearningError):
            await self.service.preview(self.teacher, "question-update", question["id"], payload)
        preview = await self.service.preview(self.student, "question-update", question["id"], payload)
        self.assertEqual(preview["sharing"], {"from": "PRIVATE_TO_INSTRUCTORS", "to": "CLASS", "body": question["body"], "page_no": 1, "version_id": version["id"], "anchor": {"kind": "PAGE"}})
        confirm = payload | {k: preview[k] for k in ("preview_id", "confirmation_token")}
        with self.assertRaises(LearningError) as failure:
            await self.cmd(replace(self.student, session_id=generate_uuid7()), "question-update", question["id"], confirm)
        self.assertEqual(failure.exception.code, "STALE_PREVIEW")
        await self.cmd(self.student, "question-update", question["id"], {"body": "Nội dung đã sửa", "revision": 1})
        with self.assertRaises(LearningError) as failure:
            await self.cmd(self.student, "question-update", question["id"], confirm)
        self.assertEqual(failure.exception.code, "REVISION_CONFLICT")
        payload["revision"] = 2
        preview = await self.service.preview(self.student, "question-update", question["id"], payload)
        confirm = payload | {k: preview[k] for k in ("preview_id", "confirmation_token")}
        key = uuid4().hex
        result = await self.cmd(self.student, "question-update", question["id"], confirm, key=key)
        self.assertEqual(await self.cmd(self.student, "question-update", question["id"], confirm, key=key), result)
        with self.assertRaises(LearningError) as failure:
            await self.cmd(self.teacher, "reply-create", question["id"], {"body": "Still private from old screen", "question_revision": 2})
        self.assertEqual(failure.exception.code, "REVISION_CONFLICT")
        public_thread, = await self.service.query(self.outsider, "questions", version["id"])
        self.assertEqual(public_thread["body"], "Nội dung đã sửa")
        self.assertEqual(public_thread["replies"], [])
        self.assertEqual(result["replies"][0]["visibility"], "PRIVATE_TO_INSTRUCTORS")
        notice, = await self.service.query(self.outsider, "notifications")
        self.assertEqual((notice["event_type"], notice["question_id"], notice["page_no"]), ("QUESTION_SCOPE_CHANGED", question["id"], 1))
        self.assertNotIn("body", notice)
        await self.cmd(self.outsider, "reply-create", question["id"], {"body": "Public reply", "question_revision": 3})
        async with self.repo.transaction() as state:
            share_events = [e for e in state["outbox"].values() if e["event_type"] == "QUESTION_SCOPE_CHANGED"]
            self.assertEqual(len(share_events), 1)
            self.assertNotIn("body", share_events[0])
        payload = {"visibility": "PRIVATE_TO_INSTRUCTORS", "revision": 3}
        preview = await self.service.preview(self.student, "question-update", question["id"], payload)
        await self.cmd(self.student, "question-update", question["id"], payload | {k: preview[k] for k in ("preview_id", "confirmation_token")})
        self.assertEqual(await self.service.query(self.outsider, "questions", version["id"]), [])
        self.assertEqual(await self.service.query(self.outsider, "notifications"), [])
        with self.assertRaises(LearningError):
            await self.cmd(self.outsider, "notification-update", notice["id"], {"read_at": "2026-11-05T10:00:00Z"})
        self.assertEqual(classmate["role"], "STUDENT")

    async def test_discussion_notices_persist_without_content_and_recheck_recipient_permissions(self):
        version = await self.upload()
        await self.publish(version)
        question = await self.cmd(self.student, "question-create", version["id"], {"page_no": 1, "body": "Private content"})
        teacher_notice, = [r for r in await self.service.query(self.teacher, "notifications") if r.get("question_id")]
        self.assertEqual(teacher_notice["event_type"], "QUESTION_CREATED")
        reply = await self.cmd(self.student, "reply-create", question["id"], {"body": "Private clarification", "question_revision": 1})
        await self.cmd(self.teacher, "reply-endorse", reply["id"], {})
        await self.cmd(self.teacher, "reply-endorse", reply["id"], {})
        await self.cmd(self.teacher, "reply-create", question["id"], {"body": "Private teacher response", "question_revision": 1})
        repo = SQLiteLearningRepository(self.root / "learning.sqlite3", workspace=self.root.parent, tenant_id=self.tenant)
        reopened = LearningService(repo, self.service.blobs, tenant_id=self.tenant, signing_key="synthetic-signing-key", directory=self.directory)
        notices = [r for r in await reopened.query(self.student, "notifications") if r.get("question_id")]
        self.assertCountEqual([r["event_type"] for r in notices], ["QUESTION_REPLIED", "REPLY_ENDORSED"])
        self.assertTrue(all("body" not in r and "anchor" not in r for r in notices))
        downgraded = replace(self.teacher, roles=(IdentityRole("STUDENT"),), student_code="SYN-DOWNGRADED")
        self.assertEqual(await reopened.query(downgraded, "notifications"), [])
        with self.assertRaises(LearningError):
            await reopened.command(downgraded, "notification-update", teacher_notice["id"], {"read_at": "2026-11-05T10:00:00Z"})

    async def test_reading_instructions_and_presentation_authority(self):
        version = await self.upload()
        await self.publish(version)
        instruction = await self.cmd(self.teacher, "instruction-create", self.session["id"], {"version_id": version["id"], "page_ranges": [{"start": 1, "end": 1}], "purpose": "Đọc trước", "timing": "BEFORE", "questions": ["Nội dung chính?"]})
        self.assertEqual((await self.service.query(self.student, "reading-instructions", self.session["id"]))[0]["id"], instruction["id"])
        with self.assertRaises(LearningError):
            await self.cmd(self.teacher, "instruction-create", self.session["id"], {"version_id": version["id"], "page_ranges": [{"start": 1, "end": 2}], "purpose": "Sai phạm vi"})
        presentation = await self.cmd(self.teacher, "presentation-create", self.offering["id"], {"version_id": version["id"]})
        with self.assertRaises(LearningError):
            await self.cmd(self.student, "presentation-position", presentation["id"], {"page_no": 1, "sequence": 1})
        moved = await self.cmd(self.teacher, "presentation-position", presentation["id"], {"page_no": 1, "sequence": 1})
        self.assertEqual(moved["sequence"], 2)
        await self.cmd(self.teacher, "presentation-end", presentation["id"], {})
        self.assertEqual((await self.service.query(self.student, "presentation", presentation["id"]))["status"], "ENDED")

    async def test_scheduled_publication_rechecks_authority(self):
        version = await self.upload()
        at = (datetime.now(UTC) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        await self.publish(version, scheduled_at=at)
        async with self.repo.transaction() as state:
            state["versions"][version["id"]]["scheduled_at"] = "2020-01-01T00:00:00Z"
            state["members"][self.teacher_member["id"]]["status"] = "INACTIVE"
        await self.service.tick()
        async with self.repo.transaction() as state:
            self.assertEqual(state["versions"][version["id"]]["publication_state"], "DRAFT")
        with self.assertRaises(LearningError):
            await self.service.query(self.student, "content", version["id"])

    async def test_blob_corruption_detected_and_worker_lease_recovery(self):
        version = await self.upload()
        await self.publish(version)
        row = await self.service.query(self.student, "content", version["id"])
        await self.service.blobs.verify(row["storage_key"], row["sha256"], row["byte_size"])
        path = self.service.blobs.path(row["storage_key"])
        # Only mutate this test-created blob; preserve it as corruption evidence.
        with path.open("r+b") as stream:
            stream.seek(10)
            original = stream.read(1)
            stream.seek(10)
            stream.write(bytes([original[0] ^ 1]))
        with self.assertRaises(LearningError) as result:
            await self.service.blobs.verify(row["storage_key"], row["sha256"], row["byte_size"])
        self.assertEqual(result.exception.code, "BLOB_CORRUPTED")

    async def test_disabled_router_fails_closed(self):
        app = FastAPI()
        @app.middleware("http")
        async def identity(request, call_next):
            request.state.identity = self.student
            return await call_next(request)
        app.include_router(create_learning_router(None))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            self.assertEqual((await client.get("/v1/learning/offerings")).status_code, 503)
            capabilities = await client.get("/v1/learning/capabilities")
            self.assertFalse(capabilities.json()["available"])
            self.assertEqual(capabilities.headers["Cache-Control"], "no-store")

    def enable_pptx_fixture(self, *, pages=1, source_matches=True, conversion_error=None):
        import zipfile
        from types import SimpleNamespace

        from campus247.ports.learning_rendition import PPTX_MEDIA_TYPE
        package = BytesIO()
        with zipfile.ZipFile(package, 'w') as archive:
            archive.writestr('[Content_Types].xml', '<Types/>')
            archive.writestr('ppt/slides/slide1.xml', '<slide/>')
        source = package.getvalue()
        preview = self.root / 'converted-fixture.pdf'
        with preview.open('xb') as stream:
            stream.write(self.pdf)
        class Converter:
            available = True
            calls = 0
            async def convert(inner, path, expected_sha256):
                inner.calls += 1
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected_sha256)
                if conversion_error:
                    raise ValueError(conversion_error)
                return SimpleNamespace(rendition_id=uuid4().hex, pdf_path=str(preview), pdf_sha256=hashlib.sha256(self.pdf).hexdigest(),
                    pdf_bytes=len(self.pdf), source_sha256=expected_sha256 if source_matches else '0'*64, slide_count=pages,
                    converter_version='fixture-converter', converter_sha256='a'*64)
        converter = Converter()
        self.service.pptx_converter = converter
        self.service.scanner = FixtureHashScanner([hashlib.sha256(source).hexdigest(), hashlib.sha256(self.pdf).hexdigest()])
        return source, PPTX_MEDIA_TYPE, converter

    async def upload_pptx_fixture(self, source, media_type):
        upload = await self.cmd(self.teacher, 'upload-create', self.material['id'], {'filename':'lesson.pptx','byte_size':len(source),'content_type':media_type})
        async def chunks():
            yield source
        await self.service.receive(self.teacher, upload['id'], chunks())
        version = await self.service.complete(self.teacher, upload['id'])
        await self.service.tick()
        return await self.service.query(self.teacher, 'version', version['id'])

    async def test_pptx_original_pdf_rendition_and_source_bound_annotations(self):
        source, media_type, converter = self.enable_pptx_fixture()
        version = await self.upload_pptx_fixture(source, media_type)
        self.assertEqual(version['processing_state'], 'READY')
        self.assertTrue(version['rendition_id'])
        await self.publish(version)
        content = await self.service.query(self.student, 'content', version['id'])
        original = await self.service.query(self.student, 'content', version['id'], download=True)
        self.assertEqual(content['content_type'], 'application/pdf')
        self.assertEqual(original['content_type'], media_type)
        self.assertEqual(self.service.blobs.path(original['storage_key']).read_bytes(), source)
        self.assertEqual(self.service.blobs.path(content['storage_key']).read_bytes(), self.pdf)
        self.assertNotEqual(content['storage_key'], original['storage_key'])
        note_payload = {'version_id':version['id'],'page_no':1,'body':'Source-bound note','anchor':{'kind':'PAGE'}}
        with self.assertRaises(LearningError) as missing:
            await self.cmd(self.student, 'annotation-create', version['id'], note_payload)
        self.assertEqual(missing.exception.code, 'RENDITION_REQUIRED')
        with self.assertRaises(LearningError) as wrong:
            await self.cmd(self.student, 'annotation-create', version['id'], note_payload | {'rendition_id':str(uuid4())})
        self.assertEqual(wrong.exception.code, 'RENDITION_MISMATCH')
        note = await self.cmd(self.student, 'annotation-create', version['id'], note_payload | {'rendition_id':version['rendition_id']})
        self.assertEqual(note['rendition_id'], version['rendition_id'])
        await self.service.process_version(version['id'])
        self.assertEqual(converter.calls, 1)
        second = await self.upload_pptx_fixture(source, media_type)
        self.assertNotEqual(second['rendition_id'], version['rendition_id'])
        await self.publish(second)
        self.assertEqual(await self.service.query(self.student, 'annotations', version_id=second['id']), [])

    async def test_pptx_page_count_mismatch_is_rejected_before_publication(self):
        source, media_type, _ = self.enable_pptx_fixture(pages=2)
        version = await self.upload_pptx_fixture(source, media_type)
        self.assertEqual(version['processing_state'], 'REJECTED')
        self.assertEqual(version['error_code'], 'PPTX_SLIDE_COUNT_MISMATCH')
        with self.assertRaises(LearningError):
            await self.publish(version)
        with self.assertRaises(LearningError):
            await self.service.query(self.teacher, 'content', version['id'])

    async def test_pptx_wrong_source_hash_is_not_ready(self):
        source, media_type, _ = self.enable_pptx_fixture(source_matches=False)
        version = await self.upload_pptx_fixture(source, media_type)
        self.assertEqual(version['processing_state'], 'FAILED')
        self.assertEqual(version['error_code'], 'RENDITION_SOURCE_MISMATCH')

    async def test_pptx_macro_rejection_from_converter_is_permanent(self):
        source, media_type, converter = self.enable_pptx_fixture(conversion_error='PPTX_ACTIVE_CONTENT_REJECTED')
        version = await self.upload_pptx_fixture(source, media_type)
        await self.service.tick()
        self.assertEqual(version['processing_state'], 'REJECTED')
        self.assertEqual(converter.calls, 1)

    async def test_unconfigured_pptx_never_accepts_upload_or_claims_capability(self):
        from campus247.ports.learning_rendition import PPTX_MEDIA_TYPE
        capabilities = await self.service.query(self.teacher, 'capabilities')
        self.assertFalse(capabilities['pptx_available'])
        self.assertEqual(capabilities['supported_types'], ['application/pdf'])
        with self.assertRaises(LearningError) as unavailable:
            await self.cmd(self.teacher, 'upload-create', self.material['id'], {'filename':'lesson.pptx','content_type':PPTX_MEDIA_TYPE,'byte_size':200})
        self.assertEqual(unavailable.exception.code, 'PPTX_CONVERTER_UNAVAILABLE')

    async def test_class_quota_includes_retained_optimized_view_bytes(self):
        version = await self.upload()
        view_id = generate_uuid7()
        async with self.repo.transaction() as state:
            state["blobs"][view_id] = {"id": view_id, "byte_size": 2 * 1024**3 - len(self.pdf), "storage_key": generate_uuid7() + ".pdf"}
            state["versions"][version["id"]]["view_blob_id"] = view_id
        with self.assertRaises(LearningError) as rejected:
            await self.cmd(self.teacher, "upload-create", self.material["id"], {"filename": "extra.pdf", "byte_size": len(self.pdf), "content_type": "application/pdf"})
        self.assertEqual(rejected.exception.code, "QUOTA_EXCEEDED")

    async def test_explanation_uses_verified_page_source_and_rejects_fake_quote(self):
        writer = PdfWriter()
        page = writer.add_blank_page(width=600, height=800)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
        content = DecodedStreamObject()
        source = "SQL JOIN combines rows using matching columns."
        content.set_data(("BT /F1 12 Tf 20 750 Td (" + source + ") Tj ET").encode())
        page[NameObject("/Contents")] = writer._add_object(content)
        output = BytesIO()
        writer.write(output)
        self.pdf = output.getvalue()
        self.service.scanner = FixtureHashScanner([hashlib.sha256(self.pdf).hexdigest()])
        version = await self.upload()
        await self.publish(version)
        from campus247.ports.llm import LlmResponse, LlmResponseStatus
        class Gateway:
            quote = "SQL JOIN"
            calls = 0
            supported = True
            async def generate(inner, request):
                inner.calls += 1
                self.assertEqual(request.allowed_tools, ())
                self.assertEqual(request.privacy_class.value, "internal")
                self.assertLessEqual(request.deadline_ms, 5000)
                self.assertLessEqual(request.max_output_tokens, 1000)
                if request.route_id == "learning_material_verification":
                    return LlmResponse(LlmResponseStatus.COMPLETED, "synthetic", "synthetic", structured_output={"supported": inner.supported, "answers_question": True})
                return LlmResponse(LlmResponseStatus.COMPLETED, "synthetic", "synthetic", structured_output={"explanation": "JOIN combines rows using matching columns.", "source_quote": inner.quote, "questions": ["What matches?"]})
        from campus247.application.learning.explanation import (
            LearningExplanationVerifier,
        )
        gateway = Gateway()
        verifier = LearningExplanationVerifier(gateway)
        with self.assertRaises(LearningError) as blocked:
            await self.service.explain(self.student, version["id"], page_no=1, question="What is JOIN?", gateway=gateway, verifier=verifier)
        self.assertEqual(blocked.exception.code, "LEARNING_AI_SOURCE_NOT_APPROVED")
        self.service.ai_source_hashes = frozenset({hashlib.sha256(self.pdf).hexdigest()})
        with self.assertRaises(LearningError) as blocked:
            await self.service.explain(replace(self.student, is_synthetic=False), version["id"], page_no=1, question="What is JOIN?", gateway=gateway, verifier=verifier)
        self.assertEqual(blocked.exception.code, "LEARNING_AI_SOURCE_NOT_APPROVED")
        self.assertEqual(gateway.calls, 0)
        result = await self.service.explain(self.student, version["id"], page_no=1, question="What is JOIN?", quote="SQL JOIN", gateway=gateway, verifier=verifier)
        self.assertEqual(result["citations"][0]["page_no"], 1)
        self.assertEqual(result["citations"][0]["version_id"], version["id"])
        self.assertEqual(result["citations"][0]["quote"], "SQL JOIN")
        gateway.quote = "NOT IN SOURCE"
        with self.assertRaises(LearningError) as rejected:
            await self.service.explain(self.student, version["id"], page_no=1, question="What is JOIN?", gateway=gateway, verifier=verifier)
        self.assertEqual(rejected.exception.code, "INSUFFICIENT_SOURCE")
        with self.assertRaises(LearningError) as invalid_selection:
            await self.service.explain(self.student, version["id"], page_no=1, question="What is JOIN?", quote="FAKE SELECTION", gateway=gateway, verifier=verifier)
        self.assertEqual(invalid_selection.exception.code, "SOURCE_SELECTION_MISMATCH")
        self.assertEqual(gateway.calls, 3)
        gateway.quote, gateway.supported = "SQL JOIN", False
        with self.assertRaises(LearningError) as unsupported:
            await self.service.explain(self.student, version["id"], page_no=1, question="What is JOIN?", gateway=gateway, verifier=verifier)
        self.assertEqual(unsupported.exception.code, "INSUFFICIENT_SOURCE")
        self.assertEqual(gateway.calls, 5)

    async def test_job_total_timeout_cancels_scanner_and_limits_retries(self):
        from unittest.mock import patch
        cancelled = []
        class BlockingScanner:
            async def scan(inner, path):
                try:
                    await asyncio.sleep(10)
                finally:
                    cancelled.append(True)
        self.service.scanner = BlockingScanner()
        version = await self.upload_without_ready()
        async with self.repo.transaction() as state:
            source = dict(state["versions"][version["id"]])
        # Verify the real source before measuring scanner cancellation. On
        # Windows a checksum thread can consume the entire 10 ms test budget.
        await self.service.blobs.verify(source["storage_key"], source["sha256"], source["byte_size"])
        with patch("campus247.application.learning.service.PROCESSING_TIMEOUT_SECONDS", 0.01):
            for _ in range(4):
                await self.service.tick()
        async with self.repo.transaction() as state:
            self.assertEqual(state["jobs"][version["id"]]["attempt"], 3)
            self.assertEqual(state["versions"][version["id"]]["error_code"], "PROCESSING_TIMEOUT")
            self.assertEqual(state["versions"][version["id"]]["processing_state"], "FAILED")
        self.assertEqual(len(cancelled), 3)

    async def test_job_total_timeout_cancels_verification_before_scanning(self):
        from unittest.mock import AsyncMock, patch
        cancelled = []
        async def blocked_verification(*args):
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.append(True)
        version = await self.upload_without_ready()
        scan = AsyncMock()
        self.service.scanner = type("Scanner", (), {"scan": scan})()
        with patch.object(self.service.blobs, "verify", side_effect=blocked_verification), \
                patch("campus247.application.learning.service.PROCESSING_TIMEOUT_SECONDS", 0.01):
            for _ in range(4):
                await self.service.tick()
        async with self.repo.transaction() as state:
            self.assertEqual(state["jobs"][version["id"]]["attempt"], 3)
            self.assertEqual(state["versions"][version["id"]]["error_code"], "PROCESSING_TIMEOUT")
            self.assertEqual(state["versions"][version["id"]]["processing_state"], "FAILED")
        self.assertEqual(len(cancelled), 3)
        scan.assert_not_awaited()

    async def upload_without_ready(self):
        intent = await self.cmd(self.teacher, "upload-create", self.material["id"], {"filename": "queued.pdf", "byte_size": len(self.pdf), "content_type": "application/pdf"})
        async def chunks():
            yield self.pdf
        await self.service.receive(self.teacher, intent["id"], chunks())
        return await self.service.complete(self.teacher, intent["id"])

    async def test_expired_lease_is_recovered_and_stale_attempt_cannot_commit(self):
        started, release = asyncio.Event(), asyncio.Event()
        class PausedScanner:
            async def scan(inner, path):
                started.set()
                await release.wait()
        self.service.scanner = PausedScanner()
        version = await self.upload_without_ready()
        first = asyncio.create_task(self.service.process_version(version["id"]))
        try:
            await asyncio.wait_for(started.wait(), 2)
            async with self.repo.transaction() as state:
                state["jobs"][version["id"]]["lease_until"] = "2020-01-01T00:00:00Z"
            self.service.scanner = self.scanner
            await self.service.tick()
            release.set()
            await first
        finally:
            release.set()
            if not first.done():
                first.cancel()
                await asyncio.gather(first, return_exceptions=True)
        async with self.repo.transaction() as state:
            self.assertEqual(state["jobs"][version["id"]]["attempt"], 2)
            self.assertEqual(state["jobs"][version["id"]]["state"], "DONE")
            self.assertEqual(state["versions"][version["id"]]["processing_state"], "READY")

    async def test_http_cursor_is_bounded_and_bound_to_actor(self):
        app = FastAPI()
        @app.middleware("http")
        async def identity(request, call_next):
            request.state.identity = self.admin if request.headers.get("X-Test-Actor") == "admin" else self.student
            return await call_next(request)
        app.include_router(create_learning_router(self.service))
        await self.cmd(self.admin, "course-create", None, {"code": "SYN102", "name": "Course2"})
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            first = await client.get("/v1/learning/courses?limit=1", headers={"X-Test-Actor": "admin"})
            self.assertEqual(len(first.json()["items"]), 1)
            self.assertTrue(first.json()["page"]["has_more"])
            second = await client.get("/v1/learning/courses", params={"limit": 1, "cursor": first.json()["page"]["next_cursor"]}, headers={"X-Test-Actor": "admin"})
            self.assertEqual(len(second.json()["items"]), 1)
            self.assertNotEqual(first.json()["items"][0]["id"], second.json()["items"][0]["id"])
            malformed = await client.get("/v1/learning/courses?limit=101", headers={"X-Test-Actor": "admin"})
            self.assertEqual(malformed.status_code, 422)
            unauth = await client.get("/v1/learning/courses", params={"cursor": first.json()["page"]["next_cursor"]})
            self.assertEqual(unauth.status_code, 403)

    async def test_admin_creation_requires_bound_confirmation(self):
        payload = {"code": "CONFIRM101", "name": "Bound creation"}
        with self.assertRaises(LearningError) as unconfirmed:
            await self.service.command(self.admin, "course-create", None, payload, key=uuid4().hex)
        self.assertEqual(unconfirmed.exception.code, "CONFIRMATION_REQUIRED")
        preview = await self.service.preview(self.admin, "course-create", None, payload)
        changed = dict(payload) | {"name": "Changed after preview", "preview_id": preview["preview_id"], "confirmation_token": preview["confirmation_token"]}
        with self.assertRaises(LearningError) as stale:
            await self.service.command(self.admin, "course-create", None, changed, key=uuid4().hex)
        self.assertEqual(stale.exception.code, "STALE_PREVIEW")


    async def test_instruction_seen_is_private_and_specific_to_the_edited_revision(self):
        version = await self.upload()
        await self.publish(version)
        instruction = await self.cmd(self.teacher, "instruction-create", self.session["id"], {
            "version_id": version["id"], "page_ranges": [{"start": 1, "end": 1}], "purpose": "Đọc bản đầu",
        })
        iid = instruction["id"]
        with self.assertRaises(LearningError):
            await self.cmd(self.outsider, "instruction-seen", iid, {"revision": 1})
        await self.cmd(self.admin, "member-create", self.offering["id"], {
            "actor_subject_id": self.outsider.subject_id, "role": "STUDENT",
        })
        seen = await self.cmd(self.student, "instruction-seen", iid, {"revision": 1})
        self.assertTrue(seen["seen_at"])
        self.assertEqual(seen, await self.cmd(self.student, "instruction-seen", iid, {"revision": 1}))
        other, = await self.service.query(self.outsider, "reading-instructions", self.session["id"])
        self.assertIsNone(other["seen_at"])
        self.assertNotIn("seen", other)
        updated = await self.cmd(self.teacher, "instruction-update", iid, {"purpose": "Đọc lại", "revision": 1})
        self.assertEqual(updated["history"][0]["purpose"], "Đọc bản đầu")
        self.assertNotIn("seen", updated)
        current, = await self.service.query(self.student, "reading-instructions", self.session["id"])
        self.assertEqual(current["purpose"], "Đọc lại")
        self.assertNotIn("history", current)
        self.assertIsNone(current["seen_at"])
        with self.assertRaises(LearningError) as stale:
            await self.cmd(self.student, "instruction-seen", iid, {"revision": 1})
        self.assertEqual(stale.exception.code, "REVISION_CONFLICT")


class RangeTests(unittest.TestCase):
    def test_boundaries_and_if_range(self):
        self.assertEqual(select_bytes(10, "bytes=-3").start, 7)
        self.assertEqual(select_bytes(10, "bytes=10-").status, 416)
        self.assertEqual(select_bytes(10, "bytes=4-3").status, 200)
        self.assertEqual(select_bytes(10, "bytes=0-2,4-5").status, 200)
        self.assertEqual(select_bytes(10, "bytes=0-2", if_range='"old"', etag='"new"').status, 200)
        self.assertEqual(select_bytes(10, "bytes=0-2", if_range='"new"', etag='"new"').status, 206)
