"""Real BGE retrieval and citation readback; this is not UI/generation evidence."""
import asyncio
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "services/api/src")]
from scripts.public_rag_retrieval import load_public_hybrid_store
from scripts.huce_source_registry import save
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy


async def main():
    store = load_public_hybrid_store(ROOT / "data/huce-public-20261013", tenant_id="HUCE", campus_id="HUCE",
                                    faq_directory=ROOT / "data/huce-faq-20261013")
    context = RetrievalContext(AuthorizedScope("HUCE", "HUCE", "actor", frozenset({"STUDENT"}),
        frozenset({"STUDENT"}), frozenset({"PUBLIC"}), frozenset({"PUBLIC"})),
        "vi", datetime.now(UTC), SimulationPolicy.DENY, "1" * 32)
    results = []
    for question in ["học phí đang là bao nhiêu", "một tín chỉ bao nhiêu tiền", "học kỹ sư cần bao nhiêu tín",
                     "ky su can may tin", "kỹ sư CNTT K71 cần bao nhiêu tín chỉ, có tính giáo dục thể chất không?",
                     "học kỹ sư xây dựng dân dụng K69 cần bao nhiêu tín chỉ?", "K69 đóng bao nhiêu", "học lại tính thế nào"]:
        try:
            rows = await store.search(question, context)
            evidence = []
            for row in rows:
                read = await store.read(row["source_id"], row["document_version_id"], row["chunk_id"], context=context)
                valid = read is not None and read.content_text == row["content_text"] and hashlib.sha256(read.content_text.encode()).hexdigest() == read.content_sha256
                evidence.append({k: row[k] for k in ("title", "canonical_uri", "section_path", "page_start", "score")})
                evidence[-1]["readback_hash_verified"] = valid
            results.append({"question": question, "results": evidence})
        except Exception as exc:
            results.append({"question": question, "error": type(exc).__name__ + ": " + str(exc)})
    output = ROOT / ".tooling/huce-expansion-20261020-01" / ("retrieval-" + datetime.now(UTC).strftime("%H%M%S%f") + ".json")
    save(output, {"index": store.fingerprint, "real_models": True, "cases": results})
    print(json.dumps({"report": str(output), "cases": results}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
