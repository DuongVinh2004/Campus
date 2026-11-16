"""Append two source-bound conference PDFs and materialize four reviewed sources."""
from collections import Counter
import copy
import huce_document_pipeline as p
from huce_public_document_pipeline import validate_release


def main():
    p.event('preflight',p.preflight())
    previous=p.checked(p.ROOT/'data/huce-discovery-20261020/reconciliation-20261021-v3/master_control_catalog_v7.json')
    old=p.read(previous);catalog=copy.deepcopy(old);by={d['identity_key']:d for d in catalog['documents']}
    release_file=p.PUB/'reviewed-corrections-20261021-v26.json';release=p.read(release_file)
    ready=p.read(release_file.with_suffix('.ready.json'))
    assert ready['release_sha256']==p.sha(release_file.read_bytes())
    assert ready['index_sha256']==p.sha(p.checked(p.ROOT/ready['index']).read_bytes())
    added=[]
    for n,coverage in enumerate(release['pipeline_coverage'],1):
        record=validate_release(release,coverage);dossier=record['review_dossier'];key=record['source_identity']
        if key not in by:
            assert key.startswith('drive:')
            doc={'document_id':'huce-'+p.sha(key.encode())[:24],'identity_key':key,
                'identity_basis':'exact public Drive ID linked by retained official FIT article',
                'observation_ids':[],'urls':[],'payload_sha256':[]}
            by[key]=doc;catalog['documents'].append(doc);added.append(key)
        doc=by[key];observation=f'it-conference-20261022-{n:04d}'
        for field,value in [('observation_ids',observation),('urls',dossier['download_url']),('payload_sha256',record['source_sha256'])]:
            if value not in doc[field]:doc[field].append(value)
        doc.update(source_sha256=record['source_sha256'],acquisition_status='downloaded_hash_checked',
            extraction_status='all_article_or_pdf_page_content_retained',verification_status='all_content_reviewed_with_explicit_source_variants',
            normalization_status='full_pages_and_continued_sections_normalized',indexing_status='indexed_v26_readback_verified',
            completion_status='complete' if record['completion_eligible'] else 'incomplete',pipeline_review_file=coverage['review_file'],
            verified_applicability=dossier['applicability'],source_role=dossier['source_role'],evidence_release=release['version_label'],
            limitations=record['limitations'],source_questions=record['source_questions'])
        catalog['observations'].append({'observation_id':observation,'document_id':doc['document_id'],'identity_key':key,
            'legacy':{'id':observation,'original_url':dossier['download_url'],'official_url':dossier['publisher_url'],
                'file_path':record['source_file'],'file_type':'text/html' if dossier['format']=='html' else 'application/pdf',
                'sha256':record['source_sha256'],'title':record['title_verbatim'],'category':'conference',
                'acquisition_status':'downloaded','verification_status':'all_pages_or_article_content_checked',
                'verification_evidence':coverage['review_file'],'event_date':'2026-10-06'}})
    counts=dict(Counter(d['completion_status'] for d in catalog['documents']))
    catalog.update(catalog_version=8,created_at=p.now(),predecessor=p.rel(previous),predecessor_sha256=p.sha(previous.read_bytes()))
    catalog['units'].update(source_identity_candidates=len(catalog['documents']),completion_by_source_identity=counts,
        current_observation_count=len(catalog['observations']),unique_payload_hashes=len({h for d in catalog['documents'] for h in d['payload_sha256']}))
    assert catalog['observations'][:len(old['observations'])]==old['observations']
    assert all(set(d['payload_sha256'])<=set(by[d['identity_key']]['payload_sha256']) for d in old['documents'])
    target=p.checked(previous.with_name('master_control_catalog_v8.json'));p.save(target,catalog)
    p.event('catalog-reconciled',{'catalog':p.rel(target),'catalog_sha256':p.sha(target.read_bytes()),'predecessor':p.rel(previous),
        'predecessor_sha256':p.sha(previous.read_bytes()),'source_status_counts':counts,'added_sources':added,
        'reviewed_sources':4,'original_observations_unchanged':True,'independent_intellectual_documents':None})
    print({'catalog':p.rel(target),'sources':len(catalog['documents']),'counts':counts,'added_sources':added})


if __name__=='__main__':main()
