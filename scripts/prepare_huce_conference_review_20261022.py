"""Compile the completed visual review of FIT_CMA2026 source pages."""
import re
import huce_document_pipeline as p
from huce_public_document_pipeline import Article,normalize
from huce_source_registry import Page

WEB='it-english-acquisition-20261022T034712327594Z.json'
PDF='it-english-acquisition-20261022T034814782658Z.json'
BOOK_STARTS=[
 (10,'Ảnh hưởng của vùng tiếp xúc ITZ','Nguyễn Thị Hải Như'),
 (11,'Effects of Reference-Sampling','Nguyen Ha Duong'),
 (11,'Nghiên cứu và phát triển mạng nơ-ron','Trần Khánh Dung'),
 (12,'Tối ưu xếp hạng truy xuất','Triệu Quốc Đạt'),
 (12,'Hierarchical LightGBM','Nguyen Thi Le Hai'),
 (13,'Cumulative Cyber Vulnerability','Vũ Tất Thành'),
 (14,'Đánh giá hiệu quả chưng cất','Triệu Quốc Đạt'),
 (14,'GraphTour:','Nguyen Dinh Quy'),
 (15,'Ảnh hưởng của tiêu chí chọn','Hà Huy Duy Minh'),
 (15,'Survey of Attributes','Nguyen Ha Duong'),
 (16,'A Two-Stage Deep Learning','Quách Nhật Bảo Sơn'),
 (17,'Tối ưu hóa YOLOv8n','Hoàng Khắc Anh Nhật'),
 (18,'Ứng dụng AI Agent','Nguyễn Thanh Thảo'),
 (18,'Nghiên cứu xây dựng công cụ Chatbot','Đỗ Quốc Hoàng'),
 (19,'Chưng cất tri thức chéo','Lê Văn Minh'),
 (20,'Kiến trúc plug-and-play','Nguyễn Tuấn Minh'),
 (20,'Đề xuất kiến trúc tích hợp AI','Nguyễn Hoàng Việt'),
 (21,'Tổng quan các nghiên cứu','Trịnh Quỳnh Anh'),
 (21,'Ứng dụng lập trình ràng buộc CP-SAT','Nguyễn Bằng Giang'),
 (22,'Nghiên cứu xây dựng công cụ hỗ trợ','Đỗ Quốc Hoàng'),
 (23,'Kết hợp học sâu và luật','Đỗ Bảo Hiền Phú'),
 (24,'PLINH engine:','Vũ Tất Thành'),
 (24,'Weighted p-Harmonic','Kieu Thi Thuy Linh'),
 (25,'Vanishing Property','Vu Thi Huong Giang'),
 (25,'Vanishing of p-Harmonic','Vu Thi Ngan'),
 (25,'Vanishing Theorems','Tran Van Khien'),
 (26,'Vanishing Result','Vu Thi Thuy'),
 (26,'Liouville Type Theorem','Vu Thi Thuy'),
 (26,'Phương pháp khớp phân vị','Nguyễn Đức Thịnh'),
 (27,'On the Uniqueness','Hoang Thu Thuy'),
 (27,'A Uniqueness Result','Tran Thi Lieu')]


def span(page,text,start,end):
    assert text[start:end].strip()
    return {'page':page,'start':start,'end':end,'text_sha256':p.sha(text[start:end].encode())}


def paper_sections(texts):
    starts=[]
    for page,prefix,author in BOOK_STARTS:
        assert texts[page].count(prefix)==1,(page,prefix)
        starts.append((page,texts[page].index(prefix),author))
    sections=[]
    for n,(page,offset,author) in enumerate(starts):
        stop_page,stop=starts[n+1][:2] if n+1<len(starts) else (27,len(texts[27]))
        spans=[]
        for current in range(page,stop_page+1):
            text=texts[current];a=offset if current==page else (re.match(r'^\d+\n',text).end() if re.match(r'^\d+\n',text) else 0)
            b=stop if current==stop_page else len(text)
            # A new chapter header belongs to the complete page, not the prior abstract.
            chapter=re.search(r'(?m)^TIỂU BAN',text[a:b])
            if chapter:b=a+chapter.start()
            if text[a:b].strip():spans.append(span(current,text,a,b))
        whole='\n'.join(texts[s['page']][s['start']:s['end']] for s in spans)
        author_offset=whole.index(author)
        affiliation=re.search(r'(?m)^(?:Faculty |Khoa |Viện |1Khoa |\(a\) |\(a\))',whole[author_offset:])
        assert affiliation,(n,whole[:300])
        title=whole[:author_offset].strip();authors=whole[author_offset:author_offset+affiliation.start()].strip()
        assert 'Abstract:' in whole or 'Tóm tắt:' in whole
        sections.append({'section':f'Tóm tắt báo cáo {n+1}: '+ ' '.join(title.split()),'spans':spans,'source_text_sha256':p.sha(whole.encode()),
            'fields':{'Tên báo cáo (theo bản kỷ yếu)':title,'Tác giả (theo bản kỷ yếu)':authors}})
    assert len(sections)==31
    return sections


def programme_sections(texts,source):
    import pdfplumber
    rows=[];bindings=[]
    with pdfplumber.open(p.ROOT/source['source_file']) as pdf:
        for page_number,page in enumerate(pdf.pages,1):
            for table_number,table in enumerate(page.extract_tables()):
                for row_number,row in enumerate(table):
                    values=[v for v in row if v]
                    if len(values)==5 and values[0].isdigit() and re.fullmatch(r'\d\dh\d\d [–-] \d\dh\d\d',values[1]):
                        rows.append(values)
                        columns=[i for i,v in enumerate(row) if v]
                        bindings.append({'Người báo cáo':dict(page=page_number,table=table_number,row=row_number,column=columns[3]),
                                         'Các tác giả':dict(page=page_number,table=table_number,row=row_number,column=columns[4])})
    assert len(rows)==30
    # The row title/presenter/authors remain in the exact native row order.
    starts=[]
    for page,text in texts.items():
        for match in re.finditer(r'(?m)^(\d+) (\d\dh\d\d) [–-] (\d\dh\d\d)',text):
            starts.append((page,match.start(),int(match[1]),match[2],match[3]))
    assert len(starts)==30
    sections=[]
    for index,(page,offset,number,begin,end) in enumerate(starts):
        stop_page,stop=starts[index+1][:2] if index+1<len(starts) else (3,len(texts[3]))
        spans=[]
        for current in range(page,stop_page+1):
            text=texts[current];a=offset if current==page else 0;b=stop if current==stop_page else len(text)
            if current!=page:
                # Repeated running/table headers precede a continued row.
                header=re.match(r'^FIT_CMA2026[^\n]*\nTT Thời gian Báo cáo Người báo cáo Các tác giả[ \t]*\n',text)
                if header:a=header.end()
            tail=text[a:b]
            boundary=re.search(r'(?m)^ ?09h45 [–-] 10h00|^(?:II\.|III\.|IV\.) TIỂU BAN|^Chủ tọa phiên họp:',tail)
            if boundary:b=a+boundary.start()
            if text[a:b].strip():spans.append(span(current,text,a,b))
        row=rows[index];assert int(row[0])==number and row[1]==begin+' – '+end
        first=texts[spans[0]['page']][spans[0]['start']:spans[0]['end']]
        after=re.match(r'\d+ \d\dh\d\d [–-] \d\dh\d\d',first).end()
        presenter=row[3];title_parts=[first[after:first.index(presenter)].strip()]
        if index==17:
            assert len(spans)==2
            title_parts.append(texts[spans[1]['page']][spans[1]['start']:spans[1]['end']].strip())
        whole='\n'.join(texts[s['page']][s['start']:s['end']] for s in spans)
        sections.append({'section':f'Chương trình tiểu ban {(index//10)+1}, báo cáo {number}, {begin}–{end}','source_text_sha256':p.sha(whole.encode()),
            'spans':spans,'fields':{'Tên báo cáo':'\n'.join(title_parts),'Người báo cáo':presenter,'Các tác giả':row[4],'Thời gian':row[1]},
            'field_fragments':{'Tên báo cáo':title_parts},'field_cells':bindings[index]})
    return sections


def main():
    p.event('preflight',p.preflight());web=p.read(p.BASE/WEB)['results'];pdfs=p.read(p.BASE/PDF)['results'];docs=[]
    scope={'cohort':None,'programme':None,'degree':None,'academic_year':None,'event':'FIT_CMA2026','event_date':'2026-10-06'}
    limits=['Hội nghị ngày 06/10/2026 đã qua tại thời điểm đối chiếu 22/10/2026; đây là lịch được công bố, không chứng minh việc tham dự hoặc diễn biến thực tế.',
            'Nội dung tóm tắt và số liệu nghiên cứu là phát biểu của tác giả trong nguồn; chưa được tái lập hay kiểm chứng độc lập. Tên tác giả, người trình bày và chức danh được giữ theo từng bản, không tự hợp nhất danh tính.']
    conflict='Bản chương trình PDF 3 trang và phần chương trình trong kỷ yếu khác nhau: tiểu ban 3 đổi vị trí báo cáo Vũ Thị Thủy/Vũ Thị Ngân ở 09:15 và 10:00; báo cáo Liouville 10:15 ghi người trình bày Vũ Thị Thủy trong bản rời, Trần Văn Khiên trong kỷ yếu. Chưa có chỉ dẫn bản nào thay thế bản nào; giữ cả hai phiên bản.'
    for source in web:
        html=(p.ROOT/source['source_file']).read_text(encoding='utf8');a=Article();a.feed(html);page=Page();page.feed(html)
        docs.append({'format':'html','source_identity':'url:'+source['url'],'source_file':source['source_file'],'source_sha256':source['source_sha256'],
            'publisher_url':source['url'],'download_url':source['url'],'title':page.text().splitlines()[0],
            'published_at':'2026-10-04','published_date_literal':'04/10/2026','all_content_checked':True,
            'reviewed_body_sha256':p.sha(a.text().encode()),'reviewed_body_links':a.links,
            'review_scope':'Every article paragraph and both linked source identities checked; attached PDFs have independent reviews.',
            'issuer':'Trường Đại học Xây dựng Hà Nội — Khoa Công nghệ thông tin','source_role':'faculty_notice',
            'applicability':scope,'reviewed_context':'Thông báo số 2 về FIT_CMA2026, đăng 04/10/2026. Hai URL chứa cùng nội dung bài, được bảo toàn như hai nguồn URL riêng. Chương trình và kỷ yếu được đối chiếu riêng.',
            'source_questions':[],'limitations':list(limits)})
    for n,source in enumerate(pdfs):
        texts={pg['page']:p.read(p.ROOT/pg['data'])['text'] for pg in source['pages']}
        d={'format':'pdf','source_identity':'drive:'+source['drive_id'],'drive_id':source['drive_id'],
            'source_file':source['source_file'],'source_sha256':source['source_sha256'],
            'publisher_url':source['publisher_url'],'download_url':source['linked_url'],'acquisition_file':p.rel(p.BASE/PDF),
            'page_count':source['page_count'],'all_content_checked':True,
            'reviewed_pages':[{'page':pg['page'],'image_sha256':pg['image_sha256'],'content_checked':True,
                'notes':'Entire original page image compared with native text; headings, author roles, continuation, mathematical symbols and printed page numbers checked. All images actually viewed.'} for pg in source['pages']],
            'issuer':'Trường Đại học Xây dựng Hà Nội — Khoa Công nghệ thông tin',
            'source_role':'conference_abstract_book' if n else 'conference_programme',
            'title':'FIT_CMA2026 — Chương trình và báo cáo tóm tắt' if n else 'FIT_CMA2026 — Chương trình hội nghị khoa học (bản rời 3 trang)',
            'published_at':None,'applicability':scope,'review_scope':'All original PDF images and complete native content checked; per-paper/row page slices retain original offsets and hashes.',
            'source_questions':[conflict],'limitations':list(limits),
            'reviewed_context':'Ngày 06/10/2026. Giữ riêng bản chương trình rời và bản kỷ yếu; không suy bản nào là đính chính chính thức. Mỗi bài có tác giả riêng; người báo cáo trong lịch có thể khác tác giả.',
            'reviewed_sections':paper_sections(texts) if n else programme_sections(texts,source)}
        if n:
            d['source_questions'] += ['Phần tổng quan PDF trang 3 ghi khai mạc 7h30–8h20, nhưng lịch chi tiết PDF trang 5 còn mục chụp ảnh/chuyển phòng 08:20–08:30; giữ nguyên hai phạm vi thời gian.',
                'Bản rời ghi đồng tác giả bài AutoResearch là Nguyễn Đình Bản, kỷ yếu ghi Nguyễn Thanh Bản; bài MCP có thêm tác giả Vũ Tất Thành trong kỷ yếu. Chưa có đính chính để đồng nhất các danh sách.',
                'Chương trình trong kỷ yếu ghi đơn vị của Quách Nhật Bảo Sơn là Học viện Công nghệ Bưu chính Viễn thông, trong phần tóm tắt tác giả (a) gắn USTH; giữ đúng từng vị trí nguồn.']
            d['limitations'].append('Bản text trích xuất làm phẳng một số chỉ số/số mũ toán học. Công thức chính xác cần đọc ảnh trang gốc; không suy biểu thức toán học chỉ từ bản text đã làm phẳng.')
            notes=[(24,'O(2N )','Bài PLINH: O(2^N) chuyển thành O(N); R_max = max_i(S_i); F_2-score = 0.2381. Chỉ số là chỉ số dưới, N trong 2^N là số mũ, không phải tích 2N.'),
                   (24,'BiRic a\nf','Bài Weighted p-Harmonic 1-Forms: ký hiệu độ cong là BiRic_f^a (a là chỉ số trên, f là chỉ số dưới).'),
                   (25,'ρ ∈ Ln/2(M )','Các bài toán p-harmonic: ρ ∈ L^{n/2}(M); L^Q và L^Q(M) có Q là số mũ. Không đọc Ln/2 hoặc LQ như tên biến đơn.'),
                   (26,'L2β-','Bài Liouville: năng lượng hữu hạn L^{2β}; bài Vanishing Result cùng trang dùng L^{n/2}. Các biểu thức 2β và n/2 là số mũ.'),
                   (27,'lim supr→∞','Bài của Tran Thi Lieu: limsup_{r→∞} log T(r,f)/r = 0; toán tử sai phân Δ_c f có c là chỉ số dưới. Đây là bản chép ký hiệu từ ảnh, không phải phép chứng minh bổ sung.')]
            d['reviewed_visual_annotations']=[{'page':page,'image_sha256':source['pages'][page-1]['image_sha256'],
                'native_literal':literal,'reviewed_text':text,'review_basis':'Original page image visually read; superscript/subscript positions compared with flattened native extraction.'} for page,literal,text in notes]
        docs.append(d)
    for d in docs:
        r=normalize(d);print({'source':d['source_identity'],'pages':len(r['page_evidence']),'sections':len(d.get('reviewed_sections',[]))},flush=True)
    target=p.BASE/'conference-review-bundle-20261022-59.json';p.save(target,{'documents':docs});print(p.rel(target))


if __name__=='__main__':main()
