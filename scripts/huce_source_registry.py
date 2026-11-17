"""Bounded, resumable public HUCE discovery. Originals and run receipts are append-only.

Discovery is NOT publication into RAG: extracted text requires scope, currency,
OCR/table and supersession review before admission. No social platform is scraped.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import io
import ipaddress
import json
import re
import socket
from collections import Counter
import unicodedata
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/huce-discovery-20261020"
TOPICS = {
    "admission": "tuyen sinh|nhap hoc|chuyen truong|ho so",
    "curriculum": "chuong trinh dao tao|chuyen nganh|khung chuong trinh",
    "credits": "tin chi|tien quyet|hoc phan thay the|tu chon",
    "registration": "dang ky hoc|hoc lai|cai thien|rut hoc phan|song nganh|hoc vuot",
    "tuition": "hoc phi|don gia|hoan phi|cong no|tai vu",
    "financial_support": "hoc bong|mien giam|tro cap|ho tro tai chinh",
    "calendar_exams": "lich thi|lich nam hoc|nghi le|hoan thi|phuc khao|ke hoach nam hoc",
    "academic_standing": "gpa|canh bao|thoi hoc|bao luu|tro lai hoc|diem hoc tap",
    "graduation": "tot nghiep|ngoai ngu|tin hoc|thuc tap|do an",
    "one_stop": "mot cua|bang diem|giay xac nhan|cap bang",
    "student_affairs": "ren luyen|khen thuong|ky luat|bao hiem|y te",
    "facilities": "thu vien|phong hoc|thi nghiem|ky tuc xa|co so vat chat",
    "it_support": "tai khoan|email|cong sinh vien|ho tro ky thuat",
    "opportunities": "viec lam|quoc te|nghien cuu|doan|hoi sinh vien",
    "contacts": "lien he|gio lam viec|dia diem|dau moi",
}
SOCIAL = ("facebook.com", "youtube.com", "youtu.be", "tiktok.com", "zalo.me", "zaloapp.com", "instagram.com")
SKIP = re.compile(r"(?:logout|signout|dang-xuat|login|signin|dang-nhap|comment|binh-luan|wp-admin|search|tim-kiem)", re.I)


def norm(value):
    return " ".join("".join(c for c in unicodedata.normalize("NFD", value.lower())
                            if unicodedata.category(c) != "Mn").replace("đ", "d").split())


def official(url):
    host = (urlsplit(url).hostname or "").lower()
    return host == "huce.edu.vn" or host.endswith(".huce.edu.vn")


def canonical(url, base="https://huce.edu.vn/"):
    url = urldefrag(urljoin(base, url.strip()))[0]
    p = urlsplit(url)
    if p.scheme not in {"http", "https"} or not p.hostname or p.username or p.password:
        return None
    if p.port not in {None, 80, 443}:
        return None
    if len(url) > 6000 or SKIP.search(p.path) or re.search(r"(?:^|&)(?:s|q|search)=", p.query):
        return None
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or "/", p.query, ""))


def checked(path):
    path = path.absolute()
    resolved = path.resolve()
    if resolved == ROOT or not resolved.is_relative_to(ROOT):
        raise ValueError("workspace descendant required")
    for parent in (path, *path.parents):
        if parent.exists() and (parent.is_symlink() or parent.is_junction()
                               or getattr(parent.stat(), "st_file_attributes", 0) & 0x400):
            raise ValueError("reparse destination denied")
        if parent == ROOT:
            break
    return resolved


def save(path, value):
    path = checked(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.parts, self.title, self.dates = [], [], [], []
        self.hidden = 0
        self.in_title = False
        self.anchor = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag == "title":
            self.in_title = True
        for key in (("href",) if tag in {"a", "link"} else ("src",) if tag in {"iframe", "img", "embed"} else ()):
            if a.get(key):
                self.links.append([a[key], a.get("title") or a.get("alt") or "", tag])
                if tag == "a":
                    self.anchor = len(self.links) - 1
        if tag == "meta" and a.get("property", a.get("name", "")) in {"article:published_time", "date", "datePublished"}:
            self.dates.append(a.get("content"))
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "br"}:
            self.parts.append("\n")
        if tag in {"td", "th"}:
            self.parts.append(" | ")

    def handle_endtag(self, tag):
        if tag == "a":
            self.anchor = None
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.anchor is not None:
            self.links[self.anchor][1] += " " + data.strip()
        if self.in_title:
            self.title.append(data)
        if not self.hidden:
            self.parts.append(data)

    def text(self):
        return "\n".join(line for raw in "".join(self.parts).splitlines()
                         if (line := re.sub(r"[ \t]+", " ", raw).strip()))


def public_address(host):
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError("non-public network target")


async def crawl(args):
    run = checked(BASE / datetime.now(UTC).strftime("run-%Y%m%dT%H%M%S%fZ"))
    checked(run).mkdir(parents=True, exist_ok=False)
    previous, queue, links, rows = {}, {}, [], []
    social, hosts = {}, {}
    if args.resume:
        previous_run = checked(Path(args.resume))
        for row in json.loads((previous_run / "registry.json").read_text(encoding="utf-8")):
            previous[row["url"]] = row
        for row in json.loads((previous_run / "frontier.json").read_text(encoding="utf-8")):
            queue[row["url"]] = row
        links = json.loads((previous_run / "links.json").read_text(encoding="utf-8"))
        social = {r["url"]: r for r in json.loads((previous_run / "social-channels.json").read_text(encoding="utf-8"))}
        hosts = json.loads((previous_run / "domains.json").read_text(encoding="utf-8"))
        if args.refresh:
            for url, row in previous.items():
                queue.setdefault(url, {k: row[k] for k in ("url", "discovered_from", "depth")})
    seeds = ["https://huce.edu.vn/", "https://huce.edu.vn/co-cau-to-chuc", "https://tuyensinh.huce.edu.vn/",
             "https://daotao.huce.edu.vn/", "https://sinhvien.huce.edu.vn/", "https://ctsv.huce.edu.vn/",
             "https://thuvien.huce.edu.vn/", "https://fit.huce.edu.vn/chuong-trinh-dao-tao",
             "https://hcm.huce.edu.vn/", "https://khcn.huce.edu.vn/", "https://sdh.huce.edu.vn/"]
    for url in seeds:
        if url not in previous or args.refresh:
            queue.setdefault(url, {"url": url, "discovered_from": "seed", "depth": 0})
    for url in args.seed:
        url = canonical(url)
        if not url or not official(url):
            raise ValueError("explicit seed must be an official public HUCE URL")
        queue.setdefault(url, {"url": url, "discovered_from": "domain_search", "depth": 0})
    robots, locks, last, delays = {}, {}, {}, {}
    attempted = set()
    host_attempts = Counter()
    async with httpx.AsyncClient(trust_env=False, timeout=18, follow_redirects=False,
                                headers={"User-Agent": "Campus247-PublicResearch/1.0"}) as client:
        async def get(url, headers=None):
            # Validate every redirect target; never follow off-domain storage automatically.
            for _ in range(5):
                if not official(url):
                    raise ValueError("external redirect needs review: " + url)
                host = urlsplit(url).hostname
                await asyncio.to_thread(public_address, host)
                async with locks.setdefault(host, asyncio.Lock()):
                    elapsed = asyncio.get_running_loop().time() - last.get(host, 0)
                    await asyncio.sleep(max(0, delays.get(host, .4) - elapsed))
                    async with client.stream("GET", url, headers=headers) as response:
                        if response.is_redirect:
                            url = canonical(response.headers.get("location", ""), url)
                            if not url:
                                raise ValueError("invalid redirect")
                            continue
                        body = bytearray()
                        async for block in response.aiter_bytes():
                            body.extend(block)
                            if len(body) > args.max_mb * 1_000_000:
                                raise ValueError("size cap; requires separate acquisition")
                        last[host] = asyncio.get_running_loop().time()
                        return response, bytes(body), url
            raise ValueError("redirect limit")

        async def policy(url):
            p = urlsplit(url)
            origin = f"{p.scheme}://{p.netloc}"
            if origin not in robots:
                try:
                    response, body, _ = await get(origin + "/robots.txt")
                    rp = RobotFileParser()
                    if response.status_code == 200:
                        rp.parse(body.decode("utf-8", errors="replace").splitlines())
                        robots[origin] = rp
                        delays[p.hostname] = max(.4, rp.crawl_delay("Campus247-PublicResearch") or rp.crawl_delay("*") or 0)
                        for sitemap in rp.site_maps() or []:
                            enqueue(sitemap, origin + "/robots.txt", 0)
                    elif response.status_code == 404:
                        rp.parse([])
                        robots[origin] = rp
                    else:
                        robots[origin] = None
                    hosts[origin] = {"robots_http": response.status_code, "robots_checked_at": datetime.now(UTC).isoformat()}
                    for suffix in ("/sitemap.xml", "/sitemap_index.xml"):
                        enqueue(origin + suffix, origin + "/robots.txt", 0)
                except Exception as exc:
                    robots[origin] = None
                    hosts[origin] = {"robots_error": str(exc)[:300]}
            return robots[origin] is not None and robots[origin].can_fetch("Campus247-PublicResearch", url)

        def enqueue(url, source, depth):
            url = canonical(url, source)
            if url and re.search(r"\.(?:css|js|woff2?|ttf|ico)(?:$|\?)", url, re.I):
                return
            if url and official(url) and url not in attempted and url not in previous:
                queue.setdefault(url, {"url": url, "discovered_from": source, "depth": depth})

        async def process(item):
            url = item["url"]
            row = dict(item, collected_at=datetime.now(UTC).isoformat(), verification="discovered_official_domain",
                       rag_status="not_admitted", effective_status="unreviewed", supersedes=[],
                       applicable_cohorts=[], applicable_programs=[], academic_years=[], published_at=None,
                       document_number=None, ocr_quality="not_applicable", visual_review="pending")
            try:
                if not await policy(url):
                    row["status"] = "robots_denied_or_unavailable"
                    return row
                old = previous.get(url, {})
                headers = {k: old[v] for k, v in (("If-None-Match", "etag"), ("If-Modified-Since", "last_modified")) if old.get(v)}
                response, body, final = await get(url, headers)
                row.update(http_status=response.status_code, final_url=final)
                if response.status_code == 304:
                    return dict(old, collected_at=row["collected_at"], status="not_modified")
                if response.status_code != 200:
                    row["status"] = "login_required" if response.status_code in {401, 403} else "http_error"
                    return row
                content_type = response.headers.get("content-type", "").lower()
                if b"captcha" in body[:10000].lower() or b"cf-chl-" in body[:10000].lower():
                    row["status"] = "access_challenge"
                    return row
                digest = hashlib.sha256(body).hexdigest()
                target = checked(BASE / "objects" / digest)
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    with target.open("xb") as stream:
                        stream.write(body)
                elif hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                    raise ValueError("retained object hash mismatch")
                row.update(status="downloaded", sha256=digest, original_file=str(target.relative_to(ROOT)),
                           bytes=len(body), content_type=content_type, etag=response.headers.get("etag"),
                           last_modified=response.headers.get("last-modified"), issuer=urlsplit(url).hostname)
                if old.get("sha256"):
                    row["previous_sha256"] = old["sha256"]
                    row["content_changed"] = old["sha256"] != digest
                    row["previous_snapshot"] = old.get("original_file")
                text = ""
                if "html" in content_type:
                    page = Page(); page.feed(body.decode(response.encoding or "utf-8", errors="replace"))
                    row.update(title="".join(page.title).strip(), published_at=next(iter(page.dates), None))
                    text = page.text()
                    if re.search(r"(?:đăng nhập|sign in|log in)", row["title"], re.I):
                        row["status"] = "login_required"
                    for href, label, tag in page.links:
                        link = canonical(href, final)
                        if not link:
                            continue
                        host = urlsplit(link).hostname or ""
                        if any(host == s or host.endswith("." + s) for s in SOCIAL):
                            social.setdefault(link, {"url": link, "linked_from": [], "verification": "official_website_link_only",
                                                     "ownership": "needs_channel_identity_review", "collection": "not_attempted_platform_review_required"})
                            if url not in social[link]["linked_from"]:
                                social[link]["linked_from"].append(url)
                        links.append({"from": url, "to": link, "label": label, "tag": tag})
                        if item["depth"] < args.depth:
                            enqueue(link, url, item["depth"] + 1)
                elif "xml" in content_type or urlsplit(url).path.endswith(".xml"):
                    from xml.etree import ElementTree
                    xml = ElementTree.fromstring(body)
                    for element in xml.iter():
                        if element.tag.rsplit("}", 1)[-1] == "loc" and element.text:
                            enqueue(element.text, url, item["depth"])
                elif body.startswith(b"%PDF"):
                    from pypdf import PdfReader
                    pdf = PdfReader(io.BytesIO(body))
                    pages = [{"page": n, "text": p.extract_text() or ""} for n, p in enumerate(pdf.pages, 1)]
                    row["pages"] = len(pages)
                    row["ocr_quality"] = "needs_ocr" if any(len(p["text"].strip()) < 60 for p in pages) else "text_extracted_needs_visual_review"
                    save(run / "pages" / (digest + ".json"), pages) if not (run / "pages" / (digest + ".json")).exists() else None
                    text = "\n".join(p["text"] for p in pages)
                else:
                    row["status"] = "downloaded_needs_parser_or_ocr"
                    row["ocr_quality"] = "pending" if content_type.startswith("image/") else "not_applicable"
                if text:
                    row["text_file"] = str((run / "text" / (digest + ".json")).relative_to(ROOT))
                    dest = run / "text" / (digest + ".json")
                    if not dest.exists():
                        save(dest, {"text": text, "extraction": "unreviewed_original_text", "sha256": hashlib.sha256(text.encode()).hexdigest()})
                    # Title/path matches measure discovered candidates, NOT semantic coverage.
                    signal = norm(row.get("title", "") + " " + urlsplit(url).path.replace("-", " "))
                    row["topic_candidates"] = [topic for topic, pattern in TOPICS.items() if re.search(pattern, signal)]
                    row["academic_years"] = sorted(set(re.findall(r"20\d{2}\s*[-–]\s*20\d{2}", text)))
                    row["applicable_cohorts"] = sorted(set(re.findall(r"\bK\d{2}\b", text)))
            except Exception as exc:
                row.update(status="fetch_or_parse_error", error=str(exc)[:500])
            return row

        while queue and len(attempted) < args.limit:
            # Prefer shallow discovery and student topics; pagination remains in frontier.
            batch = sorted(queue.values(), key=lambda r: (host_attempts[urlsplit(r["url"]).hostname], r["depth"],
                not bool(re.search("sitemap|dao-tao|hoc-phi|thong-bao|chuong-trinh|sinh-vien|van-ban|quy-che", r["url"])), r["url"]))[:min(args.concurrency, args.limit - len(attempted))]
            for item in batch:
                queue.pop(item["url"]); attempted.add(item["url"])
                host_attempts[urlsplit(item["url"]).hostname] += 1
            results = await asyncio.gather(*(process(item) for item in batch))
            for row in results:
                rows.append(row)
                with checked(run / "events.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            if len(attempted) % 24 == 0:
                print(json.dumps({"attempted": len(attempted), "frontier": len(queue), "downloaded": sum(r["status"].startswith("downloaded") for r in rows)}), flush=True)
    combined = {**previous, **{r["url"]: r for r in rows}}
    save(run / "registry.json", list(combined.values()))
    save(run / "frontier.json", list(queue.values()))
    save(run / "links.json", links)
    save(run / "social-channels.json", list(social.values()))
    save(run / "domains.json", hosts)
    unit_registry = []
    for domain in sorted({urlsplit(r["url"]).hostname for r in [*combined.values(), *queue.values()]}):
        incoming = [link for link in links if urlsplit(link["to"]).hostname == domain
                    and urlsplit(link["from"]).hostname != domain]
        unit_registry.append({"domain": domain, "labels_from_official_links": sorted({r["label"].strip() for r in incoming if r["label"].strip()}),
                              "discovery_evidence": incoming, "unit_identity": "needs_review", "coverage": "incomplete"})
    save(run / "units.json", unit_registry)
    counts = {s: sum(r["status"] == s for r in combined.values()) for s in sorted({r["status"] for r in combined.values()})}
    summary = {"run": str(run), "attempted_this_run": len(rows), "registry_urls": len(combined),
               "status_counts": counts, "domains_checked": len(hosts), "social_link_candidates": len(social),
               "frontier_remaining": len(queue), "rag_admitted": 0, "complete": False,
               "limits": vars(args), "robots": "honored; unavailable denies collection",
               "coverage_semantics": "Title/path keyword candidates only; no applicability or E2E proof"}
    save(run / "summary.json", summary)
    matrix = checked(run / "coverage.csv")
    with matrix.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["topic", "unit_domain", "cohort_or_system", "academic_year", "candidate_urls", "reviewed_sources", "e2e_passed", "gap"])
        domains = sorted({urlsplit(r["url"]).hostname for r in combined.values()})
        for topic in TOPICS:
            for domain in domains:
                candidates = [r for r in combined.values() if urlsplit(r["url"]).hostname == domain and topic in r.get("topic_candidates", [])]
                writer.writerow([topic, domain, "UNRESOLVED", "UNRESOLVED", len(candidates), 0, 0,
                                 "applicability_and_currency_unreviewed" if candidates else "no_candidate_source"])
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=240)
    parser.add_argument("--depth", type=int, default=3)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--max-mb", type=int, default=20)
    parser.add_argument("--resume")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--seed", action="append", default=[])
    args = parser.parse_args()
    if not (1 <= args.limit <= 5000 and 1 <= args.depth <= 8 and 1 <= args.concurrency <= 8 and 1 <= args.max_mb <= 50):
        parser.error("invalid bounded collection limits")
    asyncio.run(crawl(args))
