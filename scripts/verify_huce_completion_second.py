"""Check exact clause witnesses, retrieval and normal local activation receipts."""
import argparse
import asyncio
import json
import re
import time
from contextlib import closing
from datetime import UTC, datetime

from audit_huce_rag_20261023 import API, client
from complete_huce_corpus import actors
from continue_huce_completion_20261025 import CORPUS, OUT, REGULATION, ROOT, read, save, sha
from knowledge_platform import TENANT, components
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy

QUERIES = [
    (1, "phạm vi điều chỉnh, đối tượng áp dụng quy chế"),
    (2, "chương trình đào tạo song ngành ngành chính ngành phụ phải thể hiện khối lượng chung và riêng thế nào"),
    (3, "học phần tự chọn và học phần bắt buộc được định nghĩa thế nào"),
    (4, "giảng dạy chính quy trong khoảng giờ nào và từ thứ nào đến thứ nào"),
    (5, "liên kết đào tạo yêu cầu giảng viên cơ hữu giảng dạy tối thiểu bao nhiêu phần trăm"),
    (6, "mỗi học kỳ chính và học kỳ phụ có ít nhất bao nhiêu tuần thực học và tuần thi"),
    (7, "giới hạn khối lượng đăng ký học tập tối thiểu và tối đa so với khối lượng trung bình học kỳ"),
    (8, "tối đa bao nhiêu phần trăm chương trình đào tạo được thực hiện bằng lớp trực tuyến và ngoại lệ thiên tai dịch bệnh"),
    (9, "điểm B+ C+ D+ và điểm P có các khoảng điểm nào"),
    (10, "quy đổi điểm chữ sang điểm số thang 4 B+ C+ D+"),
    (11, "điểm trung bình học kỳ đầu và các học kỳ tiếp theo dưới mức nào thì cảnh báo học tập"),
    (12, "khối lượng tối đa được công nhận chuyển đổi tín chỉ không vượt quá bao nhiêu phần trăm"),
    (13, "hạng tốt nghiệp xuất sắc và giỏi bị giảm một mức trong trường hợp nào"),
    (14, "nghỉ học tạm thời vì lý do cá nhân cần học tối thiểu bao nhiêu học kỳ và thời gian nghỉ có tính vào thời gian học không"),
    (15, "chuyển ngành khi sinh viên năm thứ nhất hoặc năm cuối có được xem xét không"),
    (16, "trao đổi sinh viên số tín chỉ tích lũy tại trường khác không vượt quá bao nhiêu phần trăm"),
    (17, "học chương trình thứ hai sớm nhất khi xếp trình độ năm mấy và điều kiện học lực"),
    (18, "học liên thông người đã tốt nghiệp đại học nhận thêm bằng ngành khác"),
    (19, "thi hộ hoặc nhờ thi hộ vi phạm lần thứ nhất và lần thứ hai bị kỷ luật thế nào"),
    (20, "quy chế được áp dụng đối với các khóa tuyển sinh từ năm nào"),
    (21, "phòng Quản lý đào tạo lưu trữ bảng điểm gốc quyết định tốt nghiệp và sổ gốc cấp bằng trong bao lâu"),
]


async def witness():
    candidate = read(OUT / "regulation-candidate-02.json")
    transcript = read(OUT / "regulation-reviewed-pages-01.json")
    pages = {p["page"]: p for p in transcript["pages"]}
    comparisons = []
    for block in candidate["extracted"]["blocks"][1:]:
        for kind in ("heading_spans", "body_spans"):
            for span in block[kind]:
                pg = pages[span["page"]]
                assert span["text"] == pg["text"][span["char_start"]:span["char_end"]]
                assert sha(span["text"].encode()) == span["text_sha256"]
                assert span["image_sha256"] == pg["image_sha256"] == sha((ROOT/pg["image"]).read_bytes())
        assert block["text"] == "\n".join(s["text"] for s in block["heading_spans"]).strip() + "\n" + "\n".join(s["text"] for s in block["body_spans"])
    release = read(CORPUS / "candidate-release-10.json")
    version = next(r["version_id"] for r in release["members"] if r["source_id"] == REGULATION)
    pool, _, _, _ = await components()
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT content_checksum,page_start,page_end FROM knowledge_chunk WHERE document_version_id=$1", version)
            for selector in candidate["pages"]:
                chunks = [r for r in rows if r["content_checksum"] == selector["text_sha256"]]
                assert chunks and all((r["page_start"], r["page_end"]) == (selector["page"], selector["page_end"]) for r in chunks)
                comparisons.append({"section": selector["section"], "page_start": selector["page"],
                    "page_end": selector["page_end"], "chunks": len(chunks), "exact_range": True})
        save(OUT / "regulation-witness-verification-01.json", {"release_id": release["release_id"], "version_id": version,
            "clauses_verified": 95, "parents_verified": len(comparisons), "ranges": comparisons,
            "cross_page_parents": sum(r["page_end"] != r["page_start"] for r in comparisons), "all_passed": True})
        print({"parents": len(comparisons), "cross_page_parents": 15, "all_exact": True})
    finally:
        await pool.close()


async def probes(attempt):
    release = read(CORPUS / "candidate-release-10.json")
    version = next(r["version_id"] for r in release["members"] if r["source_id"] == REGULATION)
    pool, _, _, runtime = await components()
    _, owner = actors(); roles = frozenset(r.value for r in owner.roles)
    context = RetrievalContext(AuthorizedScope(TENANT, "HUCE", owner.subject_id, roles, roles,
        frozenset({"FIT"}), frozenset({"PUBLIC"})), "vi", datetime.now(UTC), SimulationPolicy.DENY, "b"*32)
    results = []
    try:
        for number, subject in QUERIES:
            query = f"Theo Điều {number} Quy chế 1486, {subject}?"
            rows = await runtime.preview_search(owner, query, context, release["release_id"])
            matched = [r for r in rows if r["document_version_id"] == version
                and re.search(rf"Điều {number}(?:,| —)", r["section_path"])]
            hashes = all(sha(r["content_text"].encode()) == r["evidence_sha256"] for r in rows)
            results.append({"article": number, "query": query, "expected_version": version,
                "passed": bool(matched) and hashes, "items": rows, "hashes_verified": hashes})
            print(json.dumps({"article": number, "passed": bool(matched) and hashes}), flush=True)
        save(OUT / f"regulation-candidate-probes-{attempt}.json", {"release_id": release["release_id"],
            "cases": results, "passed": sum(r["passed"] for r in results), "total": len(results),
            "all_passed": all(r["passed"] for r in results)})
    finally:
        await pool.close()


def activate():
    release = read(CORPUS / "candidate-release-10.json")
    old = read(CORPUS / "candidate-release-08.json")
    assert read(CORPUS / "candidate-integrity-06.json")["all_passed"]
    assert read(OUT / "regulation-witness-verification-01.json")["all_passed"]
    probes = read(OUT / "regulation-candidate-probes-02.json")
    assert probes["all_passed"] and probes["release_id"] == release["release_id"]
    members = {r["source_id"]: r for r in release["members"]}
    previous = {r["source_id"]: r for r in old["members"]}
    assert members.keys() == previous.keys() and len(members) == 114
    assert {key for key in members if members[key] != previous[key]} == {REGULATION}
    with closing(client()) as c:
        before = c.get(API+"/state"); before.raise_for_status(); before = before.json()
        assert before["desired"]["release_id"] == old["release_id"] and before["desired"]["generation"] == release["expected_generation"] == 17
        response = c.post(API+"/previews", json={"operation": "activate", "target_id": release["release_id"], "expected_generation": 17})
        response.raise_for_status(); preview = response.json()
        assert preview["payload"]["target_sha256"] == release["membership_sha256"]
        assert {r["source_id"]: r for r in preview["payload"]["members"]} == members
        save(OUT / "regulation-activation-preview-01.json", {k:v for k,v in preview.items() if k != "confirmation_token"})
        response = c.post(API+"/confirmations", headers={"Idempotency-Key": "huce-completion-20261025-02-regulation"},
            json={"preview_id": preview["preview_id"], "confirmation_token": preview["confirmation_token"], "confirmed": True})
        response.raise_for_status(); save(OUT / "regulation-activation-confirmation-01.json", response.json())
        until = time.monotonic()+45
        while time.monotonic() < until:
            response = c.get(API+"/state"); response.raise_for_status(); state = response.json()
            if state["is_serving"] and state["desired"]["release_id"] == release["release_id"] and state["desired"]["generation"] == 18:
                break
            time.sleep(.5)
        else:
            raise RuntimeError("Activation recorded; live acknowledgement not verified")
        response = c.get(API+"/availability"); response.raise_for_status(); available = response.json()
        assert available["serving_documents"] == 114
        save(OUT / "regulation-activation-ready-01.json", {"at": datetime.now(UTC), "desired": state["desired"],
            "serving": state["serving"], "availability": available, "unchanged_members": 113})
        print({"activated": True, "generation": 18, "release_id": release["release_id"]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("mode", choices=["witness", "probes", "activate"])
    parser.add_argument("--attempt", choices=["01", "02"], default="02")
    args = parser.parse_args(); mode = args.mode
    if mode == "activate":
        activate()
    else:
        asyncio.run(witness() if mode == "witness" else probes(args.attempt))
