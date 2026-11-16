"""Build the comprehensive, verified HUCE RAG index.

Reuses all hash-verified vectors from predecessor index-09d72d641...
Embeds new verified batch 3 and operational service child chunks via real TEI BGE-M3 (port 18081).
"""
import asyncio
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "services/api/src"), str(ROOT / "scripts")]
from scripts.public_rag_retrieval import create_public_hybrid_store, public_hybrid_index_path
from scripts.huce_source_registry import checked, save
from campus247.ports.embedding import validate_embedding_vector


async def main():
    print("Initializing old and new stores...")
    # Predecessor store (withdrawal phase flags)
    old = create_public_hybrid_store(
        ROOT / "data/huce-public-20261013",
        tenant_id="huce-local-public",
        campus_id="HUCE",
        faq_directory=ROOT / "data/huce-faq-20261013",
        include_reviewed_services=True,
        include_reviewed_course_review=True,
        include_reviewed_withdrawal=True,
        include_reviewed_batch3_verified=False,
        include_reviewed_services_02=False,
    )
    # New store with full batch3 verified + services 02
    new = create_public_hybrid_store(
        ROOT / "data/huce-public-20261013",
        tenant_id="huce-local-public",
        campus_id="HUCE",
        faq_directory=ROOT / "data/huce-faq-20261013",
        include_reviewed_services=True,
        include_reviewed_course_review=True,
        include_reviewed_withdrawal=True,
        include_reviewed_batch3_verified=True,
        include_reviewed_services_02=True,
    )

    pred_path = checked(public_hybrid_index_path(old))
    print(f"Loading predecessor index: {pred_path.name}")
    before = json.loads(pred_path.read_text(encoding="utf-8"))
    old.load_vectors(before)

    old_hashes = [hashlib.sha256(c["index_text"].encode()).hexdigest() for c in old.children]
    if before.get("index_text_sha256") != old_hashes or old.embedding_profile != new.embedding_profile:
        raise ValueError("Predecessor content or embedding profile mismatch")

    lookup = {(c["id"], h): v for c, h, v in zip(old.children, old_hashes, old.vectors, strict=True)}
    target_path = checked(public_hybrid_index_path(new))
    print(f"Target index path: {target_path.name}")

    if target_path.exists():
        existing = json.loads(target_path.read_text(encoding="utf-8"))
        if existing.get("fingerprint") == new.fingerprint:
            new.load_vectors(existing)
            print(json.dumps({"status": "already_built", "path": str(target_path)}, indent=2))
            return

    vectors, reused, new_embedded = [], 0, 0
    print(f"Processing {len(new.children)} child chunks for new index...")

    for idx, child in enumerate(new.children):
        key = (child["id"], hashlib.sha256(child["index_text"].encode()).hexdigest())
        if key in lookup:
            vectors.append(list(lookup[key]))
            reused += 1
        else:
            emb = await new.embed_query(child["index_text"])
            validated = validate_embedding_vector(
                emb.values,
                new.embedding_profile,
                model_id=emb.model_id,
                model_revision=emb.model_revision,
            )
            vectors.append(list(validated.values))
            new_embedded += 1
            if new_embedded % 5 == 0 or new_embedded == 1:
                print(f"  Embedded {new_embedded} new chunks via TEI BGE-M3 (total children {idx+1}/{len(new.children)})...")

    manifest = {
        "fingerprint": new.fingerprint,
        "child_ids": [c["id"] for c in new.children],
        "index_text_sha256": [hashlib.sha256(c["index_text"].encode()).hexdigest() for c in new.children],
        "vectors": vectors,
        "model_id": new.embedding_profile.model_id,
        "model_revision": new.embedding_profile.model_revision,
        "contextual_index": "trusted_title_section_and_source_bound_question_aliases",
        "source_text_unchanged": True,
        "predecessor_fingerprint": old.fingerprint,
        "predecessor_file_sha256": hashlib.sha256(pred_path.read_bytes()).hexdigest(),
        "reused_hash_verified_children": reused,
        "new_real_embeddings": new_embedded,
        "created_at": datetime.now(UTC).isoformat(),
    }
    new.load_vectors(manifest)
    save(target_path, manifest)

    receipt = {k: v for k, v in manifest.items() if k not in {"vectors", "child_ids", "index_text_sha256"}}
    receipt.update(
        path=str(target_path),
        parent_rows=len(new.rows),
        child_vectors=len(new.children),
        legacy_rows=len(new.legacy_rows),
    )
    receipt_dir = ROOT / ".tooling/huce-continuation-20261020-01"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    save(receipt_dir / "index-build-full-verified-20261021.json", receipt)
    print("Index build complete!")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
