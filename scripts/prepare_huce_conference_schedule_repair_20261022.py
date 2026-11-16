"""Bind the book's own schedule and scope variant notes to relevant source units."""
import copy
import re
import huce_document_pipeline as p
from huce_public_document_pipeline import normalize


def main():
    p.event('preflight',p.preflight())
    base=p.read(p.BASE/'conference-review-bundle-20261022-59.json')['documents']
    prior=p.read(p.PUB/'reviewed-corrections-20261021-v26.json');docs=[]
    for old in base[2:]:
        d=copy.deepcopy(old)
        d['replaces_excerpt_by_section']={c['section'].removeprefix(d['title']+' — '):c['text_sha256'] for c in prior['chunks'] if c['source_sha256']==d['source_sha256']}
        d['default_unit_source_questions']=['Nguồn có khác biệt giữa các phiên bản chương trình và một số thông tin tác giả. Giữ riêng từng bản; các vị trí khác biệt được ghi trong phần lịch hoặc mục báo cáo tương ứng.']
        d['unit_source_questions']={}
        if d['source_role']=='conference_programme':
            d['unit_source_questions']['Trang 3']=d['source_questions']
            for section in d['reviewed_sections']:
                if any(f'tiểu ban 3, báo cáo {number},' in section['section'] for number in [4,6,7]):d['unit_source_questions'][section['section']]=d['source_questions']
        else:
            acquisition=p.read(p.ROOT/d['acquisition_file']);entry=next(r for r in acquisition['results'] if r.get('drive_id')==d['drive_id'])
            texts={pg['page']:p.read(p.ROOT/pg['data'])['text'] for pg in entry['pages']}
            d['unit_source_questions'].update({'Trang 3':[d['source_questions'][1]],'Trang 5':[d['source_questions'][1]],'Trang 8':[d['source_questions'][0]],
                                              'Trang 18':[d['source_questions'][2]],'Trang 20':[d['source_questions'][2]],'Trang 16':[d['source_questions'][3]]})
            for section in d['reviewed_sections']:
                if section['section'].startswith(('Tóm tắt báo cáo 13:','Tóm tắt báo cáo 17:')):d['unit_source_questions'][section['section']]=[d['source_questions'][2]]
                if section['section'].startswith('Tóm tắt báo cáo 11:'):d['unit_source_questions'][section['section']]=[d['source_questions'][3]]
            count=0
            for page in [6,7,8]:
                text=texts[page];windows=list(re.finditer(r'(?m)^(\d\d:\d\d) [–-] (\d\d:\d\d)',text));number=0
                for index,m in enumerate(windows):
                    if m[1]=='09:45':continue
                    end=windows[index+1].start() if index+1<len(windows) else len(text)
                    tail=text[m.start():end];boundary=re.search(r'(?m)^Chủ tọa phiên họp:|^11:15',tail)
                    if boundary:end=m.start()+boundary.start()
                    raw=text[m.start():end];title,person=raw[m.end()-m.start():].split('Báo cáo viên:',1)
                    presenter=person.split(' (',1)[0].strip();number+=1;count+=1
                    section={'section':f'Chương trình trong kỷ yếu — tiểu ban {page-5}, báo cáo {number}, {m[1]}–{m[2]}',
                        'spans':[{'page':page,'start':m.start(),'end':end,'text_sha256':p.sha(raw.encode())}],
                        'source_text_sha256':p.sha(raw.encode()),'fields':{'Tên báo cáo':title.strip(),'Báo cáo viên':presenter,'Thời gian':m[0]}}
                    d['reviewed_sections'].append(section)
                    if page==8 and number in [4,6,7]:d['unit_source_questions'][section['section']]=[d['source_questions'][0]]
                assert number==10
            assert count==30
        result=normalize(d);print({'source':d['source_identity'],'sections':len(d['reviewed_sections']),'units':len(result['units'])},flush=True);docs.append(d)
    target=p.BASE/'conference-schedule-repair-bundle-20261022-64.json';p.save(target,{'documents':docs});print(p.rel(target))


if __name__=='__main__':main()
