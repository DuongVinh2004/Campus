"""Append current evidence dispositions without promoting incomplete sources."""
import asyncio
import json
from collections import Counter
from contextlib import closing
from datetime import UTC, datetime

from audit_huce_rag_20261023 import API, client
from complete_huce_corpus import actors
from continue_huce_completion_20261025 import CORPUS, OLD, OUT, REGULATION, ROOT, read, save, sha
from knowledge_platform import TENANT, components
from review_huce_curriculum_geometry import MULTIMEDIA
from campus247.application.knowledge.platform_models import digest
from campus247.domain.shared.values import generate_uuid7


async def main():
    release = read(CORPUS / "candidate-release-13.json")
    with closing(client()) as c:
        response = c.get(API+"/state"); response.raise_for_status(); state = response.json()
        assert state["desired"]["release_id"] == release["release_id"] and state["is_serving"]
        response = c.get(API+"/availability"); response.raise_for_status(); availability = response.json()
    dispositions = read(OLD / "source-dispositions-final-01.json")
    statuses = read(OLD / "source-status-final-01.json")
    plan = {r["source_id"]: r for r in read(CORPUS / "candidate-plan-13.json")["sources"]}
    members = {r["source_id"]: r for r in release["members"]}
    notes = {
        REGULATION: "Đã đối chiếu toàn bộ phần thân Quy chế 1486 ở PDF 2–26, 21 điều/95 đơn vị, 15 đoạn nối trang; giữ trang quyết định và ngày hiệu lực đã đối chiếu. Các phụ lục được dẫn nhưng không có trong PDF vẫn chưa có chứng cứ; không suy phiên bản sửa đổi mới nhất.",
        MULTIMEDIA: "71CNDPT K71: đã đối chiếu 60 ô môn/nhóm, bảy cột học kỳ và 13 đường nối trên PDF 1; giữ chữ viết tắt, hai nhóm tự chọn và tổng in sẵn 130TC có loại trừ. Không suy số phương án phải chọn hoặc danh mục tự chọn riêng chưa có; không lấy số trong tên GDTC/GDQP làm tín chỉ.",
    }
    pool, _, platform, _ = await components(); _, owner = actors(); platform.admin(owner)
    try:
        for row in dispositions["sources"]:
            identifier = row["source_id"]
            if identifier not in notes:
                continue
            entry = plan[identifier]; candidate = read(ROOT/entry["candidate"])
            row.update(category="PARTIAL_SOURCE_TEXT", note=notes[identifier], evidence={
                "candidate": entry["candidate"], "candidate_sha256": entry["candidate_sha256"],
                "release_id": release["release_id"], "version_id": members[identifier]["version_id"],
                "applicability": candidate["applicability"], "university_approval_claimed": False})
            async with platform.repo.transaction() as conn:
                key = "completion-20261025-02-disposition:"+identifier; fingerprint = digest(row)
                if not await platform.repo.replay(conn, owner.subject_id, key, fingerprint):
                    new_id = generate_uuid7()
                    await conn.execute("""INSERT INTO knowledge_source_disposition(id,tenant_id,source_id,original_sha256,category,
                        related_source_id,note,evidence,created_by) VALUES($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9)""",
                        new_id, TENANT, identifier, row["original_sha256"], row["category"], row["related_source_id"],
                        row["note"], json.dumps(row["evidence"]), owner.subject_id)
                    await platform.repo.audit(conn, owner.subject_id, "knowledge.source.classified", identifier,
                        {"disposition_id": new_id, "category": row["category"]})
                    await platform.repo.remember(conn, owner.subject_id, key, fingerprint, {"id": new_id})
        for row in statuses["sources"]:
            if row["source_id"] in members:
                row["serving_version"] = members[row["source_id"]]["version_id"]
            if row["source_id"] in notes:
                row["verified_limit"] = notes[row["source_id"]]
        counts = dict(Counter(r["category"] for r in dispositions["sources"]))
        dispositions["counts"] = counts
        save(OUT / "source-dispositions-01.json", dispositions)
        save(OUT / "source-status-01.json", statuses)
        remaining = [r for r in statuses["sources"] if r["category"] in {"PARTIAL_SOURCE_TEXT", "SOURCE_SCOPE_UNRESOLVED"}]
        save(OUT / "remaining-evidence-worklist-02.json", {"sources": remaining, "count": len(remaining),
            "unresolved_specific_cohort_count": 7, "all_content_complete": False,
            "new_geometry_candidates": "curriculum-cell-candidates-01.json",
            "source_geometry_review_admitted": [MULTIMEDIA], "regulation_body_admitted": True})
        save(OUT / "progress-receipt-01.json", {"at": datetime.now(UTC), "desired": state["desired"],
            "availability": availability, "source_counts": counts, "all_remaining_work_complete": False,
            "regulation_body_units": 95, "regulation_cross_page_parents": 15,
            "geometry_material_sources": 93, "geometry_material_pages": 321,
            "curriculum_candidate_sources": 87, "candidate_course_entries_unreviewed": 6258,
            "reviewed_multimedia_cells": 60, "reviewed_multimedia_edges": 13,
            "sso_and_real_academic_api": "not_connected_missing_HUCE_configuration_and_grants",
            "integrity": {"file": "candidate-integrity-08.json", "sha256": sha((CORPUS/"candidate-integrity-08.json").read_bytes())}})
        print({"source_counts": counts, "limited_sources": len(remaining), "all_complete": False})
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
