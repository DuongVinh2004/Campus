"""Record source comparisons without changing or submitting the public forms."""
import json
import subprocess
import huce_document_pipeline as p
from huce_public_document_pipeline import Article


def main():
    p.event('preflight',p.preflight())
    prior=p.read(p.BASE/'common-student-support-initial-review-20261022-63.json')
    template=p.read(p.BASE/'common-application-template-acquisition-20261022-67.json')
    original=p.checked(p.ROOT/template['source_file'])
    assert p.sha(original.read_bytes())==template['source_sha256']
    runtime=r'C:\Users\Duong Vinh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    code="""import sys,json,hashlib,xml.etree.ElementTree as E
from zipfile import ZipFile
with ZipFile(sys.argv[1]) as z:
 xml=z.read('word/document.xml'); root=E.fromstring(xml); ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
 paragraphs=[''.join(''.join(n.itertext()) for n in para.findall('.//w:t',ns)) for para in root.findall('.//w:p',ns)]
 assert not any('vbaProject' in n or n.startswith('word/embeddings/') for n in z.namelist())
 print(json.dumps({'paragraphs':[t for t in paragraphs if t.strip()],'xml_sha256':hashlib.sha256(xml).hexdigest()},ensure_ascii=False))
"""
    extraction=json.loads(subprocess.run([runtime,'-X','utf8','-B','-c',code,str(original)],check=True,capture_output=True,text=True,encoding='utf8').stdout)
    paragraphs=extraction['paragraphs']
    form='\n'.join(paragraphs)
    assert all(t in form for t in ['ĐƠN XIN MIỄN, GIẢM HỌC PHÍ','ĐƠN ĐỀ NGHỊ HỖ TRỢ CHI PHÍ HỌC TẬP','ĐƠN ĐỀ NGHỊ HỖ TRỢ HỌC TẬP','81/2021','Lô Tô'])
    pages=[]
    for page in prior['pages']:
        data=p.checked(p.ROOT/page['data']);image=p.checked(p.ROOT/page['image'])
        assert p.sha(data.read_bytes())==page['data_sha256'] and p.sha(image.read_bytes())==page['image_sha256']
        pages.append(dict(page,text=p.read(data)['text'],all_native_text_read=True))
    assert '238/2025' in pages[0]['text'] and '20/10/2026' in pages[0]['text'] and 'Lô Lô' in pages[3]['text']
    web=p.read(p.BASE/'it-english-acquisition-20261022T074044093562Z.json');articles=[]
    for source,date in zip(web['results'],['30/09/2026','29/09/2026'],strict=True):
        file=p.checked(p.ROOT/source['source_file']);raw=file.read_text(encoding='utf8')
        assert p.sha(file.read_bytes())==source['source_sha256'] and date in raw
        article=Article();article.feed(raw);assert article.found==1
        articles.append(dict(source,published_date_literal=date,body=article.text(),body_sha256=p.sha(article.text().encode()),body_links=article.links))
    output={'at':p.now(),'status':'source_comparison_recorded_not_normalized_or_indexed',
        'pdf_original_sha256':prior['source_sha256'],'pdf_source_identities':prior['drive_ids'],
        'unique_pdf_pages':pages,'all_unique_original_page_images_previously_inspected':True,
        'articles':articles,'signed_date':'2026-09-28','submission_window':{'from':'2026-09-29','through':'2026-10-20','status_at_20261022':'expired'},
        'template':dict(template,status='OOXML_text_read_layout_review_pending',paragraphs=paragraphs,document_xml_sha256=extraction['xml_sha256']),
        'source_questions':[
            'The linked fee-waiver form cites Decree81/2021 whereas notice338cites Decree238/2025. Preserve both exact citations; source comparison does not establish current legal validity of the older form.',
            'The form prints minority name Lô Tô whereas the2026notice annex prints Lô Lô. Keep both originals; do not silently repair or treat the two literals as verified equivalents.',
            'The study-support form mentions a household registration book and commune confirmation alternatives. Do not use this older template alone to infer2026document requirements.',
            'DOCX rendering unavailable: packaged renderer reports LibreOffice soffice.exe missing on PATH; standard ProgramFiles locations also absent. No layout verification or form completion claimed.'
        ],'annex_review':{'eligibility_and_proof_columns_checked':True,'geometry_tables_read_pages':[3,4,5],
            'notes':'Merged cells in1.1apply the same proof and one-time submission note to all seven listed revolutionary-family categories. Preserve100/70/50percent headings and distinct study-cost versus study-support categories, all exclusions and differing proof recurrence.'},
        'actions':'Read-only source review; no form filled or submitted, no message sent, originals retained.'}
    destination=p.checked(p.BASE/'common-student-support-content-review-20261022-68.json');p.save(destination,output);print(p.rel(destination))


if __name__=='__main__':main()
