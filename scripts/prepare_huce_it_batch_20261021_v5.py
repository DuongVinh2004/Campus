"""Five PDF grids reviewed against rendered pages, retaining source contradictions."""
import hashlib,json,re
from collections import Counter
from datetime import UTC,datetime
import pdfplumber
from huce_source_registry import ROOT,checked,save

OUT=ROOT/'data/huce-discovery-20261020/reconciliation-20261021-v3'
PUB=ROOT/'data/huce-public-20261013'
COMMON=[('428801','428802'),('446601','446602'),('446602','446603'),('446603','446604')]
CONFIG={
'1nL31OteEeU7ZkRwIxwjrgP_hJO3MK6Ux':('71PM','Kỹ sư',COMMON+[
('390121','396602'),('396602','400101'),('250101','250102'),('461716','608807'),('461762','461706'),
('471792','477717'),('467714','477714'),('941726','471754'),('471754','471755')],[],
['Hai ô tự chọn cùng ghi 6TC; bốn phương án tổng 12TC nhưng tổng kỳ 8 là 16TC, còn 6TC sau 10TC cố định. PDF không nói chọn một trong hai nhóm hay quy tắc khác. Không tự quyết định.']),
'1elVn8XX32jXyYo5eoHfznQ9PFLh01FmF':('71MHT',None,COMMON+[
('390121','396602'),('396602','400101'),('250101','250102'),('461716','608807'),('461762','461706'),
('461706','461788'),('461792','467717'),('467714','477714'),('941726','471754'),('471754','471755')],[],
['PDF không ghi bậc đào tạo trong tiêu đề; không suy từ số kỳ.',
 'Tự chọn 1 ghi 4TC nhưng hai phương án 2TC và 3TC không tạo được 4TC. Tự chọn 2 ghi 4TC có hai phương án 2TC. Tổng kỳ 8 chỉ còn 4TC sau phần cố định, chưa rõ quy tắc chọn giữa các nhóm.',
 'Mã 467710 xuất hiện với hai tên: Chuyên đề tổng hợp và Bảo vệ bản quyền số2; giữ nguyên từng lần xuất hiện.',
 'Ghi chú dẫn xem thêm danh mục tự chọn nhưng PDF không kèm đường dẫn.']),
'1g6k3O-VBtvtXOS5zOPUiQw0AM2yxVMd8':('71CS','Kỹ sư',COMMON+[
('390121','398803'),('398803','400101'),('250101','250102'),('538801','608804'),('608804','478801'),
('608825','608807'),('607715','607711'),('607712','607713')],[],[]),
'1hu58jGFk5Ue0gekWY-9WA-1wFnX7WklU':('71IS','Kỹ sư',COMMON+[
('250101','250102'),('401712','461716'),('461716','462105'),('390121','396602'),('396602','400101'),
('461730','471733'),('450101','461727'),('461727','478801')],
[('471756','471757'),('461730','461731'),('471733','471734'),('461785','462109'),('467705','467704'),('462113','462114')],
['Mã 428802 in cho cả Kinh tế chính trị Mác-Lênin kỳ 3 và CNXH Khoa học kỳ 4. Mã 462112 in cho hai học phần khác nhau kỳ 7. Không sửa mã theo suy đoán.',
 'Hai nhóm tự chọn mỗi nhóm có các phương án 3TC và 2TC; không in định mức hoặc quy tắc chọn; tổng kỳ 8 còn 5TC sau 14TC cố định. Chưa đủ căn cứ xác định chọn nhóm/học phần.',
 'Ghi chú dẫn danh mục học phần tự chọn nhưng chưa xác định tệp riêng.']),
'17OuTKVP2CL3ko8ox3XZatj7f-zzpyNYv':('71DS','Cử nhân',COMMON+[
('400101','407701'),('941714','941715'),('390121','396602'),('941723','941712'),('941712','941721'),
('941713','941722'),('471706','941706'),('941707','941708'),('471754','471755')],[('941708','941709')],[])
}

def main():
    chunks=[];results=[]; now=datetime.now(UTC).isoformat()
    prior=[]
    for name in ['reviewed-expansion-20261020.json','reviewed-expansion-20261020-batch2.json','reviewed-curricula-batch3-verified-20261021.json']:
        prior+=json.loads((PUB/name).read_text(encoding='utf-8'))['chunks']
    for did,(cohort,degree,prereqs,concurrent,issues) in CONFIG.items():
        dest=OUT/'batch-next'/did
        raw=json.loads((dest/'native-grid-unreviewed.json').read_text(encoding='utf-8'))
        source=checked(ROOT/raw['source_file']);base=next(c for c in prior if c['source_sha256']==raw['source_sha256'])
        courses=[];columns=[]
        with pdfplumber.open(source) as pdf:
            page=pdf.pages[0]; t=page.find_tables()[0]
            header=t.extract()[0];grid=t.rows[0].cells
            # Native grid sometimes splits a cell at arrow lines. Read complete semester columns.
            total_row=next(r for r,v in zip(t.rows,t.extract()) if sum(bool(x and re.fullmatch(r'\d{2}',x)) for x in v)>=7)
            printed={}
            for bbox,label in zip(grid,header):
                if not bbox or not label:continue
                sem=int(re.search(r'\d+',label)[0])
                colbox=(bbox[0]+0.1,bbox[3],bbox[2]-0.1,total_row.bbox[1])
                text=page.crop(colbox).extract_text()
                columns.append({'semester':sem,'bbox':colbox,'text':text})
                # Printed totals align with the original header, even with phantom grid columns.
                words=page.crop((bbox[0]+0.1,total_row.bbox[1],bbox[2]-0.1,total_row.bbox[3])).extract_text()
                printed[sem]=int(words)
                pattern=r'(?m)^([0-9x.]{5,8})\s*[–-]\s*(\d+)\s*$'
                matches=list(re.finditer(pattern,text))
                for k,m in enumerate(matches):
                    end=matches[k+1].start() if k+1<len(matches) else len(text)
                    body=text[m.end():end].strip()
                    group_matches=list(re.finditer(r'(?im)^Tự chọn\s*(\d+)[^\n]*',text[:m.start()]))
                    group=int(group_matches[-1][1]) if group_matches else None
                    if not body.startswith('Giáo dục TC'):
                        body=re.split(r'(?im)^(?:GD\s|Giáo dục TC|Tự chọn\s)',body)[0].strip()
                    excluded=bool(re.search(r'Giáo dục quốc phòng|Giáo dục TC',' '.join(body.split()),re.I))
                    # Stable occurrence identity retains duplicated source course codes.
                    code,credits=m.groups()
                    courses.append({'occurrence_id':f'{did}:s{sem}:{code}:{k}', 'semester':sem,'code':code,
                        'credits':int(credits),'name':' '.join(body.split()),'knowledge_block':None,
                        'requirement':'excluded_from_total' if excluded else 'elective' if group else 'not_explicitly_labelled',
                        'elective_group':group,'page':1,'column_bbox':colbox})
            relations=[]
            for kind,pairs in [('prerequisite',prereqs),('concurrent',concurrent)]:
                for a,b in pairs:
                    ca=next(c for c in courses if c['code']==a)
                    cb=next(c for c in courses if c['code']==b)
                    relations.append({'type':kind,'from_occurrence':ca['occurrence_id'],'to_occurrence':cb['occurrence_id'],
                        'from_code':a,'to_code':b,'direction':'arrowhead_points_to_target' if kind=='prerequisite' else 'double_headed',
                        'evidence':{'page':1,'image':str((dest/'page-1.png').relative_to(ROOT)),
                            'source_semester_bbox':ca['column_bbox'],'target_semester_bbox':cb['column_bbox'],
                            'basis':'visual trace of blue arrow; legend on same page'}})
            sums={s:sum(c['credits'] for c in courses if c['semester']==s and c['requirement']=='not_explicitly_labelled') for s in printed}
            has_electives=any(c['requirement']=='elective' for c in courses)
            errors=list(issues)
            if not has_electives and sums!=printed:errors.append(f'Course sums {sums} differ from printed semester totals {printed}')
            assert all(c['name'] and c['name']!='0' for c in courses)
            title=' '.join(page.crop((0,0,page.width,t.bbox[1])).extract_text().split())
            normalized={'drive_id':did,'source_file':raw['source_file'],'source_sha256':raw['source_sha256'],
                'title_verbatim':title,'cohort':cohort,'degree_level':degree,'published_at':None,'legal_effective_from':None,
                'pages_reviewed':[1],'courses_including_options_and_coded_exclusions':courses,
                'full_column_transcriptions':columns,'raw_grid_evidence':'native-grid-unreviewed.json',
                'relations':relations,'printed_semester_totals':printed,'computed_fixed_semester_totals':sums,
                'printed_total':sum(printed.values()),'total_basis':'sum of printed semester values; printed whole-course total agrees',
                'issues':errors,'exclusion':'Không tính HP Giáo dục thể chất và Giáo dục quốc phòng',
                'verification_status':'source_inconsistencies_require_resolution' if errors else 'all_page_content_and_arrows_checked',
                'normalization_status':'complete_with_explicit_source_uncertainties' if errors else 'complete',
                'indexing_status':'prepared_not_yet_built'}
            save(dest/'reviewed-full-v6.json',normalized)
            # Include every source column verbatim (including unnumbered GDTC cells), never truncate to examples.
            for col in columns:
                sem=col['semester']
                relevant=[r for r in relations if f':s{sem}:' in r['from_occurrence'] or f':s{sem}:' in r['to_occurrence']]
                text=title+'\n'+f'Học kỳ {sem}\n'+col['text']+f'\nTổng tín chỉ học kỳ ghi trên PDF: {printed[sem]}.'
                text+='\nTổng số tín chỉ toàn khóa ghi trên PDF: '+str(sum(printed.values()))+'TC. '+normalized['exclusion']+'.'
                text+='\nQuan hệ đã đối chiếu mũi tên và chú giải:\n'+'\n'.join(f"{r['from_code']} {'→' if r['type']=='prerequisite' else '↔'} {r['to_code']}: "+('tiên quyết' if r['type']=='prerequisite' else 'song hành') for r in relevant)
                if errors:text+='\nĐIỂM CHƯA RÕ/SAI LỆCH TRONG NGUỒN, KHÔNG TỰ SUY DIỄN:\n'+'\n'.join(errors)
                item=dict(base,title=f"{base['title']} — nội dung PDF {cohort}",section=f'{cohort} — toàn bộ học kỳ {sem} và quan hệ có chứng cứ',
                    text=text,text_sha256=hashlib.sha256(text.encode()).hexdigest(),source_file=str(source.relative_to(ROOT/'data')),
                    issuer='Trường Đại học Xây dựng Hà Nội — Khoa Công nghệ thông tin',published_at=None,collected_at=now,
                    legal_effective_from=None,effective_from=now,effective_date_basis='retrieval admission; not a legal date',
                    applicability={'cohort':cohort,'programme':base['title'],'degree':degree,'system':None,'academic_year':None},
                    page=1,page_end=1,degree_level=degree,cohort=cohort,academic_year=None,
                    total_credits=sum(printed.values()),total_credit_basis='Printed semester totals and printed whole-course total',
                    supersedes=[],limitations=errors+['Tên và mã giữ nguyên nguồn, kể cả lỗi in; khối kiến thức và nhãn bắt buộc không in nên không suy ra.'],
                    review_scope=f'Full PDF page grid/columns and {len(relations)} visible arrows reconciled; source contradictions explicit',
                    ocr_quality='native_pdf_columns_and_visual_review',visual_evidence=str((dest/'page-1.png').relative_to(ROOT)),
                    review_status=normalized['verification_status'],replaces_excerpt_text_sha256=base['text_sha256'])
                chunks.append(item)
            results.append({'drive_id':did,'cohort':cohort,'courses':len(courses),'relations':len(relations),'issues':errors,
                'status':normalized['verification_status']})
    save(PUB/'reviewed-corrections-20261021-v6.json',{'public_only':True,'acquired_at':now,
        'version_label':'reviewed-corrections-20261021-v6','verification':'source_verified_excerpts','chunks':chunks})
    save(OUT/'batch-next/review-summary-v6.json',{'documents':results,'chunks':len(chunks)})
    print(json.dumps({'documents':results,'chunks':len(chunks)},ensure_ascii=False))

if __name__=='__main__':main()
