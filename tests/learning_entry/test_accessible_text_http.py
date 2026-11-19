"""Exercise the real learning HTTP surface with private OCR and explicit publication."""
import hashlib
import json
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from campus247.bootstrap.learning import configure_learning_ocr

from .test_entry_http import ROOT, post
from .test_entry_http import entry as entry  # noqa: PLC0414


class FixturePipeline:
    profile_sha256 = "2" * 64

    async def process_page(self, source, page_no):
        candidate = {
            "schema": "learning-accessible-text-v1", "status": "NEEDS_REVIEW", "version_id": source.version_id,
            "rendition_id": source.rendition_id, "page_no": page_no, "source_sha256": source.sha256,
            "profile_sha256": self.profile_sha256,
            "blocks": [{
                "id": "b1", "type": "PARAGRAPH", "text": "Bản nháp OCR", "order": 0,
                "anchor": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.1},
                "confidence": 88, "needs_review": True, "provenance": "OCR", "review_reasons": ["POSSIBLE_FORMULA"],
            }],
        }
        encoded = json.dumps(candidate, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        return SimpleNamespace(payload=candidate, sha256=hashlib.sha256(encoded).hexdigest(), retained_bytes=0)


@pytest.mark.parametrize("entry", [
    pytest.param({"pages": 2}, id="bounded-fixture"),
    pytest.param({"ocr_native": True}, id="offline-sandbox",
                 marks=pytest.mark.skipif(os.environ.get("LEARNING_OCR_NATIVE_HTTP") != "1", reason="Explicit native runtime rehearsal")),
], indirect=True)
def test_accessible_text_requires_review_and_retains_the_original(entry, request, tmp_path):
    client, service, headers, accounts, pdf = entry
    admin, teacher, student = (headers[role] for role in ("SYSTEM_ADMIN", "LECTURER", "STUDENT"))
    term = post(client, "/terms", {"name": "OCR term", "start_date": "2026-11-01", "end_date": "2027-02-01"}, admin).json()
    course = post(client, "/courses", {"code": "SYN-OCR", "name": "Synthetic OCR"}, admin).json()
    offering = post(client, "/offerings", {"course_id": course["id"], "term_id": term["id"], "section_code": "A"}, admin).json()["id"]
    for role, member_role in [("LECTURER", "INSTRUCTOR"), ("STUDENT", "STUDENT")]:
        added = post(client, f"/offerings/{offering}/members", {
            "actor_subject_id": accounts[role]["subject_id"], "role": member_role,
        }, admin)
        assert added.status_code == 200, added.text
    service.accessible_text_offerings = frozenset({offering})
    native = "offline-sandbox" in request.node.name
    if native:
        work = tmp_path / "ocr-work"
        work.mkdir()
        runtime = ROOT / os.environ.get("LEARNING_OCR_RUNTIME_DIR", ".tooling/learning-ocr-native-20261105-01")
        service.accessible_text_pipeline = configure_learning_ocr({
            "executor": "wsl-bubblewrap", "runtime_root": str((runtime / "runtime").relative_to(ROOT)),
            "work_root": str(work.relative_to(ROOT)), "pins": json.loads((runtime / "pins.json").read_bytes()),
        }, workspace=ROOT, blob_root=service.blobs.root)
    else:
        service.accessible_text_pipeline = FixturePipeline()
    session = post(client, f"/offerings/{offering}/sessions", {"title": "OCR session"}, teacher).json()
    material = post(client, f"/offerings/{offering}/materials", {"title": "OCR PDF", "session_id": session["id"]}, teacher).json()
    upload = post(client, f'/materials/{material["id"]}/upload-intents', {"filename": "fixture.pdf", "byte_size": len(pdf)}, teacher).json()
    assert client.put(f'/v1/learning/upload-intents/{upload["id"]}/content', content=pdf, headers=teacher).status_code == 200
    vid = post(client, f'/upload-intents/{upload["id"]}/complete', {}, teacher).json()["id"]
    client.portal.call(service.tick)
    preview = post(client, f"/versions/{vid}/publication-preview", {"action": "publish"}, teacher).json()
    proof = {key: preview[key] for key in ("preview_id", "confirmation_token")}
    assert post(client, f"/versions/{vid}/publish", proof, teacher).status_code == 200
    for user, manage in ((teacher, True), (student, False)):
        capabilities = client.get(f"/v1/learning/versions/{vid}", headers=user).json()["capabilities"]
        assert capabilities["accessible_text"] is True
        assert capabilities["manage_accessible_text"] is manage
    pages = [1, 6] if native else [1, 2]
    jobs = f"/versions/{vid}/ocr-jobs"
    assert client.get("/v1/learning" + jobs, headers=student).status_code == 403
    dashboard = client.get("/v1/learning" + jobs, headers=teacher)
    assert dashboard.json()["daily_pages_remaining"] == 300
    job_headers = teacher | {"Idempotency-Key": str(uuid4())}
    started = client.post("/v1/learning" + jobs, json={"pages": pages}, headers=job_headers)
    assert started.status_code == 200, started.text
    job = started.json()
    assert job["state"] == "QUEUED"
    service.accessible_text_ocr_paused_offerings = frozenset({offering})
    blocked = post(client, jobs, {"pages": pages}, teacher)
    assert blocked.status_code == 503 and blocked.json()["code"] == "OCR_PROCESSING_PAUSED"
    assert post(client, jobs, {"pages": pages}, student).status_code == 403
    replay = client.post("/v1/learning" + jobs, json={"pages": pages}, headers=job_headers)
    assert replay.status_code == 200 and replay.json() == job
    client.portal.call(service.tick_accessible_text)
    assert client.get("/v1/learning" + jobs, headers=teacher).json()["jobs"] == [job]
    service.accessible_text_ocr_paused_offerings = frozenset()
    for _ in pages:
        client.portal.call(service.tick_accessible_text)
    service.accessible_text_ocr_paused_offerings = frozenset({offering})
    manifest = f"/v1/learning/versions/{vid}/accessible-text"
    assert client.get(manifest, headers=student).json()["state"] == "UNAVAILABLE"
    release_id = job["release_id"]
    staff_path = f"/v1/learning/ocr-releases/{release_id}"
    assert client.get(staff_path, params={"page_no": 1}, headers=student).status_code == 403
    staff = client.get(staff_path, params={"page_no": 1}, headers=teacher).json()
    candidate = staff["candidate"]
    assert candidate["source_sha256"] == hashlib.sha256(pdf).hexdigest()
    assert candidate["blocks"]

    def edit(payload):
        return client.patch(staff_path, json=payload, headers=teacher | {"Idempotency-Key": str(uuid4())})

    first, *other = candidate["blocks"]
    review = {"operation": "REVIEW_PAGE", "revision": staff["revision"], "page_no": 1, "candidate_sha256": candidate["sha256"],
              "review_confirmed": True, "blocks": [{"id": first["id"], "type": "HEADING", "text": "Đọc dấu tiếng Việt", "level": 2},
                                                 *({"id": block["id"], "type": "PLACEHOLDER"} for block in other)]}
    if not native:
        assert edit(review).json()["code"] == "OCR_CRITICAL_REVIEW_REQUIRED"
    review["blocks"][0]["risk_verified"] = True
    reviewed = edit(review)
    assert reviewed.status_code == 200, reviewed.text
    publish = {"operation": "PUBLISH", "revision": reviewed.json()["revision"], "pages": [1], "expected_current_release_id": None}
    not_reviewed = post(client, "/action-previews", {"action": "ocr-release-update", "target_id": release_id,
                                                     "payload": publish | {"pages": pages}}, teacher)
    assert not_reviewed.json()["code"] == "OCR_PAGE_REVIEW_REQUIRED"
    preview = post(client, "/action-previews", {"action": "ocr-release-update", "target_id": release_id, "payload": publish}, teacher)
    assert preview.status_code == 200, preview.text
    assert "_ocr_guard" not in preview.json()["payload"]
    released = edit(publish | {key: preview.json()[key] for key in ("preview_id", "confirmation_token")})
    assert released.status_code == 200, released.text
    assert client.get(manifest, headers=student).json()["release"]["available_pages"] == [1]
    shown = client.get(manifest + "/pages/1", headers=student)
    assert shown.json()["blocks"][0]["text"] == "Đọc dấu tiếng Việt"
    assert client.get(manifest + f"/pages/{pages[1]}", headers=student).status_code == 404
    hits = client.get(manifest + "/search", params={"q": "DẤU TIẾNG"}, headers=student).json()
    assert hits["hits"] == [{"page_no": 1, "block_id": first["id"]}]
    paused_range = client.get(f"/v1/learning/versions/{vid}/content", headers=student | {"Range": "bytes=0-31"})
    assert paused_range.status_code == 206 and paused_range.content == pdf[:32]
    for visibility in ("HIDDEN", "VISIBLE"):
        current = client.get(f'/v1/learning/materials/{material["id"]}', headers=teacher).json()
        payload = {"visibility": visibility, "revision": current["revision"]}
        proof = post(client, "/action-previews", {"action": "material-update", "target_id": material["id"], "payload": payload}, teacher).json()
        changed = client.patch(f'/v1/learning/materials/{material["id"]}', json=payload | {
            key: proof[key] for key in ("preview_id", "confirmation_token")
        }, headers=teacher)
        assert changed.status_code == 200, changed.text
        assert client.get(manifest + "/pages/1", headers=student).status_code == 404
    assert client.get(manifest, headers=student).json()["state"] == "UNAVAILABLE"
    service.accessible_text_offerings = frozenset()
    assert client.get(manifest, headers=student).status_code == 404
    original = client.get(f"/v1/learning/versions/{vid}/content", headers=student)
    assert original.status_code == 200 and original.content == pdf
