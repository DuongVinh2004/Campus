"""Probe the retained notice additions and all prior STEM form questions."""
import argparse
import asyncio
from datetime import UTC, datetime

from complete_huce_corpus import actors
from continue_huce_completion_20261025 import CORPUS, OUT, read, save, sha
from knowledge_platform import TENANT, components
from prepare_huce_stem_full_second import STEM
from verify_huce_stem_forms_second import CASES
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy

DETAIL_CASES = [
    ("stem_notice_heading", "Theo thông báo học bổng STEM Quỹ Châu Á năm học 2025-2026, số văn bản và ngày ban hành in trên bản gốc là gì?", ["46/TB-ĐHXDHN-CTSV", "30 tháng 01 năm 2026"], True),
    ("stem_notice_recitals", "Theo thông báo học bổng STEM Quỹ Châu Á năm học 2025-2026, ba căn cứ mở đầu ghi những ngày nào?", ["24/10/2023", "12/01/2026", "27/01/2026"], True),
    ("stem_notice_contact", "Theo thông báo học bổng STEM Quỹ Châu Á năm học 2025-2026, thông tin liên hệ được in ở cuối thông báo là gì?", ["0964245028", "thuymt@huce.edu.vn"], True),
    ("stem_notice_recipients", "Theo thông báo học bổng STEM Quỹ Châu Á năm học 2025-2026, mục Nơi nhận liệt kê những nơi nào?", ["Như trên", "Ban Giám hiệu", "huce.edu.vn", "VT, CTSV"], True),
    ("stem_notice_signatory", "Theo thông báo học bổng STEM Quỹ Châu Á năm học 2025-2026, chức danh và họ tên in dưới chữ ký là gì?", ["PHÓ TRƯỞNG PHÒNG", "Nguyễn Đình Huy"], True),
    ("stem_notice_contact_wrong_year", "Theo thông báo học bổng STEM Quỹ Châu Á năm học 2026-2027, số điện thoại và email liên hệ là gì?", [], False),
    ("stem_notice_recitals_wrong_year", "Theo thông báo học bổng STEM Quỹ Châu Á năm học 2026-2027, ba căn cứ mở đầu ghi những ngày nào?", [], False),
]


async def main(attempt, number="30"):
    release = read(CORPUS / f"candidate-release-{number}.json")
    version = next(m["version_id"] for m in release["members"] if m["source_id"] == STEM)
    pool, _, _, runtime = await components()
    _, owner = actors()
    roles = frozenset(r.value for r in owner.roles)
    context = RetrievalContext(AuthorizedScope(TENANT, "HUCE", owner.subject_id, roles, roles,
        frozenset({"FIT"}), frozenset({"PUBLIC"})), "vi", datetime.now(UTC), SimulationPolicy.DENY, "d" * 32)
    rows = []
    try:
        for name, question, terms, expected in CASES + DETAIL_CASES:
            items = await runtime.preview_search(owner, question, context, release["release_id"])
            own = [r for r in items if r["document_version_id"] == version]
            passed = any(all(t in r["content_text"] for t in terms) for r in own) if expected else not own
            passed &= all(sha(r["content_text"].encode()) == r["evidence_sha256"] for r in items)
            rows.append({"name": name, "question": question, "expected_terms": terms, "expected_present": expected,
                "passed": bool(passed), "expected_version": version, "items": items})
            print({"name": name, "passed": bool(passed)}, flush=True)
        save(OUT / f"stem-notice-details-candidate-probes-{attempt}.json", {"release_id": release["release_id"],
            "cases": rows, "count": len(rows), "passed": sum(r["passed"] for r in rows),
            "all_passed": all(r["passed"] for r in rows), "activation_claimed": False})
    finally:
        await pool.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", choices=("01", "02", "03", "04", "05", "06"), default="01")
    parser.add_argument("--release", choices=("30", "31", "32"), default="30")
    args = parser.parse_args()
    asyncio.run(main(args.attempt, args.release))
