"""Append source-bound English reviews without replacing historical observations."""
from collections import Counter
import copy
from huce_document_pipeline import ROOT, BASE, PUB, checked, event, preflight, read, rel, save, sha, now
from huce_public_document_pipeline import validate_release


def main():
    event('preflight',preflight())
    previous=checked(ROOT/'data/huce-discovery-20261020/reconciliation-20261021-v3/master_control_catalog_v5.json')
    old=read(previous);catalog=copy.deepcopy(old)
    release_file=PUB/'reviewed-corrections-20261021-v24.json';release=read(release_file)
    marker=read(release_file.with_suffix('.ready.json'))
    assert marker['release_sha256']==sha(release_file.read_bytes())
    assert marker['index_sha256']==sha(checked(ROOT/marker['index']).read_bytes())
    by_identity={d['identity_key']:d for d in catalog['documents']};added=[]
    for n,coverage in enumerate(release['pipeline_coverage'],1):
        record=validate_release(release,coverage);dossier=record['review_dossier'];key=record['source_identity']
        observation_id=f'it-english-20261022-{n:04d}'
        if key not in by_identity:
            doc={'document_id':'huce-'+sha(key.encode())[:24],'identity_key':key,
                'identity_basis':'exact public URL or Drive ID linked by retained official publication',
                'observation_ids':[],'urls':[],'payload_sha256':[]}
            by_identity[key]=doc;catalog['documents'].append(doc);added.append(key)
        doc=by_identity[key]
        for field,value in [('observation_ids',observation_id),('urls',dossier['download_url']),('payload_sha256',record['source_sha256'])]:
            if value not in doc[field]:doc[field].append(value)
        doc.update(source_sha256=record['source_sha256'],acquisition_status='downloaded_hash_checked',
            extraction_status='all_article_content_retained' if dossier['format']=='html' else 'all_pdf_pages_and_original_images_retained',
            verification_status='all_content_reviewed_with_explicit_source_limits',normalization_status='reviewed_public_document_normalized',
            indexing_status='indexed_v24_readback_verified',completion_status='complete' if record['completion_eligible'] else 'incomplete',
            pipeline_review_file=coverage['review_file'],verified_applicability=dossier['applicability'],
            evidence_release=release['version_label'],legal_effective_from=record['legal_effective_from'],
            source_role=dossier['source_role'],limitations=record['limitations'],source_questions=record['source_questions'])
        catalog['observations'].append({'observation_id':observation_id,'document_id':doc['document_id'],'identity_key':key,
            'legacy':{'id':observation_id,'original_url':dossier['download_url'],'official_url':dossier['publisher_url'],
                'file_path':record['source_file'],'file_type':'text/html' if dossier['format']=='html' else 'application/pdf',
                'sha256':record['source_sha256'],'title':record['title_verbatim'],'category':'foreign_language_requirements',
                'acquisition_status':'downloaded','extraction_status':'all_content_retained',
                'verification_status':'all_content_reviewed_with_explicit_source_limits','verification_evidence':coverage['review_file']}})
    assert catalog['observations'][:len(old['observations'])]==old['observations']
    assert all(set(d['payload_sha256'])<=set(by_identity[d['identity_key']]['payload_sha256']) for d in old['documents'])
    counts=dict(Counter(d['completion_status'] for d in catalog['documents']))
    catalog.update(catalog_version=6,created_at=now(),predecessor=rel(previous),predecessor_sha256=sha(previous.read_bytes()))
    catalog['units'].update(source_identity_candidates=len(catalog['documents']),current_observation_count=len(catalog['observations']),
        unique_payload_hashes=len({h for d in catalog['documents'] for h in d['payload_sha256']}),completion_by_source_identity=counts)
    catalog['metric_interpretation']={'curriculum_full_pages_checked':'Historical v4 baseline, not a current cumulative count; use current pipeline checkpoint.',
        'independent_intellectual_document_count':None,'completion_unit':'source identity, not an independent intellectual document',
        'html_completion':'entire article checked; linked PDFs have independent completion status'}
    target=checked(previous.with_name('master_control_catalog_v6.json'));save(target,catalog)
    assert read(target)==catalog
    event('catalog-reconciled',{'catalog':rel(target),'catalog_sha256':sha(target.read_bytes()),'predecessor':rel(previous),
        'predecessor_sha256':sha(previous.read_bytes()),'source_status_counts':counts,'added_sources':added,
        'reviewed_sources':7,'original_observations_unchanged':True,'independent_intellectual_documents':None})
    print({'catalog':rel(target),'sources':len(catalog['documents']),'added':len(added),'counts':counts})


if __name__=='__main__':main()
