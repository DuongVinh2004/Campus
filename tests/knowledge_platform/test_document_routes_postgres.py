"""HTTP layer of the document pipeline: roles, multipart, idempotency, approval. Live-DB opt-in like its sibling."""
import asyncio
import json
import os
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI, Request
from starlette.responses import JSONResponse

from campus247.application.knowledge.platform_models import PlatformError
from campus247.infrastructure.knowledge.multipart import parse_upload
from campus247.ports.identity import IdentityRole
from campus247.presentation.knowledge_platform import create_knowledge_platform_router

from .test_auto_publication_postgres import TEXT_A, TEXT_B, drain, person, setup

pytestmark = pytest.mark.skipif(os.environ.get("KNOWLEDGE_PLATFORM_LIVE_TESTS") != "1", reason="Explicit task-owned PostgreSQL opt-in required")


def build_app(platform, runtime, service, people, crawl=None):
    app = FastAPI()

    @app.exception_handler(PlatformError)
    async def handler(request, error):
        return JSONResponse({"code": error.code, "detail": error.detail}, status_code=error.status)

    @app.middleware("http")
    async def identify(request: Request, call_next):
        who = request.headers.get("x-test-actor")
        if who in people:
            request.state.identity = people[who]
        return await call_next(request)

    app.include_router(create_knowledge_platform_router(platform, runtime, lambda actor: None, upload_parser=parse_upload, auto_publication=service,
                                                crawl_service=crawl))
    return app


def form(title, text, **fields):
    meta = {"title": title, "owner_unit": "Đơn vị thử nghiệm", "canonical_uri": "urn:route:" + uuid4().hex,
            "programs": ["PUBLIC"], "audiences": ["STUDENT"], **fields}
    return {"file": ("tai-lieu.txt", text.encode("utf-8"), "text/plain"), "metadata": (None, json.dumps(meta, ensure_ascii=False))}


def test_routes_enforce_roles_and_drive_the_pipeline(retained_directory):
    async def main():
        pool, repo, platform, service, worker, runtime, builder, tenant = await setup(retained_directory)
        people = {"contributor": person(tenant, "contributor", IdentityRole.KNOWLEDGE_CONTRIBUTOR),
                  "admin": person(tenant, "admin", IdentityRole.KNOWLEDGE_ADMIN),
                  "student": person(tenant, "student", IdentityRole.STUDENT)}
        app = build_app(platform, runtime, service, people)
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                def post(path, who, key=None, **kwargs):
                    headers = {"x-test-actor": who, "Idempotency-Key": key or uuid4().hex} if who else {"Idempotency-Key": uuid4().hex}
                    return client.post(path, headers=headers, **kwargs)
                assert (await post("/v1/knowledge/platform/documents", None, files=form("Không đăng nhập", TEXT_A))).status_code == 401
                assert (await post("/v1/knowledge/platform/documents", "student", files=form("Sinh viên", TEXT_A))).status_code == 403
                direct = await post("/v1/knowledge/platform/documents", "contributor",
                                    files=form("Đóng góp đăng thẳng", TEXT_A, publish_directly=True, attested=True))
                assert direct.status_code == 403 and direct.json()["code"] == "DIRECT_PUBLISH_FORBIDDEN"
                key = "same-key-" + uuid4().hex
                created = await post("/v1/knowledge/platform/documents", "contributor", key=key, files=form("Quy định Lab Alpha", TEXT_A))
                assert created.status_code == 202 and created.json()["mode"] == "REVIEW", created.text
                version_id = created.json()["version_id"]
                bad = await post("/v1/knowledge/platform/documents", "admin", files=form("Thiếu xác nhận", TEXT_B, publish_directly=True))
                assert bad.status_code == 422 and bad.json()["code"] == "ATTESTATION_REQUIRED"
                invalid = await post("/v1/knowledge/platform/documents", "admin", files=form("Sai URI", TEXT_B, canonical_uri="ftp://x"))
                assert invalid.status_code == 422
                await drain(worker, service)
                mine = (await client.get("/v1/knowledge/platform/documents", headers={"x-test-actor": "contributor"})).json()
                assert [i["state"] for i in mine["items"]] == ["AWAITING_REVIEW"] and mine["can_publish_directly"] is False
                assert (await client.get("/v1/knowledge/platform/documents", headers={"x-test-actor": "student"})).status_code == 403
                assert (await post(f"/v1/knowledge/platform/documents/{version_id}/approve", "contributor", json={})).status_code == 403
                approved = await post(f"/v1/knowledge/platform/documents/{version_id}/approve", "admin", json={"note": "Đã đối chiếu với bản gốc."})
                assert approved.status_code == 200, approved.text
                await drain(worker, service)
                done = (await client.get("/v1/knowledge/platform/documents", headers={"x-test-actor": "admin"})).json()
                assert [i["state"] for i in done["items"]] == ["ACTIVE"] and done["can_publish_directly"] is True
                # rejection path with a reason
                second = await post("/v1/knowledge/platform/documents", "contributor", files=form("Bị từ chối", TEXT_B))
                await drain(worker, service)
                no_reason = await post(f"/v1/knowledge/platform/documents/{second.json()['version_id']}/reject", "admin", json={"note": "x"})
                assert no_reason.status_code == 422
                rejected = await post(f"/v1/knowledge/platform/documents/{second.json()['version_id']}/reject", "admin", json={"note": "Nội dung không phải văn bản chính thức."})
                assert rejected.status_code == 200 and rejected.json()["pipeline_state"] == "REJECTED"
        finally:
            await pool.close()
    asyncio.run(main())


def test_crawl_source_routes_are_administrator_only_and_start_in_dry_run(retained_directory):
    from campus247.application.knowledge.crawl.service import CrawlService
    from campus247.infrastructure.knowledge.crawl_store import CrawlStore
    from .test_crawl_postgres import site

    async def main():
        pool, repo, platform, service, worker, runtime, builder, tenant = await setup(retained_directory)
        people = {"contributor": person(tenant, "contributor", IdentityRole.KNOWLEDGE_CONTRIBUTOR),
                  "admin": person(tenant, "admin", IdentityRole.KNOWLEDGE_ADMIN)}
        fake, SOURCE = site()
        crawl = CrawlService(platform, service, CrawlStore(repo), fake, sleep=lambda s: asyncio.sleep(0))
        app = build_app(platform, runtime, service, people, crawl)
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                async def call(method, path, who, **kwargs):
                    return await client.request(method, path, headers={"x-test-actor": who, "Idempotency-Key": uuid4().hex}, **kwargs)
                assert (await call("POST", "/v1/knowledge/platform/crawl-sources", "contributor", json=SOURCE)).status_code == 403
                assert (await call("GET", "/v1/knowledge/platform/crawl-sources", "contributor")).status_code == 403
                bad = await call("POST", "/v1/knowledge/platform/crawl-sources", "admin", json={**SOURCE, "seed_urls": ["https://example.com/"]})
                assert bad.status_code == 422 and bad.json()["code"] == "CRAWL_SEED_INVALID"
                assert (await call("POST", "/v1/knowledge/platform/crawl-sources", "admin", json={**SOURCE, "max_depth": 9})).status_code == 422
                created = await call("POST", "/v1/knowledge/platform/crawl-sources", "admin", json=SOURCE)
                assert created.status_code == 201 and created.json()["ingest_enabled"] is False
                source_id = created.json()["id"]
                queued = await call("POST", f"/v1/knowledge/platform/crawl-sources/{source_id}/run", "admin", json={"dry_run": True})
                assert queued.status_code == 202 and queued.json()["dry_run"] is True
                await crawl.run_source(__import__("uuid").UUID(source_id))
                runs = (await call("GET", f"/v1/knowledge/platform/crawl-sources/{source_id}/runs", "admin")).json()["items"]
                assert runs[0]["dry_run"] is True and runs[0]["counts"].get("WOULD_CREATE")
                switched = await call("POST", f"/v1/knowledge/platform/crawl-sources/{source_id}/settings", "admin", json={"ingest_enabled": True, "interval_hours": 12})
                assert switched.status_code == 200
                listed = (await call("GET", "/v1/knowledge/platform/crawl-sources", "admin")).json()["items"][0]
                assert listed["ingest_enabled"] is True and listed["interval_hours"] == 12 and listed["last_run"]["state"] == "DONE"
        finally:
            await pool.close()
    asyncio.run(main())
