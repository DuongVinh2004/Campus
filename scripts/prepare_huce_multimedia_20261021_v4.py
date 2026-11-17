"""Full grid + visually traced arrows for the one-page 71CNDPT source."""
import hashlib
import json
import re
from datetime import UTC,datetime
from pathlib import Path
import pdfplumber
from huce_source_registry import ROOT,checked,save

OUT=ROOT/'data/huce-discovery-20261020/reconciliation-20261021-v3'
PUB=ROOT/'data/huce-public-20261013'
SHA='a445ba9bf610097033a8663a218792ff457cacebe90a4a08f555be779ebf9bae'

def main():
    source=checked(ROOT/'data/huce-discovery-20261020/objects'/SHA)
    assert hashlib.sha256(source.read_bytes()).hexdigest()==SHA
    prior=json.loads((PUB/'reviewed-expansion-20261020-batch2.json').read_text(encoding='utf-8'))
    base=next(c for c in prior['chunks'] if c['source_sha256']==SHA)
    with pdfplumber.open(source) as pdf:
        assert len(pdf.pages)==1
        page=pdf.pages[0];table=page.find_tables()[0];rows=table.extract()
        all_words=page.extract_words()
        courses=[];uncredited=[]
        for ri in range(1,11):
            for col,semester in [(0,1),(1,2),(2,3),(3,4),(4,5),(5,6),(7,7)]:
                text=rows[ri][col]
                if not text or text.startswith('TỰ CHỌN'):continue
                bbox=table.rows[ri].cells[col]
                match=re.fullmatch(r'(\d{6})\s*[–-]\s*(\d+)\s*\n(.*)',text,re.S)
                if not match:
                    uncredited.append({'semester':semester,'name':' '.join(text.split()),'code':None,'credits':None,'page':1,'bbox':bbox})
                    continue
                code,credits,name=match.groups()
                courses.append({'semester':semester,'code':code,'credits':int(credits),'name':' '.join(name.split()),
                    'requirement':'not_explicitly_labelled','knowledge_block':None,'page':1,'bbox':bbox})
        options=[('531833','Lập trình âm thanh số',5,1),('531834','Kỹ thuật âm thanh',5,1),
                 ('531835','Marketing và truyền thông số',6,2),('531836','Thiết kế mỹ thuật CN',6,2)]
        for code,name,sem,group in options:
            courses.append({'semester':sem,'code':code,'credits':2,'name':name,'requirement':'elective',
                'elective_group':group,'knowledge_block':None,'page':1,'bbox':table.rows[9].cells[4 if group==1 else 6]})
        prerequisites=[('428801','428802'),('446601','446602'),('446602','446603'),('446603','446604'),
                       ('390121','396602'),('531816','451802'),('291803','291804')]
        concurrent=[('531829','531830'),('531831','531832'),('531819','531820'),('531826','531827'),
                    ('291804','291805'),('531812','531813')]
        by_code={c['code']:c for c in courses}
        relations=[]
        for kind,pairs in [('prerequisite',prerequisites),('concurrent',concurrent)]:
            for a,b in pairs:
                ca,cb=by_code[a],by_code[b]
                boxes=[ca['bbox'],cb['bbox']]
                relations.append({'type':kind,'from':a,'to':b,'direction':'left_to_right' if kind=='prerequisite' else 'bidirectional_vertical',
                    'evidence':{'page':1,'image':str((OUT/'multimedia-1.png').relative_to(ROOT)),
                        'bbox':[min(x[0] for x in boxes),min(x[1] for x in boxes),max(x[2] for x in boxes),max(x[3] for x in boxes)],
                        'basis':'direct visual trace of blue arrow and page-bottom legend'}})
        totals={s:sum(c['credits'] for c in courses if c['semester']==s and c['requirement']!='elective')+(2 if s in [5,6] else 0) for s in range(1,8)}
        assert list(totals.values())==[18,19,21,22,20,20,10],totals
        assert len(courses)==58,len(courses)
        assert len(uncredited)==4,uncredited
        normalized={'drive_id':'1Y7H3dKHxQYqFNH9niIBZkAVpbPWRA47d','source_file':str(source.relative_to(ROOT)),
            'source_sha256':SHA,'page_count':1,'pages_visually_reviewed':[1],
            'title':'Kế hoạch giảng dạy CTĐT trình độ Cử nhân ngành Công nghệ thông tin/chuyên ngành Công nghệ đa phương tiện – 71CNDPT',
            'cohort':'71CNDPT','degree':'Cử nhân','courses':courses,'excluded_uncredited_cells':uncredited,
            'printed_total_credits':130,'semester_totals':totals,
            'exclusion':'Không tính HP giáo dục thể chất, Giáo dục quốc phòng',
            'elective_groups':[{'group':1,'semester':5,'required_credits':2,'option_codes':['531833','531834']},
                               {'group':2,'semester':6,'required_credits':2,'option_codes':['531835','531836']}],
            'relations':relations,'published_at':None,'legal_effective_from':None,
            'notes':['Tên môn giữ nguyên cách viết tắt của PDF. Khối kiến thức và nhãn bắt buộc không được ghi trong sơ đồ nên để null/not_explicitly_labelled.',
                     'Ghi chú gốc dẫn xem thêm danh mục học phần tự chọn nhưng không cung cấp URL hoặc phụ lục trong PDF; chưa xác định tài liệu danh mục riêng.'],
            'extraction_status':'all_page_content_normalized','verification_status':'full_page_grid_and_13_arrows_checked',
            'completion_status':'source_pdf_content_checked_related_elective_catalog_unresolved'}
        save(OUT/'multimedia-reviewed-full-v4.json',normalized)
        save(OUT/'multimedia-native-evidence-v4.json',{'words':all_words,'table_rows':rows,
            'source_sha256':SHA,'lines':page.lines,'curves':page.curves})
    chunks=[];now=datetime.now(UTC).isoformat()
    for sem in range(1,8):
        text=f"{normalized['title']}\nHọc kỳ {sem}. Tổng học kỳ: {totals[sem]} tín chỉ.\nMã | Tên học phần (giữ cách viết tắt nguồn) | TC | Loại\n"
        text+='\n'.join(f"{c['code']} | {c['name']} | {c['credits']} | "+(f"tự chọn nhóm {c['elective_group']}" if c['requirement']=='elective' else 'nguồn không gắn nhãn bắt buộc') for c in courses if c['semester']==sem)
        text+='\n'+'\n'.join(c['name']+' (nguồn không ghi mã hoặc tín chỉ)' for c in uncredited if c['semester']==sem)
        if sem in [5,6]:text+=f'\nTự chọn {1 if sem==5 else 2}: yêu cầu 2TC trong ô có hai phương án 2TC. Không cộng cả hai phương án vào tổng học kỳ.'
        relevant=[r for r in relations if by_code[r['from']]['semester']==sem or by_code[r['to']]['semester']==sem]
        text+='\nQuan hệ theo mũi tên và chú giải nguồn:\n'+'\n'.join(f"{r['from']} {'→' if r['type']=='prerequisite' else '↔'} {r['to']}: {'học phần tiên quyết' if r['type']=='prerequisite' else 'học phần song hành'}" for r in relevant)
        text+='\nTổng số tín chỉ toàn khóa: 130TC (Không tính HP giáo dục thể chất, Giáo dục quốc phòng). Các ô tự chọn tô màu xanh; nguồn ghi xem thêm danh mục học phần tự chọn.'
        item=dict(base,title=normalized['title'],section=f'Công nghệ đa phương tiện 71CNDPT — đầy đủ học kỳ {sem}, điều kiện và chú giải',
            text=text,text_sha256=hashlib.sha256(text.encode()).hexdigest(),page=1,page_end=1,
            issuer='Trường Đại học Xây dựng Hà Nội — Khoa Công nghệ thông tin',published_at=None,collected_at=now,
            legal_effective_from=None,effective_from=now,effective_date_basis='retrieval admission only; legal date unknown',
            applicability={'cohort':'K71 / 71CNDPT','programme':'Công nghệ thông tin / Công nghệ đa phương tiện','degree':'Cử nhân','system':None,'academic_year':None},
            supersedes=[],limitations=normalized['notes'],ocr_quality='native_pdf_grid_text_visually_reconciled',
            review_scope='All page cells, 7 prerequisite arrows, 6 concurrent arrows, elective credit rules, exclusion and totals checked',
            visual_evidence=str((OUT/'multimedia-1.png').relative_to(ROOT)),review_status='full_pdf_content_checked_related_catalog_pending',
            replaces_excerpt_text_sha256=base['text_sha256'])
        chunks.append(item)
    save(PUB/'reviewed-corrections-20261021-v4.json',{'public_only':True,'acquired_at':now,
        'version_label':'reviewed-corrections-20261021-v4','verification':'source_verified_excerpts','chunks':chunks})
    print(json.dumps({'courses_including_options':len(courses),'excluded_cells':len(uncredited),'relations':len(relations),'chunks':len(chunks),'semesters':totals}))

if __name__=='__main__':main()
