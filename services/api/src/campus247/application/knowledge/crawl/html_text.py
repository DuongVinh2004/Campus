"""Main-content extraction from an HTML page: text, title, links, publication date. Standard library only."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin

SKIP_TAGS = {"script", "style", "noscript", "nav", "header", "footer", "form", "aside", "svg", "iframe", "button", "select", "template", "head"}
BLOCK_TAGS = {"p", "div", "section", "article", "main", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "br", "table", "ul", "ol",
              "blockquote", "pre", "dd", "dt", "figcaption"}
VOID = {"br", "hr", "img", "input", "meta", "link", "area", "base", "col", "embed", "source", "track", "wbr"}
MAIN_HINT = re.compile(r"(article|post|entry|content|detail|noi-?dung|chi-?tiet|news|item-page)", re.I)
DATE_TEXT = re.compile(r"(?:ngày\s*(?:đăng|ban hành)?\s*[:\-]?\s*)?\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b", re.I)


@dataclass
class Page:
    title: str = ""
    text: str = ""
    links: list[str] = field(default_factory=list)
    published_at: datetime | None = None
    link_count: int = 0
    link_text_chars: int = 0

    @property
    def link_density(self) -> float:
        """Share of the visible text that sits inside links: high for a list/menu page, low for an article."""
        return self.link_text_chars / max(1, len(self.text))


class _Extractor(HTMLParser):
    def __init__(self, base_url):
        super().__init__(convert_charrefs=True)
        self.base, self.links, self.stack = base_url, [], []
        self.skip = 0
        self.main_depth = 0                    # >0 while inside an article/main/content-like element
        self.all_blocks, self.main_blocks = [], []
        self.row: list[str] | None = None      # cells of the table row being read
        self.cell: list[str] | None = None
        self.line: list[str] = []
        self.in_link = 0
        self.link_chars = 0
        self.h1, self.title_tag, self.in_title, self.in_h1 = [], [], False, False
        self.meta_date = None
        self.time_dates = []

    # --- helpers
    def _flush(self):
        text = re.sub(r"\s+", " ", "".join(self.line)).strip()
        self.line = []
        if text:
            self.all_blocks.append(text)
            if self.main_depth:
                self.main_blocks.append(text)

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "title":
            self.in_title = True
        if tag == "meta":
            if a.get("property") == "article:published_time" or a.get("name") in {"date", "pubdate", "publishdate", "dc.date", "created"}:
                self.meta_date = self.meta_date or a.get("content")
        if tag == "time" and a.get("datetime"):
            self.time_dates.append(a["datetime"])
        skipped = tag in SKIP_TAGS or "display:none" in a.get("style", "").replace(" ", "").lower() or "hidden" in a
        if tag == "a" and a.get("href"):
            self.links.append(urljoin(self.base, a["href"]))
        if tag in VOID:
            if tag == "br":
                self._flush()
            return
        self.stack.append((tag, skipped, bool(not skipped and (tag in {"article", "main"} or MAIN_HINT.search(a.get("class", "") + " " + a.get("id", ""))))))
        if skipped:
            self.skip += 1
            return
        if self.stack[-1][2]:
            self.main_depth += 1
        if self.skip:
            return
        if tag in BLOCK_TAGS:
            self._flush()
        if tag == "tr":
            self.row = []
        if tag in {"td", "th"}:
            self.cell = []
        if tag == "a":
            self.in_link += 1
        if tag == "h1":
            self.in_h1 = True

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag in VOID:
            return
        for index in range(len(self.stack) - 1, -1, -1):   # tolerate unclosed tags
            if self.stack[index][0] == tag:
                for name, skipped, main in reversed(self.stack[index:]):
                    if skipped:
                        self.skip -= 1
                    elif main:
                        self.main_depth -= 1
                del self.stack[index:]
                break
        else:
            return
        if self.skip:
            return
        if tag in {"td", "th"} and self.cell is not None:
            if self.row is not None:
                self.row.append(re.sub(r"\s+", " ", "".join(self.cell)).strip())
            self.cell = None
        elif tag == "tr" and self.row is not None:
            cells = [c for c in self.row if c]
            self.line = [" | ".join(cells)] if cells else []
            self._flush()
            self.row = None
        elif tag == "a":
            self.in_link = max(0, self.in_link - 1)
        elif tag == "h1":
            self.in_h1 = False
        if tag in BLOCK_TAGS and self.cell is None:
            self._flush()

    def handle_data(self, data):
        if self.in_title:
            self.title_tag.append(data)
            return
        if self.skip:
            return
        if self.in_h1:
            self.h1.append(data)
        if self.cell is not None:
            self.cell.append(data)
        else:
            self.line.append(data)
        if self.in_link:
            self.link_chars += len(data.strip())


def _parse_date(value: str | None):
    if not value:
        return None
    value = value.strip()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        pass
    match = DATE_TEXT.search(value)
    if match:
        day, month, year = map(int, match.groups())
        try:
            return datetime(year, month, day, tzinfo=UTC)
        except ValueError:
            return None
    return None


def extract_page(html: bytes | str, base_url: str) -> Page:
    if isinstance(html, bytes):
        html = _decode(html)
    parser = _Extractor(base_url)
    parser.feed(html)
    parser.close()
    parser._flush()
    main = "\n".join(parser.main_blocks)
    chosen = parser.main_blocks if len(main) >= 200 else parser.all_blocks
    lines, previous = [], None
    for block in chosen:
        if block != previous:          # menus repeat the same line; keep the first
            lines.append(block)
        previous = block
    text = "\n".join(lines)
    title = re.sub(r"\s+", " ", "".join(parser.h1)).strip() or re.sub(r"\s+", " ", "".join(parser.title_tag)).strip()
    published = _parse_date(parser.meta_date) or next((d for d in map(_parse_date, parser.time_dates) if d), None)
    if published is None:
        published = _parse_date(" ".join(lines[:12]) if DATE_TEXT.search(" ".join(lines[:12])) else None)
    seen, links = set(), []
    for link in parser.links:
        if link.startswith(("http://", "https://")) and link not in seen:
            seen.add(link)
            links.append(link)
    return Page(title=title[:300], text=text, links=links, published_at=published,
                link_count=len(parser.links), link_text_chars=parser.link_chars)


def _decode(data: bytes) -> str:
    head = data[:4096].decode("ascii", "ignore")
    match = re.search(r"charset=['\"]?([A-Za-z0-9_\-]+)", head)
    for encoding in ([match.group(1)] if match else []) + ["utf-8", "cp1258", "latin-1"]:
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", "replace")
