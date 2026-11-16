"""Probe newly added services and batch3 verified curricula."""
import asyncio
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "services/api/src"), str(ROOT / "scripts")]
from scripts.public_rag_retrieval import load_public_hybrid_store
from scripts.huce_source_registry import save
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy


async def main():
    store = load_public_hybrid_store(
        ROOT / "data/huce-public-20261013",
        tenant_id="HUCE",
        campus_id="HUCE",
        faq_directory=ROOT / "data/huce-faq-20261013",
    )
    context = RetrievalContext(
        AuthorizedScope("HUCE", "HUCE", "actor", frozenset({"STUDENT"}),
                        frozenset({"STUDENT"}), frozenset({"PUBLIC"}), frozenset({"PUBLIC"})),
        "vi", datetime.now(UTC), SimulationPolicy.DENY, "1" * 32
    )

    queries = [
        "Mượn trả giáo trình thư viện ở tầng mấy?",
        "Hồ sơ đề nghị miễn giảm học phí gồm những giấy tờ gì và nộp ở đâu?",
        "Tiêu chuẩn xét học bổng STEM Quỹ Châu Á cần GPA bao nhiêu?",
        "Quy trình đánh giá điểm rèn luyện của sinh viên gồm mấy bước?",
        "Có chứng chỉ IELTS bao nhiêu thì được miễn học tiếng Anh và quy đổi điểm 10?",
        "Thủ tục nhập học cho tân sinh viên Khóa 71 gồm những bước nào?",
        "Ngành Kiến trúc K71 cần học bao nhiêu tín chỉ?",
        "Kỹ thuật xây dựng chuyên ngành Kỹ thuật đô thị K71 cần bao nhiêu tín chỉ?",
        "Ngành Công nghệ đa phương tiện cần bao nhiêu tín chỉ?",
    ]

    results = []
    print(f"Testing {len(queries)} queries against index {store.fingerprint[:12]}...")
    for q in queries:
        rows = await store.search(q, context)
        top = rows[0] if rows else None
        read = await store.read(top["source_id"], top["document_version_id"], top["chunk_id"], context=context) if top else None
        readback_ok = bool(read and read.content_text == top["content_text"] and
                           hashlib.sha256(read.content_text.encode()).hexdigest() == read.content_sha256)
        results.append({
            "query": q,
            "top_title": top["title"] if top else None,
            "section": top["section_path"] if top else None,
            "readback_verified": readback_ok,
            "sample_content": top["content_text"][:200] if top else None
        })
        print(json.dumps({
            "query": q,
            "top_title": top["title"] if top else None,
            "section": top["section_path"] if top else None,
            "readback": readback_ok
        }, ensure_ascii=False))

    out_p = ROOT / ".tooling/huce-continuation-20261020-01" / f"probe-new-services-{datetime.now(UTC).strftime('%H%M%S')}.json"
    save(out_p, {
        "fingerprint": store.fingerprint,
        "total_queries": len(queries),
        "all_readback_verified": all(r["readback_verified"] for r in results),
        "results": results
    })
    print(f"Saved probe results to {out_p}")


if __name__ == "__main__":
    asyncio.run(main())
