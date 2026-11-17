"""Private, version-bound OCR jobs, explicit page review and immutable releases."""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import unicodedata
from datetime import UTC, datetime, timedelta

from campus247.domain.learning import require
from campus247.domain.shared.values import generate_uuid7
from campus247.ports.learning_rendition import PDF_MEDIA_TYPE

OCR_READS = {"ocr_jobs", "ocr_job", "ocr_release", "accessible_text", "accessible_text_page", "accessible_text_search"}
OCR_WRITES = {"ocr-job-create", "ocr-job-update", "ocr-release-update"}
OCR_COLLECTIONS = ("ocr_jobs", "ocr_page_results", "ocr_releases", "ocr_release_pages")
_MAX_DAILY_PAGES = 300
_MAX_ATTEMPTS = 3
_ATTEMPT_BYTES = 40 * 1024**2
_LEASE_SECONDS = 120
_HEARTBEAT_SECONDS = 20
_ACTIVE_JOBS = {"QUEUED", "RUNNING"}


def _now():
    return datetime.now(UTC)


def _sha(payload):
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(data).hexdigest(), len(data)


def _required_text(value, limit=4000):
    require(isinstance(value, str) and bool(value.strip()) and len(value) <= limit, 422, "OCR_REVIEW_TEXT_INVALID",
            "Nội dung duyệt cần có chữ trong giới hạn cho phép.")
    return unicodedata.normalize("NFC", value.strip())


def _daily_pages(jobs, today):
    return sum((len(job["pages"]) if job["day"] == today else 0)
               + (job["manual_retry_pages"] if job.get("manual_retry_day") == today else 0) for job in jobs)


class LearningAccessibleText:
    def _ocr_source(self, state, version_id):
        version = state["versions"].get(version_id)
        if (version is None or version["processing_state"] != "READY"
                or version["publication_state"] == "RETRACTED"
                or version.get("source_media_type", PDF_MEDIA_TYPE) != PDF_MEDIA_TYPE):
            return None
        material = state["materials"].get(version["material_id"])
        if material is None or material["offering_id"] not in self.accessible_text_offerings:
            return None
        blob = version
        if version.get("view_blob_id"):
            blob = state["blobs"].get(version["view_blob_id"])
            if blob is None or blob.get("derived_from_blob_id") != version["blob_id"]:
                return None
        return version, material, blob

    def _ocr_access(self, state, actor, version_id, *, manage=False, public=False):
        source = self._ocr_source(state, version_id)
        require(source is not None)
        version, material, _ = source
        _, member = self.access(state, actor, material["offering_id"], write=manage)
        if not public:
            require(member["role"] == "INSTRUCTOR", 403, "OCR_MANAGEMENT_FORBIDDEN", "Cần quyền quản lý bản chữ.")
        else:
            require(material["visibility"] == "VISIBLE" and version["publication_state"] == "PUBLISHED")
        return source

    def _ocr_job(self, state, actor, job_id, *, manage=False):
        job = state.get("ocr_jobs", {}).get(job_id)
        require(job is not None)
        self._ocr_access(state, actor, job["version_id"], manage=manage)
        return job

    def _ocr_release(self, state, actor, release_id, *, manage=False):
        release = state.get("ocr_releases", {}).get(release_id)
        require(release is not None)
        self._ocr_access(state, actor, release["version_id"], manage=manage)
        return release

    @staticmethod
    def _ocr_job_view(state, job):
        completed = sum(result["job_id"] == job["id"] for result in state.get("ocr_page_results", {}).values())
        return {key: job[key] for key in ("id", "version_id", "pages", "state", "revision", "release_id", "errors")} | {
            "completed_pages": completed, "requested_pages": len(job["pages"]),
        }

    @staticmethod
    def _ocr_manifest(state, release, version):
        return {"id": release["id"], "version_id": release["version_id"], "revision": release["revision"],
                "state": release["state"], "page_count": version["page_count"],
                "available_pages": list(release.get("published_pages", [])),
                "missing_page_count": version["page_count"] - len(release.get("published_pages", []))}

    @staticmethod
    def _release_source_matches(release, version, material, blob):
        return (release["source_sha256"] == blob["sha256"] and release["rendition_id"] == version.get("rendition_id")
                and release.get("published_source_at") == version.get("published_at")
                and release.get("source_visibility_epoch", 0) == material.get("idea_visibility_epoch", 0)
                and release.get("source_access_epoch", 0) == version.get("idea_source_epoch", 0))

    def _ocr_review_manifest(self, state, release, version):
        job = state["ocr_jobs"][release["job_id"]]
        return self._ocr_manifest(state, release, version) | {
            "current_release_id": version.get("accessible_text_release_id"),
            "requested_pages": list(job["pages"]),
            "reviewed_pages": sorted(row["page_no"] for row in state.get("ocr_release_pages", {}).values()
                                     if row["release_id"] == release["id"]),
        }

    def read_accessible_text(self, state, actor, kind, target, params):
        if kind == "ocr_jobs":
            version, material, _ = self._ocr_access(state, actor, target)
            jobs = [job for job in state.get("ocr_jobs", {}).values() if job["offering_id"] == material["offering_id"]]
            own = sorted((job for job in jobs if job["version_id"] == target), key=lambda job: job["id"], reverse=True)
            releases = sorted((row for row in state.get("ocr_releases", {}).values() if row["version_id"] == target),
                              key=lambda row: row["id"], reverse=True)
            current_id = version.get("accessible_text_release_id")
            current = [row for row in releases if row["id"] == current_id]
            recent = current + [row for row in releases if row["id"] != current_id]
            today = _now().date().isoformat()
            return {"jobs": [self._ocr_job_view(state, job) for job in own[:50]],
                    "releases": [self._ocr_review_manifest(state, row, version) for row in recent[:50]],
                    "daily_pages_remaining": max(0, _MAX_DAILY_PAGES - _daily_pages(jobs, today)),
                    "max_pages_per_job": 100,
                    "storage_available_bytes": max(0, self.accessible_text_byte_quota -
                                                   sum(job["reserved_bytes"] + job["retained_bytes"] for job in jobs)),
                    "has_more": len(own) > 50 or len(releases) > 50}
        if kind == "ocr_job":
            return self._ocr_job_view(state, self._ocr_job(state, actor, target))
        if kind == "ocr_release":
            release = self._ocr_release(state, actor, target)
            version = state["versions"][release["version_id"]]
            job = state["ocr_jobs"][release["job_id"]]
            manifest = self._ocr_review_manifest(state, release, version)
            if (page := params.get("page_no")) is not None:
                require(type(page) is int and 1 <= page <= version["page_count"], 422, "INVALID_PAGE", "Trang không hợp lệ.")
                result = state.get("ocr_page_results", {}).get(f'{job["id"]}:{page}')
                review = state.get("ocr_release_pages", {}).get(f"{target}:{page}")
                if result:
                    require(_sha(result["candidate"])[0] == result["sha256"], 503, "OCR_ARTIFACT_INTEGRITY",
                            "Không xác minh được bản chữ nháp.")
                manifest["candidate"] = {"sha256": result["sha256"], **result["candidate"]} if result else None
                manifest["review"] = {"page_no": page, "blocks": review["blocks"]} if review else None
            return copy.deepcopy(manifest)

        version, material, blob = self._ocr_access(state, actor, target, public=True)
        release = state.get("ocr_releases", {}).get(version.get("accessible_text_release_id"))
        if release is None or release["state"] != "PUBLISHED" or not self._release_source_matches(release, version, material, blob):
            if kind == "accessible_text":
                return {"release": None, "version_id": target, "state": "UNAVAILABLE"}
            require(False)
        if kind == "accessible_text":
            return {"release": self._ocr_manifest(state, release, version), "version_id": target, "state": "PUBLISHED"}
        if kind == "accessible_text_page":
            page = params.get("page_no")
            require(type(page) is int and page in release["published_pages"])
            return self._ocr_public_page(state, release, page)

        query = _required_text(params.get("q"), 120).casefold()
        hits = []
        for page in release["published_pages"]:
            for block in self._ocr_public_page(state, release, page)["blocks"]:
                if block["type"] == "PLACEHOLDER":
                    continue
                text = block.get("text") or " ".join(block.get("items", []))
                if block["type"] == "TABLE":
                    text = " ".join([*block["headers"], *(cell for row in block["rows"] for cell in row)])
                if query in unicodedata.normalize("NFC", text).casefold():
                    hits.append({"page_no": page, "block_id": block["id"]})
                    if len(hits) == 100:
                        return {"release_id": release["id"], "hits": hits, "limit_reached": True}
        return {"release_id": release["id"], "hits": hits, "limit_reached": False}

    @staticmethod
    def _ocr_public_page(state, release, page):
        row = state.get("ocr_release_pages", {}).get(f'{release["id"]}:{page}')
        require(row is not None and _sha(row["blocks"])[0] == row["sha256"], 503, "OCR_ARTIFACT_INTEGRITY",
                "Không xác minh được bản chữ đã công bố.")
        return {"release_id": release["id"], "version_id": release["version_id"], "page_no": page,
                "blocks": copy.deepcopy(row["blocks"])}

    def authorize_accessible_text(self, state, actor, action, target):
        if action == "ocr-job-create":
            self._ocr_access(state, actor, target, manage=True)
        elif action == "ocr-job-update":
            self._ocr_job(state, actor, target, manage=True)
        else:
            self._ocr_release(state, actor, target, manage=True)

    def preview_accessible_text(self, state, actor, action, target, payload):
        self.authorize_accessible_text(state, actor, action, target)
        require(action == "ocr-release-update" and payload.get("operation") in {"PUBLISH", "WITHDRAW"},
                422, "OCR_PREVIEW_ACTION_INVALID", "Chọn công bố hoặc thu hồi bản chữ.")
        release = self._ocr_release(state, actor, target, manage=True)
        self._ocr_check_transition(state, release, payload)
        version = state["versions"][release["version_id"]]
        pages = payload.get("pages", release.get("published_pages", []))
        return self._ocr_release_guard(state, actor, release), {
            "ocr_release": {"id": target, "operation": payload["operation"], "version_id": version["id"],
                            "revision": release["revision"], "pages": pages, "page_count": version["page_count"]},
        }

    def _ocr_release_guard(self, state, actor, release):
        version, material, _ = self._ocr_access(state, actor, release["version_id"], manage=True)
        _, membership = self.access(state, actor, material["offering_id"], write=True)
        return {"source_epoch": version.get("idea_source_epoch", 0), "visibility_epoch": material.get("idea_visibility_epoch", 0),
                "published_at": version.get("published_at"), "membership_revision": membership["revision"],
                "current_release_id": version.get("accessible_text_release_id")}

    def command_accessible_text(self, state, actor, action, target, payload, supplied):
        if action == "ocr-job-create":
            return self._ocr_start_job(state, actor, target, payload)
        if action == "ocr-job-update":
            return self._ocr_update_job(state, actor, target, payload)
        return self._ocr_update_release(state, actor, target, payload, supplied)

    def _ocr_reserve(self, state, offering_id, pages, today):
        jobs = [job for job in state.get("ocr_jobs", {}).values() if job["offering_id"] == offering_id]
        require(not any(job["state"] in _ACTIVE_JOBS for job in jobs), 409, "OCR_CLASS_BUSY", "Lớp đang có công việc OCR.")
        require(_daily_pages(jobs, today) + pages <= _MAX_DAILY_PAGES,
                429, "OCR_PAGE_QUOTA", "Lớp đã hết hạn mức OCR theo ngày.")
        return jobs

    def _ocr_capacity(self, jobs, reserved):
        used = sum(job["reserved_bytes"] + job["retained_bytes"] for job in jobs)
        require(used + reserved <= self.accessible_text_byte_quota, 429, "OCR_STORAGE_QUOTA",
                "Lớp đã hết hạn mức lưu bản chữ.")

    def _ocr_require_processing(self, offering_id):
        require(offering_id not in self.accessible_text_ocr_paused_offerings, 503, "OCR_PROCESSING_PAUSED",
                "Lớp đang tạm dừng xử lý OCR.")

    def _ocr_start_job(self, state, actor, version_id, payload):
        version, material, blob = self._ocr_access(state, actor, version_id, manage=True)
        offering_id = material["offering_id"]
        self._ocr_require_processing(offering_id)
        pipeline = self.accessible_text_pipeline
        require(pipeline is not None, 503, "OCR_WORKER_UNAVAILABLE", "Chưa cấu hình trình xử lý OCR.")
        pages = payload["pages"]
        require(0 < len(pages) <= 100 and all(type(page) is int and 1 <= page <= version["page_count"] for page in pages)
                and len(set(pages)) == len(pages), 422, "OCR_PAGE_RANGE_INVALID", "Chọn tối đa 100 trang hợp lệ.")
        jobs = state.setdefault("ocr_jobs", {})
        logical_key = (version_id, version.get("rendition_id"), blob["sha256"], pipeline.profile_sha256)
        for row in jobs.values():
            if (row["version_id"], row["rendition_id"], row["source_sha256"], row["profile_sha256"]) == logical_key:
                require(row["pages"] == sorted(pages), 409, "OCR_SCOPE_EXISTS", "Phiên bản đã có công việc với phạm vi khác.")
                return self._ocr_job_view(state, row)
        today = _now().date().isoformat()
        others = self._ocr_reserve(state, offering_id, len(pages), today)
        reserved = len(pages) * _MAX_ATTEMPTS * _ATTEMPT_BYTES
        self._ocr_capacity(others, reserved)
        _, member = self.access(state, actor, offering_id, write=True)
        job_id, release_id = generate_uuid7(), generate_uuid7()
        source = {"version_id": version_id, "rendition_id": version.get("rendition_id"), "source_sha256": blob["sha256"],
                  "offering_id": offering_id, "material_id": material["id"]}
        job = source | {"id": job_id, "release_id": release_id, "pages": sorted(pages), "state": "QUEUED",
                        "profile_sha256": pipeline.profile_sha256, "revision": 1, "attempts": {}, "errors": {},
                        "requested_by": actor.subject_id, "member_revision": member["revision"],
                        "source_visibility_epoch": material.get("idea_visibility_epoch", 0),
                        "source_access_epoch": version.get("idea_source_epoch", 0),
                        "day": today, "reserved_bytes": reserved, "retained_bytes": 0}
        jobs[job_id] = job
        state.setdefault("ocr_releases", {})[release_id] = source | {"id": release_id, "job_id": job_id,
            "state": "DRAFT", "revision": 1}
        return self._ocr_job_view(state, job)

    def _ocr_update_job(self, state, actor, target, payload):
        job = self._ocr_job(state, actor, target, manage=True)
        require(job["revision"] == payload["revision"], 409, "REVISION_CONFLICT", "Công việc đã thay đổi.")
        operation = payload["operation"]
        if operation == "CANCEL":
            require(job["state"] in {"QUEUED", "RUNNING", "PAUSED", "FAILED"}, 409, "OCR_JOB_STATE", "Công việc đã kết thúc.")
            if job["state"] == "RUNNING":
                self._ocr_charge_attempt(job, _ATTEMPT_BYTES)
            job.update(state="CANCELLED", reserved_bytes=0)
            self._ocr_clear_lease(job)
        else:
            self._ocr_require_processing(job["offering_id"])
            require(operation == "RESUME" and job["state"] in {"PAUSED", "FAILED", "CANCELLED", "NEEDS_REVIEW"},
                    409, "OCR_JOB_STATE", "Công việc chưa thể chạy lại.")
            pipeline = self.accessible_text_pipeline
            require(pipeline is not None and pipeline.profile_sha256 == job["profile_sha256"],
                    409, "OCR_PROFILE_CHANGED", "Cấu hình OCR đã thay đổi, hãy tạo yêu cầu mới.")
            exhausted = [page for page in job["pages"] if job["attempts"].get(str(page), 0) >= _MAX_ATTEMPTS
                         and job["errors"].get(str(page), {}).get("permanent") is False]
            today = _now().date().isoformat()
            others = self._ocr_reserve(state, job["offering_id"], len(exhausted), today)
            attempts = self._ocr_pending_attempts(state, job)
            require(attempts or exhausted, 409, "OCR_RETRY_LIMIT", "Không còn lượt thử lại cho các trang đã chọn.")
            remaining = sum(_MAX_ATTEMPTS - job["attempts"].get(str(page), 0) for page in attempts)
            reserved = (remaining + len(exhausted) * _MAX_ATTEMPTS) * _ATTEMPT_BYTES
            self._ocr_capacity([row for row in others if row["id"] != job["id"]] + [job | {"reserved_bytes": 0}], reserved)
            _, member = self.access(state, actor, job["offering_id"], write=True)
            version, material, blob = self._ocr_access(state, actor, job["version_id"], manage=True)
            require(blob["sha256"] == job["source_sha256"] and version.get("rendition_id") == job["rendition_id"],
                    409, "OCR_SOURCE_CHANGED", "Nguồn đã thay đổi, hãy tạo yêu cầu mới.")
            if exhausted:
                previous = job["manual_retry_pages"] if job.get("manual_retry_day") == today else 0
                job.update(manual_retry_day=today, manual_retry_pages=previous + len(exhausted))
                for page in exhausted:
                    job["attempts"][str(page)] = 0
            job.update(state="QUEUED", requested_by=actor.subject_id, member_revision=member["revision"], reserved_bytes=reserved,
                       source_visibility_epoch=material.get("idea_visibility_epoch", 0),
                       source_access_epoch=version.get("idea_source_epoch", 0))
        job["revision"] += 1
        return self._ocr_job_view(state, job)

    @staticmethod
    def _ocr_pending_attempts(state, job):
        return [page for page in job["pages"] if f'{job["id"]}:{page}' not in state.get("ocr_page_results", {})
                and job["attempts"].get(str(page), 0) < _MAX_ATTEMPTS
                and not job["errors"].get(str(page), {}).get("permanent")]

    @staticmethod
    def _ocr_charge_attempt(job, actual):
        job["reserved_bytes"] = max(0, job["reserved_bytes"] - _ATTEMPT_BYTES)
        job["retained_bytes"] += min(_ATTEMPT_BYTES, max(0, actual))

    @staticmethod
    def _ocr_clear_lease(job):
        for key in ("lease_token", "lease_page", "lease_expires_at"):
            job.pop(key, None)

    def _ocr_requester_active(self, state, job):
        membership = any(member["offering_id"] == job["offering_id"] and member["actor_subject_id"] == job["requested_by"]
                         and member["status"] == "ACTIVE" and member["role"] == "INSTRUCTOR"
                         and member["revision"] == job["member_revision"] for member in state["members"].values())
        principal = next((entry for entry in self.directory_items() if entry["subject_id"] == job["requested_by"]), None)
        return membership and principal is not None and "LECTURER" in principal["roles"] and state["offerings"][job["offering_id"]]["status"] == "ACTIVE"

    @staticmethod
    def _ocr_job_source_matches(job, source):
        if source is None:
            return False
        version, material, blob = source
        return (blob["sha256"] == job["source_sha256"] and version.get("rendition_id") == job["rendition_id"]
                and job.get("source_visibility_epoch", 0) == material.get("idea_visibility_epoch", 0)
                and job.get("source_access_epoch", 0) == version.get("idea_source_epoch", 0))

    async def _claim_ocr_page(self, pipeline):
        processing_offerings = self.accessible_text_offerings - self.accessible_text_ocr_paused_offerings
        if not processing_offerings:
            return None
        async with self.repository.transaction() as state:
            for job in state.get("ocr_jobs", {}).values():
                if job["state"] not in _ACTIVE_JOBS or job["offering_id"] not in processing_offerings:
                    continue
                if job["state"] == "RUNNING":
                    if job["lease_expires_at"] > _now().isoformat():
                        continue
                    self._ocr_charge_attempt(job, _ATTEMPT_BYTES)
                    if (page := job.get("lease_page")) is not None:
                        job["errors"][str(page)] = {"code": "OCR_LEASE_EXPIRED", "permanent": False}
                    self._ocr_clear_lease(job)
                    job["state"] = "QUEUED"
                source = self._ocr_source(state, job["version_id"])
                if (not self._ocr_job_source_matches(job, source)
                        or job["profile_sha256"] != pipeline.profile_sha256 or not self._ocr_requester_active(state, job)):
                    job.update(state="PAUSED", reserved_bytes=0, revision=job["revision"] + 1)
                    continue
                candidates = self._ocr_pending_attempts(state, job)
                if not candidates:
                    self._ocr_finish_job(state, job)
                    continue
                page, lease = candidates[0], generate_uuid7()
                job["attempts"][str(page)] = job["attempts"].get(str(page), 0) + 1
                job.update(state="RUNNING", lease_token=lease, lease_page=page,
                           lease_expires_at=(_now() + timedelta(seconds=_LEASE_SECONDS)).isoformat(),
                           revision=job["revision"] + 1)
                return copy.deepcopy(job), page, lease, copy.deepcopy(source)
        return None

    def _ocr_finish_job(self, state, job):
        completed = any(row["job_id"] == job["id"] for row in state.get("ocr_page_results", {}).values())
        job.update(state="NEEDS_REVIEW" if completed else "FAILED", reserved_bytes=0, revision=job["revision"] + 1)
        self._ocr_clear_lease(job)

    async def tick_accessible_text(self):
        pipeline = self.accessible_text_pipeline
        if pipeline is None:
            return
        claim = await self._claim_ocr_page(pipeline)
        if claim is None:
            return
        from campus247_worker.learning.accessible_text import (
            OcrCandidateError,
            OcrSource,
        )

        job, page, lease, (version, _, blob) = claim
        source = OcrSource(self.blobs.path(blob["storage_key"]), blob["sha256"], blob["byte_size"], version["page_count"],
                           version["id"], version.get("rendition_id"))
        task = asyncio.create_task(pipeline.process_page(source, page))
        try:
            while not task.done():
                done, _ = await asyncio.wait({task}, timeout=_HEARTBEAT_SECONDS)
                if done:
                    break
                async with self.repository.transaction() as state:
                    current = state["ocr_jobs"][job["id"]]
                    if current.get("lease_token") != lease or current["lease_expires_at"] <= _now().isoformat():
                        return
                    if (not self._ocr_requester_active(state, current) or
                            not self._ocr_job_source_matches(current, self._ocr_source(state, current["version_id"]))):
                        self._ocr_charge_attempt(current, _ATTEMPT_BYTES)
                        self._ocr_clear_lease(current)
                        current.update(state="PAUSED", reserved_bytes=0, revision=current["revision"] + 1)
                        return
                    current["lease_expires_at"] = (_now() + timedelta(seconds=_LEASE_SECONDS)).isoformat()
            result = task.result()
            error = None
        except OcrCandidateError as caught:
            result = None
            error = {"code": caught.code, "permanent": not caught.retryable}
        except (TimeoutError, OSError):
            result = None
            error = {"code": "OCR_WORKER_UNAVAILABLE", "permanent": False}
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        async with self.repository.transaction() as state:
            current = state["ocr_jobs"][job["id"]]
            if current.get("lease_token") != lease or current["lease_expires_at"] <= _now().isoformat():
                return
            self._ocr_clear_lease(current)
            source_now = self._ocr_source(state, job["version_id"])
            if not self._ocr_job_source_matches(current, source_now) or not self._ocr_requester_active(state, current):
                self._ocr_charge_attempt(current, _ATTEMPT_BYTES)
                current.update(state="PAUSED", reserved_bytes=0, revision=current["revision"] + 1)
                return
            if result:
                candidate = result.payload
                checksum, byte_size = _sha(candidate)
                valid = (checksum == result.sha256 and candidate.get("version_id") == job["version_id"]
                         and candidate.get("rendition_id") == job["rendition_id"] and candidate.get("page_no") == page
                         and candidate.get("source_sha256") == job["source_sha256"]
                         and candidate.get("profile_sha256") == job["profile_sha256"]
                         and candidate.get("schema") == "learning-accessible-text-v1"
                         and isinstance(candidate.get("blocks"), list) and candidate.get("status") == "NEEDS_REVIEW")
                if valid:
                    state.setdefault("ocr_page_results", {}).setdefault(f'{job["id"]}:{page}', {
                        "job_id": job["id"], "page_no": page, "candidate": candidate, "sha256": checksum, "byte_size": byte_size})
                    current["errors"].pop(str(page), None)
                    self._ocr_charge_attempt(current, byte_size + getattr(result, "retained_bytes", _ATTEMPT_BYTES))
                else:
                    error = {"code": "OCR_RESULT_BINDING", "permanent": True}
            if error:
                current["errors"][str(page)] = error
                self._ocr_charge_attempt(current, _ATTEMPT_BYTES)
            if self._ocr_pending_attempts(state, current):
                current.update(state="QUEUED", revision=current["revision"] + 1)
            else:
                self._ocr_finish_job(state, current)

    def _ocr_check_transition(self, state, release, payload):
        require(release["revision"] == payload["revision"], 409, "REVISION_CONFLICT", "Bản chữ đã thay đổi.")
        source = self._ocr_source(state, release["version_id"])
        require(source is not None)
        version, material, blob = source
        require(blob["sha256"] == release["source_sha256"] and version.get("rendition_id") == release["rendition_id"],
                409, "OCR_SOURCE_CHANGED", "Nguồn bản chữ đã thay đổi.")
        operation = payload["operation"]
        if operation == "PUBLISH":
            require(release["state"] == "DRAFT" and material["visibility"] == "VISIBLE" and version["publication_state"] == "PUBLISHED",
                    409, "OCR_RELEASE_STATE", "Cần bản chữ nháp và PDF đang công bố.")
            require(payload.get("expected_current_release_id") == version.get("accessible_text_release_id"),
                    409, "OCR_CURRENT_RELEASE_CHANGED", "Bản chữ hiện hành đã thay đổi.")
            pages = payload.get("pages", [])
            require(0 < len(pages) <= 100 and all(type(page) is int for page in pages) and len(set(pages)) == len(pages),
                    422, "OCR_PAGE_RANGE_INVALID", "Chọn các trang đã duyệt để công bố.")
            require(all(f'{release["id"]}:{page}' in state.get("ocr_release_pages", {}) for page in pages),
                    409, "OCR_PAGE_REVIEW_REQUIRED", "Còn trang chưa được duyệt.")
            for page in pages:
                self._ocr_public_page(state, release, page)
        elif operation == "WITHDRAW":
            require(release["state"] == "PUBLISHED" and version.get("accessible_text_release_id") == release["id"],
                    409, "OCR_RELEASE_STATE", "Chỉ thu hồi bản chữ hiện hành.")
        return version, material

    @staticmethod
    def _review_block(decision, candidate):
        block_type = decision["type"]
        result = {"id": candidate["id"], "type": block_type, "anchor": candidate["anchor"]}
        if block_type == "PLACEHOLDER":
            return result | {"text": "Đoạn này chưa có bản chữ đã xác minh. Mở ảnh gốc để đối chiếu."}
        sensitive = {"POSSIBLE_TABLE", "POSSIBLE_FORMULA", "LOW_CONFIDENCE"}
        if sensitive.intersection(candidate["review_reasons"]) or block_type in {"TABLE", "FORMULA"}:
            require(decision.get("risk_verified") is True, 422, "OCR_CRITICAL_REVIEW_REQUIRED",
                    "Xác nhận đã đối chiếu số liệu, dấu, công thức và đơn vị với ảnh gốc.")
        if block_type == "HEADING":
            level = decision.get("level")
            require(type(level) is int and 2 <= level <= 4, 422, "OCR_BLOCK_INVALID", "Cấp tiêu đề không hợp lệ.")
            return result | {"level": level, "text": _required_text(decision.get("text"), 400)}
        if block_type == "LIST":
            items = decision.get("items")
            ordered = decision.get("ordered")
            require(isinstance(items, list) and 0 < len(items) <= 40 and type(ordered) is bool,
                    422, "OCR_BLOCK_INVALID", "Danh sách cần các mục và kiểu thứ tự rõ.")
            return result | {"items": [_required_text(item, 500) for item in items], "ordered": ordered}
        if block_type == "TABLE":
            headers, rows = decision.get("headers"), decision.get("rows")
            require(isinstance(headers, list) and 0 < len(headers) <= 12 and isinstance(rows, list)
                    and 0 < len(rows) <= 40 and all(isinstance(row, list) and len(row) == len(headers) for row in rows),
                    422, "OCR_TABLE_INVALID", "Bảng cần tiêu đề cột và hàng có cùng số ô.")
            return result | {"headers": [_required_text(cell, 200) for cell in headers],
                             "rows": [[_required_text(cell, 200) for cell in row] for row in rows]}
        require(block_type in {"PARAGRAPH", "FORMULA", "FIGURE"}, 422, "OCR_BLOCK_INVALID", "Loại khối bản chữ không hợp lệ.")
        return result | {"text": _required_text(decision.get("text"))}

    def _ocr_store_review(self, state, release, payload):
        require(release["state"] == "DRAFT" and payload.get("review_confirmed") is True,
                409, "OCR_REVIEW_REQUIRED", "Xác nhận đã đọc và đối chiếu trang trước khi lưu.")
        page = payload["page_no"]
        artifact = state.get("ocr_page_results", {}).get(f'{release["job_id"]}:{page}')
        require(artifact is not None)
        require(artifact["sha256"] == payload["candidate_sha256"] == _sha(artifact["candidate"])[0],
                409, "OCR_CANDIDATE_CHANGED", "Đầu vào bản duyệt đã thay đổi.")
        blocks = {row["id"]: row for row in artifact["candidate"]["blocks"]}
        decisions = payload["blocks"]
        seen = [decision["id"] for decision in decisions]
        require(len(seen) == len(blocks) and set(seen) == set(blocks), 422, "OCR_REVIEW_INCOMPLETE",
                "Mỗi khối cần một nội dung đã duyệt hoặc một nhãn dẫn tới ảnh gốc.")
        result = [self._review_block(decision, blocks[decision["id"]]) for decision in decisions]
        checksum, byte_size = _sha(result)
        require(byte_size <= 512 * 1024, 422, "OCR_REVIEW_LIMIT", "Bản chữ trang vượt hạn mức.")
        job = state["ocr_jobs"][release["job_id"]]
        others = [row for row in state["ocr_jobs"].values() if row["offering_id"] == job["offering_id"]]
        self._ocr_capacity(others, byte_size)
        job["retained_bytes"] += byte_size
        reviews = state.setdefault("ocr_release_pages", {})
        key = f'{release["id"]}:{page}'
        previous = reviews.get(key)
        history = list(previous.get("history", [])) if previous else []
        if previous:
            history.append({field: previous[field] for field in ("blocks", "sha256", "reviewed_revision")})
        reviews[key] = {"release_id": release["id"], "page_no": page, "blocks": result, "sha256": checksum,
                        "reviewed_revision": release["revision"] + 1, "history": history}

    def _ocr_update_release(self, state, actor, target, payload, supplied):
        release = self._ocr_release(state, actor, target, manage=True)
        version, material = self._ocr_check_transition(state, release, payload)
        operation = payload["operation"]
        if operation == "REVIEW_PAGE":
            self._ocr_store_review(state, release, payload)
        elif operation == "CLONE":
            require(release["state"] in {"PUBLISHED", "WITHDRAWN", "SUPERSEDED"}, 409, "OCR_RELEASE_STATE",
                    "Chỉ tạo bản nháp mới từ bản chữ đã công bố.")
            new_id = generate_uuid7()
            clone = {field: release[field] for field in ("job_id", "version_id", "rendition_id", "source_sha256", "offering_id", "material_id")}
            clone.update(id=new_id, revision=1, state="DRAFT")
            state["ocr_releases"][new_id] = clone
            pages = state.setdefault("ocr_release_pages", {})
            copies = [row for row in pages.values() if row["release_id"] == target]
            job = state["ocr_jobs"][release["job_id"]]
            bytes_added = sum(_sha(row["blocks"])[1] for row in copies)
            self._ocr_capacity([row for row in state["ocr_jobs"].values() if row["offering_id"] == job["offering_id"]], bytes_added)
            job["retained_bytes"] += bytes_added
            for row in copies:
                pages[f'{new_id}:{row["page_no"]}'] = {
                    "release_id": new_id, "page_no": row["page_no"], "blocks": copy.deepcopy(row["blocks"]),
                    "sha256": row["sha256"], "reviewed_revision": 1, "history": [],
                }
            return self._ocr_manifest(state, clone, version)
        else:
            require(operation in {"PUBLISH", "WITHDRAW"}, 422, "OCR_RELEASE_ACTION_INVALID", "Thao tác bản chữ không hợp lệ.")
            preview = state.get("previews", {}).get(supplied.get("preview_id"))
            require(preview is not None, 409, "CONFIRMATION_REQUIRED", "Cần xem trước và xác nhận thao tác.")
            guard = self._ocr_release_guard(state, actor, release)
            require(guard == preview["payload"].get("_ocr_guard"), 409, "STALE_PREVIEW", "Nguồn hoặc quyền truy cập đã thay đổi.")
            self.verify_preview(state, actor, "ocr-release-update", target, payload | {"_ocr_guard": guard}, supplied)
            if operation == "PUBLISH":
                current = state["ocr_releases"].get(version.get("accessible_text_release_id"))
                if current is not None:
                    current.update(state="SUPERSEDED", revision=current["revision"] + 1)
                release.update(state="PUBLISHED", published_pages=sorted(payload["pages"]),
                               published_source_at=version.get("published_at"),
                               source_visibility_epoch=material.get("idea_visibility_epoch", 0),
                               source_access_epoch=version.get("idea_source_epoch", 0))
                version["accessible_text_release_id"] = target
            else:
                release["state"] = "WITHDRAWN"
                version["accessible_text_release_id"] = None
        release["revision"] += 1
        return self._ocr_manifest(state, release, version)
