"""Exercise the OCR application lifecycle with deterministic private fixtures."""
from __future__ import annotations

import asyncio
import copy
import hashlib
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from campus247.application.learning.accessible_text import LearningAccessibleText
from campus247.domain.learning import LearningError, require
from campus247_worker.learning.accessible_text import (
    OcrCandidateError,
    OcrPageCandidate,
    canonical_json,
)

VERSION = "version-a"
OFFERING = "offering-a"
MATERIAL = "material-a"
SOURCE_HASH = "a" * 64
PROF = "b" * 64
LECTURER = SimpleNamespace(subject_id="teacher")
STUDENT = SimpleNamespace(subject_id="student")
OUTSIDER = SimpleNamespace(subject_id="outsider")


@contextmanager
def error_code(code):
    with pytest.raises(LearningError) as caught:
        yield
    assert caught.value.code == code


class TransactionRepository:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.state = {
            "versions": {VERSION: {"id": VERSION, "material_id": MATERIAL, "processing_state": "READY",
                                   "publication_state": "PUBLISHED", "rendition_id": "pdf-rendition", "sha256": SOURCE_HASH,
                                   "storage_key": "immutable.pdf", "byte_size": 123, "page_count": 4,
                                   "published_at": "2026-11-06T08:00:00Z"}},
            "materials": {MATERIAL: {"id": MATERIAL, "offering_id": OFFERING, "visibility": "VISIBLE"}},
            "offerings": {OFFERING: {"id": OFFERING, "status": "ACTIVE"}},
            "members": {
                "teacher": {"offering_id": OFFERING, "actor_subject_id": "teacher", "status": "ACTIVE", "role": "INSTRUCTOR", "revision": 1},
                "student": {"offering_id": OFFERING, "actor_subject_id": "student", "status": "ACTIVE", "role": "STUDENT", "revision": 1},
            },
            "previews": {}, "blobs": {},
        }

    @asynccontextmanager
    async def transaction(self):
        async with self.lock:
            state = copy.deepcopy(self.state)
            yield state
            self.state = state


class FixturePipeline:
    profile_sha256 = PROF

    def __init__(self, *, retry_once=False):
        self.retry_once = retry_once
        self.calls = 0

    async def process_page(self, source, page):
        self.calls += 1
        if self.retry_once and self.calls == 1:
            raise OcrCandidateError("OCR_TIMEOUT", retryable=True)
        candidate = {
            "version_id": source.version_id, "rendition_id": source.rendition_id, "page_no": page,
            "source_sha256": source.sha256, "profile_sha256": self.profile_sha256, "status": "NEEDS_REVIEW",
            "schema": "learning-accessible-text-v1",
            "blocks": [{"id": "p1-b1", "type": "PARAGRAPH", "text": "Tiếng Việt v = −3 m/s",
                        "anchor": {"x": .1, "y": .2, "width": .4, "height": .1},
                        "needs_review": True, "review_reasons": ["POSSIBLE_FORMULA"]}],
        }
        return OcrPageCandidate(candidate, hashlib.sha256(canonical_json(candidate)).hexdigest(), 1024)


class Harness(LearningAccessibleText):
    def __init__(self, pipeline):
        self.accessible_text_pipeline = pipeline
        self.accessible_text_offerings = {OFFERING}
        self.accessible_text_ocr_paused_offerings = set()
        self.accessible_text_byte_quota = 400 * 1024**2
        self.repository = TransactionRepository()
        self.blobs = SimpleNamespace(path=lambda name: Path(name))

    @staticmethod
    def directory_items():
        return [{"subject_id": "teacher", "roles": ["LECTURER"]}]

    @staticmethod
    def access(state, actor, offering, *, write=False):
        member = state["members"].get(actor.subject_id)
        require(member is not None and member["status"] == "ACTIVE" and member["offering_id"] == offering)
        if write:
            require(member["role"] == "INSTRUCTOR", 403)
        return state["offerings"][offering], member

    @staticmethod
    def verify_preview(state, actor, action, target, payload, supplied):
        row = state["previews"][supplied["preview_id"]]
        require(not row["consumed"] and row["payload"] == payload and row["actor"] == actor.subject_id
                and row["target"] == target and action == "ocr-release-update", 409, "STALE_PREVIEW")
        row["consumed"] = True

    async def write(self, action, target, payload, *, preview_id=None):
        async with self.repository.transaction() as state:
            return self.command_accessible_text(state, LECTURER, action, target, payload, {"preview_id": preview_id})

    async def preview(self, release_id, payload):
        async with self.repository.transaction() as state:
            guard, _ = self.preview_accessible_text(state, LECTURER, "ocr-release-update", release_id, payload)
            token = str(len(state["previews"]))
            state["previews"][token] = {"payload": payload | {"_ocr_guard": guard}, "actor": LECTURER.subject_id,
                                        "target": release_id, "consumed": False}
            return token

    def read(self, kind, target, actor=STUDENT, **params):
        return self.read_accessible_text(self.repository.state, actor, kind, target, params)


def test_retry_then_review_publish_and_no_revive_after_hidden_source():
    async def scenario():
        worker = FixturePipeline(retry_once=True)
        service = Harness(worker)
        job = await service.write("ocr-job-create", VERSION, {"pages": [1]})
        assert job == await service.write("ocr-job-create", VERSION, {"pages": [1]})
        with error_code("OCR_SCOPE_EXISTS"):
            await service.write("ocr-job-create", VERSION, {"pages": [2]})
        with pytest.raises(LearningError):
            service.read("ocr_jobs", VERSION)
        listing = service.read("ocr_jobs", VERSION, LECTURER)
        assert listing["jobs"] == [job] and listing["daily_pages_remaining"] == 299
        await service.tick_accessible_text()
        assert service.read("ocr_job", job["id"], LECTURER)["errors"] == {"1": {"code": "OCR_TIMEOUT", "permanent": False}}
        await service.tick_accessible_text()
        job = service.read("ocr_job", job["id"], LECTURER)
        assert job["state"] == "NEEDS_REVIEW" and job["completed_pages"] == 1 and worker.calls == 2
        release_id = job["release_id"]
        release = service.read("ocr_release", release_id, LECTURER, page_no=1)
        assert release["review"] is None and release["candidate"]["blocks"][0]["needs_review"]
        assert service.read("accessible_text", VERSION)["release"] is None
        publish = {"operation": "PUBLISH", "revision": 1, "pages": [1], "expected_current_release_id": None}
        with error_code("OCR_PAGE_REVIEW_REQUIRED"):
            await service.preview(release_id, publish)
        decision = {"id": "p1-b1", "type": "FORMULA", "text": "Tiếng Việt. Vận tốc âm ba mét mỗi giây."}
        review = {"operation": "REVIEW_PAGE", "revision": 1, "page_no": 1, "review_confirmed": True,
                  "candidate_sha256": release["candidate"]["sha256"], "blocks": [decision]}
        with error_code("OCR_CRITICAL_REVIEW_REQUIRED"):
            await service.write("ocr-release-update", release_id, review)
        await service.write("ocr-release-update", release_id, review | {"blocks": [decision | {"risk_verified": True}]})
        publish["revision"] = 2
        stale = await service.preview(release_id, publish)
        async with service.repository.transaction() as state:
            state["materials"][MATERIAL]["idea_visibility_epoch"] = 1
        with error_code("STALE_PREVIEW"):
            await service.write("ocr-release-update", release_id, publish, preview_id=stale)
        signed = await service.preview(release_id, publish)
        await service.write("ocr-release-update", release_id, publish, preview_id=signed)
        assert service.read("accessible_text", VERSION)["release"]["missing_page_count"] == 3
        page = service.read("accessible_text_page", VERSION, page_no=1)
        assert page["blocks"][0]["text"] == decision["text"] and "needs_review" not in page["blocks"][0]
        hits = service.read("accessible_text_search", VERSION, q="TIẾNG VIỆT")["hits"]
        assert hits == [{"page_no": 1, "block_id": "p1-b1"}]
        with pytest.raises(LearningError):
            service.read("accessible_text", VERSION, OUTSIDER)
        with pytest.raises(LearningError):
            service.read("accessible_text_page", VERSION, page_no=2)
        clone = await service.write("ocr-release-update", release_id, {"operation": "CLONE", "revision": 3})
        assert clone["state"] == "DRAFT" and service.read("accessible_text", VERSION)["release"]["id"] == release_id
        assert len(service.read("ocr_jobs", VERSION, LECTURER)["releases"]) == 2
        async with service.repository.transaction() as state:
            state["materials"][MATERIAL].update(visibility="HIDDEN", idea_visibility_epoch=2)
        with pytest.raises(LearningError):
            service.read("accessible_text", VERSION)
        async with service.repository.transaction() as state:
            state["materials"][MATERIAL]["visibility"] = "VISIBLE"
        assert service.read("accessible_text", VERSION)["release"] is None
        with pytest.raises(LearningError):
            service.read("accessible_text_search", VERSION, q="Tiếng")
    asyncio.run(scenario())


def test_quota_and_cancel_fence_stop_stale_workers():
    class WaitingWorker(FixturePipeline):
        def __init__(self):
            super().__init__()
            self.started = asyncio.Event()
            self.resume = asyncio.Event()

        async def process_page(self, source, page):
            self.started.set()
            await self.resume.wait()
            return await super().process_page(source, page)

    async def scenario():
        worker = WaitingWorker()
        service = Harness(worker)
        service.accessible_text_byte_quota = 119 * 1024**2
        with error_code("OCR_STORAGE_QUOTA"):
            await service.write("ocr-job-create", VERSION, {"pages": [1]})
        service.accessible_text_byte_quota = 400 * 1024**2
        job = await service.write("ocr-job-create", VERSION, {"pages": [1]})
        running = asyncio.create_task(service.tick_accessible_text())
        await worker.started.wait()
        current = service.read("ocr_job", job["id"], LECTURER)
        await service.write("ocr-job-update", job["id"], {"operation": "CANCEL", "revision": current["revision"]})
        worker.resume.set()
        await running
        saved = service.read("ocr_job", job["id"], LECTURER)
        assert saved["state"] == "CANCELLED" and not saved["completed_pages"]
        usage = service.repository.state["ocr_jobs"][job["id"]]
        assert usage["retained_bytes"] > 0 and not usage["reserved_bytes"]
        service.accessible_text_ocr_paused_offerings.add(OFFERING)
        with error_code("OCR_PROCESSING_PAUSED"):
            await service.write("ocr-job-update", job["id"], {"operation": "RESUME", "revision": saved["revision"]})
        assert service.read("ocr_job", job["id"], LECTURER) == saved
        service.accessible_text_ocr_paused_offerings.clear()
        await service.write("ocr-job-update", job["id"], {"operation": "RESUME", "revision": saved["revision"]})
        await service.tick_accessible_text()
        assert service.read("ocr_job", job["id"], LECTURER)["state"] == "NEEDS_REVIEW"
    asyncio.run(scenario())


def test_offering_pause_skips_its_queue_without_blocking_other_classes():
    async def scenario():
        worker = FixturePipeline()
        service = Harness(worker)
        first = await service.write("ocr-job-create", VERSION, {"pages": [1]})
        other = "offering-b"
        service.accessible_text_offerings.add(other)
        async with service.repository.transaction() as state:
            state["offerings"][other] = {"id": other, "status": "ACTIVE"}
            state["members"]["teacher"]["offering_id"] = other
            state["members"]["first-teacher"] = state["members"]["teacher"] | {"offering_id": OFFERING}
            state["materials"]["material-b"] = {"id": "material-b", "offering_id": other, "visibility": "VISIBLE"}
            state["versions"]["version-b"] = state["versions"][VERSION] | {"id": "version-b", "material_id": "material-b"}
        second = await service.write("ocr-job-create", "version-b", {"pages": [1]})
        service.accessible_text_ocr_paused_offerings.add(OFFERING)
        await service.tick_accessible_text()
        assert worker.calls == 1
        state = service.repository.state
        assert state["ocr_jobs"][first["id"]]["state"] == "QUEUED"
        assert state["ocr_jobs"][first["id"]]["revision"] == first["revision"]
        assert state["ocr_jobs"][second["id"]]["state"] == "NEEDS_REVIEW"
        service.accessible_text_ocr_paused_offerings.clear()
        await service.tick_accessible_text()
        assert worker.calls == 2
        assert service.repository.state["ocr_jobs"][first["id"]]["state"] == "NEEDS_REVIEW"

    asyncio.run(scenario())


def test_expired_lease_then_manual_retry_preserves_checkpoints_and_charges_quota():
    class FixtureFailurePipeline(FixturePipeline):
        async def process_page(self, source, page):
            if page == 3:
                raise OcrCandidateError("OCR_SOURCE_INVALID")
            return await super().process_page(source, page)

    async def scenario():
        worker = FixtureFailurePipeline()
        service = Harness(worker)
        job = await service.write("ocr-job-create", VERSION, {"pages": [1, 2, 3]})
        await service.tick_accessible_text()
        for _ in range(3):
            claim = await service._claim_ocr_page(worker)
            assert claim[1] == 2
            async with service.repository.transaction() as state:
                state["ocr_jobs"][job["id"]]["lease_expires_at"] = "2020-01-01T00:00:00+00:00"
        await service.tick_accessible_text()
        saved = service.read("ocr_job", job["id"], LECTURER)
        assert saved["state"] == "NEEDS_REVIEW" and saved["completed_pages"] == 1
        assert saved["errors"] == {"2": {"code": "OCR_LEASE_EXPIRED", "permanent": False},
                                   "3": {"code": "OCR_SOURCE_INVALID", "permanent": True}}
        assert service.read("ocr_jobs", VERSION, LECTURER)["daily_pages_remaining"] == 297
        retry = {"operation": "RESUME", "revision": saved["revision"]}
        service.accessible_text_byte_quota = 250 * 1024**2
        with error_code("OCR_STORAGE_QUOTA"):
            await service.write("ocr-job-update", job["id"], retry)
        assert service.read("ocr_jobs", VERSION, LECTURER)["daily_pages_remaining"] == 297
        service.accessible_text_byte_quota = 400 * 1024**2
        await service.write("ocr-job-update", job["id"], retry)
        assert service.read("ocr_jobs", VERSION, LECTURER)["daily_pages_remaining"] == 296
        await service.tick_accessible_text()
        saved = service.read("ocr_job", job["id"], LECTURER)
        assert saved["state"] == "NEEDS_REVIEW" and saved["completed_pages"] == 2 and worker.calls == 2
        assert saved["errors"] == {"3": {"code": "OCR_SOURCE_INVALID", "permanent": True}}
        with error_code("OCR_RETRY_LIMIT"):
            await service.write("ocr-job-update", job["id"], {"operation": "RESUME", "revision": saved["revision"]})

    asyncio.run(scenario())
