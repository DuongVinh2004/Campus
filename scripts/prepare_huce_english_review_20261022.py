"""Bind the primary agent's completed source review to original bytes and images."""
from pathlib import Path
import re

from huce_document_pipeline import ROOT,BASE,read,save,sha,rel,event,preflight
from huce_public_document_pipeline import Article


def main():
    event('preflight',preflight())
    web=read(BASE/'it-english-acquisition-20261022T031156840772Z.json')['results']
    pdf_file=BASE/'it-english-acquisition-20261022T031242419385Z.json';pdfs=read(pdf_file)['results']
    titles=[
        'Về việc học và đạt chuẩn đầu vào tiếng Anh A2 cho sinh viên K70, 71',
        'CƠ HỘI MIỄN HỌC, MIỄN THI VÀ QUY ĐỔI 9 - 10 ĐIỂM TIẾNG ANH BẰNG CHỨNG CHỈ IELTS/VSTEP',
        'Thông báo số 360/TB-ĐHXDHN về việc tổ chức thi đánh giá trình độ Tiếng anh tháng 10-2026',
        'Quy định về phân loại trình độ đầu vào, chương trình học và chuẩn ngoại ngữ yêu cầu đối với sinh viên đại học hệ chính quy']
    dates=['01/10/2026','19/10/2026','15/10/2026','13/01/2026']
    scopes=[{'cohort':None,'cohorts':['K70','K71'],'programme':'Sinh viên Khoa Công nghệ thông tin','degree':None,'academic_year':None},
        {'cohort':None,'cohort_min':70,'programme':None,'degree':None,'academic_year':None},
        {'cohort':None,'cohorts':['K64','K65','K66','K67','K68','K69','K70'],'programme':None,'degree':None,'academic_year':None},
        {'cohort':None,'cohort_min':70,'programme':None,'degree':None,'system':'Đại học chính quy','academic_year':None}]
    contexts=[
        'Bài ngày01/10/2026 áp dụngK70,K71. Sinh viên có thể tự lựa chọn cơ sở đào tạo; JAXTINA là đơn vị được khuyến khích, không phải nơi học bắt buộc. Hạn đăng ký trung tâm được nêu là04/10/2026, đã qua tại thời điểm đối chiếu22/10/2026; không đồng nhất hạn này với quy định chuẩn A2.',
        'ĐỐI CHIẾU NGUỒN GỐC: Bài dưới đây là nội dung tóm tắt kèm quảng bá. Khẳng định IELTS≥6.0/VSTEP≥6.5 được10điểm cả4học phần không khớp Bảng2 của Quyết định94/QĐ-ĐHXDHN ngày13/01/2026: đúng tại IELTS Academic6.0 hoặcVSTEP6.5 là Anh ngữ1=10,2=10,3=10,4=9; mức10cả4 ở dòngIELTS Academic≥6.5 hoặcVSTEP≥7. Bảng3 cho lớp Anh ngữ/PFIEV khác Bảng2. Giữ nguyên bài để thể hiện mâu thuẫn, không dùng bảng quảng bá thay quyết định gốc.',
        'Nội dung chính nằm trong PDFiframe2trang đã đọc đầy đủ. Tiêu đềHTMLgọi360/TB-ĐHXDHN, nhưng PDFđểtrống số thông báo vàngày ký; không tự điền. Đăng ký13–18/10/2026,nộp150.000đ19/10đến15h21/10đã hết hạn tại22/10; ngày thi từ27/10làDỰ KIẾN. Không suyK71được dự thi vì các nhóm đối tượng in trong PDFchỉ đếnK70.',
        'Trang chính thức công bố Quyết định94/QĐ-ĐHXDHN ngày13/01/2026 và liên kết bản10trang. Phạm vi đại học chính quy từkhóa70; Khóa69vềtrước áp dụng quy định hiện hành của khóa đó.']
    docs=[]
    for n,item in enumerate(web):
        article=Article();article.feed((ROOT/item['source_file']).read_text(encoding='utf8'))
        day,month,year=dates[n].split('/')
        doc={'format':'html','source_identity':'url:'+item['url'],'source_file':item['source_file'],'source_sha256':item['source_sha256'],
             'publisher_url':item['url'],'download_url':item['url'],'title':titles[n],
             'published_at':f'{year}-{month}-{day}','published_date_literal':dates[n],
             'all_content_checked':True,'reviewed_body_sha256':sha(article.text().encode()),'reviewed_body_links':article.links,
             'review_scope':'Every article paragraph and article-body link checked against the bound HTML; linked PDF reviewed separately',
             'applicability':scopes[n],'issuer':'Trường Đại học Xây dựng Hà Nội — Khoa CNTT' if n<3 else 'Trường Đại học Xây dựng Hà Nội',
             'source_role':['faculty_notice','faculty_advertorial_summary','faculty_notice','school_notice'][n],
             'reviewed_context':contexts[n],'source_questions':[],'limitations':['Phân biệt nội dung thông báo/quảng bá với quy định gốc; không suy quyết định công nhận chứng chỉ cho từng sinh viên.']}
        if n==1:
            doc['source_questions']=['Bài khoa chưa đính chính ngưỡng quy đổi10toàn bộ học phần mâu thuẫn Bảng2 của quyết định gốc.']
            doc['replaces_excerpt_text_sha256']='fa4dfd050b8a0354acb45751d83fa342f18320fddde4703aeae993db0e633f9d'
        docs.append(doc)
    transcript=BASE/'q94-reviewed-pages-20261022-41.json';manual=read(transcript)
    for n,item in enumerate(pdfs):
        doc={'format':'pdf','source_identity':'drive:'+item['drive_id'],'drive_id':item['drive_id'],
            'source_file':item['source_file'],'source_sha256':item['source_sha256'],
            'publisher_url':item['publisher_url'],'download_url':item['linked_url'],'acquisition_file':rel(pdf_file),
            'page_count':item['page_count'],'all_content_checked':True,'reviewed_pages':[],
            'issuer':'Trường Đại học Xây dựng Hà Nội' if n>0 else 'HUCE + JAXTINA ENGLISH — tài liệu đề án được khoa liên kết',
            'source_role':['training_proposal','school_notice','school_decision'][n],
            'title':['Đề án triển khai chương trình đào tạo tiếng Anh — HUCE + JAXTINA ENGLISH',
                     'Thông báo tổ chức thi đánh giá trình độ tiếng Anh đợt tháng10năm2026 — PDFđính kèm bài360/TB-ĐHXDHN',
                     'Quyết định 94/QĐ-ĐHXDHN ngày13/01/2026 — Quy định phân loại đầu vào, chương trình học và chuẩn ngoại ngữ'][n],
            'published_at':None,'legal_effective_from':'2026-01-13' if n==2 else None,
            'applicability':{'cohort':'K71','degree':None,'academic_year':None,'programme':None,'additional_audience':'Cao học/nghiên cứu sinh có nhu cầuB2'} if n==0 else scopes[2 if n==1 else 3],
            'review_scope':'Every original PDF page image and full text checked; normalized merged tables preserve literal bounds; raw native/OCR retained',
            'reviewed_context':'','source_questions':[],'limitations':[]}
        for pg in item['pages']:
            ref={'page':pg['page'],'image_sha256':pg['image_sha256'],'content_checked':True,
                 'notes':'Whole page image compared with native text, headings, table rows and source limits; no inferred missing content.'}
            if n==2:
                matches=[(f,r) for f in (BASE/'ocr'/item['drive_id']).glob('*.json') if (r:=read(f))['page']==pg['page']]
                assert len(matches)==1;f,ocr=matches[0];ref.update(ocr_file=rel(f),ocr_sha256=sha(f.read_bytes()))
            doc['reviewed_pages'].append(ref)
        if n==0:
            doc['reviewed_context']='Đây là đề án/lộ trình của đơn vị đào tạo, không phải quyết định ngoại ngữ của HUCE. Các tỷ lệ88%/80% là tuyên bố trong tài liệu, chưa phải bằng chứng độc lập. Bài thông báo A2cho phép tự chọn đơn vị đào tạo.'
            doc['source_questions']=['PDFcó7trang(kèm bìa), kết thúc ở trang in6. Mục lục dẫn chi tiết giai đoạn3A2→B1 và4B1→B2 nhưng các phần này không có trong tệp; chỉ có bảng lộ trình tổng quát.',
                'Bối cảnh nhắcK70, trong khi mục2.1ghi đối tượngK71; giữ hai phát biểu, không tự hợp nhất.']
            doc['limitations']=['Không suy học phí/ưu đãi/hiệu quả thực tế từ tài liệu đề án; không xem JAXTINA là lựa chọn bắt buộc.']
        if n==1:
            doc['reviewed_context']=contexts[2]
            doc['limitations']=['Số và ngày ký trên bản PDFđểtrống; tên360vàngày đăng15/10là dữ liệu từ trang công bố.',
                'Chỉ nghe+đọc120phút(45+75); không đồng nhất kỳ thi2kỹ năng này với chuẩnB2nội bộ4kỹ năng trongQĐ94.']
            doc['source_assertions']=[{'page':1,'pattern':r'13/10/2026\s+đến hết ngày 18/10/2026'},
                {'page':1,'pattern':r'150\.000đ.*?19/10/2026.*?15h00.*?21/10/2026'.replace('.*?',r'[\s\S]*?')},
                {'page':1,'pattern':r'Dự kiến thi từ ngày 27/10/2026'}]
        if n==2:
            doc.update(transcript_file=rel(transcript),transcript_sha256=sha(transcript.read_bytes()),document_number='94/QĐ-ĐHXDHN',
                reviewed_context='Nguồn quyết định gốc. Áp dụng từK70(tuyển sinh2025), không áp dụng ngược choK69vềtrước. IELTS Academic6.0/VSTEP6.5 ởBảng2cho điểm10–10–10–9; IELTS Academic≥6.5/VSTEP≥7mới là10cả4. H là học phần phải học. TOEIC2kỹ năng KHÔNG XÉT CĐR. Không áp Bảng3(lớpAnhngữ/PFIEV)cho chương trình chuẩn.')
            doc['source_questions']=['Điều5dẫn Bảng2,3,4 nhưng tệp10trang chỉ có Bảng1,2,3,5; chưa có Bảng4.',
                'Bảng2/Bảng3 in các khoảngTOEFL iBT46÷60,60÷75,75÷93 có điểm biên60và75chồng nhau; không tự quyết định dòng quy đổi ở biên.']
            doc['limitations']=['Bản chép đã đối chiếu ảnh, chuẩn hóa khoảng trắng và khai triển ôgộp theo từng dòng; ảnh và OCRgốc được giữ. Không tự động quyết định công nhận chứng chỉ cho cá nhân.']
            tables=[]
            for page,count,label,scope in [(8,4,'','Bảng2 — học phần Anh ngữ1–4 của chương trình chuẩn; không áp bảng9học phần cho đối tượng này.'),
                                          (9,9,'TA','Bảng3 — lớpAnhngữvàPFIEV,9học phầnTA1–TA9; không thay thếBảng2cho chương trình chuẩn.')]:
                text=next(x['text'] for x in manual['pages'] if x['page']==page);rows=[]
                for line in text.splitlines():
                    if not re.match(r'Bậc[0-9]',line):continue
                    grades=[int(g) if g.isdigit() else g for g in re.findall((r'TA[1-9]=' if label else r'(?:Anh ngữ1|(?<=[,;])[2-4])=')+r'(10|9|8|H)(?!\d)',line)]
                    assert len(grades)==count
                    rows.append({'level':re.match(r'Bậc([0-9.]+)',line)[1],'source_line':line,'grades':grades})
                tables.append({'page':page,'header':'Bảng2:' if page==8 else 'Bảng3:','scope_verbatim':scope,
                    'expected_rows':8,'course_count':count,'grade_label':label,'rows':rows,
                    'legend':'H: học phần sinh viên phải học. Chứng chỉ chỉ ghi bậc: dùng mức điểm cao nhất của bậc theo ghi chú nguồn; vẫn phải đáp ứng Điều5/6về tính hợp lệ,thời hạn vàkỹ năng.'})
            doc['reviewed_tables']=tables
        docs.append(doc)
    target=BASE/'it-english-review-bundle-20261022-42.json';save(target,{'documents':docs,'reviewer':'Codex primary agent; all four refreshed official article bodies and nineteen PDF page images inspected; primary decision supersedes summary claims only in interpretation, originals retained'})
    print({'dossier':rel(target),'sources':len(docs),'pdf_pages':sum(d.get('page_count',0) for d in docs)})


if __name__=='__main__':main()
