"""Crawler: from public school pages to documents in the automatic pipeline.

A source is only ever read-only (a dry run: fetch, extract, decide, report) until an administrator has looked at the report
and switched ingestion on. Ingested documents enter the same pipeline as uploads, as the service identity `crawler`
(a contributor), so by default they wait for one person to approve them.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import re
import time
import unicodedata
from collections import Counter, deque
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from starlette.datastructures import Headers, UploadFile

from campus247.application.knowledge.crawl.docx_text import DocxError, docx_to_text
from campus247.application.knowledge.crawl.html_text import extract_page
from campus247.application.knowledge.crawl.pii import scan_personal_data
from campus247.application.knowledge.crawl.rules import RobotsPolicy, classify, normalize_url, parse_sitemap, wanted
from campus247.application.knowledge.platform_models import IntakeMetadata, PlatformError
from campus247.domain.shared.values import generate_uuid7
from campus247.ports.identity import IdentityContext, IdentityRole

LOGGER = logging.getLogger("campus247.crawl")
MIN_ARTICLE_CHARS = 300
MAX_LINK_DENSITY = 0.5
MAX_DECISIONS = 400
HTML_MEDIA = {"text/html", "application/xhtml+xml"}
DOCX_MEDIA = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def safe_filename(url: str, extension: str) -> str:
    base = urlsplit(url).path.rsplit("/", 1)[-1].rsplit(".", 1)[0] or urlsplit(url).hostname or "tai-lieu"
    folded = "".join(c for c in unicodedata.normalize("NFD", base) if unicodedata.category(c) != "Mn").replace("đ", "d").replace("Đ", "D")
    return (re.sub(r"[^A-Za-z0-9._-]+", "-", folded).strip("-.")[:100] or "tai-lieu") + extension


class CrawlService:
    def __init__(self, platform, auto, store, fetcher, *, delay_seconds=3.0, sleep=asyncio.sleep, run_budget_seconds=1800):
        self.platform, self.auto, self.store, self.fetcher, self.repo = platform, auto, store, fetcher, platform.repo
        self.delay, self.sleep, self.budget = delay_seconds, sleep, run_budget_seconds
        self._task = None
        self._last_request = {}

    # ------------------------------------------------------------------ administration (API)
    async def create_source(self, actor, body: dict):
        self.platform.admin(actor)
        await self.store.ensure()
        seeds = [normalize_url(url) for url in body.get("seed_urls", [])]
        if not seeds or any(s is None for s in seeds) or len(seeds) > 20:
            raise PlatformError(422, "CRAWL_SEED_INVALID", "Cần 1–20 địa chỉ gốc https:// thuộc huce.edu.vn.")
        if body.get("mode", "REVIEW") not in {"REVIEW", "DIRECT"}:
            raise PlatformError(422, "CRAWL_MODE_INVALID", "Chế độ phát hành không hợp lệ.")
        for pattern in [*body.get("include", []), *body.get("exclude", [])]:
            try:
                re.compile(pattern)
            except re.error:
                raise PlatformError(422, "CRAWL_PATTERN_INVALID", "Mẫu URL không hợp lệ: " + pattern[:60]) from None
        async with self.repo.transaction() as conn:
            identifier = await self.store.create_source(conn, name=body["name"], seed_urls=seeds, kind=body.get("kind", "LIST"),
                include=body.get("include", []), exclude=body.get("exclude", []), max_depth=body.get("max_depth", 2),
                max_pages=body.get("max_pages", 200), interval_hours=body.get("interval_hours", 24), owner_unit=body["owner_unit"],
                programs=body.get("programs", ["PUBLIC"]), audiences=body.get("audiences", ["STUDENT", "KNOWLEDGE_ADMIN", "SYSTEM_ADMIN"]),
                mode=body.get("mode", "REVIEW"), configured_by=actor.subject_id)
            await self.repo.audit(conn, actor.subject_id, "knowledge.crawl.source.created", str(identifier), {"seeds": seeds, "mode": body.get("mode", "REVIEW")})
        return {"id": str(identifier), "ingest_enabled": False, "note": "Nguồn mới chỉ chạy thử (không nạp gì) cho đến khi bạn xem báo cáo và bật nạp."}

    async def list_sources(self, actor):
        self.platform.admin(actor)
        await self.store.ensure()
        async with self.repo.pool.acquire() as conn:
            sources = await self.store.sources(conn)
            out = []
            for source in sources:
                runs = await self.store.runs(conn, source["id"], limit=1)
                out.append({**_public_source(source), "last_run": _public_run(runs[0]) if runs else None})
        return {"items": out}

    async def update_source(self, actor, identifier, patch: dict):
        self.platform.admin(actor)
        await self.store.ensure()
        if "mode" in patch and patch["mode"] not in {"REVIEW", "DIRECT"}:
            raise PlatformError(422, "CRAWL_MODE_INVALID", "Chế độ phát hành không hợp lệ.")
        async with self.repo.transaction() as conn:
            if not await self.store.source(conn, identifier):
                raise PlatformError(404, "CRAWL_SOURCE_NOT_FOUND", "Không tìm thấy nguồn tự động.")
            await self.store.update_source(conn, identifier, **{k: v for k, v in patch.items()
                                           if k in {"active", "ingest_enabled", "mode", "interval_hours", "max_pages", "max_depth", "name"}})
            await self.repo.audit(conn, actor.subject_id, "knowledge.crawl.source.updated", str(identifier), patch)
        return {"id": str(identifier), **patch}

    async def request_run(self, actor, identifier, *, dry_run: bool):
        self.platform.admin(actor)
        await self.store.ensure()
        async with self.repo.transaction() as conn:
            if not await self.store.source(conn, identifier):
                raise PlatformError(404, "CRAWL_SOURCE_NOT_FOUND", "Không tìm thấy nguồn tự động.")
            await self.store.update_source(conn, identifier, next_run_at=datetime.now(UTC), active=True, pending_run="DRY" if dry_run else "RUN")
            await self.repo.audit(conn, actor.subject_id, "knowledge.crawl.run.requested", str(identifier), {"dry_run": dry_run})
        return {"id": str(identifier), "queued": True, "dry_run": dry_run}

    async def runs(self, actor, identifier):
        self.platform.admin(actor)
        await self.store.ensure()
        async with self.repo.pool.acquire() as conn:
            return {"items": [_public_run(r, detail=True) for r in await self.store.runs(conn, identifier)]}

    # ------------------------------------------------------------------ worker
    async def tick(self):
        await self.store.ensure()
        if self._task is not None and not self._task.done():
            return {"running": True}
        if self._task is not None:
            self._task.exception()  # logged inside; never raised here
            self._task = None
        async with self.repo.pool.acquire() as conn:
            due = await self.store.due(conn)
        if not due:
            return {"due": 0}
        self._task = asyncio.create_task(self.run_source(due[0]["id"]), name="crawl-run")
        return {"started": str(due[0]["id"])}

    async def crawler_actor(self) -> IdentityContext:
        async with self.repo.pool.acquire() as conn:
            subject = await self.auto.store.service_identity(conn, "crawler")
        now = datetime.now(UTC)
        return IdentityContext(subject, "system:crawler", "internal:crawler", (IdentityRole.KNOWLEDGE_CONTRIBUTOR,), "crawler", now,
                               now + timedelta(minutes=30), tenant_id=self.repo.tenant, session_id=generate_uuid7(), is_synthetic=False)

    async def run_source(self, identifier, *, trigger="schedule"):
        async with self.repo.pool.acquire() as lock:
            if not await lock.fetchval("SELECT pg_try_advisory_lock(hashtextextended($1,0))", f"{self.repo.tenant}:crawl:{identifier}"):
                return None
            try:
                async with self.repo.pool.acquire() as conn:
                    source = await self.store.source(conn, identifier)
                    await self.store.stale_running(conn, identifier)
                if not source:
                    return None
                dry = not source["ingest_enabled"] or source["pending_run"] == "DRY"
                async with self.repo.pool.acquire() as conn:
                    run_id = await self.store.start_run(conn, identifier, trigger=trigger, dry_run=dry)
                counts, decisions, error = Counter(), [], None
                try:
                    await asyncio.wait_for(self._crawl(source, dry, counts, decisions), self.budget)
                except TimeoutError:
                    error = "RUN_BUDGET_EXCEEDED"
                except Exception as exc:  # noqa: BLE001 -- reported in the run; the next scheduled run retries
                    LOGGER.warning("crawl_run_failed kind=%s", type(exc).__name__)
                    error = type(exc).__name__
                async with self.repo.pool.acquire() as conn:
                    await self.store.finish_run(conn, run_id, "FAILED" if error else "DONE", dict(counts), decisions[:MAX_DECISIONS], error)
                    await self.store.update_source(conn, identifier, last_run_at=datetime.now(UTC), pending_run=None,
                        next_run_at=datetime.now(UTC) + timedelta(hours=source["interval_hours"]),
                        last_status=("FAILED:" + error) if error else ("DRY_RUN" if dry else "OK"))
                return run_id
            finally:
                await lock.execute("SELECT pg_advisory_unlock(hashtextextended($1,0))", f"{self.repo.tenant}:crawl:{identifier}")

    # ------------------------------------------------------------------ the crawl itself
    async def _robots(self, cache, host):
        if host in cache:
            return cache[host]
        try:
            await self._pace(host, RobotsPolicy.absent())
            resource = await self.fetcher.get(f"https://{host}/robots.txt", max_bytes=512 * 1024, accept="text/plain")
            if resource.status == 200:
                policy = RobotsPolicy(resource.body.decode("utf-8", "replace"))
            elif resource.status in {404, 410}:
                policy = RobotsPolicy.absent()
            else:
                policy = RobotsPolicy.unreadable()
        except PlatformError:
            policy = RobotsPolicy.unreadable()
        cache[host] = policy
        return policy

    async def _pace(self, host, policy):
        gap = policy.delay(self.delay)
        wait = self._last_request.get(host, 0) + gap - time.monotonic()
        if wait > 0:
            await self.sleep(wait)
        self._last_request[host] = time.monotonic()

    async def _crawl(self, source, dry, counts, decisions):
        robots, seen, queue = {}, set(), deque()
        for seed in source["seed_urls"]:
            queue.append((seed, 0, "seed"))
        if source["kind"] == "SITEMAP":
            for seed in list(queue):
                policy = await self._robots(robots, urlsplit(seed[0]).hostname)
                for sitemap in [seed[0], *policy.sitemaps()]:
                    await self._expand_sitemap(sitemap, queue, robots, 0)
        fetched, consecutive_errors = 0, 0
        def decided(url, kind, decision, reason="", **extra):
            counts.update([decision])
            decisions.append({"url": url, "kind": kind, "decision": decision, "reason": reason, **extra})
        while queue and fetched < source["max_pages"]:
            url, depth, origin = queue.popleft()
            if url in seen:
                continue
            seen.add(url)
            kind = classify(url)
            if kind == "skip":
                decided(url, kind, "SKIPPED", "loại địa chỉ bỏ qua (ảnh, đăng nhập, tìm kiếm…)")
                continue
            if origin != "seed" and not wanted(url, source["include"], source["exclude"]):
                decided(url, kind, "SKIPPED", "ngoài mẫu địa chỉ được phép")
                continue
            host = urlsplit(url).hostname
            policy = await self._robots(robots, host)
            if not policy.can_fetch(url) and not (policy.mode == "seeds_only" and origin == "seed"):
                decided(url, kind, "BLOCKED_ROBOTS", "robots.txt không cho phép" if policy.mode == "rules" else "không đọc được robots.txt: chỉ lấy địa chỉ gốc")
                continue
            if kind == "unsupported_document":
                decided(url, kind, "UNSUPPORTED", "định dạng chưa đọc được tự động (.doc, .xls, .ppt…)")
                continue
            await self._pace(host, policy)
            fetched += 1
            try:
                async with self.repo.pool.acquire() as conn:
                    known = await self.store.page(conn, source["id"], url)
                validators = {}
                if known and known.get("etag"):
                    validators["If-None-Match"] = known["etag"]
                if known and known.get("last_modified"):
                    validators["If-Modified-Since"] = known["last_modified"]
                resource = await self.fetcher.get(url, max_bytes=50 * 1024 * 1024 if kind == "document" else 5 * 1024 * 1024, validators=validators)
                consecutive_errors = 0
            except PlatformError as error:
                consecutive_errors += 1
                decided(url, kind, "ERROR", error.code)
                if consecutive_errors >= 10:
                    raise RuntimeError("TOO_MANY_FETCH_ERRORS") from None
                continue
            if resource.status in {404, 410}:
                decided(url, kind, "MISSING", f"nguồn trả {resource.status}; tài liệu đã nạp (nếu có) được giữ nguyên, cần quản trị quyết định")
                if not dry and known:
                    async with self.repo.pool.acquire() as conn:
                        await self.store.save_page(conn, source["id"], url, kind=kind, status="MISSING", reason=str(resource.status))
                continue
            if resource.status == 304 and known:
                decided(url, kind, "UNCHANGED", "máy chủ báo không đổi")
                continue
            if resource.status != 200:
                decided(url, kind, "ERROR", f"HTTP {resource.status}")
                continue
            await self._handle(source, dry, queue, seen, url, depth, kind, resource, known, decided)

    async def _expand_sitemap(self, url, queue, robots, level):
        normalized = normalize_url(url)
        if normalized is None or level > 2:
            return
        policy = await self._robots(robots, urlsplit(normalized).hostname)
        if not policy.can_fetch(normalized) and policy.mode != "seeds_only":
            return
        await self._pace(urlsplit(normalized).hostname, policy)
        try:
            resource = await self.fetcher.get(normalized, max_bytes=5 * 1024 * 1024, accept="application/xml,text/xml")
        except PlatformError:
            return
        if resource.status != 200:
            return
        pages, nested = parse_sitemap(resource.body)
        for page in pages:
            candidate = normalize_url(page)
            if candidate:
                queue.append((candidate, 1, "sitemap"))
        for child in nested:
            await self._expand_sitemap(child, queue, robots, level + 1)

    async def _handle(self, source, dry, queue, seen, url, depth, kind, resource, known, decided):
        media, final = resource.media, normalize_url(resource.final_url) or url
        etag, modified = resource.headers.get("etag"), resource.headers.get("last-modified")
        title, published, flags = None, None, []
        if media in HTML_MEDIA or (kind == "page" and media.startswith("text/")):
            page = extract_page(resource.body, final)
            if depth < source["max_depth"]:
                for link in page.links:
                    candidate = normalize_url(link)
                    if candidate and candidate not in seen:
                        queue.append((candidate, depth + 1, "link"))
            else:
                for link in page.links:   # attachments of the last level are still read
                    candidate = normalize_url(link)
                    if candidate and candidate not in seen and classify(candidate) in {"document", "unsupported_document"}:
                        queue.append((candidate, depth + 1, "attachment"))
            is_article = len(page.text) >= MIN_ARTICLE_CHARS and page.link_density < MAX_LINK_DENSITY
            if not is_article and not (source["kind"] == "PAGE" and len(page.text) >= 80):
                decided(url, "page", "SKIPPED", "trang danh sách hoặc ít nội dung (không phải một văn bản)", title=page.title)
                return
            findings = scan_personal_data(page.text)
            if findings:
                decided(url, "page", "BLOCKED_PII", "; ".join(f"{f.note} ({f.count})" for f in findings), title=page.title)
                return
            title, published = page.title or final, page.published_at
            lines = [title, "Nguồn: " + final] + ([f"Ngày đăng: {published:%d/%m/%Y}"] if published else []) + ["", page.text]
            body, content_sha, filename, content_type = "\n".join(lines).encode("utf-8"), hashlib.sha256(page.text.encode("utf-8")).hexdigest(), safe_filename(final, ".txt"), "text/plain"
            label = "page"
        elif media == "application/pdf" or final.lower().endswith(".pdf"):
            body, content_sha, filename, content_type, label = resource.body, hashlib.sha256(resource.body).hexdigest(), safe_filename(final, ".pdf"), "application/pdf", "document"
            title = safe_filename(final, "").replace("-", " ")
        elif media == DOCX_MEDIA or final.lower().endswith(".docx"):
            try:
                text = docx_to_text(resource.body)
            except DocxError as error:
                decided(url, "document", "ERROR", str(error))
                return
            findings = scan_personal_data(text)
            if findings:
                decided(url, "document", "BLOCKED_PII", "; ".join(f"{f.note} ({f.count})" for f in findings))
                return
            title = safe_filename(final, "").replace("-", " ")
            body = f"{title}\nNguồn: {final} (tệp .docx)\n\n{text}".encode("utf-8")
            content_sha, filename, content_type, label = hashlib.sha256(resource.body).hexdigest(), safe_filename(final, ".txt"), "text/plain", "document"
        elif media == "text/plain" or final.lower().endswith(".txt"):
            text = resource.body.decode("utf-8", "replace")
            findings = scan_personal_data(text)
            if findings:
                decided(url, "document", "BLOCKED_PII", "; ".join(f"{f.note} ({f.count})" for f in findings))
                return
            body, content_sha, filename, content_type, label = resource.body, hashlib.sha256(resource.body).hexdigest(), safe_filename(final, ".txt"), "text/plain", "document"
            title = safe_filename(final, "").replace("-", " ")
        else:
            decided(url, kind, "SKIPPED", f"loại nội dung không hỗ trợ ({media or 'không rõ'})")
            return
        if known and known.get("content_sha") == content_sha and known.get("version_id"):
            decided(url, label, "UNCHANGED", "nội dung không đổi so với lần trước", title=title)
            async with self.repo.pool.acquire() as conn:
                if not dry:
                    await self.store.save_page(conn, source["id"], url, kind=label, status="UNCHANGED", content_sha=content_sha, etag=etag, last_modified=modified)
            return
        if not (known and known.get("knowledge_source_id")):
            # A page already in the knowledge base (curated by hand or by an earlier import) is never overwritten or duplicated
            # by the crawler: its URI is unique across the platform, and its curated content has its own review history.
            async with self.repo.pool.acquire() as conn:
                existing = await conn.fetchval("""SELECT s.title FROM knowledge_source s JOIN knowledge_source_scope x ON x.source_id=s.id
                    WHERE x.tenant_id=$1 AND s.canonical_uri=$2""", self.repo.tenant, url)
                if existing is None:
                    existing = await conn.fetchval("SELECT title FROM knowledge_source WHERE canonical_uri=$1", url)
            if existing is not None:
                decided(url, label, "EXISTS", f"đã có trong kho («{existing}»); bộ cào không ghi đè hay tạo bản trùng, cần quản trị liên kết thủ công", title=title)
                return
        change = "CHANGED" if known and known.get("knowledge_source_id") else "NEW"
        if dry:
            decided(url, label, "WOULD_UPDATE" if change == "CHANGED" else "WOULD_CREATE", "chạy thử: chưa nạp gì", title=title,
                    chars=len(body))
            return
        if published is None:
            flags.append("EFFECTIVE_FROM_ASSUMED")
        try:
            version = await self._ingest(source, url, label, title, filename, content_type, body, content_sha, published, flags, known)
        except PlatformError as error:
            decided(url, label, "ERROR", error.code + ": " + error.detail[:120], title=title)
            return
        async with self.repo.pool.acquire() as conn:
            await self.store.save_page(conn, source["id"], url, kind=label, status="INGESTED", content_sha=content_sha, etag=etag, last_modified=modified,
                                       version_id=version["version_id"], knowledge_source_id=version["source_id"], title=title)
        decided(url, label, "UPDATED" if change == "CHANGED" else "CREATED", "đã đưa vào luồng " + ("đăng thẳng" if source["mode"] == "DIRECT" else "chờ duyệt"), title=title,
                version_id=str(version["version_id"]))

    async def _ingest(self, source, url, label, title, filename, content_type, body, content_sha, published, flags, known):
        actor = await self.crawler_actor()
        now = datetime.now(UTC)
        effective = published if published and published <= now else now - timedelta(minutes=1)
        common = dict(programs=source["programs"], audiences=source["audiences"], effective_from=effective)
        if known and known.get("knowledge_source_id"):
            async with self.repo.pool.acquire() as conn:
                row = await conn.fetchrow("""SELECT title,owner_unit,canonical_uri,authority_level,campus_scope,faculty_scope,program_scope,audiences
                    FROM knowledge_source WHERE id=$1""", known["knowledge_source_id"])
            metadata = IntakeMetadata(title=row["title"], owner_unit=row["owner_unit"], canonical_uri=row["canonical_uri"], campus=row["campus_scope"],
                faculties=row["faculty_scope"], programs=row["program_scope"], audiences=row["audiences"], authority_level=row["authority_level"],
                source_id=str(known["knowledge_source_id"]), effective_from=effective)
        else:
            metadata = IntakeMetadata(title=(title or "Tài liệu")[:300], owner_unit=source["owner_unit"], canonical_uri=url, **common)
        upload = UploadFile(io.BytesIO(body), filename=filename, headers=Headers({"content-type": content_type}))
        result = await self.platform.upload(actor, metadata, upload, f"crawl:{source['id']}:{content_sha}"[:128])
        attestation = None
        if source["mode"] == "DIRECT":
            attestation = {"text": "Nguồn tự động được quản trị tri thức cấu hình ĐĂNG THẲNG.", "by": str(source["configured_by"]),
                           "at": now.isoformat(), "crawl_source": str(source["id"]), "url": url, "content_sha": content_sha}
        async with self.repo.transaction() as conn:
            await self.auto.register(conn, version_id=result["version_id"], source_id=result["source_id"], author_id=actor.subject_id,
                author_role="KNOWLEDGE_CONTRIBUTOR", mode=source["mode"], origin="CRAWL", flags=flags, attestation=attestation)
        return result


def _public_source(source):
    return {"id": str(source["id"]), "name": source["name"], "seed_urls": source["seed_urls"], "kind": source["kind"], "include": source["include"],
            "exclude": source["exclude"], "max_depth": source["max_depth"], "max_pages": source["max_pages"], "interval_hours": source["interval_hours"],
            "owner_unit": source["owner_unit"], "mode": source["mode"], "active": source["active"], "ingest_enabled": source["ingest_enabled"],
            "next_run_at": source["next_run_at"].isoformat() if source["next_run_at"] else None,
            "last_run_at": source["last_run_at"].isoformat() if source["last_run_at"] else None, "last_status": source["last_status"],
            "pending_run": source["pending_run"]}


def _public_run(run, detail=False):
    value = {"id": str(run["id"]), "trigger": run["trigger"], "dry_run": run["dry_run"], "state": run["state"], "counts": run["counts"] or {},
             "error": run["error"], "started_at": run["started_at"].isoformat(), "finished_at": run["finished_at"].isoformat() if run["finished_at"] else None}
    if detail:
        value["decisions"] = run["decisions"] or []
    return value
