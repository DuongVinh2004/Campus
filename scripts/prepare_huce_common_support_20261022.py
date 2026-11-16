"""Bind notice338, all annex categories and three unfilled forms to retained originals."""
import copy
import huce_document_pipeline as p
from huce_public_document_pipeline import normalize
from huce_source_registry import Page


def main():
    p.event('preflight',p.preflight())
    review=p.read(p.BASE/'common-student-support-content-review-20261022-68.json')
    geometry=p.read(p.BASE/'common-support-annex-geometry-20261022-69.json')
    assert geometry['source_sha256']==review['pdf_original_sha256']
    acquisition=p.BASE/'it-english-acquisition-20261022T074230954247Z.json'
    entries=p.read(acquisition)['results']; docs=[]
    scope={'cohort':None,'degree':None,'programme':None,'academic_year':'2026-2027',
           'semester':'I','system':'chính quy','campuses':['Hà Nội','Phân hiệu Thành phố Hồ Chí Minh']}
    context='Thông báo338/TB-ĐHXDHN-CTSV ký28/09/2026. Tiếp nhận29/9/2026–20/10/2026; đã hết hạn tại22/10/2026. Không có bằng chứng gia hạn trong bộ nguồn đã đọc. Chỉ áp dụng đối tượng và điều kiện tại từng dòng; không suy mọi sinh viên dân tộc thiểu số đều được miễn học phí.'
    questions=[
        'Thông báo dẫn238/2025/NĐ-CP, mẫu miễn giảm học phí liên kết vẫn dẫn81/2021/NĐ-CP; chưa có đính chính hoặc xác nhận mẫu cập nhật trong bộ nguồn.',
        'Phụ lục in Lô Lô; mẫu miễn giảm in Lô Tô. Giữ riêng hai cách ghi, không tự sửa hay xác nhận tương đương.',
        'Mẫu miễn giảm mục4 in hộ nghèo và hộ cận nghèo; phụ lục1.5 dùng hộ nghèo hoặc hộ cận nghèo. Mẫu mục6nêu chương trình/đề án, phụ lục1.4nêu hệ cử tuyển; không tự đồng nhất.',
        'Mẫu hỗ trợ học tập có yêu cầu/xác nhận thay thế liên quan sổ hộ khẩu, giấy khai sinh; phụ lụcII.2chỉ liệt kê đơn theo mẫu. Không suy mẫu cũ tự thay thế hướng dẫn2026.'
    ]
    for index,a in enumerate(review['articles']):
        page=Page();page.feed(p.checked(p.ROOT/a['source_file']).read_text(encoding='utf8'))
        title=page.text().splitlines()[0]
        assert title.casefold() in page.text().casefold()
        docs.append({'format':'html','source_identity':'url:'+a['url'],'source_file':a['source_file'],'source_sha256':a['source_sha256'],
            'publisher_url':a['url'],'download_url':a['url'],'title':title,'published_at':['2026-09-30','2026-09-29'][index],
            'published_date_literal':a['published_date_literal'],'all_content_checked':True,
            'reviewed_body_sha256':a['body_sha256'],'reviewed_body_links':a['body_links'],
            'applicability':scope,'issuer':'Trường Đại học Xây dựng Hà Nội','source_role':'school_notice',
            'reviewed_context':context,'source_questions':questions,'limitations':['Trang công bố và các tệp đính kèm có nguồn nhận diện riêng.'],
            'review_scope':'All article paragraphs, links and literal publication date checked against original retained HTML.'})
    tables={t['page']:t['rows'] for t in geometry['tables']}
    def heading(page,row):return {'page':page,'table':0,'row':row,'text':tables[page][row][1]}
    rows=[]
    def add(page,row,label,headers,inherit=False):
        origins={str(col):(3 if inherit and col in (2,3) else row) for col in (1,2,3)}
        rows.append({'page':page,'table':0,'row':row,'section':'Phụ lục — '+label,'headings':headers,
                     'cell_rows':origins,'fields':{label:tables[page][origins[str(col)]][col]
                     for col,label in [(1,'Đối tượng và điều kiện'),(2,'Hồ sơ cần nộp'),(3,'Ghi chú')]}})
    hundred=[heading(3,1),heading(3,2)]
    add(3,3,'I.1.1 người có công — nhóm chung',hundred)
    for row in range(4,11):add(3,row,'I.1.1 — '+tables[3][row][1].replace('\n',' ').strip('+ ;'),hundred+[heading(3,3)],True)
    add(3,11,'I.1.2 sinh viên khuyết tật',hundred)
    for row in range(4):add(4,row,'I.'+tables[4][row][0]+' — '+tables[4][row][1].replace('\n',' ')[:95],hundred)
    add(4,5,'I.2 giảm70% học phí',[heading(3,1),heading(4,4)])
    add(5,1,'I.3 giảm50% học phí',[heading(3,1),heading(5,0)])
    add(5,4,'II.1 hỗ trợ chi phí học tập',[heading(5,2),heading(5,3)])
    add(5,6,'II.2 hỗ trợ học tập',[heading(5,2),heading(5,5)])
    assert len(rows)==17
    for entry in entries:
        doc={'format':'pdf','source_identity':'drive:'+entry['drive_id'],'drive_id':entry['drive_id'],
            'source_file':entry['source_file'],'source_sha256':entry['source_sha256'],'publisher_url':entry['publisher_url'],
            'download_url':entry['linked_url'],'acquisition_file':p.rel(acquisition),'page_count':5,
            'title':'Thông báo338/TB-ĐHXDHN-CTSV và toàn bộ phụ lục miễn giảm học phí hỗ trợ học tập HKI2026–2027',
            'all_content_checked':True,'reviewed_pages':[{'page':pg['page'],'image_sha256':pg['image_sha256'],
                'content_checked':True,'notes':'All unique original images inspected in review68; all text and table columns retained, merged cell inheritance checked against actual PDF geometry.'} for pg in entry['pages']],
            'reviewed_annex_rows':copy.deepcopy(rows),'issuer':'Trường Đại học Xây dựng Hà Nội','source_role':'school_notice',
            'document_number':'338/TB-ĐHXDHN-CTSV','published_at':None,'signed_date':'2026-09-28',
            'applicability':scope,'reviewed_context':context,'source_questions':questions,
            'default_unit_source_questions':['Mẫu đơn liên kết có khác biệt với thông báo/phụ lục; xem phần mẫu và ghi chú nguồn. Không tự sửa bản gốc.'],
            'unit_source_questions':{'Phụ lục — II.2 hỗ trợ học tập':[questions[3]],
                'Phụ lục — I.1.6 — '+tables[4][3][1].replace('\n',' ')[:95]:[questions[1]]},
            'limitations':['Giữ nguyên điều kiện kết hợp, các ngoại lệ và kỳ nộp bổ sung riêng của từng dòng. Ô ghi chú trống không có nghĩa miễn nộp bổ sung theo mọi quy định khác.',
                'Không tự suy mức tiền hỗ trợ, tình trạng tiếp nhận muộn, quyết định hưởng cá nhân hay hiệu lực pháp lý hiện tại từ riêng bộ nguồn này.'],
            'review_scope':'Every original page image and full text retained;17annex units bind exact original columns and merged-cell geometry.'}
        docs.append(doc)
    t=review['template']; paragraphs=t['paragraphs'];forms=[]
    for start,end,title_index in [(0,24,2),(24,42,26),(42,len(paragraphs),44)]:
        forms.append({'title':paragraphs[title_index],'start':start,'end':end,'text_sha256':p.sha('\n'.join(paragraphs[start:end]).encode())})
    doc={'format':'docx','source_identity':'drive:'+t['drive_id'],'drive_id':t['drive_id'],
        **{k:t[k] for k in ['source_file','source_sha256','publisher_file','publisher_sha256','publisher_url','document_xml_sha256']},
        'download_url':t['linked_url'],'title':'Ba mẫu đơn miễn giảm học phí hỗ trợ chi phí học tập và hỗ trợ học tập — tệp liên kết thông báo338',
        'all_content_checked':True,'reviewed_paragraphs':paragraphs,'reviewed_forms':forms,'layout_status':'not_verified',
        'applicability':scope,'issuer':'Trường Đại học Xây dựng Hà Nội — mẫu được trang trường liên kết','source_role':'school_form',
        'published_at':None,'reviewed_context':'MẪU ĐƠN CHƯA ĐIỀN. Nội dung XML đã đọc đầy đủ; bố cục Word chưa kiểm chứng. '+context,
        'source_questions':questions+['Chưa có renderer LibreOffice trong bundled runtime; chưa kiểm chứng bố cục và phân trang Word.'],
        'unit_source_questions':{forms[0]['title']:questions[:3],forms[1]['title']:[],forms[2]['title']:[questions[3]]},
        'limitations':['Chỉ đối chiếu nội dung XML, không xác nhận bố cục/phân trang; không điền hay gửi mẫu, không dùng mẫu cũ để tự quyết định điều kiện hiện hành.'],
        'review_scope':'Every nonempty OOXML paragraph retained exactly once across three forms, source ZIP/XML hashes verified. No rendered layout review claimed.'}
    docs.append(doc)
    for d in docs:
        result=normalize(d);print({'source':d['source_identity'],'units':len(result['units']),'complete':result['completion_eligible']})
    target=p.BASE/'common-support-review-bundle-20261022-71.json';p.save(target,{'documents':docs,'prior_content_review':p.rel(p.BASE/'common-student-support-content-review-20261022-68.json')})
    p.event('common-support-normalized',{'bundle':p.rel(target),'sources':5,'annex_rows_per_pdf':17,'forms':3,'layout_status':'not_verified','generation_calls':0})


if __name__=='__main__':main()
