"""Append-only work dispositions for each of the 117 retained public sources."""
import asyncio
import json
from collections import Counter

from complete_huce_corpus import SCOPE, actors, read
from knowledge_platform import ROOT, TENANT, components, retain
from campus247.application.knowledge.platform_models import digest
from campus247.domain.shared.values import generate_uuid7


async def main():
    plan = read(SCOPE / "candidate-plan-04.json")
    inventory = read(SCOPE / "inventory-01.json")
    versions = {row["source_id"]: row for row in inventory["versions"]}
    entries = {row["source_id"]: row for row in plan["sources"]}
    assert len(entries) == 117 and set(entries) == {row["source_id"] for row in inventory["sources"]}
    pool, _, platform, _ = await components(); _, owner = actors(); platform.admin(owner)
    results = []
    try:
        for entry in plan["sources"]:
            candidate = read(ROOT / entry["candidate"]) if entry["status"] == "PREPARED" else None
            original = candidate["original_sha256"] if candidate else versions[entry["source_id"]]["original_sha256"]
            category = "SOURCE_TEXT_AVAILABLE"; related = entry.get("related_source_id")
            evidence = {"plan": "candidate-plan-04.json", "candidate_sha256": entry.get("candidate_sha256"),
                "source_id": entry["source_id"], "original_sha256": original, "university_approval_claimed": False}
            if entry["status"] == "SERVING_UNCHANGED":
                note = "Giữ nguyên phiên bản đã phục vụ; không thay bằng bản nhập cũ. Nguồn và giới hạn đã kiểm ở đợt phục hồi runtime."
            elif entry["status"] == "EQUIVALENT_SOURCE_ALIAS":
                assert original == versions[related]["original_sha256"]
                category = "EQUIVALENT_SOURCE_ALIAS"; note = entry["reason"]
                evidence["same_original_sha256_verified"] = True
            elif entry["status"] == "LINKED_SOURCE_ALIAS":
                async with pool.acquire() as conn:
                    row = await platform.repo.version(conn, versions[entry["source_id"]]["version_id"])
                    artifact = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1", row["original_id"])
                raw = platform.storage.read(artifact)
                linked = entries[related]["uri"]
                bound = linked.encode() in raw
                category = "EQUIVALENT_SOURCE_ALIAS" if bound else "LINKED_ORIGINAL_REQUIRED"
                note = entry["reason"] + (" Đã kiểm URI PDF xuất hiện trong HTML gốc." if bound else " Cần đối soát trực tiếp URI iframe với bản PDF trước khi gộp trạng thái trang công bố.")
                evidence.update(linked_uri=linked, direct_link_verified=bound)
            elif candidate:
                scope = candidate["applicability"]
                evidence["applicability"] = scope
                if scope["kind"] == "COHORT_SNAPSHOT":
                    category = "PARTIAL_SOURCE_TEXT" if scope["cohorts"] else "SOURCE_SCOPE_UNRESOLVED"
                    note = ("Đã lập chỉ mục bản chữ gốc; khóa đối chiếu: " + ", ".join(scope["cohorts"]) + ". " if scope["cohorts"] else
                        "Đã lập chỉ mục bản chữ gốc nhưng chưa chứng minh được khóa áp dụng; chặn câu hỏi gán khóa cụ thể. ")
                    note += "Chưa xác minh đầy đủ các ô và mũi tên tiên quyết/song hành; không dùng bản chữ để suy ra các quan hệ này."
                else:
                    partial = scope.get("omitted_sparse_pages") or scope.get("limitations") or scope["kind"] == "LEGAL_EFFECT"
                    category = "PARTIAL_SOURCE_TEXT" if partial else "SOURCE_TEXT_AVAILABLE"
                    note = "Đã đối chiếu hash và lập chỉ mục nội dung bản nguồn; chỉ trả lời trong các trang/đoạn đã chọn, không xác nhận thay đổi sau bản lưu."
                    if scope.get("academic_years"): note += " Năm học: " + ", ".join(scope["academic_years"]) + "; không áp dụng thời hạn lịch sử cho năm hiện tại."
                    if partial: note += " Còn phần ngoài bản chữ đã chọn: " + "; ".join(scope.get("limitations", [])) + ("; trang ít chữ/ảnh " + str(scope["omitted_sparse_pages"]) if scope.get("omitted_sparse_pages") else "")
            else:
                raise ValueError("Unclassified source")
            result = {"source_id": entry["source_id"], "original_sha256": original, "category": category,
                "related_source_id": related, "note": note, "evidence": evidence}
            fingerprint = digest(result)
            async with platform.repo.transaction() as conn:
                key = "corpus-disposition-20261024:" + entry["source_id"]
                replay = await platform.repo.replay(conn, owner.subject_id, key, fingerprint)
                if not replay:
                    identifier = generate_uuid7()
                    await conn.execute("""INSERT INTO knowledge_source_disposition(id,tenant_id,source_id,original_sha256,category,
                        related_source_id,note,evidence,created_by) VALUES($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9)""",
                        identifier, TENANT, result["source_id"], original, category, related, note, json.dumps(evidence), owner.subject_id)
                    await platform.repo.audit(conn, owner.subject_id, "knowledge.source.classified", entry["source_id"],
                        {"disposition_id": identifier, "category": category, "original_sha256": original})
                    await platform.repo.remember(conn, owner.subject_id, key, fingerprint, {"id": identifier})
            results.append(result)
        retain(SCOPE / "source-dispositions-01.json", {"sources": results, "counts": dict(Counter(row["category"] for row in results))})
        print(json.dumps({"classified": len(results), "counts": dict(Counter(row["category"] for row in results))}))
    finally: await pool.close()


if __name__ == "__main__": asyncio.run(main())
