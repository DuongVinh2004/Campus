"""Source-bound corrections after actual page review; never inherit completion."""
import hashlib
import json
import re
from collections import defaultdict
from datetime import UTC, datetime
import pdfplumber
from huce_source_registry import ROOT, checked, save, Page

OUT = ROOT / 'data/huce-discovery-20261020/reconciliation-20261021-v3'
PUB = ROOT / 'data/huce-public-20261013'

def digest(b): return hashlib.sha256(b).hexdigest()
def read(p): return json.loads(p.read_text(encoding='utf-8'))

def main():
    now = datetime.now(UTC).isoformat()
    services = read(PUB / 'reviewed-services-20261021-02.json')['chunks']
    old_arch = read(PUB / 'reviewed-curricula-batch3-verified-20261021.json')['chunks'][0]
    chunks = []
    def chunk(base, text, section, source=None, **extra):
        item = dict(base)
        source = checked(source or ROOT / 'data' / base['source_file'])
        item.update(text=text, text_sha256=digest(text.encode()), section=section,
            source_file=str(source.relative_to(ROOT / 'data')),source_sha256=digest(source.read_bytes()),
            collected_at=now, legal_effective_from=None, effective_from=now,
            effective_date_basis='retrieval admission only; legal effective date unknown',
            supersedes=[], review_status='source_checked_scope_explicit',
            review_scope=section, limitations=[], published_at=None,
            replaces_excerpt_text_sha256=base['text_sha256'])
        item.update(extra)
        chunks.append(item)
        return item
    # Keep the exact HTML article's ranges instead of inventing score mapping.
    english = services[4]
    parser = Page(); parser.feed((ROOT / 'data' / english['source_file']).read_text(encoding='utf-8'))
    text = parser.text()
    article = text[text.index('Căn cứ Quyết định mới nhất'):text.index('Thông tin liên hệ', text.index('Căn cứ Quyết định mới nhất'))].strip()
    chunk(english, article, 'Bài đăng Khoa CNTT ngày 19/10/2026 — nội dung đầy đủ, chưa thay thế Quyết định 94',
        published_at='2026-10-19', applicability={'cohort':'K70 trở đi theo bài đăng','programme':None,'academic_year':None,'system':None},
        limitations=['Bài đăng tóm tắt có nội dung quảng bá; chưa đối chiếu bản gốc Quyết định 94 và Bảng 2. Không suy ra điểm riêng cho từng học phần từ khoảng 9–10.'],
        visual_evidence=english['source_file'], ocr_quality='native_html_text_checked', review_status='html_article_text_checked')
    stem_pages = [
'''THÔNG BÁO số 46/TB-ĐHXDHN-CTSV ngày 30/01/2026. Về Chương trình học bổng STEM Quỹ Châu Á năm học 2025-2026.
Căn cứ Thỏa thuận dự án ký ngày 24/10/2023 giữa Trường Đại học Xây dựng Hà Nội và The Asia Foundation (Quỹ Châu Á); Thư tài trợ (sửa đổi) Letter of Amendment ngày 12/01/2026; Công văn của Quỹ Châu Á ngày 27/01/2026.
1. Đối tượng tham gia: Nữ sinh viên năm thứ ba đối với chương trình hệ đào tạo 4 năm hoặc năm thứ tư đối với hệ đào tạo 5 năm. Đang theo học tại các khoa: Cơ khí; Vật liệu xây dựng; Kỹ thuật Môi trường; Công nghệ thông tin.
2. Quyền lợi: Học bổng 10.000.000 đồng/sinh viên; tham gia hoạt động phát triển kỹ năng mềm, kỹ năng nghề nghiệp và kết nối doanh nghiệp trong khuôn khổ Chương trình; tham gia mạng lưới cộng đồng sinh viên nữ ngành STEM do Quỹ Châu Á tổ chức; tiếp cận thông tin chuyên sâu, cập nhật về cơ hội nghề nghiệp ngành STEM.
3. Điều kiện: Kết quả học tập của 03 học kỳ liền kề gần nhất đạt từ 2,5/4,0 trở lên. Có ý chí phấn đấu trong học tập, đam mê và cam kết theo đuổi các ngành nghề nêu trên. Trình độ tiếng Anh 450 TOEIC trở lên hoặc tương đương. Sinh viên có hoàn cảnh gia đình khó khăn được ưu tiên xem xét. Tham gia và đạt yêu cầu tại vòng phỏng vấn do Ban tuyển chọn tổ chức, gồm đại diện Quỹ Châu Á và đại diện Trường Đại học Xây dựng Hà Nội.
4. Hồ sơ: CV (tham khảo mẫu trên Internet); đơn xin cấp học bổng theo mẫu; sơ yếu lý lịch sinh viên theo mẫu; bảng điểm 03 học kỳ gần nhất; bản sao sổ hộ nghèo/cận nghèo (nếu có); chứng chỉ tiếng Anh (nếu có).''',
'''5. Phương thức xét duyệt: Quỹ Châu Á phối hợp cùng Trường Đại học Xây dựng Hà Nội tổ chức gặp gỡ, phỏng vấn ứng viên đăng ký. Căn cứ kết quả đánh giá hồ sơ và phỏng vấn, Ban Tuyển chọn quyết định danh sách sinh viên được cấp học bổng để Nhà trường thông báo chính thức tới sinh viên.
6. Địa điểm, thời gian tiếp nhận hồ sơ: Từ 02/02/2026 đến hết ngày 13/02/2026. Phòng CTCT&QLSV, tầng 2, Trung tâm hỗ trợ sinh viên.
Phòng Công tác Chính trị và Quản lý sinh viên thông báo để các Khoa và sinh viên có liên quan biết và thực hiện. Thông tin liên hệ công bố tại trang nguồn. Ký thay Trưởng phòng CTCT&QLSV, Phó Trưởng phòng ThS. Nguyễn Đình Huy, thừa lệnh Hiệu trưởng. Nơi nhận: Như trên; Ban Giám hiệu (để b/c); Website huce.edu.vn; Lưu VT, CTSV.''',
'''ĐƠN XIN CẤP HỌC BỔNG STEM QUỸ CHÂU Á. Kính gửi The Asia Foundation (Quỹ Châu Á) và Trường Đại học Xây dựng Hà Nội.
Gợi ý thể hiện: (1) Thông tin sơ lược bản thân và gia đình: họ tên, trường, chuyên ngành, khoa, năm học, GPA, địa chỉ, hoàn cảnh gia đình, v.v. (2) Câu chuyện và động lực khi đăng ký học chuyên ngành hiện tại; vì sao chọn ngành, mong muốn học tập và làm việc trong STEM. (3) Dự định/mong muốn nghề nghiệp, lĩnh vực trong 3-5 năm tới. (4) Mục tiêu và kế hoạch học tập năm học sắp tới. (5) Khó khăn/rào cản khi theo học STEM, cách đã/đang/dự định ứng phó. (6) Thành tích, kinh nghiệm; hoạt động xã hội, đoàn thể, nghiên cứu, cuộc thi, dự án đã tham gia; ghi rõ chứng nhận nếu có. (7) Lý do đăng ký học bổng. (8) Tại sao nên chọn em thay vì ứng viên khác. (9) Thông tin khác muốn chia sẻ.
Người viết xin xét nhận học bổng và quyết tâm phấn đấu học tập, rèn luyện tốt, đọc, hiểu và cam kết thực hiện quyền và nghĩa vụ:
Quyền lợi: 10.000.000 VND; chương trình phát triển kỹ năng mềm, kỹ năng việc làm, kết nối doanh nghiệp; cộng đồng mạng lưới sinh viên nữ STEM; thông tin chuyên sâu cập nhật về cơ hội nghề nghiệp STEM.
Nghĩa vụ: Cung cấp hồ sơ theo yêu cầu; cam kết học tập với kết quả tốt nhất; tham gia tích cực tất cả hoạt động chương trình; sử dụng tiền học bổng cho học tập; nộp báo cáo theo yêu cầu; cập nhật kết quả thực tập và việc làm sau khi kết thúc chương trình.''',
'''Các hoạt động của Chương trình năm học 2025-2026 (tiếp trang 3): Chuỗi hội thảo trực tuyến của Quỹ Châu Á (STEMConnectHER và Skills2Work); đào tạo kỹ năng xanh và kỹ năng khởi nghiệp; kết nối chuyên gia, doanh nghiệp; đào tạo kỹ năng công việc gồm viết CV, phỏng vấn, thực tập hiệu quả, hòa nhập môi trường làm việc, hỗ trợ kết nối việc làm và thực tập; tham quan doanh nghiệp; lễ tốt nghiệp và gặp gỡ cựu sinh viên.
Đơn có lời cảm ơn, địa điểm/ngày tháng năm và chữ ký, họ tên sinh viên.
Lưu ý của Ban Tuyển chọn: Các em không nên dùng AI hoặc các công cụ hỗ trợ khác mà phải chuẩn bị hồ sơ bằng chính tư duy của mình.''',
'''SƠ YẾU LÝ LỊCH TỰ THUẬT. Quốc hiệu, tiêu ngữ; vị trí ảnh 4x6. Các trường: Họ và tên; ngày sinh; giới tính; tên trường Đại học; khoa; ngành; mã số SV; nơi sinh; hộ khẩu thường trú; dân tộc; tôn giáo; khu vực; đối tượng ưu tiên (ghi rõ gia đình chính sách, v.v.); trình độ ngoại ngữ; sở trường/năng khiếu; email; số điện thoại cá nhân; số điện thoại bố/mẹ; khi cần báo tin cho ai và theo địa chỉ nào. Đây là biểu mẫu trống, không chứa thông tin sinh viên đã điền.''',
'''HOÀN CẢNH GIA ĐÌNH. Thông tin cha và mẹ, mỗi người gồm: họ và tên; ngày tháng năm sinh; dân tộc; tôn giáo; nghề nghiệp; địa chỉ cơ quan; nơi ở hiện nay; điện thoại. Bảng những người đang chung sống với gia đình: STT | Họ và tên | Quan hệ | Tuổi | Nghề nghiệp (7 dòng trống).
LỜI CAM ĐOAN: Người khai cam đoan những lời khai là đúng sự thật, chịu trách nhiệm về những lời khai đó; nếu cơ quan có thẩm quyền phát hiện vấn đề không đúng thì chấp hành biện pháp xử lý theo quy định. Địa điểm, ngày tháng năm, người khai ký và ghi rõ họ tên.'''
    ]
    stem_source = OUT / 'stem-attachment.pdf'
    for i, text in enumerate(stem_pages,1):
        chunk(services[2],text, f'Học bổng STEM 2025-2026 — PDF đính kèm trang {i}/6',source=stem_source,
            download_url='https://drive.google.com/file/d/15aajVthfvwJoRiaBFZvsje03VsAxrXci/view',
            page=i,page_end=i,published_at='2026-01-30',document_number='46/TB-ĐHXDHN-CTSV',
            applicability={'cohort':None,'programme':'Cơ khí; Vật liệu xây dựng; Kỹ thuật Môi trường; Công nghệ thông tin','academic_year':'2025-2026','system':'nữ sinh năm 3 hệ 4 năm hoặc năm 4 hệ 5 năm'},
            visual_evidence=str((OUT / f'stem-{i}.png').relative_to(ROOT)),
            review_status='all_six_pages_visually_checked_manual_transcription',ocr_quality='scan_manual_corrected',
            limitations=['Mốc nộp hồ sơ năm 2026 đã qua; không suy ra đợt học bổng hiện hành.', 'Số điện thoại/email công bố giữ tại bản gốc, không nhập vào văn bản cho mô hình.'])
    arch = read(OUT / 'architecture-native-pages.json')
    courses=[]; semester=None
    # Geometry-aware grid extraction preserves the multi-code elective cells.
    with pdfplumber.open(checked(ROOT / arch['source_file'])) as pdf:
        for page_no,page in enumerate(pdf.pages[:3],1):
            for table in page.find_tables():
                for grid,row in zip(table.rows,table.extract(),strict=True):
                    if row[1] and row[1].startswith('Học kỳ'):
                        semester=int(re.search(r'\d+',row[1])[0]);continue
                    if row[0] == '' and page_no==3 and row[1]:
                        courses[-1]['codes'].extend(row[1].splitlines())
                        courses[-1]['locators'].append({'page':page_no,'bbox':grid.bbox});continue
                    if not row[0] or not row[0].isdigit():continue
                    courses.append({'semester':semester,'ordinal':int(row[0]),'codes':row[1].splitlines(),
                        'name':' '.join(row[2].split()),'credits':int(row[3]),'knowledge_block':row[4],
                        'requirement':'elective_group' if 'tự chọn' in ' '.join(row[2].split()) else 'not_explicitly_labelled',
                        'locators':[{'page':page_no,'bbox':grid.bbox}]})
    totals={s:sum(c['credits'] for c in courses if c['semester']==s) for s in range(1,11)}
    assert list(totals.values())==[18,21,23,22,22,16,18,15,15,10]
    assert len(courses)==67, len(courses)
    scope='PDF phiên bản 2025; cùng Drive ID được HUCE liên kết ở bảng K71 và bảng các khóa từ K70 về trước. PDF không tự ghi khóa.'
    normalized={'source_file':arch['source_file'],'source_sha256':arch['sha256'],'pages_reviewed':[1,2,3,4,5],
        'courses':courses,'semester_credit_sums':totals,'computed_total_credits':sum(totals.values()),
        'total_basis':'computed sum of 67 grid rows counting each elective group once; no printed total',
        'cohort':None,'scope_evidence':scope,'degree_level':'Kiến trúc sư','degree_evidence':'page 4 Mục tiêu chung: Đào tạo kiến trúc sư',
        'exclusion_clause':None,'prerequisites':None,'concurrent_courses':None,
        'elective_rule':None,'elective_rule_note':'Four multi-code elective cells are retained as groups. No explicit choose-count or individual option names are supplied by this PDF.',
        'completion_status':'content_extracted_all_pages_scope_limitations_explicit',
        'publication_evidence':{'source_file':'data/huce-discovery-20261020/objects/2d37c91e7a53a481580e94d2c1b393a2340a71fa1ea0f370d2bb14ddd1b54ccb','table_indices':[0,1]}}
    save(OUT / 'architecture-reviewed-full.json',normalized)
    # Full page transcriptions, including objectives/outcomes, enter RAG rather than a sample of courses.
    for page in arch['pages']:
        text=page['text']
        if page['page']<=3:
            rows=[c for c in courses if c['locators'][0]['page']==page['page']]
            text='Mã HP (các mã trong một ô giữ chung nhóm) | Tên học phần | TC | Khối kiến thức | Học kỳ\n'+'\n'.join(
                f"{' / '.join(c['codes'])} | {c['name']} | {c['credits']} | {c['knowledge_block']} | {c['semester']}" for c in rows)
        text=scope+'\n'+text
        if page['page']==1:
            text+='\nTổng cộng tính từ các dòng bảng: 180 tín chỉ, tính mỗi nhóm tự chọn một lần. PDF không in tổng hoặc ngoại lệ GDTC/GDQP; không suy ra ngoại lệ. Tổng từng kỳ: '+str(totals)
        chunk(old_arch,text,f'Kiến trúc phiên bản 2025 — toàn bộ nội dung trang {page["page"]}/5',
            title='Khung chương trình ngành Kiến trúc — phiên bản 2025',page=page['page'],page_end=page['page'],
            cohort=None,academic_year=None,total_credits=180,total_credit_basis=normalized['total_basis'],
            applicability={'cohort':None,'programme':'Kiến trúc','degree':'Kiến trúc sư','system':'chính quy','academic_year':None},
            limitations=[scope,normalized['elective_rule_note'],'Không có quan hệ tiên quyết/song hành được ghi trong PDF này.'],
            visual_evidence=str((OUT / f'architecture-{page["page"]}.png').relative_to(ROOT)),
            review_status='five_pages_visually_checked_full_content_extracted')
    release={'public_only':True,'acquired_at':now,'version_label':'reviewed-corrections-20261021-v3',
             'verification':'source_verified_excerpts','chunks':chunks}
    save(PUB / 'reviewed-corrections-20261021-v3.json',release)
    save(OUT / 'batch1-content-validation.json',{'chunks':len(chunks),'architecture_grid_rows':len(courses),
        'architecture_semester_sums':totals,'architecture_credits':sum(totals.values()),
        'stem_pages':6,'english_full_article':True,'independent_documents_fully_completed':None,
        'curriculum_documents_content_reviewed':1,'curriculum_remaining':90,
        'note':'Source content review is separate from unresolved applicability and RAG/index activation.'})
    print(json.dumps({'chunks':len(chunks),'architecture_grid_rows':len(courses),'totals':totals},ensure_ascii=False))

if __name__=='__main__':main()
