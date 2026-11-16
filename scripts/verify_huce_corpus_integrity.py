"""Verify preserved originals and the exact candidate membership, read-only DB."""
import asyncio
import argparse
import json
from datetime import datetime

from complete_huce_corpus import SCOPE, read
from knowledge_platform import components, retain
from campus247.application.knowledge.platform_models import digest
from campus247.application.knowledge.source_snapshot import read_snapshot


async def main(release_number="04", attempt="01"):
    inventory = read(SCOPE / "inventory-01.json")
    release = read(SCOPE / ("candidate-release-" + release_number + ".json"))
    pool, _, platform, _ = await components()
    originals = {}; preserved = []; members = []
    try:
        async with pool.acquire() as conn:
            async with conn.transaction(readonly=True, isolation="repeatable_read"):
                for old in inventory["versions"]:
                    version = await platform.repo.version(conn, old["version_id"])
                    assert version["original_sha256"] == old["original_sha256"]
                    assert version["review_state"] == old["review_state"]
                    assert version["effective_from"] == (datetime.fromisoformat(old["effective_from"]) if old["effective_from"] else None)
                    artifact = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1", version["original_id"])
                    if old["original_sha256"] not in originals:
                        originals[old["original_sha256"]] = digest(platform.storage.read(artifact)) == old["original_sha256"]
                    assert originals[old["original_sha256"]]
                    preserved.append(old["version_id"])
                sealed, actual = await platform._release(conn, release["release_id"])
                assert actual == release["members"] and sealed["membership_sha256"] == release["membership_sha256"]
                for member in actual:
                    version = await platform._eligible(conn, member["version_id"])
                    scope = await read_snapshot(platform, conn, version)
                    chunks = await conn.fetch("""SELECT c.content_text,c.content_checksum,ci.index_text,ci.input_sha256
                        FROM knowledge_chunk c JOIN knowledge_chunk_input ci ON ci.chunk_id=c.id WHERE c.document_version_id=$1""", member["version_id"])
                    assert chunks
                    for chunk in chunks:
                        assert digest(chunk["content_text"].encode()) == chunk["content_checksum"]
                        assert digest(chunk["index_text"].encode()) == chunk["input_sha256"]
                        if scope: assert chunk["content_checksum"] in scope["_evidence_hashes"]
                    members.append({**member, "chunks": len(chunks), "source_integrity_verified": True})
        result = {"baseline_versions_preserved": len(preserved), "baseline_originals_preserved": len(originals),
            "baseline_review_and_applicability_unchanged": True, "release_id": release["release_id"],
            "membership_sha256": release["membership_sha256"], "members": members,
            "member_count": len(members), "chunks_verified": sum(row["chunks"] for row in members),
            "original_three_versions_preserved": all(any(member["version_id"] == row["serving_version"] for member in members)
                for row in inventory["sources"] if row["serving_version"]), "all_passed": True}
        retain(SCOPE / ("candidate-integrity-" + attempt + ".json"), result)
        print(json.dumps({key: value for key, value in result.items() if key != "members"}))
    finally: await pool.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--release", choices=("04", "05", "06"), default="04")
    parser.add_argument("--attempt", choices=("01", "02", "03"), default="01"); args = parser.parse_args()
    asyncio.run(main(args.release, args.attempt))
