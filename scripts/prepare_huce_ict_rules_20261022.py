"""Bind all19new ICT rule page images and full articles/clauses, preserving source issues."""
import re
import huce_document_pipeline as p
from huce_public_document_pipeline import normalize


def main():
    p.event('preflight',p.preflight())
    acquisition=p.BASE/'it-english-acquisition-20261022T145232183582Z.json'
    entries=p.read(acquisition)['results'];docs=[]
    for index,entry in enumerate(entries):
        d={'format':'pdf','source_identity':'drive:'+entry['drive_id'],'drive_id':entry['drive_id'],
           **{k:entry[k] for k in ['source_file','source_sha256','publisher_url','page_count']},
           'download_url':entry['linked_url'],'acquisition_file':p.rel(acquisition),'all_content_checked':True,
           'title':['Quyết định2114/QĐ-ĐHXDHN31/12/2024 — Quy chế đảm bảo An toàn thông tin HUCE',
                    'Nội quy Phòng thực hành máy tính Trung tâm CNTT&CSDL — bản quyết định09/4/2024'][index],
           'issuer':'Trường Đại học Xây dựng Hà Nội','source_role':'school_decision','published_at':None,
           'legal_effective_from':['2024-12-31','2024-04-09'][index],
           'applicability':{'cohort':None,'programme':None,'degree':None,'academic_year':None,
                            'audience':'Các đơn vị, viên chức, người lao động, sinh viên, học viên và các bên liên quan theo Điều1 của quy chế' if index==0 else 'Sinh viên học, thực hành, thi tại phòng máy do Trung tâm CNTT&CSDL quản lý'},
           'reviewed_pages':[{'page':pg['page'],'image_sha256':pg['image_sha256'],'content_checked':True,
               'notes':'Whole original page image and every native/OCR paragraph read; keep printed page numbering distinct from PDF page number.'} for pg in entry['pages']],
           'reviewed_context':'Nội dung nguồn quy định được trường công bố; chỉ trích xuất và kiểm chứng nội dung. Không thực thi các thao tác quản trị/thu hồi/xóa dữ liệu được tài liệu nhắc đến. Ngày đăng trang TTCNTT khác ngày ký của quyết định.',
           'source_questions':[],
           'limitations':['Ngày có hiệu lực ghi từ ngày ký là thông tin trong nguồn; chưa xác nhận văn bản sửa đổi/thay thế mới nhất hay tính đúng đắn của mọi căn cứ pháp luật được nguồn dẫn.',
                         'Không xem các định nghĩa rút gọn trong phụ lục là tiêu chuẩn kỹ thuật đầy đủ. Không tự thực thi thao tác từ văn bản nguồn.'],
           'review_scope':'All original PDF images and entire native/OCR text read. Continued articles/clauses bind exact page offsets and hashes; no whole-catalog completion inferred.'}
        if index==0:
            d['document_number']='2114/QĐ-ĐHXDHN'
            texts={pg['page']:p.read(p.ROOT/pg['data'])['text'] for pg in entry['pages']}
            starts=[(pg,m.start(),int(m[1])) for pg,text in texts.items() if 3<=pg<=16
                    for m in re.finditer(r'(?m)^Điều (\d+)\.',text)]
            assert [n for _,_,n in starts]==list(range(1,20))
            sections=[]
            for i,(page,start,number) in enumerate(starts):
                end_page,end=(starts[i+1][0],starts[i+1][1]) if i+1<len(starts) else (16,len(texts[16]))
                spans=[];parts=[]
                for pg in range(page,end_page+1):
                    lo=start if pg==page else 0;hi=end if pg==end_page else len(texts[pg])
                    if lo==hi:continue
                    value=texts[pg][lo:hi];parts.append(value)
                    spans.append({'page':pg,'start':lo,'end':hi,'text_sha256':p.sha(value.encode())})
                sections.append({'section':f'Quy chế — Điều{number}: '+texts[page][start:].splitlines()[0].split('. ',1)[1].strip(),
                                 'spans':spans,'source_text_sha256':p.sha('\n'.join(parts).encode())})
            d['reviewed_sections']=sections
            d['source_questions']=['Điều17trong bản gốc đánh số4hai lần cho hai phần khác nhau. Giữ nguyên số và thứ tự nguồn; không tự sửa thành khoản5.',
                'Một số căn cứ và cách diễn giải thuật ngữ trong nguồn cần đối chiếu nguồn pháp luật/tiêu chuẩn riêng; ví dụ nguồn in147/2024ngày25/12/2024và mô tảTier2. Việc đọc nguồn không xác nhận các diễn giải đó là chuẩn bên ngoài.']
            d['default_unit_source_questions']=['Giữ nguyên cách ghi/định nghĩa của bản2114; chưa xác nhận mọi căn cứ pháp luật hay văn bản thay thế mới nhất.']
            d['unit_source_questions']={sections[16]['section']:[d['source_questions'][0]]}
        else:
            transcript=p.BASE/'ict-lab-reviewed-text-20261022-77.json'
            d.update(transcript_file=p.rel(transcript),transcript_sha256=p.sha(transcript.read_bytes()))
            texts={x['page']:x['text'] for x in p.read(transcript)['pages']}
            for pg in d['reviewed_pages']:
                matches=[(f,r) for f in (p.BASE/'ict-lab-ocr-20261022-76').glob('*.json') if (r:=p.read(f))['page']==pg['page']]
                assert len(matches)==1;f,ocr=matches[0]
                pg.update(ocr_file=p.rel(f),ocr_sha256=p.sha(f.read_bytes()))
            d['source_questions']=['Số quyết định viết tay ở trang1chưa đọc chắc chắn; không dùng kết quả OCR5ð3để gán số. Ngày ký09/4/2024được đọc từ ảnh; chờ xác nhận số từ nguồn rõ hơn.']
            sections=[];text=texts[2];matches=list(re.finditer(r'(?m)^(\d+)\. ',text));assert [int(m[1]) for m in matches]==list(range(1,13))
            for i,m in enumerate(matches):
                end=matches[i+1].start() if i+1<len(matches) else len(text);value=text[m.start():end]
                sections.append({'section':f'Nội quy — khoản{m[1]}','spans':[{'page':2,'start':m.start(),'end':end,'text_sha256':p.sha(value.encode())}],
                                 'source_text_sha256':p.sha(value.encode())})
            d['reviewed_sections']=sections
        record=normalize(d);print({'source':d['source_identity'],'pages':len(record['page_evidence']),'units':len(record['units'])})
        docs.append(d)
    file=p.BASE/'ict-rules-review-bundle-20261022-78.json';p.save(file,{'documents':docs});print(p.rel(file))


if __name__=='__main__':main()
