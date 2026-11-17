"""Remove adjacent-post chrome and correct one visually checked OCR typo."""
import asyncio
import json
from collections import Counter
from datetime import UTC, datetime

from complete_huce_corpus import SCOPE, read, windows
from prepare_huce_supplements import Body
from knowledge_platform import ROOT, checked_path, components, retain
from campus247.application.knowledge.platform_models import digest
from campus247.application.knowledge.source_snapshot import validate_snapshot


async def main():
    plan = read(SCOPE / "candidate-plan-05.json")
    targets = {"44c96321-30ae-72aa-8453-182aacdb2bed", "5c0b7c32-2740-720a-87a5-3db734608d01", "129ba0a6-652e-70b8-8532-8e63661262ce"}
    folder = checked_path(SCOPE / "candidates-clean-text-01", ROOT); folder.mkdir(exist_ok=False)
    pool, _, platform, _ = await components()
    try:
        for entry in plan["sources"]:
            if entry["source_id"] not in targets: continue
            candidate = read(ROOT / entry["candidate"])
            if entry["source_id"] == "129ba0a6-652e-70b8-8532-8e63661262ce":
                block = candidate["extracted"]["blocks"][1]
                assert block["page"] == 2 and block["text"].count("cắp học bổng") == 1
                block["text"] = block["text"].replace("cắp học bổng", "cấp học bổng")
                witness = candidate["extracted"]["review_witness"]
                image = witness["images"][1]
                assert digest(checked_path(ROOT / image["image"], ROOT).read_bytes()) == image["image_sha256"]
                witness["correction"] = {"page": 2, "before": "cắp học bổng", "after": "cấp học bổng",
                    "basis": "Visually inspected original page 2", "image_sha256": image["image_sha256"]}
            else:
                async with pool.acquire() as conn:
                    version = await platform.repo.version(conn, candidate["previous_version_id"])
                    artifact = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1", version["original_id"])
                raw = platform.storage.read(artifact); assert digest(raw) == candidate["original_sha256"]
                parser = Body(); parser.feed(raw.decode("utf-8-sig")); text = parser.text()
                assert parser.found == 1 and len(text) > 100 and "Previous Post" not in text and "Next Post" not in text
                candidate["extracted"] = {"original_sha256": candidate["original_sha256"],
                    "blocks": [{"block_id": "0", "page": None, "text": text}],
                    "review_witness": {"extractor": "single-blog-content-without-post-navigation-v2",
                        "excluded_dom_class": "post-navigation", "original_sha256": candidate["original_sha256"]}}
            pages = []
            for block in candidate["extracted"]["blocks"]:
                for start, end in windows(block["text"]):
                    text = block["text"][start:end]
                    pages.append({"block_id": block["block_id"], "page": block["page"], "char_start": start,
                        "char_end": end, "text": text, "text_sha256": digest(text.encode()), "section": entry["title"] + " · nội dung bản gốc đã đối chiếu"})
            candidate["pages"] = pages; candidate["applicability"]["reviewed_at"] = datetime.now(UTC).isoformat()
            validate_snapshot(candidate, candidate["extracted"], original_sha256=candidate["original_sha256"],
                effective_from=datetime.fromisoformat(candidate["applicability"]["reviewed_at"]))
            destination = checked_path(folder / (entry["source_id"] + ".json"), ROOT); retain(destination, candidate)
            entry.update(candidate=str(destination.relative_to(ROOT)), candidate_sha256=digest(destination.read_bytes()), parents=len(pages))
        plan["counts"] = dict(Counter(row["status"] for row in plan["sources"]))
        retain(SCOPE / "candidate-plan-06.json", plan)
        print(json.dumps({"cleaned_sources": sorted(targets), "counts": plan["counts"]}))
    finally: await pool.close()


if __name__ == "__main__": asyncio.run(main())
