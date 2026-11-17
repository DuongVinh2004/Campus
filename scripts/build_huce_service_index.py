"""Add a reviewed service release using a fully validated retained predecessor."""
import asyncio
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "services/api/src")]
from scripts.public_rag_retrieval import create_public_hybrid_store, public_hybrid_index_path
from scripts.huce_source_registry import checked, save
from campus247.ports.embedding import validate_embedding_vector


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("services", "course-review", "withdrawal"), default="services")
    args = parser.parse_args()
    def create(services, courses, withdrawal):
        return create_public_hybrid_store(ROOT / "data/huce-public-20261013", tenant_id="huce-local-public",
            campus_id="HUCE", faq_directory=ROOT / "data/huce-faq-20261013", include_reviewed_services=services,
            include_reviewed_course_review=courses, include_reviewed_withdrawal=withdrawal)
    phases = {"services": ((False, False, False), (True, False, False)),
              "course-review": ((True, False, False), (True, True, False)),
              "withdrawal": ((True, True, False), (True, True, True))}
    old, new = (create(*flags) for flags in phases[args.phase])
    previous = checked(public_hybrid_index_path(old))
    before = json.loads(previous.read_text(encoding="utf-8"))
    old.load_vectors(before)
    hashes = [hashlib.sha256(c["index_text"].encode()).hexdigest() for c in old.children]
    if before.get("index_text_sha256") != hashes or old.embedding_profile != new.embedding_profile:
        raise ValueError("predecessor content/config mismatch")
    lookup = {(c["id"], h): v for c, h, v in zip(old.children, hashes, old.vectors, strict=True)}
    target = checked(public_hybrid_index_path(new))
    if target.exists():
        new.load_vectors(json.loads(target.read_text(encoding="utf-8")))
        print(json.dumps({"validated_existing": str(target)})); return
    vectors, reused = [], 0
    for child in new.children:
        key = child["id"], hashlib.sha256(child["index_text"].encode()).hexdigest()
        if key in lookup:
            vectors.append(list(lookup[key])); reused += 1
        else:
            output = await new.embed_query(child["index_text"])
            vectors.append(list(validate_embedding_vector(output.values, new.embedding_profile,
                model_id=output.model_id, model_revision=output.model_revision).values))
    manifest = {"fingerprint": new.fingerprint, "child_ids": [c["id"] for c in new.children],
        "index_text_sha256": [hashlib.sha256(c["index_text"].encode()).hexdigest() for c in new.children],
        "vectors": vectors, "model_id": new.embedding_profile.model_id, "model_revision": new.embedding_profile.model_revision,
        "contextual_index": "trusted_title_section_and_source_bound_question_aliases", "source_text_unchanged": True,
        "predecessor_fingerprint": old.fingerprint, "predecessor_file_sha256": hashlib.sha256(previous.read_bytes()).hexdigest(),
        "reused_hash_verified_children": reused, "new_real_embeddings": len(vectors)-reused}
    new.load_vectors(manifest)
    save(target, manifest)
    receipt = {k: v for k, v in manifest.items() if k not in {"vectors", "child_ids", "index_text_sha256"}}
    receipt.update(path=str(target), parent_rows=len(new.rows), child_vectors=len(new.children))
    receipt_name = "index-build.json" if args.phase == "services" else "index-build-" + args.phase + ".json"
    save(ROOT / ".tooling/huce-continuation-20261020-01" / receipt_name, receipt)
    print(json.dumps(receipt), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
