"""Read-only source/content audit. No approvals, applicability guesses or model calls."""
import asyncio
import io
import json
import re
import unicodedata
from collections import Counter
from datetime import UTC, datetime

from knowledge_platform import ROOT, STATE, components, retain
from acquire_huce_public_knowledge import Text


def comparable(text):
    return re.sub(r"[^\w]", "", unicodedata.normalize("NFKC", text).lower())


async def run():
    from pypdf import PdfReader
    pool, _, platform, _ = await components()
    report, cache = [], {}
    try:
        async with pool.acquire() as conn:
            versions = await conn.fetch("""SELECT x.version_id FROM knowledge_ingest_version x
                JOIN document_version v ON v.id=x.version_id JOIN knowledge_source s ON s.id=v.knowledge_source_id
                WHERE x.tenant_id=$1 AND s.canonical_uri LIKE 'https://%' ORDER BY x.version_id""", platform.repo.tenant)
            for record in versions:
                row = await platform.repo.version(conn, record["version_id"])
                artifacts = {kind: await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1", row[kind+"_id"])
                             for kind in ("original", "rendition")}
                original, rendition = (platform.storage.read(artifacts[k]) for k in ("original", "rendition"))
                rendition = json.loads(rendition)
                key = row["original_sha256"]
                if key not in cache:
                    if original.startswith(b"%PDF-"):
                        reader = PdfReader(io.BytesIO(original))
                        texts = [page.extract_text() or "" for page in reader.pages]
                    else:
                        try:
                            parser = Text(); parser.feed(original.decode("utf-8", errors="strict")); texts = [parser.text()]
                        except UnicodeError:
                            texts = [""]  # Binary/image original requires visual/OCR verification, never pretend it is text.
                    cache[key] = texts
                texts = cache[key]
                matches, missing = [], []
                for page in rendition["pages"]:
                    target = comparable(page["text"])
                    start, end = page.get("page"), page.get("page_end") or page.get("page")
                    candidates = texts[max(0,start-1):end] if start and original.startswith(b"%PDF-") else texts
                    matched = target in comparable(" ".join(candidates))
                    (matches if matched else missing).append({"page": start, "section": page.get("section"),
                        "legacy_chunk_id": page.get("legacy_chunk_id")})
                full = "\n".join(texts)
                clauses = [full[max(0,m.start()-150):m.end()+280] for m in re.finditer(r"hiệu lực|áp dụng từ|kể từ ngày|thay thế",full,re.I)]
                report.append({"version_id":str(row["version_id"]), "source_id":str(row["source_id"]), "title":row["title"],
                    "canonical_uri":row["canonical_uri"], "original_sha256":key, "original_hash_verified":True,
                    "rendition_hash_verified":True, "metadata_sha256":row["metadata_sha256"],
                    "page_count":len(texts), "matched_parents":len(matches), "unmatched_parents":missing,
                    "header":full[:1800], "applicability_clauses":clauses[:15],
                    "original_mapping":rendition.get("original_mapping"),
                    "legacy_issues":rendition.get("issues"), "effective_from":str(row["effective_from"]) if row["effective_from"] else None})
                print(json.dumps({"audited":len(report),"version_id":str(row["version_id"]),"matched":len(matches),"unmatched":len(missing)},ensure_ascii=False),flush=True)
        path = STATE / ("source-audit-"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")+".json")
        retain(path,{"scope":"read-only comparison; no human approval", "versions":report,"new_model_calls":0})
        print(json.dumps({"report":str(path),"versions":len(report),"fully_text_matched":sum(not x["unmatched_parents"] for x in report)}))
    finally:
        await pool.close()


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(run())
