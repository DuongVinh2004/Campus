"""Append-only candidate retrieval probes through the real release runtime."""
import argparse
import asyncio
import json
import re
import time
from datetime import UTC, datetime

from complete_huce_corpus import SCOPE, actors, read
from knowledge_platform import ROOT, TENANT, checked_path, components, retain
from campus247.application.knowledge.platform_models import digest
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy


async def main(attempt, failed_only=False, changed_totals=False):
    release = read(SCOPE / "candidate-release-04.json")
    plan = read(SCOPE / "candidate-plan-04.json")
    entries = {row["source_id"]: row for row in plan["sources"]}
    failed = set(read(SCOPE / "retrieval-probes-03/summary.json")["failed"]) if failed_only else None
    if changed_totals:
        from campus247.application.knowledge.curriculum_excerpt import printed_total_excerpt
        failed = set(read(SCOPE / "retrieval-probes-08/summary.json")["failed"])
        for entry in plan["sources"]:
            if entry["status"] != "PREPARED": continue
            candidate = read(ROOT / entry["candidate"])
            for page in candidate["pages"]:
                if (not re.search(r"(?mi)^\s*Tổng\s*:\s*\d", page["text"])
                        and printed_total_excerpt(page["text"], "Tổng số tín chỉ TC?")):
                    failed.add(entry["source_id"])
    folder = checked_path(SCOPE / ("retrieval-probes-" + attempt), ROOT); folder.mkdir(exist_ok=False)
    pool, _, platform, runtime = await components()
    _, owner = actors()
    roles = frozenset(role.value for role in owner.roles)
    context = RetrievalContext(AuthorizedScope(TENANT, "HUCE", owner.subject_id, roles, roles, frozenset({"FIT"}),
        frozenset({"PUBLIC"})), "vi", datetime.now(UTC), SimulationPolicy.DENY, "a" * 32)
    try:
        for member in release["members"]:
            if failed is not None and member["source_id"] not in failed:
                continue
            entry = entries[member["source_id"]]
            title = entry["title"]
            candidate = read(ROOT / entry["candidate"]) if entry.get("candidate") else None
            if candidate and candidate["applicability"]["kind"] == "COHORT_SNAPSHOT":
                title = re.sub(r"^(?:K\d{2}|K70_and_earlier_verify_individual_row)\s*[—–-]\s*", "", title)
                title = re.sub(r"^Kế hoạch giảng dạy.*?(?:—\s*)?Ngành\s+", "", title, flags=re.I)
                scope = candidate["applicability"]
                title += " " + " ".join(scope.get("cohorts", []) + scope.get("programme_codes", []))
            query = ("Các học phần và số tín chỉ của " + title + "?") if candidate and candidate["applicability"]["kind"] == "COHORT_SNAPSHOT" else title + " có nội dung gì?"
            if member["source_id"] == "c56e7a4c-b1c4-7a66-8132-24fe88db8ecc":
                query = "Hạn nộp hồ sơ miễn giảm học phí học kỳ I năm học 2025-2026 theo thông báo 1106?"
            if member["source_id"] == "129ba0a6-652e-70b8-8532-8e63661262ce":
                query = "Học bổng STEM Quỹ Châu Á 2025-2026 có mức tiền và điều kiện gì?"
            alternatives = {
                "55df8e8c-00d5-716a-8b1c-9bc5a74d46a1": "Theo sổ tay sinh viên 2026-2027, có được tự ý đổi chỗ ở trong ký túc xá không?",
                "897021bc-ba08-72a7-859f-6e76d2bb206d": "Quy định phân loại trình độ đầu vào và chuẩn ngoại ngữ được ban hành theo Quyết định số nào ngày 13/01/2026?",
                "d7a2d4ed-3047-7e2e-86a1-86569ca2e60c": "Mẫu đơn xin miễn giảm học phí có phần điền số tài khoản và ngân hàng không?",
                "e417f8f1-8615-7d8c-8a75-f7a7cc3a83c9": "Theo hướng dẫn dịch vụ thư viện HUCE, mượn trả giáo trình ở tầng mấy?",
                "df5e9d5d-b5aa-7c5a-8097-995386d0c3cb": "Báo cáo FIT_CMA2026 về ảnh hưởng vùng tiếp xúc ITZ nghiên cứu sự khởi phát và lan truyền vết nứt bằng mô hình nào?",
                "d0c02f97-cdd6-7d9e-8738-55b26b0839b8": "Chương trình kỹ sư kỹ thuật xây dựng hợp tác với Mississippi tương đương chuyên ngành nào?",
            }
            query = alternatives.get(member["source_id"], query)
            started = time.perf_counter()
            try:
                rows = await runtime.preview_search(owner, query, context, release["release_id"])
                result = {"source_id": member["source_id"], "query": query, "expected_version": member["version_id"],
                    "found": any(row["document_version_id"] == member["version_id"] for row in rows),
                    "hashes_verified": all(digest(row["content_text"].encode()) == row["evidence_sha256"] for row in rows), "items": rows}
            except Exception as error:
                result = {"source_id": member["source_id"], "query": query, "found": False, "error": type(error).__name__ + ": " + str(error)}
            result["latency_seconds"] = round(time.perf_counter() - started, 3)
            retain(folder / (member["source_id"] + ".json"), result)
            print(json.dumps({k: result.get(k) for k in ("source_id", "found", "error", "latency_seconds")}), flush=True)
        results = [read(path) for path in folder.glob("*.json")]
        retain(folder / "summary.json", {"release_id": release["release_id"], "tested": len(results),
            "found": sum(row["found"] for row in results), "failed": [row["source_id"] for row in results if not row["found"]],
            "qualification": "Source-title retrieval probes; not proof of every real-world question or diagram relationship"})
    finally:
        await pool.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("attempt"); parser.add_argument("--failed-only", action="store_true")
    parser.add_argument("--changed-totals", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"\d{2}", args.attempt): raise ValueError("Exact numbered attempt required")
    asyncio.run(main(args.attempt, args.failed_only, args.changed_totals))
