"""Record bounded common-source review; never infer whole-document completion."""
import re
import huce_document_pipeline as p


def main():
    p.event('preflight',p.preflight())
    handbook=p.read(p.PUB/'handbook-human-reviewed.json')
    regulations=p.read(p.PUB/'regulations-human-reviewed.json')
    root=p.checked(p.BASE/'common-core-review-20261022-73')
    def bind(source,pages,image):
        import pypdfium2 as pdfium
        from PIL import Image
        refs=[]
        with pdfium.PdfDocument(str(source)) as pdf:
            count=len(pdf)
            for n in pages:
                path=p.checked(image(n));bitmap=pdf[n-1].render(scale=2.5)
                rendered=bitmap.to_pil()
                with Image.open(path) as retained:
                    assert rendered.size==retained.size and rendered.convert('RGB').tobytes()==retained.convert('RGB').tobytes()
                bitmap.close()
                refs.append({'pdf_page':n,'image':p.rel(path),'image_sha256':p.sha(path.read_bytes()),
                             'render_scale':2.5,'pixels_reproduced_from_original':True,'image_visually_read':True})
        return {'source_file':p.rel(source),'source_sha256':p.sha(source.read_bytes()),'original_page_count':count,'reviewed_pages':refs}
    h=bind(p.checked(p.PUB/'handbook-2026-2027.pdf'),[26,30,31,49,55],lambda n:root/f'handbook-{n}.png')
    r=bind(p.checked(p.PUB/'training-regulations.pdf'),[1,2,9,10,18,19],lambda n:p.PUB/'regulation-pages'/f'page-{n:02}.png')
    for record,old in [(h,handbook),(r,regulations)]:
        for pg in record['reviewed_pages']:
            chunk=next(c for c in old['chunks'] if c['page']==pg['pdf_page'])
            pg.update(previous_extraction_text=chunk['text'],previous_extraction_sha256=p.sha(chunk['text'].encode()))
        record.update(whole_document_review_complete=False,index_correction_status='not_yet_published')
    fees_root=p.checked(p.ROOT/'.tooling/tuition-credit-rag-20261020-01')
    acquisition=p.read(fees_root/'acquisition.json')
    fees=[]
    for name in ['student-tuition-publication.html','student-tuition-4.jpeg','student-tuition-5.jpeg','tuition-924-2026.pdf']:
        file=p.checked(fees_root/name);assert p.sha(file.read_bytes())==next(x['sha256'] for x in acquisition['files'] if x['file']==name)
        fees.append({'file':p.rel(file),'sha256':p.sha(file.read_bytes()),'images_actually_read':name.endswith('.jpeg')})
    # These are source comparisons, not a determination of current legal validity.
    findings=[
        {'id':'core-source-identities','status':'catalog_metadata_correction_required','detail':'Legacy core handbook/regulation/tuition catalog URLs differ from the actual retained official publication URLs. Keep identities and old observations; add verified publisher links, do not silently rewrite historical source identities.'},
        {'id':'regulation1486-scope','pages':[1,2],'detail':'Signed06/11/2023,1486/QĐ-ĐHXDHN. Actual title covers đại học and chuyên sâu đặc thù bậc7. Điều1covers chính quy and vừa làm vừa học and linked/cooperative programmes subject to the regulation. Legacy label đại học chính quy is incomplete.'},
        {'id':'regulation1486-appendices','pages':[9,19],'status':'source_followup_open','detail':'Điều7references Phụ lục1/2; Điều13references Phụ lục4/5. The retained26page PDF ends in the implementation/reporting provisions; linked appendices need separate discovery and verification. Legacy45articles claim is not verified.'},
        {'id':'registration-load','pages':[9,10],'detail':'Điều7continues across PDF9–10. Minimum2/3and maximum3/2of average semester load under the standard programme plan; not a fixed credit count applicable to every student. Separate current registration windows are needed.'},
        {'id':'graduation-conditions','pages':[18,19],'detail':'Điều13continues across PDF18–19: required credits/compulsory content/output standards, accumulated GPAfrom2.0, stated criminal/disciplinary conditions.45working days begins only after full graduation conditions and obligations are met. The03year clause is conditional on listed remaining GDQP/GDTC/language/IT standards, not an unconditional extension of all study.'},
        {'id':'handbook31-versus-regulation13','pages':[31],'comparison_pdf_pages':[18,19],'status':'unresolved_source_difference','detail':'Sổ tay31prints general-education Fcredits≥5%and a>45day standard-duration statement under hạn chế xếp loại. Điều13.3prints học phần phải học lại vượt quá5%of total programme credits, applicable to excellent/good graduation classification, or discipline from warning upward. Do not merge the scopes or convert45working-day processing time into an automatic study-duration/classification rule.'},
        {'id':'handbook31-versus-q94','pages':[31],'status':'unresolved_source_difference','detail':'Handbook31gives TOEIC450/IELTS4.5for bachelor and TOEIC600/IELTS5.5for engineer/architect without a cohort boundary in that table. ReviewedQĐ94/2026applies fromK70and has distinct validity/skills/score conditions, including TOEIC2skillsnot xétCĐR. Do not use handbook summary alone forK70/K71certificate recognition.'},
        {'id':'handbook49-versus-notice338','pages':[49],'status':'source_channel_difference_recorded','detail':'Handbook49states online application onmotcua.huce.edu.vn then proof submission atCTCT&QLSV. Notice338specifies its2026paper reception locations and expired window, without spelling out that online step. Preserve both source instructions; do not imply current reopening or invent a confirmed replacement channel.'},
        {'id':'handbook26-registration','pages':[26],'detail':'Read all diagram steps and right-side notes. Student portalregistrationrequiresLưu đăng ký. This page supplies no current opening/closing date and no guaranteed payment grace period.'},
        {'id':'handbook30-diploma','pages':[30],'detail':'Read both diploma receipt and copy procedures including survey, clearance, faculty diploma appendix and ID/CCCD. Printed sinh viên.huce.edu.vn literal wraps and contains a space; preserve the source literal separately rather than inventing a URL redirect.'},
        {'id':'tuition924-date','status':'catalog_metadata_correction_required','detail':'Both official student-page images print924/QĐ-ĐHXDHN10/06/2026. Legacycatalog15/08/2026is not the signed date. Preserve distinct image payloads and old acquisition evidence. Fee table rates already in supplemental20261020match the two images checked here.'},
        {'id':'tuition924-units','detail':'PFIEVfromK66backward uses336000đ/ĐVHT; fromK67uses533000under the table credit heading. FromK69bachelor592500and engineer/architect547000are distinct rows; programme for students who already hold bachelor degree696500is a separate row. English/French and international extras are peryear and limited to standard duration. Do not convert ĐVHTtoTCor add extras to all students.'}
    ]
    urls={'handbook':handbook['handbook_publication_url'],'regulations':regulations['sources'][0]['url'],
          'tuition':p.read(p.PUB/'supplemental-20261020.json')['chunks'][0]['url']}
    target=p.BASE/'common-core-source-audit-20261022-74.json'
    p.save(target,{'at':p.now(),'handbook':h,'regulations':r,'tuition_source_files':fees,'verified_publisher_urls':urls,
        'findings':findings,'scope':'Only listed pages and the two tuition scans were visually read this turn. Full original text and all previous evidence retained. Whole common-document completion is not claimed.',
        'next':'Publish source-bound corrections and compare full handbook/regulations plus missing appendices; keep unresolved variants explicit.'})
    print(p.rel(target))


if __name__=='__main__':main()
