"""Acquire anonymous Drive PDFs linked by HUCE's curriculum table, retaining row scope."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from pypdf import PdfReader

from huce_source_registry import BASE, ROOT, checked, save, public_address

PUBLICATION = "https://huce.edu.vn/khung-chuong-trinh-dao-tao-chinh-quy"


class Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables, self.row, self.cell, self.table, self.links = [], None, None, None, []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.table = []; self.tables.append(self.table)
        if tag == "tr" and self.table is not None:
            self.row = []; self.table.append(self.row)
        if tag in {"td", "th"} and self.row is not None:
            self.cell = {"parts": [], "links": []}; self.row.append(self.cell)
        if tag == "a" and self.cell is not None and dict(attrs).get("href"):
            self.cell["links"].append(dict(attrs)["href"])

    def handle_endtag(self, tag):
        if tag in {"td", "th"}: self.cell = None
        if tag == "tr": self.row = None
        if tag == "table": self.table = None

    def handle_data(self, text):
        if self.cell is not None: self.cell["parts"].append(text)


async def main(args):
    source_run = checked(Path(args.discovery))
    registry = json.loads((source_run / "registry.json").read_text(encoding="utf-8")) if (source_run / "registry.json").exists() else [json.loads(s) for s in (source_run / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    source = next(r for r in registry if r["url"] == PUBLICATION)
    body = checked(ROOT / source["original_file"]).read_bytes()
    if hashlib.sha256(body).hexdigest() != source["sha256"]:
        raise ValueError("publication hash mismatch")
    parser = Tables(); parser.feed(body.decode("utf-8"))
    destination = checked(BASE / datetime.now(UTC).strftime("curricula-%Y%m%dT%H%M%S%fZ"))
    destination.mkdir(parents=True, exist_ok=False)
    entries = []
    previous = {}
    if args.resume:
        previous_manifest = checked(Path(args.resume) / "manifest.json")
        previous = {r["drive_id"]: r for r in json.loads(previous_manifest.read_text(encoding="utf-8"))["files"]}
    for table_index, table in enumerate(parser.tables):
        for row in table:
            cells = [" ".join("".join(c["parts"]).split()) for c in row]
            for cell in row:
                for link in cell["links"]:
                    match = re.fullmatch(r"https://drive\.google\.com/file/d/([a-zA-Z0-9_-]+)/view(?:\?.*)?", link)
                    if match:
                        entries.append({"publication_url": PUBLICATION, "publication_sha256": source["sha256"],
                            "table_index": table_index, "row_cells": cells, "url": link, "drive_id": match[1],
                            "scope": "K71" if table_index == 0 else "K70_and_earlier_verify_individual_row",
                            "rag_status": "not_admitted", "visual_review": "pending"})
    save(destination / "table-rows.json", entries)
    semaphore = asyncio.Semaphore(3)
    async with httpx.AsyncClient(timeout=30, trust_env=False, follow_redirects=False) as client:
        async def acquire(entry):
            async with semaphore:
                entry = dict(entry, collected_at=datetime.now(UTC).isoformat())
                retained = previous.get(entry["drive_id"])
                if retained and retained["status"] == "downloaded" and not args.refresh:
                    original = checked(ROOT / retained["original_file"])
                    if hashlib.sha256(original.read_bytes()).hexdigest() != retained["sha256"]:
                        raise ValueError("retained snapshot hash mismatch")
                    return dict(retained, reuse="hash_verified_snapshot_not_a_remote_freshness_check")
                url = "https://drive.google.com/uc?export=download&id=" + entry["drive_id"]
                try:
                    for _ in range(4):
                        host = urlsplit(url).hostname
                        if host == "accounts.google.com":
                            entry.update(status="login_required", redirect_host=host)
                            return entry
                        if host not in {"drive.google.com", "drive.usercontent.google.com"}:
                            raise ValueError("external redirect requires review")
                        await asyncio.to_thread(public_address, host)
                        async with client.stream("GET", url) as response:
                            if response.is_redirect:
                                from urllib.parse import urljoin
                                url = urljoin(url, response.headers["location"])
                                continue
                            content = bytearray()
                            async for chunk in response.aiter_bytes():
                                content.extend(chunk)
                                if len(content) > 20_000_000: raise ValueError("size cap")
                            break
                    else: raise ValueError("redirect limit")
                    if response.status_code != 200 or not content.startswith(b"%PDF"):
                        entry.update(status="unavailable_or_login_required", http_status=response.status_code)
                        return entry
                    digest = hashlib.sha256(content).hexdigest()
                    file = checked(BASE / "objects" / digest)
                    if not file.exists():
                        with file.open("xb") as stream: stream.write(content)
                    elif hashlib.sha256(file.read_bytes()).hexdigest() != digest:
                        raise ValueError("object hash mismatch")
                    pdf = PdfReader(io.BytesIO(content))
                    pages = [{"page": i, "text": p.extract_text() or ""} for i, p in enumerate(pdf.pages, 1)]
                    page_file = checked(destination / (entry["drive_id"] + "-pages.json"))
                    if not page_file.exists(): save(page_file, pages)
                    entry.update(status="downloaded", sha256=digest, original_file=str(file.relative_to(ROOT)),
                                 page_file=str(page_file.relative_to(ROOT)), page_count=len(pages),
                                 ocr_quality="needs_ocr" if any(len(p["text"].strip()) < 60 for p in pages) else "text_extracted_unreviewed")
                except Exception as exc:
                    entry.update(status="error", error=str(exc)[:300])
                return entry
        # Download each immutable file once, retaining all original row bindings.
        unique = {entry["drive_id"]: entry for entry in entries}
        results = await asyncio.gather(*(acquire(entry) for entry in unique.values()))
    save(destination / "manifest.json", {"public_only": True, "publication": source, "rows": entries, "files": results})
    print(json.dumps({"destination": str(destination), "table_rows": len(entries), "unique_files": len(unique),
                      "downloaded": sum(r["status"] == "downloaded" for r in results),
                      "pages": sum(r.get("page_count", 0) for r in results), "rag_admitted": 0}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discovery", required=True)
    parser.add_argument("--resume")
    parser.add_argument("--refresh", action="store_true")
    asyncio.run(main(parser.parse_args()))
