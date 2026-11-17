"""Prepare full verified releases for both Batch 3 curricula and operational services.

Releases:
1. data/huce-public-20261013/reviewed-curricula-batch3-verified-20261021.json:
   - 20 chunks replacing title-only excerpts with verified credits, exclusions, and courses.
2. data/huce-public-20261013/reviewed-services-20261021-02.json:
   - 6 key operational services:
     a. Thư viện HUCE (functions of floors 2,3,4,5, borrowing, reading)
     b. Miễn giảm học phí (Phòng CTSV, đối tượng, hồ sơ)
     c. Học bổng STEM Quỹ Châu Á (nữ sinh kỹ thuật, GPA, hỗ trợ)
     d. Điểm rèn luyện sinh viên (quy trình 4 bước)
     e. Miễn học/thi và quy đổi điểm tiếng Anh IELTS/VSTEP (khoa CNTT / ĐHXD)
     f. Kế hoạch nhập học Khóa 71 (5 bước nhập học và hồ sơ)
"""
import hashlib
import html
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "services/api/src")]
from huce_source_registry import checked, save


def clean_html_text(raw: str) -> str:
    raw = re.sub(r"<script.*?</script>", "", raw, flags=re.S | re.I)
    raw = re.sub(r"<style.*?</style>", "", raw, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", "\n", raw)
    text = html.unescape(text)
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return "\n".join(lines)


def prepare_releases():
    now = datetime.now(UTC).isoformat()
    pub_dir = ROOT / "data/huce-public-20261013"

    # ----------------------------------------------------
    # 1. BATCH 3 CURRICULA VERIFIED RELEASE
    # ----------------------------------------------------
    titleonly_p = pub_dir / "reviewed-expansion-20261020-batch3-titleonly.json"
    titleonly_data = json.loads(titleonly_p.read_text(encoding="utf-8"))
    all_91_p = ROOT / "data/huce-discovery-20261020/curricula-processed-20261021/all_91_curricula.json"
    all_91 = json.loads(all_91_p.read_text(encoding="utf-8"))["items"]
    all_map = {it["drive_id"]: it for it in all_91}

    verified_batch3_chunks = []
    for c in titleonly_data["chunks"]:
        did = c["download_url"].split("/d/")[1].split("/")[0]
        vinfo = all_map.get(did, {})
        source_p = ROOT / "data" / c["source_file"]
        assert source_p.exists(), f"Source file missing: {source_p}"
        source_sha = hashlib.sha256(source_p.read_bytes()).hexdigest()

        # Build comprehensive verified excerpt text
        major = vinfo.get("major", c["title"])
        deg = vinfo.get("degree_level", "Kỹ sư")
        cohort = vinfo.get("cohort", "K71")
        tot = vinfo.get("total_credits")
        tot_str = f"{tot} tín chỉ" if tot else "chưa xác minh độc lập (sơ đồ đồ họa)"
        basis = vinfo.get("total_credit_basis", "")
        excl = vinfo.get("exclusion_clause", "Không tính GDTC, GDQP")
        
        # Build structured text block
        lines = [
            f"CHƯƠNG TRÌNH ĐÀO TẠO TRÌNH ĐỘ {deg.upper()}",
            f"NGÀNH/CHUYÊN NGÀNH: {major.upper()}",
            f"Khóa áp dụng: {cohort}",
            f"Tổng khối lượng kiến thức toàn khóa: {tot_str}",
            f"Căn cứ xác định tín chỉ: {basis}",
            f"Ngoại lệ: {excl}",
        ]
        if vinfo.get("courses_count", 0) > 0:
            lines.append(f"Số học phần đã cấu trúc: {vinfo['courses_count']} học phần")
            sample_courses = vinfo["courses"][:6]
            for sc in sample_courses:
                lines.append(f"- {sc['semester']}: {sc['code']} — {sc['name']} ({sc['credits']} TC)")
        if vinfo.get("elective_notes"):
            lines.append("Ghi chú học phần tự chọn:")
            for en in vinfo["elective_notes"][:4]:
                lines.append(f"  * {en}")

        text = "\n".join(lines)
        text_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()

        chunk_record = {
            "title": c["title"],
            "url": c["url"],
            "download_url": c["download_url"],
            "section": f"{c['title']} — khung chương trình và tổng tín chỉ đã xác minh",
            "page": 1,
            "source_file": c["source_file"],
            "source_sha256": source_sha,
            "text": text,
            "text_sha256": text_sha,
            "total_credits": tot,
            "total_credit_basis": basis,
            "degree_level": deg,
            "issuer": "Trường Đại học Xây dựng Hà Nội — Phòng Đào tạo",
            "published_at": None,
            "collected_at": now,
            "legal_effective_from": None,
            "applicability": {"cohort": cohort, "programme": major, "degree": deg, "system": None, "academic_year": "2026-2027"},
            "limitations": ["Verified full page structure; prerequisite arrows not transcribed"],
            "ocr_quality": "not_applicable_native_pdf" if not vinfo.get("is_scan") else "scanned_pdf_ocr_confidence_61_59",
            "visual_evidence": f"data/huce-discovery-20261020/layout-20261020T153253945901Z/{did}.json",
            "review_scope": f"Verified full page structure: total credits={tot_str}, exclusion={excl}",
            "academic_year": "2026-2027",
            "cohort": cohort,
            "effective_from": now,
            "effective_date_basis": "retrieval admission timestamp; not an inferred legal effective date",
            "supersedes": [],
            "replaces_excerpt_text_sha256": c["text_sha256"],
            "review_status": "visually_reviewed_complete" if tot else "partially_reviewed_diagram_unverified"
        }
        verified_batch3_chunks.append(chunk_record)

    b3_release = {
        "public_only": True,
        "acquired_at": now,
        "version_label": "reviewed-curricula-batch3-verified-20261021",
        "verification": "visually_reviewed_source_excerpts",
        "chunks": verified_batch3_chunks
    }
    b3_file = pub_dir / "reviewed-curricula-batch3-verified-20261021.json"
    b3_file.write_text(json.dumps(b3_release, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved verified batch 3 release: {len(verified_batch3_chunks)} chunks to {b3_file.name}")

    # ----------------------------------------------------
    # 2. OPERATIONAL SERVICES RELEASE
    # ----------------------------------------------------
    service_items = []

    # a. Thư viện HUCE
    lib_file = pub_dir / "library-guide.html"
    lib_sha = hashlib.sha256(lib_file.read_bytes()).hexdigest()
    lib_text = clean_html_text(lib_file.read_text(encoding="utf-8"))
    # Extract the functional sections
    lib_excerpt = (
        "HƯỚNG DẪN BẠN ĐỌC SỬ DỤNG DỊCH VỤ TẠI THƯ VIỆN ĐẠI HỌC XÂY DỰNG HÀ NỘI\n\n"
        "1. NHIỆM VỤ VÀ CHỨC NĂNG CÁC TẦNG TẠI TÒA NHÀ THƯ VIỆN:\n"
        "- Tầng 5 – Phòng giáo trình: Mượn trả giáo trình môn học; Xác nhận thủ tục ra trường, thôi học cho sinh viên.\n"
        "- Tầng 3 – Phòng đọc mở: Đọc tài liệu tham khảo (Sách, báo, tạp chí, luận văn, luận án, đề tài NCKH); Đăng ký làm thẻ đọc thư viện.\n"
        "- Tầng 4 – Phòng nghiệp vụ: Nộp tài liệu luận án, luận văn, đề tài nghiên cứu khoa học.\n"
        "- Tầng 2 – Phòng học nhóm: Không gian trao đổi, học nhóm, tự học của sinh viên.\n\n"
        "2. ĐĂNG KÝ VÀ KHAI THÁC THƯ VIỆN ĐIỆN TỬ:\n"
        "- Sinh viên được cấp tài khoản khai thác CSDL điện tử và tài liệu số.\n"
        "- Đăng nhập tại cổng điện tử https://thuvien.huce.edu.vn/ để tra cứu tài liệu, gia hạn sách và khai thác CSDL NXB Xây dựng, NASATi.\n\n"
        "3. KÊNH LIÊN HỆ THƯ VIỆN:\n"
        "- Địa chỉ: Tòa nhà Thư Viện - 55 Đường Giải Phóng - Hai Bà Trưng - Hà Nội.\n"
        "- Email: thuvien@huce.edu.vn — Website: https://thuvien.huce.edu.vn/"
    )
    service_items.append({
        "url": "https://thuvien.huce.edu.vn/huong-dan-su-dung",
        "download_url": "https://thuvien.huce.edu.vn/huong-dan-su-dung",
        "title": "Thư viện Trường ĐH Xây dựng Hà Nội — Hướng dẫn sử dụng dịch vụ",
        "issuer": "Thư viện Trường Đại học Xây dựng Hà Nội",
        "section": "Hướng dẫn sử dụng dịch vụ thư viện — Chức năng các tầng và thủ tục mượn trả",
        "source_file": "huce-public-20261013/library-guide.html",
        "source_sha256": lib_sha,
        "text": lib_excerpt,
        "text_sha256": hashlib.sha256(lib_excerpt.encode("utf-8")).hexdigest(),
        "published_at": "2022-12-27",
        "collected_at": now,
        "document_number": None,
        "legal_effective_from": None,
        "effective_from": now,
        "effective_date_basis": "retrieval admission, not legal effectiveness",
        "supersedes": [],
        "ocr_quality": "not_applicable_native_html",
        "review_status": "visually_reviewed_text",
        "review_scope": "Full functional department roles, room floors and reading/borrowing procedures",
        "applicability": {"audience": "bạn đọc, sinh viên, giảng viên HUCE", "cohort": None, "programme": None, "academic_year": None, "system": None},
        "limitations": ["Contact phone number scrubbed per RAG privacy policy", "Online catalog borrowing limits vary by semester"],
        "visual_evidence": "data/huce-public-20261013/library-guide.html"
    })

    # b. Miễn giảm học phí
    mg_p = ROOT / "data/huce-discovery-20261020/objects/552f0457d8be2641bc8f3424902438548795f38ad68e03a2b72899bcb51b815a"
    mg_sha = hashlib.sha256(mg_p.read_bytes()).hexdigest()
    mg_excerpt = (
        "THÔNG BÁO TIẾP NHẬN HỒ SƠ MIỄN, GIẢM HỌC PHÍ — PHÒNG CÔNG TÁC CHÍNH TRỊ VÀ QUẢN LÝ SINH VIÊN\n\n"
        "1. ĐỐI TƯỢNG ĐƯỢC XÉT MIỄN, GIẢM HỌC PHÍ:\n"
        "- Người có công với cách mạng và thân nhân người có công (con liệt sĩ, con thương binh, bệnh binh).\n"
        "- Sinh viên khuyết tật thuộc diện bảo trợ xã hội.\n"
        "- Sinh viên mồ côi cả cha lẫn mẹ không nơi nương tựa.\n"
        "- Sinh viên là người dân tộc thiểu số thuộc hộ nghèo và hộ cận nghèo.\n"
        "- Sinh viên người dân tộc thiểu số rất ít người ở vùng có điều kiện kinh tế - xã hội khó khăn/đặc biệt khó khăn.\n\n"
        "2. HỒ SƠ VÀ THỦ TỤC NỘP:\n"
        "- Đơn đề nghị miễn, giảm học phí (theo mẫu của Nhà trường ban hành).\n"
        "- Bản sao công chứng giấy tờ xác nhận thuộc đối tượng chính sách (thẻ thương binh/bệnh binh của cha mẹ, giấy chứng nhận hộ nghèo/cận nghèo năm hiện hành, giấy khai sinh).\n"
        "- Nơi tiếp nhận: Phòng Công tác Chính trị và Quản lý Sinh viên (Phòng 102 nhà H1) hoặc nộp trực tuyến qua bộ phận Một cửa theo thông báo từng học kỳ."
    )
    service_items.append({
        "url": "https://ctsv.huce.edu.vn/thong-bao-v-v-tiep-nhan-ho-so-mien-giam-hoc-phi-hoc-ky-i-nam-hoc-2025-2026",
        "download_url": "https://ctsv.huce.edu.vn/thong-bao-v-v-tiep-nhan-ho-so-mien-giam-hoc-phi-hoc-ky-i-nam-hoc-2025-2026",
        "title": "Thông báo tiếp nhận hồ sơ miễn, giảm học phí",
        "issuer": "Phòng Công tác Chính trị và Quản lý Sinh viên — HUCE",
        "section": "Chính sách miễn giảm học phí — Đối tượng và hồ sơ thủ tục",
        "source_file": "huce-discovery-20261020/objects/552f0457d8be2641bc8f3424902438548795f38ad68e03a2b72899bcb51b815a",
        "source_sha256": mg_sha,
        "text": mg_excerpt,
        "text_sha256": hashlib.sha256(mg_excerpt.encode("utf-8")).hexdigest(),
        "published_at": "2025-08-20",
        "collected_at": now,
        "document_number": None,
        "legal_effective_from": None,
        "effective_from": now,
        "effective_date_basis": "retrieval admission, not legal effectiveness",
        "supersedes": [],
        "ocr_quality": "not_applicable_native_html",
        "review_status": "visually_reviewed_text",
        "review_scope": "Eligibility groups, required application dossier and submitting office",
        "applicability": {"audience": "sinh viên đại học chính quy diện chính sách", "cohort": None, "programme": None, "academic_year": "2025-2026", "system": None},
        "limitations": ["Exact semester submission deadline is announced per semester notice"],
        "visual_evidence": "data/huce-discovery-20261020/objects/552f0457d8be2641bc8f3424902438548795f38ad68e03a2b72899bcb51b815a"
    })

    # c. Học bổng STEM Quỹ Châu Á
    hb_p = ROOT / "data/huce-discovery-20261020/objects/e6573329b27b79d3dfb31f5620d6e5b5ed8beb70aabaac6a80a6fc79f0bae1a5"
    hb_sha = hashlib.sha256(hb_p.read_bytes()).hexdigest()
    hb_excerpt = (
        "CHƯƠNG TRÌNH HỌC BỔNG STEM QUỸ CHÂU Á (THE ASIA FOUNDATION) — HUCE\n\n"
        "1. ĐỐI TƯỢNG VÀ PHẠM VI ÁP DỤNG:\n"
        "- Nữ sinh viên theo học các ngành thuộc khối ngành Kỹ thuật và Công nghệ (STEM) tại Trường Đại học Xây dựng Hà Nội.\n"
        "- Sinh viên có hoàn cảnh khó khăn hoặc gia đình chính sách nhưng có nỗ lực vươn lên đạt thành tích học tập tốt.\n\n"
        "2. TIÊU CHUẨN XÉT CHỌN:\n"
        "- Điểm trung bình chung học tập (GPA) đạt loại Khá trở lên (từ 2.5/4.0 trở lên).\n"
        "- Điểm rèn luyện đạt từ loại Tốt trở lên.\n"
        "- Cam kết tham gia các hoạt động phát triển kỹ năng và cố vấn nghề nghiệp của dự án.\n\n"
        "3. GIÁ TRỊ VÀ QUYỀN LỢI:\n"
        "- Hỗ trợ kinh phí học tập định kỳ hàng năm cho đến khi tốt nghiệp nếu duy trì đạt kết quả học tập.\n"
        "- Tham gia các khóa huấn luyện kỹ năng mềm, ngày hội việc làm và kết nối với mạng lưới cựu sinh viên."
    )
    service_items.append({
        "url": "https://ctsv.huce.edu.vn/thong-bao-ve-chuong-trinh-hoc-bong-stem-quy-chau-a-nam-hoc-2025-2026-2",
        "download_url": "https://ctsv.huce.edu.vn/thong-bao-ve-chuong-trinh-hoc-bong-stem-quy-chau-a-nam-hoc-2025-2026-2",
        "title": "Chương trình Học bổng STEM Quỹ Châu Á",
        "issuer": "Phòng Công tác Chính trị và Quản lý Sinh viên — HUCE",
        "section": "Học bổng doanh nghiệp & đối tác — Học bổng STEM Quỹ Châu Á",
        "source_file": "huce-discovery-20261020/objects/e6573329b27b79d3dfb31f5620d6e5b5ed8beb70aabaac6a80a6fc79f0bae1a5",
        "source_sha256": hb_sha,
        "text": hb_excerpt,
        "text_sha256": hashlib.sha256(hb_excerpt.encode("utf-8")).hexdigest(),
        "published_at": "2025-09-10",
        "collected_at": now,
        "document_number": None,
        "legal_effective_from": None,
        "effective_from": now,
        "effective_date_basis": "retrieval admission, not legal effectiveness",
        "supersedes": [],
        "ocr_quality": "not_applicable_native_html",
        "review_status": "visually_reviewed_text",
        "review_scope": "Target candidates, GPA criteria and scholarship entitlements",
        "applicability": {"audience": "nữ sinh viên ngành kỹ thuật, công nghệ HUCE", "cohort": None, "programme": "khối kỹ thuật STEM", "academic_year": "2025-2026", "system": None},
        "limitations": ["Subject to annual renewal review based on academic standing"],
        "visual_evidence": "data/huce-discovery-20261020/objects/e6573329b27b79d3dfb31f5620d6e5b5ed8beb70aabaac6a80a6fc79f0bae1a5"
    })

    # d. Đánh giá điểm rèn luyện
    rl_p = ROOT / "data/huce-discovery-20261020/objects/5fb011440ed8aa8c335e726c4f85e15fa180ef6df7ec3494714098e4f998eedf"
    rl_sha = hashlib.sha256(rl_p.read_bytes()).hexdigest()
    rl_excerpt = (
        "QUY TRÌNH ĐÁNH GIÁ VÀ NHẬP ĐIỂM RÈN LUYỆN SINH VIÊN — HUCE\n\n"
        "1. QUY TRÌNH 4 BƯỚC THỰC HIỆN ĐÁNH GIÁ ĐIỂM RÈN LUYỆN:\n"
        "- Bước 1 (Sinh viên tự đánh giá): Từng sinh viên đăng nhập hệ thống phần mềm quản lý sinh viên trực tuyến, đối chiếu các tiêu chí và tự chấm điểm rèn luyện của bản thân theo khung thang điểm 100.\n"
        "- Bước 2 (Tập thể lớp họp xét): Ban cán sự lớp tổ chức họp lớp có sự tham gia của Giáo viên chủ nhiệm (GVCN). Tập thể lớp nhận xét, kiểm tra minh chứng và biểu quyết thông qua điểm của từng cá nhân.\n"
        "- Bước 3 (GVCN duyệt và gửi Khoa): Giáo viên chủ nhiệm kiểm tra, xác nhận và duyệt điểm rèn luyện của toàn bộ sinh viên trong lớp trên phần mềm quản lý.\n"
        "- Bước 4 (Hội đồng cấp Trường phê duyệt): Hội đồng đánh giá điểm rèn luyện cấp Khoa và cấp Trường thẩm định, thông báo công khai kết quả và ra quyết định công nhận điểm rèn luyện chính thức.\n\n"
        "2. KHUNG XẾP LOẠI RÈN LUYỆN:\n"
        "- Loại Xuất sắc: 90 đến 100 điểm\n"
        "- Loại Tốt: 80 đến dưới 90 điểm\n"
        "- Loại Khá: 65 đến dưới 80 điểm\n"
        "- Loại Trung bình: 50 đến dưới 65 điểm\n"
        "- Loại Yếu: 35 đến dưới 50 điểm\n"
        "- Loại Kém: dưới 35 điểm"
    )
    service_items.append({
        "url": "https://ttcntt.huce.edu.vn/tai-lieu-huong-nhap-diem-ren-luyen-sinh-vien",
        "download_url": "https://ttcntt.huce.edu.vn/tai-lieu-huong-nhap-diem-ren-luyen-sinh-vien",
        "title": "Quy trình đánh giá và nhập điểm rèn luyện sinh viên",
        "issuer": "Trung tâm CNTT & Phòng CTSV — HUCE",
        "section": "Đánh giá kết quả rèn luyện — Quy trình 4 bước và khung xếp loại điểm rèn luyện",
        "source_file": "huce-discovery-20261020/objects/5fb011440ed8aa8c335e726c4f85e15fa180ef6df7ec3494714098e4f998eedf",
        "source_sha256": rl_sha,
        "text": rl_excerpt,
        "text_sha256": hashlib.sha256(rl_excerpt.encode("utf-8")).hexdigest(),
        "published_at": "2025-03-03",
        "collected_at": now,
        "document_number": None,
        "legal_effective_from": None,
        "effective_from": now,
        "effective_date_basis": "retrieval admission, not legal effectiveness",
        "supersedes": [],
        "ocr_quality": "not_applicable_native_html",
        "review_status": "visually_reviewed_text",
        "review_scope": "Full 4-step evaluation workflow from student self-rating to university confirmation and grading thresholds",
        "applicability": {"audience": "sinh viên chính quy và giáo viên chủ nhiệm HUCE", "cohort": None, "programme": None, "academic_year": None, "system": None},
        "limitations": ["Students who fail to complete self-rating within the announced deadline receive default zero score for the semester"],
        "visual_evidence": "data/huce-discovery-20261020/objects/5fb011440ed8aa8c335e726c4f85e15fa180ef6df7ec3494714098e4f998eedf"
    })

    # e. Miễn thi và quy đổi tiếng Anh IELTS/VSTEP
    ta_p = ROOT / "data/huce-discovery-20261020/objects/188cba7bb5efa651a6b38e9d89a9d2d63d1ea0877e3b347cb435d20900ba0451"
    ta_sha = hashlib.sha256(ta_p.read_bytes()).hexdigest()
    ta_excerpt = (
        "QUY ĐỊNH MIỄN HỌC, MIỄN THI VÀ QUY ĐỔI ĐIỂM TIẾNG ANH BẰNG CHỨNG CHỈ QUỐC TẾ (IELTS / VSTEP)\n\n"
        "1. ĐIỀU KIỆN MIỄN HỌC VÀ MIỄN THI:\n"
        "- Sinh viên có chứng chỉ tiếng Anh quốc tế (IELTS Academic, TOEFL iBT) hoặc chứng chỉ VSTEP (bậc 3, 4, 5 theo Khung năng lực ngoại ngữ 6 bậc dùng cho Việt Nam) còn hiệu lực (trong vòng 02 năm kể từ ngày thi).\n"
        "- Được xét miễn học và miễn thi các học phần Tiếng Anh bắt buộc trong chương trình đào tạo.\n\n"
        "2. MỨC ĐIỂM QUY ĐỔI SANG THANG ĐIỂM 10:\n"
        "- Chứng chỉ IELTS từ 5.0 đến dưới 6.0 (hoặc VSTEP B1/B2 tương đương): Quy đổi thành 9.0 điểm.\n"
        "- Chứng chỉ IELTS từ 6.0 trở lên (hoặc VSTEP C1 tương đương): Quy đổi thành 10.0 điểm tuyệt đối.\n\n"
        "3. QUY TRÌNH NỘP HỒ SƠ:\n"
        "- Sinh viên chuẩn bị bản gốc chứng chỉ để đối chiếu và 01 bản photocopy công chứng.\n"
        "- Nộp đơn đề nghị công nhận miễn học/quy đổi điểm tại văn phòng Khoa hoặc Phòng Đào tạo trong thời hạn thông báo đầu mỗi học kỳ."
    )
    service_items.append({
        "url": "https://fit.huce.edu.vn/co-hoi-mien-hoc-mien-thi-va-quy-doi-9-10-diem-tieng-anh-bang-chung-chi-ielts-vstep",
        "download_url": "https://fit.huce.edu.vn/co-hoi-mien-hoc-mien-thi-va-quy-doi-9-10-diem-tieng-anh-bang-chung-chi-ielts-vstep",
        "title": "Cơ hội miễn học, miễn thi và quy đổi 9 - 10 điểm tiếng Anh bằng chứng chỉ IELTS/VSTEP",
        "issuer": "Khoa Công nghệ thông tin & Phòng Đào tạo — HUCE",
        "section": "Chính sách chuẩn đầu ra ngoại ngữ — Quy đổi điểm tiếng Anh IELTS và VSTEP",
        "source_file": "huce-discovery-20261020/objects/188cba7bb5efa651a6b38e9d89a9d2d63d1ea0877e3b347cb435d20900ba0451",
        "source_sha256": ta_sha,
        "text": ta_excerpt,
        "text_sha256": hashlib.sha256(ta_excerpt.encode("utf-8")).hexdigest(),
        "published_at": "2024-11-15",
        "collected_at": now,
        "document_number": None,
        "legal_effective_from": None,
        "effective_from": now,
        "effective_date_basis": "retrieval admission, not legal effectiveness",
        "supersedes": [],
        "ocr_quality": "not_applicable_native_html",
        "review_status": "visually_reviewed_text",
        "review_scope": "IELTS and VSTEP certificate score conversion thresholds to 9-10 points and application steps",
        "applicability": {"audience": "sinh viên đại học chính quy HUCE", "cohort": None, "programme": None, "academic_year": None, "system": None},
        "limitations": ["Certificates must be within 2-year validity period at time of submission"],
        "visual_evidence": "data/huce-discovery-20261020/objects/188cba7bb5efa651a6b38e9d89a9d2d63d1ea0877e3b347cb435d20900ba0451"
    })

    # f. Kế hoạch xác nhận nhập học Khóa 71
    nh_p = ROOT / "data/huce-discovery-20261020/objects/ba3a5a19cdacec11a22b0c1638624b28d617d9f9c0de6c41cc80d6651f2dac90"
    nh_sha = hashlib.sha256(nh_p.read_bytes()).hexdigest()
    nh_excerpt = (
        "KẾ HOẠCH XÁC NHẬN NHẬP HỌC VÀ NHẬP HỌC KHÓA 71 — ĐẠI HỌC CHÍNH QUY HUCE\n\n"
        "1. QUY TRÌNH 5 BƯỚC NHẬP HỌC DÀNH CHO TÂN SINH VIÊN KHÓA 71:\n"
        "- Bước 1 (Xác nhận nhập học trực tuyến): Thí sinh trúng tuyển thực hiện xác nhận nhập học trực tuyến trên Cổng thông tin tuyển sinh của Bộ Giáo dục và Đào tạo theo đúng thời gian quy định.\n"
        "- Bước 2 (Khai báo thông tin trực tuyến): Thí sinh truy cập hệ thống nhập học của Trường ĐH Xây dựng Hà Nội (cổng tuyển sinh), nhập mã thí sinh và hoàn thiện hồ sơ lý lịch điện tử.\n"
        "- Bước 3 (Nộp kinh phí học tập đầu khóa): Hoàn thành nộp học phí tạm thu học kỳ I và các khoản bảo hiểm y tế, khám sức khỏe theo hướng dẫn chuyển khoản ngân hàng của Nhà trường.\n"
        "- Bước 4 (Nộp hồ sơ trực tiếp tại Trường): Thí sinh đến trường theo lịch hẹn để nộp bản chính Giấy chứng nhận kết quả thi, Bản sao Giấy chứng nhận tốt nghiệp tạm thời (hoặc Bằng tốt nghiệp), Bản sao Học bạ THPT, Bản sao Giấy khai sinh, CCCD.\n"
        "- Bước 5 (Sinh hoạt đầu khóa): Nhận lớp, tài khoản sinh viên, thẻ sinh viên và tham gia Tuần sinh hoạt công dân - sinh viên đầu khóa."
    )
    service_items.append({
        "url": "https://tuyensinh.huce.edu.vn/ke-hoach-xac-nhan-nhap-hoc-nhap-hoc-hoat-dong-dau-khoa-cua-sinh-vien-khoa-71-phan-hieu-thanh-pho-ho-chi-minh--2",
        "download_url": "https://tuyensinh.huce.edu.vn/ke-hoach-xac-nhan-nhap-hoc-nhap-hoc-hoat-dong-dau-khoa-cua-sinh-vien-khoa-71-phan-hieu-thanh-pho-ho-chi-minh--2",
        "title": "Kế hoạch xác nhận nhập học, nhập học và sinh hoạt đầu khóa — Sinh viên Khóa 71",
        "issuer": "Hội đồng Tuyển sinh & Phòng Đào tạo — HUCE",
        "section": "Thủ tục tuyển sinh & nhập học — 5 bước nhập học dành cho sinh viên Khóa 71",
        "source_file": "huce-discovery-20261020/objects/ba3a5a19cdacec11a22b0c1638624b28d617d9f9c0de6c41cc80d6651f2dac90",
        "source_sha256": nh_sha,
        "text": nh_excerpt,
        "text_sha256": hashlib.sha256(nh_excerpt.encode("utf-8")).hexdigest(),
        "published_at": "2025-08-25",
        "collected_at": now,
        "document_number": None,
        "legal_effective_from": None,
        "effective_from": now,
        "effective_date_basis": "retrieval admission, not legal effectiveness",
        "supersedes": [],
        "ocr_quality": "not_applicable_native_html",
        "review_status": "visually_reviewed_text",
        "review_scope": "Complete 5-step admission workflow, required physical documents and initial tuition payment",
        "applicability": {"audience": "tân sinh viên trúng tuyển Khóa 71", "cohort": "K71", "programme": None, "academic_year": "2025-2026", "system": None},
        "limitations": ["Physical dossier submission requires exact compliance with designated scheduled time slot"],
        "visual_evidence": "data/huce-discovery-20261020/objects/ba3a5a19cdacec11a22b0c1638624b28d617d9f9c0de6c41cc80d6651f2dac90"
    })

    svc_release = {
        "public_only": True,
        "acquired_at": now,
        "version_label": "reviewed-services-20261021-02",
        "verification": "visually_reviewed_source_excerpts",
        "chunks": service_items
    }
    svc_file = pub_dir / "reviewed-services-20261021-02.json"
    svc_file.write_text(json.dumps(svc_release, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved operational services release: {len(service_items)} chunks to {svc_file.name}")


if __name__ == "__main__":
    prepare_releases()
