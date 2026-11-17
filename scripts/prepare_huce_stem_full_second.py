"""Visual transcription of the retained six-page STEM notice and blank forms."""
from datetime import UTC, datetime

from knowledge_platform import ROOT
from continue_huce_completion_20261025 import CORPUS, OUT, read, save, sha
from campus247.application.knowledge.source_snapshot import validate_snapshot

STEM = "129ba0a6-652e-70b8-8532-8e63661262ce"

FORM_APPLICATION = """The Asia Foundation
ĐƠN XIN CẤP HỌC BỔNG STEM QUỸ CHÂU Á
Kính gửi: - The Asia Foundation (Quỹ Châu Á)
- Trường Đại học Xây dựng Hà Nội

Đơn xin cấp Học bổng STEM Quỹ Châu Á được gợi ý thể hiện các ý chính dưới đây:
1. Thông tin sơ lược về bản thân và gia đình
(họ tên, trường, chuyên ngành, khoa, năm học, GPA, địa chỉ, hoàn cảnh gia đình, v.v.)
2. Câu chuyện và động lực của em khi đăng ký học chuyên ngành hiện tại?
Vì sao em chọn ngành này? Điều gì khiến em mong muốn học tập và làm việc trong lĩnh vực STEM trong tương lai?
3. Em dự định/ mong muốn làm nghề gì/ở lĩnh vực nào trong 3-5 năm tới?
4. Mục tiêu và kế hoạch học tập của em trong năm học sắp tới?
5. Những khó khăn/rào cản nào em đã và đang gặp khi theo học ngành liên quan đến STEM? Em đã/đang và có dự định làm gì để ứng phó/vượt qua những khó khăn/thách thức này như thế nào?
6. Những thành tích, kinh nghiệm em đã đạt được trong quá trình học tập trước đây? Liệt kê các hoạt động xã hội, đoàn thể, nghiên cứu khoa học, cuộc thi, dự án, ... em đã tham gia (ghi rõ các chứng nhận nếu có)?
7. Lý do em đăng ký Chương trình Học bổng STEM Quỹ Châu Á?
8. Tại sao chúng tôi nên chọn em mà không phải ứng viên khác?
9. Bất kỳ thông tin nào khác em muốn chia sẻ.

Em viết đơn này xin được xét nhận Học bổng STEM Quỹ Châu Á và quyết tâm phấn đấu học tập, rèn luyện tốt để xứng đáng với sự tin tưởng của Chương trình đã trao cho em.
Em đã đọc, hiểu và cam kết thực hiện các Quyền và Nghĩa vụ của chương trình như sau:

Quyền lợi của sinh viên nhận học bổng
o Được nhận học bổng trị giá 10,000,000 VND;
o Được tham gia chương trình phát triển kỹ năng mềm, kỹ năng việc làm và kết nối với doanh nghiệp;
o Được tham gia cộng đồng mạng lưới sinh viên nữ ngành STEM của Quỹ Châu Á;
o Được nhận thông tin chuyên sâu và cập nhật về cơ hội nghề nghiệp của các ngành STEM;

Nghĩa vụ của sinh viên nhận học bổng
o Cung cấp hồ sơ theo yêu cầu của chương trình;
o Cam kết học tập với kết quả tốt nhất;
o Tham gia tích cực vào tất cả các hoạt động của chương trình;
o Sử dụng tiền học bổng phục vụ cho mục đích học tập;
o Nộp báo cáo theo yêu cầu của chương trình;
o Cập nhật về kết quả thực tập và việc làm sau khi kết thúc chương trình.

Các hoạt động của Chương trình trong năm học 2025 – 2026"""

FORM_CONTINUATION = """o Chuỗi hội thảo trực tuyến của Quỹ Châu Á (bao gồm STEMConnectHER và Skills2Work);
o Chương trình đào tạo kỹ năng xanh và kỹ năng khởi nghiệp;
o Kết nối với chuyên gia, doanh nghiệp;
o Đào tạo về kỹ năng công việc, bao gồm kỹ năng viết CV, kỹ năng phỏng vấn, kỹ năng thực tập hiệu quả, kỹ năng hoà nhập môi trường làm việc, hỗ trợ kết nối việc làm và thực tập.
o Chương trình tham quan doanh nghiệp;
o Lễ tốt nghiệp và gặp gỡ cựu sinh viên.

Em xin trân trọng cảm ơn.
...................., ngày ...... tháng ..... năm 20......
Sinh viên
(Ký và ghi rõ họ tên)

Lưu ý: Ban Tuyển chọn lưu ý các em không nên dùng AI hoặc các công cụ hỗ trợ khác mà phải chuẩn bị hồ sơ bằng chính tư duy của mình."""

FORM_CV = """CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc
Ảnh 4x6
SƠ YẾU LÝ LỊCH
TỰ THUẬT
Họ và tên:................................................................
Ngày sinh:................................................................
Giới tính:................................................................
Tên trường Đại học:........................................................
Khoa:.....................................................................
Ngành:....................................................................
Mã số SV:.................................................................
Nơi sinh:.................................................................
Hộ khẩu thường trú:........................................................
Dân tộc:..................................................................
Tôn giáo:..........................Khu vực:................................
Đối tượng ưu tiên(ghi rõ gia đình chính sách,vv..):..........................
Trình độ ngoại ngữ:........................................................
Sở trường/năng khiếu:......................................................
Email:....................................................................
SĐT cá nhân:..............................................................
SĐT bố/ mẹ:...............................................................
Khi cần, báo tin cho ai và theo địa chỉ nào:................................."""

FORM_FAMILY = """HOÀN CẢNH GIA ĐÌNH
Họ và tên cha:............................................................
Ngày tháng năm sinh:................Dân tộc:...........Tôn giáo:............
Nghề nghiệp:..............................................................
Địa chỉ cơ quan:..........................................................
Nơi ở hiện nay:...........................................................
Điện thoại:...............................................................
Họ và tên mẹ:.............................................................
Ngày tháng năm sinh:................Dân tộc:...........Tôn giáo:............
Nghề nghiệp:..............................................................
Địa chỉ cơ quan:..........................................................
Nơi ở hiện nay:...........................................................
Điện thoại:...............................................................

Họ và tên những người đang chung sống với gia đình
STT | Họ và tên | Quan hệ | Tuổi | Nghề nghiệp

LỜI CAM ĐOAN
Tôi xin cam đoan những lời khai trên là đúng sự thực và chịu trách nhiệm về những lời khai đó. Nếu sau này cơ quan thẩm quyền phát hiện vấn đề gì không đúng, tôi xin chấp hành biện pháp xử lý theo quy định./.
...................., Ngày....tháng....năm 20.......
Người khai
(Ký, ghi rõ họ tên)"""


def main():
    plan = read(CORPUS / "candidate-plan-14.json")
    entry = next(e for e in plan["sources"] if e["source_id"] == STEM)
    assert sha((ROOT / entry["candidate"]).read_bytes()) == entry["candidate_sha256"]
    candidate = read(ROOT / entry["candidate"])
    source = next(s for s in read(OUT / "original-geometry-manifest-01.json")["sources"] if s["source_id"] == STEM)
    assert len(source["pages"]) == 6 and candidate["original_sha256"] == source["original_sha256"]
    assert sha((ROOT / source["original"]).read_bytes()) == source["original_sha256"]
    for p in source["pages"]:
        assert sha((ROOT / p["image"]).read_bytes()) == p["image_sha256"]
        assert sha((ROOT / p["evidence"]).read_bytes()) == p["sha256"]
    old_blocks = candidate["extracted"]["blocks"]
    assert [b["page"] for b in old_blocks] == [1, 2]
    # The original six notice clauses were independently re-read on the images.
    # Retain their existing transcription verbatim and add previously omitted forms.
    blocks = [{**b, "section": f"STEM Quỹ Châu Á 2025–2026 — Thông báo46 — PDF {b['page']}"} for b in old_blocks]
    for page, text, section in [(3, FORM_APPLICATION, "Đơn xin học bổng — gợi ý, quyền lợi và nghĩa vụ"),
            (4, FORM_CONTINUATION, "Đơn xin học bổng — hoạt động tiếp trang3, ký tên và lưu ý"),
            (5, FORM_CV, "Sơ yếu lý lịch tự thuật — các trường trống"),
            (6, FORM_FAMILY, "Hoàn cảnh gia đình — các trường trống, bảng và lời cam đoan")]:
        blocks.append({"block_id": str(len(blocks)), "page": page, "text": text,
            "section": f"STEM Quỹ Châu Á 2025–2026 — {section} — PDF {page}"})
    # Keep the title attached to the continuation; no standalone activity list
    # is allowed to lose its year or its relationship to the application form.
    blocks[3]["text"] = "Các hoạt động của Chương trình trong năm học 2025 – 2026\n" + blocks[3]["text"]
    at = datetime.now(UTC)
    review = {"at": at, "source_id": STEM, "original_sha256": source["original_sha256"],
        "pages": source["pages"], "method": "All6 original images individually read; existing selected notice clauses rechecked; previously omitted blank application/CV forms transcribed",
        "transcript_blocks": blocks, "nontext_details": {"page5": "One blank photograph rectangle labelledẢnh4x6",
            "page6": "Five-column family table with blank writable rows; no filled personal record"},
        "limits": ["Only the retained2025–2026 notice; past deadline13/02/2026, no current open intake inferred",
            "Notice pages1–2 retain selected clauses1–6; ceremonial headings, signature and public contact footer remain visible in original rather than fully transcribed",
            "Form blank dotted runs are layout placeholders; their dot count is not semantically reproduced",
            "Page4 Ban Tuyển chọn advice to prepare applications with one's own thinking is preserved as source content"],
        "category_remains": "PARTIAL_SOURCE_TEXT", "university_approval_claimed": False}
    review_file = OUT / "stem-six-page-review-01.json"; save(review_file, review)
    previous = read(CORPUS / "candidate-release-14.json")
    candidate["previous_version_id"] = next(m["version_id"] for m in previous["members"] if m["source_id"] == STEM)
    candidate["extracted"] = {"original_sha256": candidate["original_sha256"], "blocks": blocks,
        "review_witness": {"extractor": "agent-visual-six-page-stem-forms-v1", "review": str(review_file.relative_to(ROOT)),
            "review_sha256": sha(review_file.read_bytes()), "images": source["pages"], "limitations": review["limits"]}}
    candidate["pages"] = [{"block_id": b["block_id"], "page": b["page"], "char_start": 0,
        "char_end": len(b["text"]), "text": b["text"], "text_sha256": sha(b["text"].encode()), "section": b["section"]} for b in blocks]
    candidate["applicability"].update(reviewed_at=at.isoformat(), limitations=review["limits"])
    validate_snapshot(candidate, candidate["extracted"], original_sha256=candidate["original_sha256"], effective_from=at)
    destination = OUT / "stem-six-page-candidate-01.json"; save(destination, candidate)
    entry.update(candidate=str(destination.relative_to(ROOT)), candidate_sha256=sha(destination.read_bytes()), parents=len(blocks))
    save(CORPUS / "candidate-plan-15.json", plan)
    print({"source": STEM, "pages_reviewed": 6, "previously_omitted_form_pages_added": 4, "activated": False})


if __name__ == "__main__":
    main()
