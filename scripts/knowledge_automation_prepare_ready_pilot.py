"""Prepare exact already-available public originals for the local UI pilot.

Copies only the named SOURCE_TEXT_AVAILABLE records from the frozen focus map.
No new account, reviewer, authority, publication, source metadata or model call.
"""
import argparse
import asyncio
from datetime import UTC, datetime
import json

from knowledge_platform import ROOT, checked_path, components, retain, rehearsal_bundle_paths


async def main(args):
    manifest = checked_path((ROOT / args.manifest).absolute(), ROOT)
    if not rehearsal_bundle_paths(manifest):
        raise ValueError("Complete verified restored bundle required")
    shadow_path = checked_path((ROOT / args.shadow_map).absolute(), ROOT)
    shadow = json.loads(shadow_path.read_text(encoding="utf-8"))
    ready = {row["source_id"]: row for row in shadow["sources"] if row["legacy_evidence_category"] == "SOURCE_TEXT_AVAILABLE"
        and row["category"] == "REUSABLE_EXISTING_RELEASE_BINDING"}
    if not 1 <= len(args.source) <= 3 or len(set(args.source)) != len(args.source) or any(value not in ready for value in args.source):
        raise ValueError("Select up to three exact already-available focused source IDs")
    output = checked_path(ROOT / "infra/local/knowledge-automation-20261026" /
        ("ready-pilot-"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")), ROOT)
    output.mkdir()
    pool, _, platform, _ = await components(rehearsal=manifest)
    report = {"started_at": datetime.now(UTC), "database": json.loads(manifest.read_text(encoding="utf-8"))["database"],
        "ui_upload_destination": "http://127.0.0.1:8018", "sources": [], "new_reviews": 0, "new_publications": 0, "model_calls": 0}
    try:
        async with pool.acquire() as conn:
            async with conn.transaction(readonly=True):
                report["pointer_before"] = await platform.repo.pointer(conn)
                for index, source_id in enumerate(args.source, 1):
                    expected = ready[source_id]
                    version = await platform._eligible(conn, expected["version_id"])
                    if version["original_sha256"] != expected["original_sha256"] or str(version["source_id"]) != source_id:
                        raise ValueError("Source changed since the read-only shadow map")
                    artifact = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2", version["original_id"], platform.repo.tenant)
                    raw = platform.storage.read(artifact)
                    if not raw.startswith(b"%PDF-"):
                        raise ValueError("This pilot accepts already-bound PDF originals only; no format substitution")
                    target = checked_path(output / f"ready-public-source-{index:02d}.pdf", ROOT)
                    with target.open("xb") as stream:
                        stream.write(raw)
                    report["sources"].append({"source_id": source_id, "version_id": expected["version_id"], "title": version["title"],
                        "canonical_uri": version["canonical_uri"], "original_sha256": artifact["sha256"], "file": str(target),
                        "legacy_evidence_category": expected["legacy_evidence_category"], "byte_size": len(raw)})
        report["status"] = "prepared_existing_public_originals"
    except Exception as error:
        report.update(status="failed", error_type=type(error).__name__)
        raise
    finally:
        await pool.close()
        report["finished_at"] = datetime.now(UTC)
        retain(output / "prepared.json", report)
    print(json.dumps({"receipt": str(output / "prepared.json"), "sources": report["sources"]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--shadow-map", required=True)
    parser.add_argument("--source", action="append", required=True)
    asyncio.run(main(parser.parse_args()))
