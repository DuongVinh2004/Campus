"""Verify and publish this exact six-source batch via normal application controls."""
import argparse
import asyncio
import json
import time
from contextlib import closing
from datetime import UTC, datetime

from audit_huce_rag_20261023 import API, client
from complete_huce_corpus import SCOPE, actors, read
from knowledge_platform import ROOT, TENANT, components, retain
from prepare_huce_evidence_20261025 import CALENDAR, OUT, REGULATION, SHARED
from campus247.application.knowledge.platform_models import digest
from campus247.application.knowledge.source_snapshot import read_snapshot, scope_allows
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy
from campus247.domain.shared.values import generate_uuid7


async def probes(attempt):
    release = read(SCOPE / "candidate-release-07.json")
    targets = {r["source_id"]: r["version_id"] for r in release["members"]}
    questions = [
        ("4b89bce7-4935-713b-8747-f97a0853d726", "Sơ đồ cấu trúc kỹ sư Kỹ thuật xây dựng chuyên ngành Xây dựng DD&CN K71 có học phần Triết học Mác Lê Nin không?", True),
        ("8da40ef9-1850-7fa5-878d-86a2eb357674", "Khung chương trình ngành Kiến trúc K71 phiên bản 2025 ghi học phần Giới thiệu ngành kiến trúc như thế nào?", True),
        ("bc455d2c-2b63-734f-8f60-7796c9635290", "Kế hoạch đào tạo ngành Kinh tế xây dựng K71 năm 2025 có những học phần tự chọn bắt buộc HPTCBB nào?", True),
        ("dc43e7f5-466f-7ce3-8fe2-a10a0c809d9b", "Kế hoạch kỹ sư Công nghệ kỹ thuật vật liệu xây dựng K71 năm 2025 chú giải X và Y của mã HP là gì?", True),
        ("dc43e7f5-466f-7ce3-8fe2-a10a0c809d9b", "Theo kế hoạch kỹ sư Công nghệ kỹ thuật vật liệu xây dựng K71 bản 2025, X và Y trong chú giải Mã HP-X-Y là gì?", True),
        (REGULATION, "Theo Quy chế 1486, một tín chỉ tương đương bao nhiêu giờ học tập định mức?", True),
        (REGULATION, "Theo Quy chế 1486, học phần tiên quyết và học phần học trước khác nhau thế nào?", True),
        (CALENDAR, "Kế hoạch CNTT K68 năm học 2026-2027 tuần 9 ngày bắt đầu và ký hiệu là gì?", True),
        (CALENDAR, "Kế hoạch CNTT K71 năm học 2026-2027 tuần 40 ngày bắt đầu và ký hiệu là gì, có phải dự kiến không?", True),
        (CALENDAR, "Kế hoạch CNTT K67 năm học 2026-2027 tuần 9 có ký hiệu gì?", False),
        (CALENDAR, "Kế hoạch CNTT K68 năm học 2025-2026 tuần 9 có ký hiệu gì?", False),
        (CALENDAR, "Kế hoạch CNTT K68 tuần 9 có ký hiệu gì?", False),
        ("8da40ef9-1850-7fa5-878d-86a2eb357674", "Khung chương trình Kiến trúc K70 phiên bản 2025 có những môn nào?", False),
        ("4b89bce7-4935-713b-8747-f97a0853d726", "Kỹ thuật xây dựng DD&CN K71 học kỳ 1 có môn gì?", False),
        ("4b89bce7-4935-713b-8747-f97a0853d726", "Kỹ thuật xây dựng DD&CN K71 môn nào là tiên quyết Cơ học kết cấu?", False),
    ]
    pool, _, platform, runtime = await components()
    _, owner = actors()
    roles = frozenset(role.value for role in owner.roles)
    context = RetrievalContext(AuthorizedScope(TENANT, "HUCE", owner.subject_id, roles, roles,
        frozenset({"FIT"}), frozenset({"PUBLIC"})), "vi", datetime.now(UTC), SimulationPolicy.DENY, "b"*32)
    results = []
    try:
        for identifier, query, positive in questions:
            items = await runtime.preview_search(owner, query, context, release["release_id"])
            selected = [r for r in items if r["document_version_id"] == targets[identifier]]
            valid = True
            async with pool.acquire() as conn:
                version = await platform.repo.version(conn, targets[identifier])
                scope = await read_snapshot(platform, conn, version)
                for row in selected:
                    row_scope = scope.get("_evidence_scopes", {}).get(row["evidence_sha256"], scope)
                    valid &= scope_allows(query, row_scope)
                    if row.get("content_text"):
                        valid &= digest(row["content_text"].encode()) == row["evidence_sha256"]
            passed = (bool(selected) == positive) and valid
            results.append({"source_id": identifier, "expected_version": targets[identifier], "query": query,
                "expected_present": positive, "passed": passed, "items": items})
            print(json.dumps({"source_id": identifier, "passed": passed, "expected_present": positive}), flush=True)
        result = {"release_id": release["release_id"], "cases": results,
            "all_passed": all(r["passed"] for r in results), "changed_sources": sorted(SHARED | {CALENDAR, REGULATION})}
        retain(OUT / f"candidate-probes-{attempt}.json", result)
        if not result["all_passed"]:
            raise RuntimeError("Candidate retrieval did not pass; retained without activation")
    finally:
        await pool.close()


def activate(attempt):
    release = read(SCOPE / "candidate-release-07.json")
    old = read(SCOPE / "candidate-release-06.json")
    probes_result = read(OUT / f"candidate-probes-{attempt}.json")
    integrity = read(OUT / "candidate-integrity-01.json")
    assert probes_result["all_passed"] and probes_result["release_id"] == release["release_id"]
    assert integrity["all_passed"] and integrity["release_id"] == release["release_id"]
    previous = {r["source_id"]: r for r in old["members"]}
    members = {r["source_id"]: r for r in release["members"]}
    assert set(members) == set(previous) and len(members) == 114
    assert {key for key in members if previous[key] != members[key]} == SHARED | {CALENDAR, REGULATION}
    with closing(client()) as c:
        state = c.get(API + "/state").json()
        assert state["desired"]["release_id"] == old["release_id"] and state["desired"]["generation"] == 15
        response = c.post(API + "/previews", json={"operation": "activate", "target_id": release["release_id"], "expected_generation": 15})
        response.raise_for_status()
        preview = response.json()
        assert preview["payload"]["target_sha256"] == release["membership_sha256"]
        assert {r["source_id"]: r for r in preview["payload"]["members"]} == members
        retain(OUT / "activation-preview-01.json", {k: v for k, v in preview.items() if k != "confirmation_token"})
        response = c.post(API + "/confirmations", headers={"Idempotency-Key": "huce-evidence-20261025-activate-01"},
            json={"preview_id": preview["preview_id"], "confirmation_token": preview["confirmation_token"], "confirmed": True})
        response.raise_for_status()
        retain(OUT / "activation-confirmation-01.json", response.json())
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            state = c.get(API + "/state").json()
            if state["is_serving"] and state["desired"]["release_id"] == release["release_id"] and state["desired"]["generation"] == 16:
                break
            time.sleep(.5)
        else:
            raise RuntimeError("Runtime acknowledgement not verified")
        availability = c.get(API + "/availability").json()
        assert availability["serving_documents"] == 114
        retain(OUT / "activation-ready-01.json", {"at": datetime.now(UTC).isoformat(), "desired": state["desired"],
            "serving": state["serving"], "availability": availability, "unchanged_members": 108})
        print(json.dumps({"release_id": release["release_id"], "generation": 16, "serving": 114}))


async def classify():
    old = read(SCOPE / "source-dispositions-03.json")
    plan = {r["source_id"]: r for r in read(SCOPE / "candidate-plan-07.json")["sources"]}
    pool, _, platform, _ = await components()
    _, owner = actors()
    platform.admin(owner)
    try:
        for row in old["sources"]:
            identifier = row["source_id"]
            if identifier not in SHARED | {CALENDAR, REGULATION}:
                continue
            candidate = read(ROOT / plan[identifier]["candidate"])
            if identifier in SHARED:
                note = "Đã đối chiếu đúng hàng liên kết trong bảng K71 của trang công bố HUCE. Không gán K70 hoặc khóa trước chỉ từ mục chung. Giữ giới hạn nội dung, ô học kỳ và mũi tên chưa xác minh."
            elif identifier == CALENDAR:
                note = "Đã đối chiếu riêng 4 hàng CNTT K68–K71, 208 ô tuần, ngày bắt đầu và chú giải. K71 là DỰ KIẾN; yêu cầu năm học 2026–2027. Chưa xác minh các ngành khác hoặc thời khóa biểu cá nhân."
            else:
                note = "Giữ trang quyết định; bổ sung các điều khoản đã đối chiếu ảnh ở trang PDF 2–5. Có phân biệt tiên quyết/học trước/song hành bằng chữ; chưa xác minh mũi tên giữa môn. Các phần chưa trích và trang PDF 6–26 vẫn ngoài phạm vi."
            row.update(category="PARTIAL_SOURCE_TEXT", note=note,
                evidence={"candidate_sha256": plan[identifier]["candidate_sha256"],
                    "plan": "candidate-plan-07.json", "scope_review": str((OUT / "scope-review-01.json").relative_to(ROOT)),
                    "applicability": candidate["applicability"], "university_approval_claimed": False})
            fingerprint = digest(row)
            async with platform.repo.transaction() as conn:
                key = "evidence-20261025-disposition:" + identifier
                if not await platform.repo.replay(conn, owner.subject_id, key, fingerprint):
                    new_id = generate_uuid7()
                    await conn.execute("""INSERT INTO knowledge_source_disposition(id,tenant_id,source_id,original_sha256,category,
                        related_source_id,note,evidence,created_by) VALUES($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9)""",
                        new_id, TENANT, identifier, row["original_sha256"], row["category"], row["related_source_id"],
                        note, json.dumps(row["evidence"]), owner.subject_id)
                    await platform.repo.audit(conn, owner.subject_id, "knowledge.source.classified", identifier,
                        {"disposition_id": new_id, "category": row["category"]})
                    await platform.repo.remember(conn, owner.subject_id, key, fingerprint, {"id": new_id})
        from collections import Counter
        old["counts"] = dict(Counter(r["category"] for r in old["sources"]))
        retain(OUT / "source-dispositions-01.json", old)
        print(json.dumps(old["counts"]))
    finally:
        await pool.close()


async def integrity():
    # Reuse the complete baseline check; redirect only its new output receipt.
    import verify_huce_corpus_integrity as verification
    await verification.main("07", "04")
    result = read(SCOPE / "candidate-integrity-04.json")
    retain(OUT / "candidate-integrity-01.json", result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("probes", "integrity", "activate", "classify"))
    parser.add_argument("--attempt", choices=("01", "02", "03"), default="01")
    args = parser.parse_args()
    if args.mode == "activate":
        activate(args.attempt)
    else:
        asyncio.run(probes(args.attempt) if args.mode == "probes" else integrity() if args.mode == "integrity" else classify())
