"""Selected common-source corrections retain originals and never imply full review."""
import argparse
from huce_document_pipeline import ROOT,BASE,PUB,checked,read,save,sha,rel,now,stamp,event,preflight
from huce_public_document_pipeline import chunks


def normalize(d):
    source=checked(ROOT/d['source_file']);assert sha(source.read_bytes())==d['source_sha256']
    audit_file=checked(ROOT/d['audit_file']);assert sha(audit_file.read_bytes())==d['audit_sha256']
    audit=read(audit_file);bound=audit[d['audit_source']]
    assert bound['source_file']==d['source_file'] and bound['source_sha256']==d['source_sha256']
    legacy_file=checked(ROOT/d['legacy_manifest']);assert sha(legacy_file.read_bytes())==d['legacy_manifest_sha256']
    legacy=read(legacy_file);pages=[];images=[];raw=[]
    for n in d['selected_pages']:
        reference=next(pg for pg in bound['reviewed_pages'] if pg['pdf_page']==n)
        image=checked(ROOT/reference['image']);assert sha(image.read_bytes())==reference['image_sha256']
        assert reference['pixels_reproduced_from_original'] and reference['image_visually_read']
        old=next(c for c in legacy['chunks'] if c.get('page')==n)
        assert sha(old['text'].encode())==reference['previous_extraction_sha256']
        assert old['text']==reference['previous_extraction_text']
        pages.append(n);images.append(reference['image']);raw.append(old['text'])
    assert pages==sorted(set(pages)) and len(pages)<bound['original_page_count']
    findings=[next(f for f in audit['findings'] if f['id']==key) for key in d['finding_ids']]
    assert d['source_questions'] and d['whole_document_complete'] is False
    # The source comparison is shown before the original wording, with both kept.
    text='ĐỐI CHIẾU NGUỒN ĐÃ ĐỌC ẢNH GỐC:\n'
    if d.get('reviewed_comparison_vi'):
        assert d['comparison_reviewed_against_images'] is True
        assert sha(d['reviewed_comparison_vi'].encode())==d['reviewed_comparison_vi_sha256']
        text+=d['reviewed_comparison_vi']+'\n'
    text+='\n'.join(f['detail'] for f in findings)
    text+='\nNỘI DUNG NGUYÊN BẢN TRÍCH XUẤT, GIỮ RIÊNG CÁC PHÁT BIỂU CỦA NGUỒN:\n'+'\n'.join(raw)
    if d.get('visual_table'):
        assert d['selected_pages']==[31] and d['visual_table']==[
            '3.6–4.0: Xuất sắc','3.2–<3.6: Giỏi','2.5–<3.2: Khá','2.0–<2.5: Trung bình']
        text+='\nBảng TBTL(thang4) đọc từ ảnh gốc trang31:\n'+'\n'.join(d['visual_table'])
    replacement=d.get('replacement_raw_sha256')
    if replacement:assert len(raw)==1 and replacement==sha(raw[0].encode())
    return {'kind':'reviewed_common_source_slices','source_file':d['source_file'],'source_sha256':d['source_sha256'],
        'source_identity':d['source_identity'],'title_verbatim':d['title'],
        'units':[{'page':pages[0],'page_end':pages[-1],'section':d['section'],'text':text,'links':[],
                  'image':images[0],'images':images}], 'page_evidence':bound['reviewed_pages'],
        'source_questions':d['source_questions'],'limitations':d['limitations'],'review_dossier':d,
        'printed_total':None,'legal_effective_from':None,'completion_eligible':False}


def validate_release(release,coverage):
    record=read(ROOT/coverage['review_file']);assert normalize(record['review_dossier'])==record
    assert [c for c in release['chunks'] if c['download_url']==coverage['download_url']]==chunks(record,release['acquired_at'])
    assert coverage['complete_eligible_after_index'] is False
    return record


def main():
    event('preflight',preflight());audit_file=BASE/'common-core-source-audit-20261022-74.json';audit=read(audit_file)
    at=now();coverage=[];output=[]
    for source,pages,keys,section in [
        ('handbook',[31],['handbook31-versus-regulation13','handbook31-versus-q94'],'Trang31 — đối chiếu xếp loại tốt nghiệp và ngoại ngữ'),
        ('regulations',[18,19],['graduation-conditions','handbook31-versus-regulation13'],'Điều13 — công nhận tốt nghiệp và cấp bằng, PDF18–19')]:
        source_file=ROOT/audit[source]['source_file'];legacy=PUB/('handbook-human-reviewed.json' if source=='handbook' else 'regulations-human-reviewed.json')
        old=read(legacy);url=audit['verified_publisher_urls'][source]
        download=old.get('handbook_pdf_url') if source=='handbook' else old['sources'][0]['linked_pdf']
        title='Sổ tay sinh viên HUCE năm học2026–2027' if source=='handbook' else 'Quy chế đào tạo1486/QĐ-ĐHXDHN06/11/2023'
        d={'source_identity':'url:'+url if source=='handbook' else 'drive:1vyhUdenpbRKFC_hlFIgnh5oyEz56s8sF',
           'source_file':rel(source_file),'source_sha256':sha(source_file.read_bytes()),'audit_file':rel(audit_file),'audit_sha256':sha(audit_file.read_bytes()),
           'legacy_manifest':rel(legacy),'legacy_manifest_sha256':sha(legacy.read_bytes()),'audit_source':source,'selected_pages':pages,
           'finding_ids':keys,'whole_document_complete':False,'title':title,'section':section,'publisher_url':url,'download_url':download,
           'issuer':'Trường Đại học Xây dựng Hà Nội','published_at':None,'source_role':'school_handbook' if source=='handbook' else 'school_decision',
           'applicability':{'cohort':None,'programme':None,'degree':None,'academic_year':'2026-2027' if source=='handbook' else None},
           'reviewed_context':'Chỉ các trang/mục đã ghi được đối chiếu ảnh và nguồn. Không xác nhận toàn bộ tài liệu hay quyết định tốt nghiệp cá nhân.',
           'review_scope':'Selected full page images read and pixel-reproduced from original PDF; comparison with original rules retained. No full-document completion.',
           'source_questions':['Khác biệt giữa sổ tay31và Điều13quy chế gốc chưa có đính chính trong bộ nguồn; không áp dụng tóm tắt khác biệt như quy tắc chung.',
                               'Chưa kiểm tra lại toàn bộ tài liệu và phụ lục quy trình kèm theo; chưa xác nhận mọi sửa đổi hiện hành.'],
           'limitations':['Bản gốc, văn bản trích xuất và lịch sử trích dẫn cũ giữ nguyên; đối chiếu chỉ bao phủ phạm vi trang đã ghi.']}
        if source=='handbook':
            d.update(replacement_raw_sha256=sha(next(c for c in old['chunks'] if c['page']==31)['text'].encode()),
                     replaces_excerpt_text_sha256=sha(next(c for c in old['chunks'] if c['page']==31)['text'].encode()),
                     visual_table=['3.6–4.0: Xuất sắc','3.2–<3.6: Giỏi','2.5–<3.2: Khá','2.0–<2.5: Trung bình'])
        else:d['document_number']='1486/QĐ-ĐHXDHN'
        record=normalize(d);file=checked(BASE/'document-reviews'/f'{stamp()}-common-{source}.json');save(file,record)
        output+=chunks(record,at);coverage.append({'kind':'reviewed_common_source_slices','source_identity':d['source_identity'],
            'drive_id':d['source_identity'].removeprefix('drive:') if source!='handbook' else download,'download_url':download,
            'review_file':rel(file),'complete_eligible_after_index':False})
    release={'public_only':True,'acquired_at':at,'version_label':'reviewed-corrections-20261021-v30',
             'verification':'source_verified_excerpts','chunks':output,'pipeline_coverage':coverage}
    for c in coverage:validate_release(release,c)
    target=checked(PUB/'reviewed-corrections-20261021-v30.json');save(target,release)
    event('common-core-slices-published',{'release':rel(target),'chunks':len(output),'whole_documents_complete':False})
    print(rel(target))


if __name__=='__main__':main()
