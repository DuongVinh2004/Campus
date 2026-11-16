"""Real retrieval/readback cases; no claim of end-to-end answer correctness."""
import asyncio
import argparse
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--changed-only", action="store_true")
    args = parser.parse_args()
    store = load_public_hybrid_store(ROOT / "data/huce-public-20261013", tenant_id="HUCE", campus_id="HUCE",
                                    faq_directory=ROOT / "data/huce-faq-20261013")
    context = RetrievalContext(AuthorizedScope("HUCE", "HUCE", "actor", frozenset({"STUDENT"}),
        frozenset({"STUDENT"}), frozenset({"PUBLIC"}), frozenset({"PUBLIC"})),
        "vi", datetime.now(UTC), SimulationPolicy.DENY, "1" * 32)
    cases = []
    questions = ["Cài Office 365 bằng tài khoản trường như thế nào?", "cai office bang tai khoan truong",
                 "Quản lý dự án K71 cần bao nhiêu tín chỉ?",
                 "Quản lý dự án K71 học kỳ 1 có môn Môi trường và phát triển bền vững không?",
                 "học phí đang là bao nhiêu", "một tín chỉ bao nhiêu tiền", "học kỹ sư cần bao nhiêu tín",
                 "ky su CNTT K71 can bao nhieu tin chi?", "K69 chương trình kỹ sư một tín bao nhiêu tiền?",
                 "Em muốn rút học phần thì phải làm thế nào?", "Em muốn bảo lưu rồi trở lại học thì phải làm sao?"]
    if args.changed_only:
        questions = [q for q in questions if "Quản lý dự án" in q or "rút học phần" in q]
    for question in questions:
        case = {"question": question}
        try:
            rows = await store.search(question, context)
            case["results"] = []
            for row in rows:
                read = await store.read(row["source_id"], row["document_version_id"], row["chunk_id"], context=context)
                case["results"].append({**{k: row[k] for k in ("title", "canonical_uri", "section_path", "page_start", "content_text")},
                    "readback_hash_verified": bool(read and read.content_text == row["content_text"] and
                        hashlib.sha256(read.content_text.encode()).hexdigest() == read.content_sha256)})
        except Exception as exc:
            case["error"] = type(exc).__name__ + ": " + str(exc)
        cases.append(case)
        print(json.dumps({"question": question, "top": case.get("results", [{}])[0].get("title") if case.get("results") else None,
                          "error": case.get("error")}, ensure_ascii=False), flush=True)
    output = ROOT / ".tooling/huce-continuation-20261020-01" / ("retrieval-" + datetime.now(UTC).strftime("%H%M%S%f") + ".json")
    save(output, {"fingerprint": store.fingerprint, "real_models": True, "cases": cases,
                  "limitation": "retrieval and readback only, not generated answers or UI"})
    print(str(output), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
