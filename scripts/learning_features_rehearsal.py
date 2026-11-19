"""Seed and serve an isolated synthetic learning bundle with every optional feature on.

Used by apps/web/e2e/learning-features.mjs. Nothing here touches the Campus 8015 runtime or real data:

    python scripts/learning_features_rehearsal.py seed  --name learning-features-20261117-01 --pdf a.pdf --pdf b.pdf
    python scripts/learning_features_rehearsal.py serve --name learning-features-20261117-01 --port 8025 --frontend-port 3025

`seed` creates a new bundle under .tooling (it refuses to reuse a directory), one class with a lecturer, two
students, one session and one published three-page lecture, then enables the five per-class features.
`serve` runs the loopback test host and a deterministic stand-in for the OCR pipeline (the pinned native OCR
runtime is not required for UI checks).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services/api/src"), str(ROOT / "services/worker/src"), str(ROOT / "scripts")]

FLAGS = ("page_feedback_offerings", "version_change_offerings", "exit_ticket_offerings",
         "idea_card_offerings", "accessible_text_offerings")


def bundle(name: str) -> Path:
    if not name.startswith("learning-features-") or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in name):
        raise ValueError("Use a name such as learning-features-20261117-01")
    return ROOT / ".tooling" / name


def seed(args):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from campus247.application.identity.session_service import SessionService
    from campus247.bootstrap.learning import load_local_learning
    from campus247.presentation.identity import IdentityMiddleware
    from campus247.presentation.learning import create_learning_router
    from learning_local_setup import setup

    scope = bundle(args.name)
    pdfs = [Path(p).resolve(strict=True) for p in args.pdf]
    first = pdfs[0]
    setup(scope, "huce-local-public", first, second_student=True)
    config_path = scope / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["synthetic_fixture_sha256"] += [hashlib.sha256(p.read_bytes()).hexdigest() for p in pdfs[1:]]
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    service, adapter = load_local_learning(config_path, workspace=ROOT, tenant_id="huce-local-public")
    accounts = json.loads((scope / "credentials.json").read_text())["accounts"]
    by_role = {a["role"]: a for a in accounts}
    by_role["STUDENT"], by_role["STUDENT_2"] = [a for a in accounts if a["role"] == "STUDENT"]
    headers = {r: {"Authorization": "Bearer " + adapter.authenticate(a["username"], a["password"])} for r, a in by_role.items()}
    app = FastAPI()
    app.add_middleware(IdentityMiddleware, adapter=adapter, session_service=SessionService())
    app.include_router(create_learning_router(service))
    from uuid import uuid4

    def call(client, method, path, who, **kw):
        extra = {"Idempotency-Key": str(uuid4())} if method in {"POST", "PUT", "PATCH"} else {}
        return client.request(method, "/v1/learning" + path, headers=headers[who] | extra, **kw)

    def confirmed(client, action, target, payload):
        preview = call(client, "POST", "/action-previews", "SYSTEM_ADMIN", json={"action": action, "target_id": target, "payload": payload})
        assert preview.status_code == 200, preview.text
        return payload | {k: preview.json()[k] for k in ("preview_id", "confirmation_token")}

    with TestClient(app) as client:
        term = call(client, "POST", "/terms", "SYSTEM_ADMIN", json=confirmed(client, "term-create", None, {"name": "Học kỳ thử", "start_date": "2026-11-01", "end_date": "2027-02-01"})).json()
        course = call(client, "POST", "/courses", "SYSTEM_ADMIN", json=confirmed(client, "course-create", None, {"code": "FEAT", "name": "Kiểm thử tính năng"})).json()
        offering = call(client, "POST", "/offerings", "SYSTEM_ADMIN", json=confirmed(client, "offering-create", None, {"course_id": course["id"], "term_id": term["id"], "section_code": "A"})).json()["id"]
        for role, member in (("LECTURER", "INSTRUCTOR"), ("STUDENT", "STUDENT"), ("STUDENT_2", "STUDENT")):
            payload = {"actor_subject_id": by_role[role]["subject_id"], "role": member}
            added = call(client, "POST", f"/offerings/{offering}/members", "SYSTEM_ADMIN", json=confirmed(client, "member-create", offering, payload))
            assert added.status_code == 200, added.text
        session = call(client, "POST", f"/offerings/{offering}/sessions", "LECTURER", json={"title": "Buổi 1"}).json()["id"]
        material = call(client, "POST", f"/offerings/{offering}/materials", "LECTURER", json={"title": "Bài giảng kiểm thử tính năng", "session_id": session}).json()["id"]
        data = first.read_bytes()
        intent = call(client, "POST", f"/materials/{material}/upload-intents", "LECTURER", json={"filename": "bai-giang.pdf", "byte_size": len(data), "content_type": "application/pdf"}).json()
        sent = client.put(f"/v1/learning/upload-intents/{intent['id']}/content", content=data, headers=headers["LECTURER"] | {"Content-Type": "application/pdf"})
        assert sent.status_code == 200, sent.text
        version = call(client, "POST", f"/upload-intents/{intent['id']}/complete", "LECTURER", json={}).json()["id"]
        client.portal.call(service.tick)
        preview = call(client, "POST", f"/versions/{version}/publication-preview", "LECTURER", json={"action": "publish"}).json()
        published = call(client, "POST", f"/versions/{version}/publish", "LECTURER", json={k: preview[k] for k in ("preview_id", "confirmation_token")})
        assert published.status_code == 200, published.text
    for flag in FLAGS:
        config[flag] = [offering]
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(json.dumps({"bundle": str(scope), "offering": offering, "credentials": str(scope / "credentials.json")}))


class StandInOcr:
    """Deterministic page candidates; the real offline OCR sandbox is exercised elsewhere."""
    profile_sha256 = "2" * 64

    async def process_page(self, source, page_no):
        candidate = {"schema": "learning-accessible-text-v1", "status": "NEEDS_REVIEW", "version_id": source.version_id,
                     "rendition_id": source.rendition_id, "page_no": page_no, "source_sha256": source.sha256,
                     "profile_sha256": self.profile_sha256,
                     "blocks": [{"id": "b1", "type": "PARAGRAPH", "text": f"Bản nháp OCR trang {page_no}", "order": 0,
                                 "anchor": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.1}, "confidence": 88,
                                 "needs_review": True, "provenance": "OCR", "review_reasons": ["POSSIBLE_FORMULA"]}]}
        encoded = json.dumps(candidate, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        return SimpleNamespace(payload=candidate, sha256=hashlib.sha256(encoded).hexdigest(), retained_bytes=0)


def serve(args):
    import uvicorn

    import learning_test_host as host

    original = host.load_local_learning

    def with_stand_in(*a, **kw):
        service, adapter = original(*a, **kw)
        if args.ocr_runtime:
            # Real offline OCR: pinned Tesseract/Poppler bundle inside the WSL bubblewrap sandbox.
            from campus247.bootstrap.learning import configure_learning_ocr

            runtime = Path(args.ocr_runtime)
            pins = json.loads((ROOT / runtime / "pins.json").read_bytes())
            work = bundle(args.name) / "ocr-work"
            work.mkdir(exist_ok=True)
            service.accessible_text_pipeline = configure_learning_ocr({
                "executor": "wsl-bubblewrap", "runtime_root": str(runtime / "runtime"),
                "work_root": str(work.relative_to(ROOT)), "pins": pins,
            }, workspace=ROOT, blob_root=service.blobs.root)
        else:
            service.accessible_text_pipeline = StandInOcr()
        return service, adapter

    host.load_local_learning = with_stand_in
    uvicorn.run(host.create_test_app(bundle(args.name) / "config.json", args.frontend_port),
                host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("seed")
    one.add_argument("--name", required=True)
    one.add_argument("--pdf", action="append", required=True, help="first PDF is published; the others are only allow-listed")
    one.set_defaults(run=seed)
    two = sub.add_parser("serve")
    two.add_argument("--name", required=True)
    two.add_argument("--port", type=int, default=8025)
    two.add_argument("--frontend-port", type=int, default=3025)
    two.add_argument("--ocr-runtime", help="workspace-relative pinned OCR bundle (contains runtime/ and pins.json); default is the stand-in")
    two.set_defaults(run=serve)
    parsed = parser.parse_args()
    parsed.run(parsed)
