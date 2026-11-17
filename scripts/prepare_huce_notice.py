"""Source-bound selected transcript of the five visually inspected notice pages."""
import json
from datetime import UTC, datetime

from complete_huce_corpus import SCOPE, read, windows
from knowledge_platform import ROOT, checked_path, retain
from campus247.application.knowledge.platform_models import digest
from campus247.application.knowledge.source_snapshot import validate_snapshot

NOTICE = "c56e7a4c-b1c4-7a66-8132-24fe88db8ecc"
SHA = "75cf2382f79b6ec0e1a017225b3b33187083843d9a1f0e144e6c001b0b898e55"
TEXT = [
"""Số: 1106/TB-ĐHXDHN-CTSV
Hà Nội, ngày 03 tháng 10 năm 2025
THÔNG BÁO
V/v tiếp nhận hồ sơ xét miễn, giảm học phí học kỳ I năm học 2025-2026
Để đảm bảo quyền lợi của sinh viên trong việc xét miễn, giảm học phí học kỳ I năm học 2025-2026, sinh viên nộp đầy đủ hồ sơ (theo hướng dẫn đính kèm).
Hạn nộp hồ sơ: từ ngày 06/10/2025 đến hết ngày 31/10/2025.
Nơi nhận hồ sơ: Phòng CTCT&QLSV – Tầng 2, tòa nhà Trung tâm hỗ trợ sinh viên.
Đề nghị các Khoa/Ban phổ biến thông báo đến các lớp sinh viên.""",
"""HƯỚNG DẪN HỒ SƠ MIỄN, GIẢM HỌC PHÍ HỌC KỲ I NĂM HỌC 2025-2026
ĐỐI TƯỢNG VÀ HỒ SƠ CẦN NỘP XÉT MIỄN, GIẢM HỌC PHÍ
(Kèm theo TB số: 1106/TB - ĐHXDHN ngày 03 tháng 10 năm 2025)
STT | Đối tượng và điều kiện | Hồ sơ cần nộp | Ghi chú
I | Đối tượng và điều kiện xét miễn, giảm học phí.
1 | Miễn học phí 100%
1.1 | Các đối tượng theo quy định tại Pháp lệnh Ưu đãi người có công với cách mạng nếu đang theo học tại các cơ sở giáo dục thuộc hệ thống giáo dục quốc dân.
+ Con của người hoạt động cách mạng trước ngày 01/01/1945; con của người hoạt động cách mạng từ ngày 01/01/1945 đến ngày khởi nghĩa tháng Tám năm 1945;
+ Con của liệt sĩ;
+ Con của anh hùng lực lượng vũ trang nhân dân;
+ Con của anh hùng lao động trong thời kỳ kháng chiến;
+ Con của thương binh, con của người hưởng chính sách như thương binh;
+ Con của bệnh binh;
+ Con của người hoạt động kháng chiến bị nhiễm chất độc hóa học
| 1. Đơn đề nghị miễn, giảm học phí (Theo mẫu).
2. Giấy xác nhận của cơ quan quản lý đối với người có công với cách mạng
3. Bản sao Thẻ thương binh, bệnh binh, giấy xác nhận con liệt sĩ, giấy xác nhận được hưởng chính sách như thương binh hoặc biên bản giám định y khoa bị nhiễm chất độc hóa học của bố (mẹ).
| Sinh viên chỉ cần nộp hồ sơ minh chứng 01 lần cho đến khi kết thúc khóa học hoặc cho đến khi có văn bản hướng dẫn mới của chính phủ.""",
"""STT | Đối tượng và điều kiện | Hồ sơ cần nộp | Ghi chú
1.2 | Sinh viên là người khuyết tật
| 1. Đơn đề nghị miễn, giảm học phí (Theo mẫu).
2. Giấy xác nhận khuyết tật.
| Sinh viên chỉ cần nộp hồ sơ minh chứng 01 lần cho đến khi kết thúc khóa học hoặc cho đến khi có văn bản hướng dẫn mới của chính phủ.
1.3 | Sinh viên từ 16 đến 22 tuổi không có nguồn nuôi dưỡng đang học đại học văn bằng thứ nhất thuộc đối tượng hưởng trợ cấp xã hội hàng tháng theo quy định tại khoản 1 và 2 Điều 5 Nghị định số 20/2021/NĐ-CP ngày 15/3/2021 của Chính phủ.
| 1. Đơn đề nghị miễn, giảm học phí (Theo mẫu).
2. Quyết định về việc trợ cấp xã hội hoặc Giấy xác nhận mồ côi cả cha lẫn mẹ do Ủy ban nhân dân xã, phường, đặc khu thuộc cấp tỉnh.
| Sinh viên chỉ cần nộp hồ sơ minh chứng 01 lần cho đến khi kết thúc khóa học hoặc cho đến khi có văn bản hướng dẫn mới của chính phủ.
1.4 | Sinh viên hệ cử tuyển
| Thực hiện theo quy định của Chính phủ về chế độ cử tuyển vào các cơ sở giáo dục đại học và giáo dục nghề nghiệp thuộc hệ thống giáo dục quốc dân.
1.5 | Sinh viên là người dân tộc thiểu số có cha hoặc mẹ hoặc cả cha và mẹ hoặc ông, bà (trong trường hợp ở với ông, bà) thuộc hộ nghèo hoặc hộ cận nghèo theo quy định của Thủ tướng Chính phủ.
| 1. Đơn đề nghị miễn, giảm học phí (Theo mẫu)
2. Giấy xác nhận hộ nghèo hoặc hộ cận nghèo do Ủy ban nhân dân xã, phường, đặc khu trực thuộc cấp tỉnh cấp.
| Sinh viên nộp hồ sơ một lần vào đầu khóa học và nộp hồ sơ bổ sung giấy xác nhận hộ nghèo/hộ cận nghèo vào đầu năm tài chính hàng năm.""",
"""STT | Đối tượng và điều kiện | Hồ sơ cần nộp | Ghi chú
1.6 | Sinh viên là người dân tộc thiểu số rất ít người (Cống, Mảng, Pu Péo, Si La, Cờ Lao, Bố Y, La Ha, Ngái, Chứt, Ơ Đu, Brâu, Rơ Măm, Lô Lô, Lự, Pà Thẻn, La Hủ) ở vùng có điều kiện kinh tế - xã hội khó khăn hoặc đặc biệt khó khăn theo quy định hiện hành của cơ quan có thẩm quyền.
| 1. Đơn đề nghị miễn, giảm học phí (Theo mẫu)
2. Giấy xác nhận nơi cư trú ở vùng có điều kiện kinh tế - xã hội khó khăn hoặc đặc biệt khó khăn do UBND xã cấp.
| Sinh viên nộp giấy xác nhận nơi cư trú vào đầu khóa học và vào đầu năm tài chính hàng năm.
2 | Giảm 70% học phí
Sinh viên là người dân tộc thiểu số (ngoài đối tượng dân tộc thiểu số rất ít người) ở thôn/bản đặc biệt khó khăn, xã khu vực III vùng dân tộc và miền núi, xã đặc biệt khó khăn vùng bãi ngang ven biển hải đảo theo quy định của cơ quan có thẩm quyền.
| 1. Đơn đề nghị miễn, giảm học phí (Theo mẫu)
2. Giấy xác nhận nơi cư trú ở vùng có điều kiện kinh tế - xã hội khó khăn hoặc đặc biệt khó khăn do UBND xã cấp.
| Sinh viên nộp giấy xác nhận nơi cư trú vào đầu khóa học và vào đầu năm tài chính hàng năm.
3 | Giảm 50% học phí
Sinh viên là con cán bộ, công chức, viên chức, công nhân mà cha hoặc mẹ bị tai nạn lao động hoặc mắc bệnh nghề nghiệp được hưởng trợ cấp thường xuyên.
| 1. Đơn đề nghị miễn, giảm học phí (Theo mẫu)
2. Quyết định hưởng trợ cấp hàng tháng của cha hoặc mẹ bị tai nạn lao động hoặc mắc bệnh nghề nghiệp do cơ quan bảo hiểm xã hội cấp.
| Sinh viên chỉ cần nộp hồ sơ minh chứng 01 lần cho đến khi kết thúc khóa học hoặc cho đến khi có văn bản hướng dẫn mới của chính phủ.
II | Đối tượng và điều kiện xét hỗ trợ chi phí học tập, hỗ trợ học tập.
1 | Hỗ trợ chi phí học tập
Sinh viên là người dân tộc thiểu số thuộc hộ nghèo, hộ cận nghèo theo quy định của Nhà nước hiện đang học đại học hệ chính quy tại trường Đại học Xây dựng Hà Nội. Quy định không áp dụng đối với sinh viên: Cử tuyển, các đối tượng chính sách được xét tuyển, đào tạo theo địa chỉ, đào tạo liên thông, văn bằng hai và học đại học sau khi hoàn thành chương trình dự bị đại học.
| 1. Đơn đề nghị hỗ trợ chi phí học tập (Theo mẫu);
2. Giấy xác nhận hộ nghèo hoặc hộ cận nghèo do Ủy ban nhân dân xã, phường, đặc khu trực thuộc cấp tỉnh cấp.
| Sinh viên nộp hồ sơ một lần vào đầu khóa học và nộp hồ sơ bổ sung giấy xác nhận hộ nghèo/hộ cận nghèo vào đầu năm tài chính hàng năm.""",
"""2 | Hỗ trợ học tập
Sinh viên là người dân tộc thiểu số rất ít người (Cống, Mảng, Pu Péo, Si La, Cờ Lao, Bố Y, La Ha, Ngái, Chứt, Ơ Đu, Brâu, Rơ Măm, Lô Lô, Lự, Pà Thẻn, La Hủ) ở vùng có điều kiện kinh tế - xã hội khó khăn hoặc đặc biệt khó khăn.
| 1. Đơn đề nghị hỗ trợ học tập (Theo mẫu);""",
]


def main():
    plan = read(SCOPE / "candidate-plan-02.json")
    entry = next(row for row in plan["sources"] if row["source_id"] == NOTICE)
    inv = read(SCOPE / "inventory-01.json")
    previous = next(row for row in inv["versions"] if row["source_id"] == NOTICE)
    template = read(ROOT / next(row["candidate"] for row in plan["sources"] if row["status"] == "PREPARED"))
    pdf = checked_path(SCOPE / "linked-original-01/original.pdf", ROOT)
    assert digest(pdf.read_bytes()) == SHA
    jobs = read(SCOPE / "linked-original-01/ocr-jobs.json")["pages"][:1] + read(SCOPE / "linked-original-01/ocr-upright-jobs-01.json")["pages"]
    for job in jobs:
        assert digest(checked_path(ROOT / job["image"], ROOT).read_bytes()) == job["image_sha256"]
    blocks = [{"block_id": str(n), "page": n + 1, "text": text} for n, text in enumerate(TEXT)]
    pages = []
    for block in blocks:
        for start, end in windows(block["text"]):
            text = block["text"][start:end]
            pages.append({"block_id": block["block_id"], "page": block["page"], "text": text,
                "char_start": start, "char_end": end, "text_sha256": digest(text.encode()),
                "section": "Thông báo 1106 · HKI 2025-2026 · trang " + str(block["page"])})
    scope = {"kind": "INFORMATION_SNAPSHOT", "reviewed_at": datetime.now(UTC).isoformat(), "admission_only": True,
        "legal_effective_from": None, "cohorts": [], "programme_codes": [], "relations_verified": False,
        "academic_years": ["2025-2026"], "requires_academic_year": True,
        "limitations": ["Historical HKI 2025-2026 only; original page 1 references/signature/contact omitted; table cells transcribed in row order with pipe separators"]}
    candidate = {**{k: entry[k] for k in ("source_id", "title", "uri")}, "status": "PREPARED",
        "previous_version_id": previous["version_id"], "original_sha256": SHA, "processor": template["processor"],
        "issues": [], "applicability": scope, "pages": pages,
        "replacement_original": {"publisher_sha256": previous["original_sha256"],
            "published_attachment": "https://drive.google.com/file/d/1DvFm3Qo6Ji6F8_A_NOiKTET4qutt7TEl/preview?",
            "file": str(pdf.relative_to(ROOT))},
        "extracted": {"original_sha256": SHA, "blocks": blocks,
            "review_witness": {"extractor": "agent-visual-selected-transcript-table-row-order-v1", "images": jobs,
                "university_approval_claimed": False, "limitations": scope["limitations"]}}}
    validate_snapshot(candidate, candidate["extracted"], original_sha256=SHA, effective_from=datetime.fromisoformat(scope["reviewed_at"]))
    target = checked_path(SCOPE / "notice-1106-candidate-01.json", ROOT); retain(target, candidate)
    entry.update(status="PREPARED", candidate=str(target.relative_to(ROOT)), candidate_sha256=digest(target.read_bytes()), kind=scope["kind"], parents=len(pages), cohorts=[])
    retain(SCOPE / "candidate-plan-03.json", plan)
    print(json.dumps({"selected_pages": 5, "candidate": str(target), "academic_year_only": "2025-2026"}))


if __name__ == "__main__":
    main()
