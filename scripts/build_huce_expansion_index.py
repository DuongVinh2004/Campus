"""Reuse only a reconstructed, fingerprint-validated predecessor; embed new bytes with BGE."""
import asyncio
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "services/api/src")]
from scripts.public_rag_retrieval import create_public_hybrid_store, public_hybrid_index_path
from campus247.ports.embedding import validate_embedding_vector
from scripts.huce_source_registry import checked, save


def create(include):
    return create_public_hybrid_store(ROOT / "data/huce-public-20261013", tenant_id="huce-local-public", campus_id="HUCE",
        faq_directory=ROOT / "data/huce-faq-20261013", include_reviewed_expansion=include)


async def main():
    old, new = create(False), create(True)
    previous_path = checked(public_hybrid_index_path(old))
    predecessor = json.loads(previous_path.read_text(encoding="utf-8"))
    old.load_vectors(predecessor)  # full corpus/config fingerprint and vector dimensions
    if old.embedding_profile != new.embedding_profile:
        raise ValueError("model/config drift")
    lookup = {(child["id"], hashlib.sha256(child["index_text"].encode()).hexdigest()): vector
              for child, vector in zip(old.children, old.vectors, strict=True)}
    target = checked(public_hybrid_index_path(new))
    if target.exists():
        new.load_vectors(json.loads(target.read_text(encoding="utf-8")))
        print(json.dumps({"validated_existing": str(target)})); return
    vectors, reused = [], 0
    for child in new.children:
        binding = (child["id"], hashlib.sha256(child["index_text"].encode()).hexdigest())
        if binding in lookup:
            vectors.append(list(lookup[binding])); reused += 1
        else:
            output = await new.embed_query(child["index_text"])
            vectors.append(list(validate_embedding_vector(output.values, new.embedding_profile,
                model_id=output.model_id, model_revision=output.model_revision).values))
    manifest = {"fingerprint": new.fingerprint, "child_ids": [c["id"] for c in new.children],
        "index_text_sha256": [hashlib.sha256(c["index_text"].encode()).hexdigest() for c in new.children],
        "vectors": vectors, "model_id": new.embedding_profile.model_id, "model_revision": new.embedding_profile.model_revision,
        "contextual_index": "trusted_title_section_and_source_bound_question_aliases", "source_text_unchanged": True,
        "predecessor_fingerprint": old.fingerprint, "predecessor_file_sha256": hashlib.sha256(previous_path.read_bytes()).hexdigest(),
        "reused_hash_verified_children": reused, "new_real_embeddings": len(vectors) - reused}
    new.load_vectors(manifest)
    save(target, manifest)
    receipt = {k: v for k, v in manifest.items() if k not in {"vectors", "child_ids", "index_text_sha256"}}
    receipt["path"] = str(target)
    save(ROOT / ".tooling/huce-expansion-20261020-01/index-build.json", receipt)
    print(json.dumps(receipt), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
