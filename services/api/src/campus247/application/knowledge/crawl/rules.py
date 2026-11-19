"""URL rules, robots.txt and sitemap handling for the crawler. Pure functions, standard library only."""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urldefrag, urlencode, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree as ET

from campus247.application.knowledge.platform_models import PlatformError
from campus247.application.knowledge.values import public_document_url

USER_AGENT = "Campus247-KnowledgeBot/1.0 (+public school pages only; respects robots.txt)"
TRACKING = re.compile(r"^(utm_.*|fbclid|gclid|sessionid|phpsessid|sid|jsessionid|share|print|fontsize|replytocom)$", re.I)
DOCUMENT_EXTENSIONS = {".pdf": "application/pdf", ".txt": "text/plain",
                       ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
UNSUPPORTED_DOCUMENT_EXTENSIONS = {".doc", ".xls", ".xlsx", ".ppt", ".pptx", ".rar", ".zip"}
SKIP_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".mp3", ".mp4", ".avi", ".mov", ".css", ".js", ".woff", ".woff2",
                   ".ttf", ".eot", ".xml", ".json", ".rss", ".atom"}
NOISE_PATH = re.compile(r"(?:^|/)(?:login|logout|dang-?nhap|dang-?ky|register|search|tim-?kiem|cart|wp-admin|wp-login|feed|tag|calendar|lich)(?:/|$|\?)", re.I)


def normalize_url(url: str) -> str | None:
    """Canonical https URL inside the allowed domain, or None. Fragments and tracking/session parameters are dropped."""
    try:
        raw = urldefrag(url.strip())[0]
        public_document_url(raw)   # strict check on what was actually given: credentials, ports, other hosts are refused here
        parts = urlsplit(raw)
        if parts.scheme != "https":
            return None
        query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not TRACKING.match(k)))
        path = re.sub(r"/{2,}", "/", parts.path or "/")
        canonical = urlunsplit(("https", (parts.hostname or "").lower(), path, query, ""))
        public_document_url(canonical)   # the same domain/credentials rules the document fetcher enforces
        return canonical
    except (ValueError, PlatformError):
        return None


def extension(url: str) -> str:
    match = re.search(r"(\.[A-Za-z0-9]{2,5})$", urlsplit(url).path)
    return match.group(1).lower() if match else ""


def classify(url: str) -> str:
    """'page' | 'document' | 'unsupported_document' | 'skip'."""
    ext = extension(url)
    if ext in DOCUMENT_EXTENSIONS:
        return "document"
    if ext in UNSUPPORTED_DOCUMENT_EXTENSIONS:
        return "unsupported_document"
    if ext in SKIP_EXTENSIONS or NOISE_PATH.search(urlsplit(url).path + ("?" + urlsplit(url).query if urlsplit(url).query else "")):
        return "skip"
    return "page"


def wanted(url: str, include: list[str], exclude: list[str]) -> bool:
    target = urlsplit(url).path + ("?" + urlsplit(url).query if urlsplit(url).query else "")
    if any(re.search(pattern, target) for pattern in exclude):
        return False
    return not include or any(re.search(pattern, target) for pattern in include)


class RobotsPolicy:
    def __init__(self, text: str | None, *, mode: str = "rules"):
        """mode: 'rules' (parsed text), 'allow_all' (robots.txt absent: 404), 'seeds_only' (unreadable: be conservative)."""
        self.mode, self.parser = mode, RobotFileParser()
        if mode == "rules":
            self.parser.parse((text or "").splitlines())

    @classmethod
    def absent(cls):
        return cls(None, mode="allow_all")

    @classmethod
    def unreadable(cls):
        return cls(None, mode="seeds_only")

    def can_fetch(self, url: str) -> bool:
        if self.mode == "allow_all":
            return True
        if self.mode == "seeds_only":
            return False  # the caller lets seed URLs through explicitly
        return self.parser.can_fetch(USER_AGENT, url) and self.parser.can_fetch("*", url)

    def delay(self, default: float) -> float:
        if self.mode != "rules":
            return default
        value = self.parser.crawl_delay(USER_AGENT) or self.parser.crawl_delay("*")
        return max(default, float(value)) if value else default

    def sitemaps(self) -> list[str]:
        return list(self.parser.site_maps() or []) if self.mode == "rules" else []


def parse_sitemap(xml: bytes, *, limit: int = 5000) -> tuple[list[str], list[str]]:
    """(page urls, nested sitemap urls) from a sitemap or sitemap index; invalid XML yields nothing."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return [], []
    pages, nested = [], []
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag in {"url", "sitemap"}:
            loc = next((c.text.strip() for c in element if c.tag.rsplit("}", 1)[-1] == "loc" and c.text), None)
            if loc:
                (pages if tag == "url" else nested).append(loc)
        if len(pages) + len(nested) >= limit:
            break
    return pages, nested
