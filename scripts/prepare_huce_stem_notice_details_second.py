"""Add visually read notice headings, recitals and closing; preserve old parents."""
from datetime import UTC, datetime

from continue_huce_completion_20261025 import CORPUS, OUT, ROOT, checked, read, save, sha
from prepare_huce_stem_full_second import STEM
from campus247.application.knowledge.source_snapshot import validate_snapshot

DETAILS = [
    (1, "tiêu đề, cơ quan và ngày ban hành", """BỘ GIÁO DỤC VÀ ĐÀO TẠO
TRƯỜNG ĐẠI HỌC XÂY DỰNG HÀ NỘI
CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập – Tự do – Hạnh phúc
Số: 46/TB-ĐHXDHN-CTSV
Hà Nội, ngày 30 tháng 01 năm 2026
THÔNG BÁO
Về Chương trình học bổng STEM Quỹ Châu Á năm học 2025-2026"""),
    (1, "các căn cứ và đoạn mở đầu", """Căn cứ Thỏa thuận dự án ký ngày 24/10/2023 giữa Trường Đại học Xây dựng Hà Nội
và The Asia Foundation (Quỹ Châu Á);
Căn cứ Thư tài trợ (sửa đổi) Letter of Amendment ngày 12/01/2026 giữa Trường Đại
học Xây dựng Hà Nội và Quỹ Châu Á;
Căn cứ Công văn của Quỹ Châu Á ngày 27/01/2026;
Phòng Công tác Chính trị và Quản lý sinh viên thông báo về Chương trình học bổng
STEM Quỹ Châu Á giai đoạn năm 2025-2026 với các nội dung cụ thể như sau:"""),
    (2, "đoạn kết và thông tin liên hệ in trong thông báo", """Phòng Công tác Chính trị và Quản lý sinh viên thông báo để các Khoa và sinh viên
có liên quan được biết và thực hiện.
Mọi thắc mắc liên hệ qua Phòng CTCT&QLSV, Số điện thoại: 0964245028 hoặc qua
Email: thuymt@huce.edu.vn.
Trân trọng./."""),
    (2, "nơi nhận", """Nơi nhận:
- Như trên;
- Ban Giám hiệu (để b/c);
- Website: huce.edu.vn;
- Lưu: VT, CTSV."""),
    (2, "chức danh và họ tên in dưới chữ ký", """TL. HIỆU TRƯỞNG
KT. TRƯỞNG PHÒNG CTCT&QLSV
PHÓ TRƯỞNG PHÒNG
ThS. Nguyễn Đình Huy"""),
]


def main():
    plan = read(CORPUS / "candidate-plan-27.json")
    entry = next(e for e in plan["sources"] if e["source_id"] == STEM)
    candidate_file = checked(ROOT / entry["candidate"])
    assert sha(candidate_file.read_bytes()) == entry["candidate_sha256"]
    candidate = read(candidate_file)
    previous = read(CORPUS / "candidate-release-25.json")
    candidate["previous_version_id"] = next(m["version_id"] for m in previous["members"] if m["source_id"] == STEM)
    old_blocks = candidate["extracted"]["blocks"]
    assert len(old_blocks) == 19
    source = next(s for s in read(OUT / "original-geometry-manifest-01.json")["sources"] if s["source_id"] == STEM)
    assert candidate["original_sha256"] == source["original_sha256"]
    assert sha(checked(ROOT / source["original"]).read_bytes()) == source["original_sha256"]
    evidence = [p for p in source["pages"] if p["page"] in (1, 2)]
    assert len(evidence) == 2
    for page in evidence:
        assert sha(checked(ROOT / page["image"]).read_bytes()) == page["image_sha256"]
        assert sha(checked(ROOT / page["evidence"]).read_bytes()) == page["sha256"]
    blocks = list(old_blocks)
    for page, section, text in DETAILS:
        blocks.append({"block_id": str(len(blocks)), "page": page, "text": text,
            "section": f"STEM Quỹ Châu Á 2025–2026 — Thông báo46 — {section} — PDF {page}"})
    assert blocks[:19] == old_blocks
    at = datetime.now(UTC)
    limits = ["Historical2025–2026 notice only; its13/02/2026 deadline has passed. No current open intake or current contact availability inferred.",
        "Previously retained notice clauses and four blank form pages remain verbatim. Blank fields are not personal records; no fields filled.",
        "New transcription covers readable notice headings, recitals, closing, public contact, recipient list and printed signatory authority/name. The seal and handwritten autograph remain image evidence; no handwriting recognition or signature authentication claimed.",
        "The three referenced documents are mentioned in this notice; their full texts, legal effect and later amendments have not been acquired or inferred."]
    review_file = checked(OUT / "stem-notice-details-review-01.json")
    review = {"at": at, "source_id": STEM, "original_sha256": candidate["original_sha256"],
        "previous_candidate": str(candidate_file.relative_to(ROOT)), "previous_candidate_sha256": sha(candidate_file.read_bytes()),
        "original_pages": evidence, "new_blocks": blocks[19:], "preserved_parent_count": 19,
        "method": "Both original notice page images individually read; all five new logical sections transcribed visually. OCR is retained as diagnostic evidence only, not copied as authoritative text. Left/right header and signature columns serialized as separate text groups.",
        "reviewer": "coding agent technical visual transcription; no official HUCE approval claimed",
        "limits": limits, "category_remains": "PARTIAL_SOURCE_TEXT", "serving_scope_expanded": False}
    save(review_file, review)
    candidate["extracted"]["blocks"] = blocks
    candidate["extracted"]["review_witness"].update(notice_details_review=str(review_file.relative_to(ROOT)),
        notice_details_review_sha256=sha(review_file.read_bytes()), limitations=limits)
    candidate["pages"] = [{"block_id": b["block_id"], "page": b["page"], "char_start": 0, "char_end": len(b["text"]),
        "text": b["text"], "text_sha256": sha(b["text"].encode()), "section": b["section"]} for b in blocks]
    candidate["applicability"].update(reviewed_at=at.isoformat(), limitations=limits)
    validate_snapshot(candidate, candidate["extracted"], original_sha256=candidate["original_sha256"], effective_from=at)
    destination = checked(OUT / "stem-notice-details-candidate-01.json")
    save(destination, candidate)
    entry.update(candidate=str(destination.relative_to(ROOT)), candidate_sha256=sha(destination.read_bytes()), parents=len(blocks))
    save(checked(CORPUS / "candidate-plan-28.json"), plan)
    print({"parents": len(blocks), "new_sections": 5, "preserved_parents": 19, "plan": "28", "activated": False})


if __name__ == "__main__":
    main()
