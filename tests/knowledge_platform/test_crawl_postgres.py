"""Crawler end to end on the real local PostgreSQL (fresh tenant): fake web, real worker, real automatic pipeline.

Every test crawls its own unique sub-domain of huce.edu.vn: a source URI is unique across the whole platform.
"""
import asyncio
import io
import os
from uuid import UUID, uuid4

import pytest
from starlette.datastructures import Headers, UploadFile

from campus247.application.knowledge.crawl.service import CrawlService
from campus247.application.knowledge.platform_models import IntakeMetadata, PlatformError
from campus247.infrastructure.knowledge.crawl_fetch import FetchedResource
from campus247.infrastructure.knowledge.crawl_store import CrawlStore
from campus247.ports.identity import IdentityRole

from .test_auto_publication_postgres import drain, person, run, setup
from .test_crawl_pure import ARTICLE, STUDENT_LIST, make_docx

pytestmark = pytest.mark.skipif(os.environ.get("KNOWLEDGE_PLATFORM_LIVE_TESTS") != "1", reason="Explicit task-owned PostgreSQL opt-in required")

LIST_PAGE = """<html><head><title>Thông báo</title></head><body><nav><a href="/">Trang chủ</a></nav><main><ul>
<li><a href="/thong-bao/hoc-phi">Thông báo nộp học phí</a></li><li><a href="/thong-bao/danh-sach">Danh sách sinh viên</a></li>
<li><a href="/files/quy-dinh.txt">Quy định (txt)</a></li><li><a href="/files/cu.doc">Mẫu cũ</a></li><li><a href="/private/noi-bo">Nội bộ</a></li>
<li><a href="/dang-nhap">Đăng nhập</a></li><li><a href="https://example.com/ngoai">Bên ngoài</a></li><li><a href="/thong-bao/da-xoa">Bài đã xóa</a></li></ul></main></body></html>"""
PII_PAGE = "<html><body><article><h1>Danh sách sinh viên được xét</h1>" + "".join(
    f"<p>{line}</p>" for line in STUDENT_LIST.splitlines()) + "<p>" + "Nội dung thông báo. " * 30 + "</p></article></body></html>"
TXT = "Quy định thử nghiệm về mượn phòng\n\nĐiều 1. Sinh viên mượn phòng sinh hoạt tối đa 3 giờ mỗi lần.\n".encode("utf-8")
DOCX_MEDIA = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class FakeWeb:
    def __init__(self, host, pages):
        self.host, self.pages, self.requests = host, pages, []

    def url(self, path):
        return f"https://{self.host}{path}"

    async def get(self, url, *, max_bytes=0, validators=None, accept="*/*"):
        self.requests.append(url)
        item = self.pages.get(url)
        if item is None:
            return FetchedResource(404, url)
        media, body = item
        return FetchedResource(200, url, media, body, {})


def site(article=ARTICLE):
    """(fake web, source definition) for a unique host."""
    host = f"t{uuid4().hex[:10]}.huce.edu.vn"
    fake = FakeWeb(host, {})
    fake.pages = {
        fake.url("/robots.txt"): ("text/plain", b"User-agent: *\nDisallow: /private/\n"),
        fake.url("/thong-bao"): ("text/html", LIST_PAGE.encode("utf-8")),
        fake.url("/thong-bao/hoc-phi"): ("text/html", article.encode("utf-8")),
        fake.url("/thong-bao/danh-sach"): ("text/html", PII_PAGE.encode("utf-8")),
        fake.url("/files/quy-dinh.txt"): ("text/plain", TXT),
        fake.url("/files/mau-don.docx"): (DOCX_MEDIA, make_docx(
            '<w:p><w:r><w:t>Mẫu đơn xin hoãn nộp học phí. Họ tên sinh viên, lớp, lý do hoãn nộp và cam kết thời hạn nộp bổ sung.</w:t></w:r></w:p>')),
    }
    source = {"name": "Thông báo thử nghiệm", "seed_urls": [fake.url("/thong-bao")], "kind": "LIST", "owner_unit": "Phòng thử nghiệm",
              # /private/ is allowed by pattern: only robots.txt keeps it out
              "include": [r"^/thong-bao", r"^/files/", r"^/private/"], "max_depth": 2, "max_pages": 50}
    return fake, source


def decisions(run_report, host):
    return {d["url"].replace(f"https://{host}", ""): d for d in run_report["decisions"]}


def test_crawl_dry_run_then_ingest_then_change_detection(retained_directory):
    async def scenario(pool, repo, platform, auto, worker, runtime, builder, tenant):
        admin = person(tenant, "admin", IdentityRole.KNOWLEDGE_ADMIN)
        waits = []

        async def sleep(seconds):
            waits.append(seconds)
        fake, source = site()
        crawler = CrawlService(platform, auto, CrawlStore(repo), fake, delay_seconds=3.0, sleep=sleep)
        source_id = UUID((await crawler.create_source(admin, source))["id"])

        # --- 1. a new source only does a dry run: it reports, and creates nothing
        await crawler.run_source(source_id)
        runs = (await crawler.runs(admin, source_id))["items"]
        assert runs[0]["dry_run"] is True and runs[0]["state"] == "DONE"
        found = decisions(runs[0], fake.host)
        assert found["/thong-bao/hoc-phi"]["decision"] == "WOULD_CREATE" and found["/files/quy-dinh.txt"]["decision"] == "WOULD_CREATE"
        assert found["/files/mau-don.docx"]["decision"] == "WOULD_CREATE"          # attachment found on the article
        assert found["/thong-bao/danh-sach"]["decision"] == "BLOCKED_PII"          # a student list never enters
        assert found["/thong-bao"]["decision"] == "SKIPPED"                       # the list page itself is not a document
        assert found["/files/cu.doc"]["decision"] == "UNSUPPORTED" and found["/private/noi-bo"]["decision"] == "BLOCKED_ROBOTS"
        assert found["/dang-nhap"]["decision"] == "SKIPPED" and found["/thong-bao/da-xoa"]["decision"] == "MISSING"
        assert not any("example.com" in url for url in fake.requests) and fake.url("/private/noi-bo") not in fake.requests
        assert (await auto.listing(admin))["items"] == []
        assert waits and all(w >= 2.5 for w in waits)                             # polite: about 3 s between requests to one host

        # --- 2. switching ingestion on makes the same crawl create documents in the normal pipeline (pending approval)
        await crawler.update_source(admin, source_id, {"ingest_enabled": True})
        await crawler.run_source(source_id)
        await drain(worker, auto)
        items = (await auto.listing(admin))["items"]
        assert len(items) == 3 and all(i["origin"] == "CRAWL" and i["mode"] == "REVIEW" for i in items), items
        assert all(i["state"] == "AWAITING_REVIEW" for i in items)
        article = next(i for i in items if "học phí" in i["title"].lower())
        assert article["canonical_uri"] == fake.url("/thong-bao/hoc-phi") and "EFFECTIVE_FROM_ASSUMED" not in article["flags"]  # the page carried a date
        async with pool.acquire() as conn:
            text = await conn.fetchval("SELECT string_agg(c.content_text, ' ') FROM knowledge_chunk c WHERE c.document_version_id=$1", article["version_id"])
        assert "420.000" in text and "Trang chủ" not in text and "© Trường" not in text
        crawler_actor = await crawler.crawler_actor()                              # a crawler can never approve or publish by itself
        with pytest.raises(PlatformError):
            await auto.approve(crawler_actor, article["version_id"], None)

        # --- 3. nothing changed: nothing new
        before = len((await auto.listing(admin))["items"])
        await crawler.run_source(source_id)
        again = decisions((await crawler.runs(admin, source_id))["items"][0], fake.host)
        assert again["/thong-bao/hoc-phi"]["decision"] == "UNCHANGED" and again["/files/quy-dinh.txt"]["decision"] == "UNCHANGED"
        assert len((await auto.listing(admin))["items"]) == before

        # --- 4. the article changes: a new version of the same source, again waiting for approval
        fake.pages[fake.url("/thong-bao/hoc-phi")] = ("text/html", ARTICLE.replace("420.000", "450.000").encode("utf-8"))
        await crawler.run_source(source_id)
        await drain(worker, auto)
        assert decisions((await crawler.runs(admin, source_id))["items"][0], fake.host)["/thong-bao/hoc-phi"]["decision"] == "UPDATED"
        versions = [i for i in (await auto.listing(admin))["items"] if i["canonical_uri"] == fake.url("/thong-bao/hoc-phi")]
        assert len(versions) == 2 and len({v["source_id"] for v in versions}) == 1 and {v["state"] for v in versions} == {"AWAITING_REVIEW"}

        # --- 5. a page that disappears is reported, never silently removed
        del fake.pages[fake.url("/files/quy-dinh.txt")]
        await crawler.run_source(source_id)
        gone = decisions((await crawler.runs(admin, source_id))["items"][0], fake.host)
        assert gone["/files/quy-dinh.txt"]["decision"] == "MISSING"
        assert any("quy" in (i["title"] or "").lower() for i in (await auto.listing(admin))["items"])
    run(scenario, retained_directory)


def test_a_page_already_in_the_knowledge_base_is_reported_not_overwritten_or_duplicated(retained_directory):
    async def scenario(pool, repo, platform, auto, worker, runtime, builder, tenant):
        admin = person(tenant, "admin", IdentityRole.KNOWLEDGE_ADMIN)
        fake, source = site()
        existing_uri = fake.url("/thong-bao/hoc-phi")
        manual = IntakeMetadata(title="Học phí (nhập tay)", owner_unit="Phòng thử nghiệm", canonical_uri=existing_uri, programs=["PUBLIC"], audiences=["STUDENT"])
        await platform.upload(admin, manual, UploadFile(io.BytesIO("Học phí do quản trị nhập tay.\n".encode()), filename="hp.txt",
                                                        headers=Headers({"content-type": "text/plain"})), "manual-1")
        crawler = CrawlService(platform, auto, CrawlStore(repo), fake, sleep=lambda s: asyncio.sleep(0))
        source_id = UUID((await crawler.create_source(admin, source))["id"])
        await crawler.update_source(admin, source_id, {"ingest_enabled": True})
        await crawler.run_source(source_id)
        report = decisions((await crawler.runs(admin, source_id))["items"][0], fake.host)
        assert report["/thong-bao/hoc-phi"]["decision"] == "EXISTS" and "Học phí (nhập tay)" in report["/thong-bao/hoc-phi"]["reason"]
        assert report["/files/quy-dinh.txt"]["decision"] == "CREATED"             # the other pages are still ingested
        async with pool.acquire() as conn:
            assert await conn.fetchval("SELECT count(*) FROM knowledge_source WHERE canonical_uri=$1", existing_uri) == 1
    run(scenario, retained_directory)


def test_source_validation_and_roles(retained_directory):
    async def scenario(pool, repo, platform, auto, worker, runtime, builder, tenant):
        admin = person(tenant, "admin", IdentityRole.KNOWLEDGE_ADMIN)
        contributor = person(tenant, "contributor", IdentityRole.KNOWLEDGE_CONTRIBUTOR)
        fake, source = site()
        crawler = CrawlService(platform, auto, CrawlStore(repo), fake, sleep=lambda s: asyncio.sleep(0))
        for bad in ({**source, "seed_urls": ["https://example.com/x"]}, {**source, "seed_urls": ["http://huce.edu.vn/x"]},
                    {**source, "seed_urls": []}, {**source, "include": ["("]}, {**source, "mode": "AUTO"}):
            with pytest.raises(PlatformError) as error:
                await crawler.create_source(admin, bad)
            assert error.value.status == 422
        with pytest.raises(PlatformError) as denied:
            await crawler.create_source(contributor, source)
        assert denied.value.status == 403
        created = await crawler.create_source(admin, source)
        assert created["ingest_enabled"] is False  # a new source never ingests before its dry run was looked at
        listed = (await crawler.list_sources(admin))["items"]
        assert listed[0]["ingest_enabled"] is False and listed[0]["mode"] == "REVIEW"
    run(scenario, retained_directory)
