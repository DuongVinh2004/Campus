"""Append common/ICT reviews to catalog10 without changing old observations."""
import copy
from collections import Counter
import huce_document_pipeline as p


def main():
    p.event('preflight',p.preflight())
    previous=p.checked(p.ROOT/'data/huce-discovery-20261020/reconciliation-20261021-v3/master_control_catalog_v9.json');old=p.read(previous);catalog=copy.deepcopy(old)
    by={d['identity_key']:d for d in catalog['documents']};added=[];reviewed=[]
    for version in [28,29,30]:
        file=p.PUB/f'reviewed-corrections-20261021-v{version}.json';release=p.read(file)
        ready=p.read(file.with_suffix('.ready.json'))
        assert ready['release_sha256']==p.sha(file.read_bytes())
        assert ready['index_sha256']==p.sha(p.checked(p.ROOT/ready['index']).read_bytes())
        for n,coverage in enumerate(release['pipeline_coverage'],1):
            if coverage['kind']=='reviewed_public_document':
                from huce_public_document_pipeline import validate_release
            else:
                assert coverage['kind']=='reviewed_common_source_slices'
                from huce_common_source_slices import validate_release
            record=validate_release(release,coverage);d=record['review_dossier'];key=record['source_identity']
            if key not in by:
                doc={'document_id':'huce-'+p.sha(key.encode())[:24],'identity_key':key,
                     'identity_basis':'exact official public URL or exact linked public Drive ID; payload equality does not merge source identity',
                     'observation_ids':[],'urls':[],'payload_sha256':[]}
                by[key]=doc;catalog['documents'].append(doc);added.append(key)
            doc=by[key];observation=f'common-ict-review-20261022-v{version}-{n:04d}'
            for field,value in [('observation_ids',observation),('urls',d['download_url']),('urls',d['publisher_url']),('payload_sha256',record['source_sha256'])]:
                if value not in doc[field]:doc[field].append(value)
            partial=coverage['kind']=='reviewed_common_source_slices'
            doc.update(source_sha256=record['source_sha256'],acquisition_status='downloaded_hash_checked',
                extraction_status='selected_original_pages_and_comparison_retained' if partial else 'all_article_pdf_or_form_text_retained',
                verification_status='selected_pages_visually_checked_with_source_differences' if partial else 'source_content_checked_with_explicit_limits',
                normalization_status='source_bound_reviewed_units',indexing_status=f'indexed_v{version}_readback_verified',
                completion_status='incomplete',pipeline_review_file=coverage['review_file'],verified_applicability=d['applicability'],
                source_role=d['source_role'],evidence_release=release['version_label'],source_questions=record['source_questions'],limitations=record['limitations'])
            assert not record['completion_eligible'], 'new unresolved sources must not be reported complete'
            if d.get('layout_status'):doc['layout_status']=d['layout_status']
            catalog['observations'].append({'observation_id':observation,'document_id':doc['document_id'],'identity_key':key,
                'legacy':{'id':observation,'original_url':d['download_url'],'official_url':d['publisher_url'],
                    'file_path':record['source_file'],'sha256':record['source_sha256'],'title':record['title_verbatim'],
                    'category':'student_support' if version==28 else 'it_common_rules' if version==29 else 'common_source_comparison',
                    'verification_status':doc['verification_status'],'verification_evidence':coverage['review_file']}})
            reviewed.append(key)
    audit_file=p.BASE/'common-core-source-audit-20261022-74.json';audit=p.read(audit_file)
    for key,metadata in [
        ('url:https://huce.edu.vn/so-tay-sinh-vien-2026-2027',{'publisher_url':audit['verified_publisher_urls']['handbook'],'whole_document_rechecked':False}),
        ('url:https://huce.edu.vn/quy-che-dao-tao-dai-hoc-chinh-quy',{'publisher_url':audit['verified_publisher_urls']['regulations'],
            'signed_date':'2023-11-06','title':'Quy chế đào tạo trình độ đại học, chuyên sâu đặc thù bậc7','systems':['chính quy','vừa làm vừa học'],
            'whole_document_rechecked':False,'legacy_article_count_45_not_verified':True}),
        ('url:https://huce.edu.vn/quyet-dinh-hoc-phi-nam-hoc-2026-2027',{'publisher_url':audit['verified_publisher_urls']['tuition'],
            'signed_date':'2026-06-10','legacy_date_2026_08_15_not_signed_date':True,'source_scans_checked':2})]:
        assert key in by
        by[key].update(verified_metadata=metadata,common_source_audit=p.rel(audit_file),common_source_audit_sha256=p.sha(audit_file.read_bytes()))
    counts=dict(Counter(d['completion_status'] for d in catalog['documents']))
    catalog.update(catalog_version=10,created_at=p.now(),predecessor=p.rel(previous),predecessor_sha256=p.sha(previous.read_bytes()))
    catalog['units'].update(source_identity_candidates=len(catalog['documents']),completion_by_source_identity=counts,
        current_observation_count=len(catalog['observations']),unique_payload_hashes=len({h for d in catalog['documents'] for h in d['payload_sha256']}))
    assert catalog['observations'][:len(old['observations'])]==old['observations']
    assert all(set(d['payload_sha256'])<=set(by[d['identity_key']]['payload_sha256']) and set(d['observation_ids'])<=set(by[d['identity_key']]['observation_ids']) for d in old['documents'])
    target=p.checked(previous.with_name('master_control_catalog_v10.json'));p.save(target,catalog)
    p.event('catalog-reconciled',{'catalog':p.rel(target),'catalog_sha256':p.sha(target.read_bytes()),
        'predecessor':p.rel(previous),'predecessor_sha256':p.sha(previous.read_bytes()),'source_status_counts':counts,
        'added_sources':added,'reviewed_sources':reviewed,'original_observations_unchanged':True,'independent_intellectual_documents':None})
    print({'catalog':p.rel(target),'sources':len(catalog['documents']),'counts':counts,'added':len(added)})


if __name__=='__main__':main()
