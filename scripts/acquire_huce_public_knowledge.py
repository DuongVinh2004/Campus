"""Acquire the current official HUCE handbook and library guide, without overwrites."""
from __future__ import annotations

import hashlib
import io
import json
import re
import ssl
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data/huce-public-20261013"
HANDBOOK = "https://huce.edu.vn/so-tay-sinh-vien-nam-hoc-2026-2027-truong-dai-hoc-xay-dung-ha-noi"
LIBRARY = "https://thuvien.huce.edu.vn/introduction.aspx?contentid=1191&mnuid=164"


def checked(path: Path) -> Path:
    if not path.resolve().is_relative_to(ROOT) or path.resolve() == ROOT:
        raise ValueError("destination outside workspace")
    for ancestor in (path, *path.parents):
        if ancestor.exists() and (ancestor.is_symlink() or ancestor.is_junction()):
            raise ValueError("reparse destination")
        if ancestor == ROOT:
            break
    return path


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag in {"p", "div", "br", "tr", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        if tag in {"p", "div", "tr", "li"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)

    def text(self):
        return "\n".join(line for raw in "".join(self.parts).splitlines()
                         if (line := re.sub(r"\s+", " ", raw).strip()))


def main():
    # Pure Python PDF extractor from the desktop's existing bundled runtime.
    sys.path.append(str(Path(sys.base_prefix) / "Lib/site-packages"))
    from pypdf import PdfReader
    checked(DEST)
    if (DEST / "corpus.json").exists():
        raise FileExistsError("completed source acquisition already exists; retain it")
    DEST.mkdir(parents=True, exist_ok=True)
    sources, chunks = [], []
    with httpx.Client(verify=ssl.create_default_context(), trust_env=False, timeout=30) as client:
        def fetch(url, name):
            path = checked(DEST / name)
            if path.exists():
                data = path.read_bytes()
                sources.append({"url": url, "file": name, "sha256": hashlib.sha256(data).hexdigest()})
                return SimpleNamespace(content=data, text=data.decode("utf-8", errors="replace"))
            response = client.get(url)
            response.raise_for_status()
            if len(response.content) > 30_000_000:
                raise ValueError("source size cap")
            with checked(DEST / name).open("xb") as stream:
                stream.write(response.content)
            sources.append({"url": url, "file": name, "sha256": hashlib.sha256(response.content).hexdigest()})
            return response

        article = fetch(HANDBOOK, "handbook-publication.html")
        flipbook = next(link for link in re.findall(r'https://heyzine\.com/flip-book/[a-z0-9]+\.html', article.text))
        book = fetch(flipbook, "handbook-viewer.html")
        pdf_url = next(link for link in re.findall(r'https://cdn[a-z]?\.heyzine\.com/files/uploaded/(?:v3/)?[a-z0-9]+\.pdf', book.text))
        pdf = fetch(pdf_url, "handbook-2026-2027.pdf")
        reader = PdfReader(io.BytesIO(pdf.content))
        for page, item in enumerate(reader.pages, 1):
            text = item.extract_text() or ""
            text = "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()).strip()
            if text:
                chunks.append({"title": "Sổ tay sinh viên HUCE năm học 2026–2027", "url": HANDBOOK,
                    "download_url": pdf_url, "page": page, "section": f"Trang {page}", "text": text,
                    "source_file": "handbook-2026-2027.pdf"})
        guide = fetch(LIBRARY, "library-guide.html")
        parser = Text(); parser.feed(guide.text)
        content = parser.text()
        start = content.index("Hướng dẫn bạn đọc sử dụng dịch vụ tại Thư viện")
        end = content.index("CÁC KÊNH THÔNG TIN", start)
        chunks.append({"title": "Hướng dẫn sử dụng dịch vụ Thư viện HUCE", "url": LIBRARY,
            "page": None, "section": "Các phòng chức năng", "text": content[start:end].strip(),
            "source_file": "library-guide.html"})
    manifest = {"acquired_at": datetime.now(timezone.utc).isoformat(), "sources": sources, "chunks": chunks,
        "public_only": True, "handbook_publication_url": HANDBOOK, "handbook_pdf_url": pdf_url}
    with checked(DEST / "corpus.json").open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"source_count": len(sources), "page_count": len(reader.pages),
        "chunk_count": len(chunks), "handbook_url": HANDBOOK, "pdf_url": pdf_url}, ensure_ascii=False))


if __name__ == "__main__":
    main()
