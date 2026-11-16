"""Verify and admit only the retained STEM blank-form additions."""
import argparse
import asyncio
import time
from contextlib import closing
from datetime import UTC, datetime

from audit_huce_rag_20261023 import API, client
from complete_huce_corpus import actors
from continue_huce_completion_20261025 import CORPUS, OUT, read, save, sha
from knowledge_platform import TENANT, components
from prepare_huce_stem_full_second import STEM
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy

CASES = [
    ("stem_application_prompts", "Theo mẫu đơn học bổng STEM Quỹ Châu Á năm học 2025-2026, ý7 và8 gợi ý viết nội dung gì?", ["Lý do em đăng ký", "Tại sao chúng tôi nên chọn em"], True),
    ("stem_obligations", "Theo mẫu đơn học bổng STEM Quỹ Châu Á năm học 2025-2026, sinh viên nhận học bổng có những nghĩa vụ gì?", ["Cung cấp hồ sơ", "Nộp báo cáo", "Cập nhật về kết quả thực tập"], True),
    ("stem_activities", "Theo mẫu đơn học bổng STEM Quỹ Châu Á năm học 2025-2026, chuỗi hội thảo gồm STEMConnectHER và Skills2Work không?", ["STEMConnectHER", "Skills2Work"], True),
    ("stem_cv", "Theo mẫu sơ yếu lý lịch học bổng STEM Quỹ Châu Á năm học 2025-2026, cần ảnh cỡ nào và có mục số điện thoại bố mẹ không?", ["Ảnh 4x6", "SĐT bố/ mẹ"], True),
    ("stem_family", "Theo mẫu sơ yếu lý lịch học bổng STEM Quỹ Châu Á năm học 2025-2026, bảng người chung sống với gia đình có những cột nào?", ["STT", "Họ và tên", "Quan hệ", "Tuổi", "Nghề nghiệp"], True),
    ("stem_ai_notice", "Theo mẫu đơn học bổng STEM Quỹ Châu Á năm học 2025-2026, Ban Tuyển chọn lưu ý gì về dùng AI khi chuẩn bị hồ sơ?", ["không nên dùng AI", "chính tư duy của mình"], True),
    ("stem_notice_retained", "Theo thông báo học bổng STEM Quỹ Châu Á năm học 2025-2026, thời gian nhận hồ sơ từ ngày nào đến ngày nào?", ["02/02/2026", "13/02/2026"], True),
    ("stem_wrong_year", "Theo mẫu đơn học bổng STEM Quỹ Châu Á năm học 2026-2027, Ban Tuyển chọn lưu ý gì về dùng AI?", [], False),
]


async def probes(attempt, number):
    release = read(CORPUS / f"candidate-release-{number}.json")
    version = next(m["version_id"] for m in release["members"] if m["source_id"] == STEM)
    pool, _, _, runtime = await components(); _, owner = actors()
    roles = frozenset(r.value for r in owner.roles)
    context = RetrievalContext(AuthorizedScope(TENANT, "HUCE", owner.subject_id, roles, roles,
        frozenset({"FIT"}), frozenset({"PUBLIC"})), "vi", datetime.now(UTC), SimulationPolicy.DENY, "f"*32)
    results = []
    try:
        for name, query, terms, expected in CASES:
            items = await runtime.preview_search(owner, query, context, release["release_id"])
            relevant = [r for r in items if r["document_version_id"] == version]
            passed = (any(all(t in r["content_text"] for t in terms) for r in relevant) if expected else not relevant)
            passed &= all(sha(r["content_text"].encode()) == r["evidence_sha256"] for r in items)
            results.append({"name": name, "question": query, "passed": bool(passed), "expected_present": expected,
                "expected_terms": terms, "items": items, "expected_version": version})
            print({"name": name, "passed": bool(passed)}, flush=True)
        save(OUT / f"stem-candidate-probes-{attempt}.json", {"release_id": release["release_id"], "cases": results,
            "passed": sum(r["passed"] for r in results), "total": len(results), "all_passed": all(r["passed"] for r in results)})
        case_file = OUT / "stem-live-cases-01.json"
        live_cases = [{"name": n, "question": q, "followup": False} for n, q, _, _ in CASES]
        if case_file.exists():
            assert read(case_file) == live_cases
        else:
            save(case_file, live_cases)
    finally:
        await pool.close()


def activate(number):
    current = number == "22"
    prior, generation, integrity_number, probe_number, attempt = ("21", 24, "17", "07", "02") if current else ("14", 21, "11", "06", "01")
    release = read(CORPUS / f"candidate-release-{number}.json"); previous = read(CORPUS / f"candidate-release-{prior}.json")
    integrity = read(CORPUS / f"candidate-integrity-{integrity_number}.json"); probe = read(OUT / f"stem-candidate-probes-{probe_number}.json")
    if current:
        regression = read(OUT / "live-verdict-40-01.json")
        assert regression["all_passed"] and regression["binding"]["release_id"] == previous["release_id"]
    assert integrity["all_passed"] and integrity["release_id"] == release["release_id"]
    assert probe["all_passed"] and probe["release_id"] == release["release_id"]
    members = {r["source_id"]: r for r in release["members"]}; old = {r["source_id"]: r for r in previous["members"]}
    assert len(members) == 114 and members.keys() == old.keys() and {k for k in members if members[k] != old[k]} == {STEM}
    assert release["expected_generation"] == generation
    with closing(client()) as c:
        response = c.get(API + "/state"); response.raise_for_status(); state = response.json()
        assert state["is_serving"] and state["desired"]["release_id"] == previous["release_id"] and state["desired"]["generation"] == generation
        response = c.post(API + "/previews", json={"operation": "activate", "target_id": release["release_id"], "expected_generation": generation})
        response.raise_for_status(); preview = response.json()
        assert preview["payload"]["target_sha256"] == release["membership_sha256"]
        assert {r["source_id"]: r for r in preview["payload"]["members"]} == members
        save(OUT / f"stem-activation-preview-{attempt}.json", {k: v for k, v in preview.items() if k != "confirmation_token"})
        response = c.post(API + "/confirmations", headers={"Idempotency-Key": "huce-completion-20261025-02-stem-" + attempt},
            json={"preview_id": preview["preview_id"], "confirmation_token": preview["confirmation_token"], "confirmed": True})
        response.raise_for_status(); save(OUT / f"stem-activation-confirmation-{attempt}.json", response.json())
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            response = c.get(API + "/state"); response.raise_for_status(); state = response.json()
            if state["is_serving"] and state["desired"]["release_id"] == release["release_id"] and state["desired"]["generation"] == generation + 1:
                break
            time.sleep(.5)
        else:
            raise RuntimeError("Activation recorded; live acknowledgement not verified")
        response = c.get(API + "/availability"); response.raise_for_status()
        save(OUT / f"stem-activation-ready-{attempt}.json", {"at": datetime.now(UTC), "desired": state["desired"],
            "serving": state["serving"], "availability": response.json(), "unchanged_members": 113})
        print({"activated": True, "generation": generation + 1, "release_id": release["release_id"]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("mode", choices=["probes", "activate"])
    parser.add_argument("--attempt", choices=["01", "02", "03", "04", "05", "06", "07"], default="06")
    parser.add_argument("--release", choices=["16", "22"], default="16")
    args = parser.parse_args()
    asyncio.run(probes(args.attempt, args.release)) if args.mode == "probes" else activate(args.release)
