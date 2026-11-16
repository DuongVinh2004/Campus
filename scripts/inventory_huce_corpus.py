"""Read-only full corpus inventory with append-only extraction receipts."""
import asyncio
import io
import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime

from knowledge_platform import ROOT, STATE, TENANT, checked_path, components, retain

SCOPE = checked_path(ROOT / "infra/local/huce-corpus-completion-20261024-01", ROOT)


async def main():
    from pypdf import PdfReader
    from acquire_huce_public_knowledge import Text
    from campus247.application.knowledge.platform_models import digest
    pool, _, platform, _ = await components()
    SCOPE.mkdir(exist_ok=False)
    extracted = checked_path(SCOPE / "extracted", ROOT)
    extracted.mkdir()
    report = {"at": datetime.now(UTC).isoformat(), "mutation": "new local evidence files only", "sources": [], "versions": []}
    try:
        async with pool.acquire() as conn:
            async with conn.transaction(isolation="repeatable_read", readonly=True):
                pointer = await platform.repo.pointer(conn)
                members = await conn.fetch("SELECT * FROM knowledge_release_member WHERE release_id=$1", pointer["release_id"])
                served = {str(row["source_id"]): str(row["version_id"]) for row in members}
                rows = await conn.fetch("""SELECT x.version_id FROM knowledge_ingest_version x
                    JOIN document_version v ON v.id=x.version_id JOIN knowledge_source s ON s.id=v.knowledge_source_id
                    WHERE x.tenant_id=$1 AND s.canonical_uri LIKE 'https://%' ORDER BY s.id,v.created_at""", TENANT)
                cache = {}
                grouped = {}
                for record in rows:
                    row = await platform.repo.version(conn, record["version_id"])
                    source = str(row["source_id"])
                    if source not in grouped:
                        grouped[source] = {"source_id": source, "title": row["title"], "uri": row["canonical_uri"],
                            "serving_version": served.get(source), "version_ids": []}
                    grouped[source]["version_ids"].append(str(record["version_id"]))
                    original = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1", row["original_id"])
                    raw = platform.storage.read(original)
                    if row["original_sha256"] not in cache:
                        pages, failure = [], None
                        kind = "PDF" if raw.startswith(b"%PDF-") else "HTML" if b"<html" in raw[:2000].lower() or b"<!doctype" in raw[:2000].lower() else "OTHER"
                        try:
                            if len(raw) > 50 * 1024**2:
                                raise ValueError("ORIGINAL_SIZE_LIMIT")
                            if kind == "PDF":
                                reader = PdfReader(io.BytesIO(raw))
                                if reader.is_encrypted or len(reader.pages) > 500:
                                    raise ValueError("ENCRYPTED_OR_PAGE_LIMIT")
                                pages = [{"page": n, "text": page.extract_text() or ""} for n, page in enumerate(reader.pages, 1)]
                            else:
                                text = raw.decode("utf-8-sig", errors="strict")
                                if "<" in text[:500]:
                                    parser = Text(); parser.feed(text); text = parser.text()
                                    kind = "HTML"
                                pages = [{"page": None, "text": text}]
                        except Exception as error:
                            failure = type(error).__name__
                        full = "\n".join(p["text"] for p in pages)
                        clauses = [{"page": p["page"], "text": p["text"][max(0, m.start()-180):m.end()+350]}
                            for p in pages for m in re.finditer(r"có hiệu lực|áp dụng (?:cho|từ)|kể từ ngày|thay thế|Hà Nội.{0,12}ngày", p["text"], re.I)]
                        extraction = {"original_sha256": row["original_sha256"], "kind": kind, "pages": pages, "failure": failure}
                        target = checked_path(extracted / (row["original_sha256"] + ".json"), ROOT)
                        retain(target, extraction)
                        cache[row["original_sha256"]] = {"kind": kind, "pages": len(pages), "chars": len(full),
                            "thin_pages": [p["page"] for p in pages if len(p["text"].strip()) < 80],
                            "replacement_chars": full.count("\ufffd"), "failure": failure,
                            "text_sha256": digest(full.encode()), "extraction": str(target.relative_to(ROOT)),
                            "header": full[:2500], "applicability_clauses": clauses[:25]}
                    chunks = await conn.fetch("SELECT content_checksum,count(*) AS n FROM knowledge_chunk WHERE document_version_id=$1 GROUP BY content_checksum", row["version_id"])
                    report["versions"].append({"version_id": str(row["version_id"]), "source_id": source,
                        "title": row["title"], "uri": row["canonical_uri"], "original_sha256": row["original_sha256"],
                        "original_bytes": len(raw), "original_verified": True, "review_state": row["review_state"],
                        "effective_from": row["effective_from"], "processor": row["processor_profile"],
                        "rendition_sha256": row["rendition_sha256"], "chunk_count": sum(r["n"] for r in chunks),
                        "parent_count": len(chunks), **cache[row["original_sha256"]]})
                report["sources"] = list(grouped.values())
                report["release"] = pointer
        report["summary"] = {"sources": len(report["sources"]), "versions": len(report["versions"]),
            "serving_sources": len(served), "unique_originals": len(cache),
            "original_kinds": dict(Counter(v["kind"] for v in cache.values())),
            "originals_with_thin_pages": sum(bool(v["thin_pages"]) for v in cache.values()),
            "originals_with_parse_failure": sum(bool(v["failure"]) for v in cache.values()),
            "pages": sum(v["pages"] for v in cache.values()), "extracted_chars": sum(v["chars"] for v in cache.values())}
        retain(SCOPE / "inventory-01.json", report)
        print(json.dumps(report["summary"], ensure_ascii=False), flush=True)
        for source in report["sources"]:
            versions = [v for v in report["versions"] if v["source_id"] == source["source_id"]]
            v = versions[-1]
            print(json.dumps({"id": source["source_id"], "title": source["title"], "kind": v["kind"], "pages": v["pages"],
                "thin": v["thin_pages"], "serving": bool(source["serving_version"])}, ensure_ascii=False), flush=True)
    finally:
        await pool.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
