"""Extract retained originals with PDFium; preserve the earlier extraction."""
import asyncio
import json
import sys
from datetime import UTC, datetime

from knowledge_platform import ROOT, STATE, TENANT, checked_path, components, retain

SCOPE = checked_path(ROOT / "infra/local/huce-corpus-completion-20261024-01", ROOT)


async def main():
    import pypdfium2 as pdfium
    from acquire_huce_public_knowledge import Text
    from campus247.application.knowledge.platform_models import digest
    pool, _, platform, _ = await components()
    target = checked_path(SCOPE / "original-extraction-03", ROOT)
    target.mkdir(exist_ok=False)
    rows, seen = [], set()
    try:
        async with pool.acquire() as conn:
            originals = await conn.fetch("""SELECT DISTINCT a.* FROM knowledge_artifact a
                JOIN knowledge_ingest_version x ON x.original_id=a.id JOIN document_version v ON v.id=x.version_id
                JOIN knowledge_source s ON s.id=v.knowledge_source_id
                WHERE x.tenant_id=$1 AND s.canonical_uri LIKE 'https://%' ORDER BY a.sha256""", TENANT)
        for artifact in originals:
            if artifact["sha256"] in seen:
                continue
            seen.add(artifact["sha256"])
            raw = platform.storage.read(artifact)
            pages, failure = [], None
            kind = "PDF" if raw.startswith(b"%PDF-") else "HTML"
            if kind == "PDF":
                with pdfium.PdfDocument(raw) as document:
                    for number in range(len(document)):
                        page = document[number]
                        textpage = page.get_textpage()
                        pages.append({"page": number + 1, "text": textpage.get_text_bounded().replace("\r", "")})
                        textpage.close(); page.close()
            else:
                try:
                    text = raw.decode("utf-8-sig")
                    parser = Text(); parser.feed(text)
                    pages = [{"page": None, "text": parser.text()}]
                except UnicodeError:
                    kind, failure = "BINARY", "BINARY_REQUIRES_FORMAT_ADAPTER"
            report = {"original_sha256": artifact["sha256"], "kind": kind, "processor": "pdfium-native-page-text-v1" if kind == "PDF" else "html-visible-text-v1",
                "pages": pages, "failure": failure, "at": datetime.now(UTC).isoformat(),
                "original_object_key": artifact["object_key"]}
            path = checked_path(target / (artifact["sha256"] + ".json"), ROOT)
            retain(path, report)
            rows.append({"original_sha256": artifact["sha256"], "kind": kind, "pages": len(pages),
                "thin_pages": [p["page"] for p in pages if len(p["text"].strip()) < 80], "failure": failure,
                "extraction": str(path.relative_to(ROOT)), "extraction_sha256": digest(path.read_bytes())})
        retain(SCOPE / "extraction-03-manifest.json", {"originals": rows})
        print(json.dumps({"originals": len(rows), "pages": sum(r["pages"] for r in rows),
            "thin_originals": sum(bool(r["thin_pages"]) for r in rows), "failures": [r for r in rows if r["failure"]]}))
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
