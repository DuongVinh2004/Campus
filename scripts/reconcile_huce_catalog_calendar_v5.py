"""Materialize verified pipeline statuses and the additive FIT calendar source."""
from collections import Counter
import copy

from huce_document_pipeline import ROOT, BASE, PUB, checked, event, preflight, read, rel, save, sha, now
from huce_calendar_pipeline import validate_release


def main():
    event('preflight',preflight())
    previous=checked(ROOT/'data/huce-discovery-20261020/reconciliation-20261021-v3/master_control_catalog_v4.json')
    old=read(previous);catalog=copy.deepcopy(old)
    release_file=PUB/'reviewed-corrections-20261021-v23.json';release=read(release_file)
    marker=read(release_file.with_suffix('.ready.json'))
    assert marker['release_sha256']==sha(release_file.read_bytes())
    assert marker['index_sha256']==sha(checked(ROOT/marker['index']).read_bytes())
    coverage=release['pipeline_coverage'][0];calendar=validate_release(release,coverage)
    checkpoints=sorted((BASE/'events').glob('*-checkpoint.json'));checkpoint=read(checkpoints[-1])
    by_identity={d['identity_key']:d for d in catalog['documents']}
    for review in checkpoint['new_reviewed_documents']:
        item=by_identity['drive:'+review['drive_id']];record=read(ROOT/review['review'])
        assert record['source_sha256'] in item['payload_sha256']
        item.update(verification_status=record['verification_status'],normalization_status=record['normalization_status'],
            indexing_status=review['indexing_status'],completion_status=review['completion_status'],
            pipeline_review_file=review['review'],verified_applicability=record['applicability'],
            limitations=[i['detail'] for i in record['source_issues']])
    key='drive:'+calendar['drive_id'];assert key not in by_identity
    identifier='huce-'+sha(key.encode())[:24];observation_id='it-calendar-20261022-0001'
    dossier=calendar['review_dossier'];urls=[dossier['download_url']]
    doc={'document_id':identifier,'identity_key':key,'identity_basis':'exact Drive ID linked by retained official FIT page',
        'observation_ids':[observation_id],'urls':urls,'payload_sha256':[calendar['source_sha256']],
        'source_sha256':calendar['source_sha256'],'acquisition_status':'downloaded_hash_checked',
        'extraction_status':'original_one_page_text_and_full_table_geometry_retained',
        'verification_status':calendar['verification_status'],'normalization_status':'selected_CNTT_calendar_rows_normalized',
        'indexing_status':'selected_CNTT_rows_and_common_notes_indexed_v23','completion_status':'incomplete',
        'evidence_release':'reviewed-corrections-20261021-v23','pipeline_review_file':coverage['review_file'],
        'degree_level':None,'legal_effective_from':None,'published_at':None,'limitations':calendar['limitations']}
    catalog['documents'].append(doc)
    catalog['observations'].append({'observation_id':observation_id,'document_id':identifier,'identity_key':key,
        'legacy':{'id':observation_id,'original_url':urls[0],'official_url':dossier['publisher_url'],
            'file_path':calendar['source_file'],'file_type':'application/pdf','sha256':calendar['source_sha256'],
            'title':calendar['title_verbatim'],'category':'calendar_exams','acquisition_status':'downloaded',
            'extraction_status':'full_page_and_table_geometry_retained','verification_status':'selected_CNTT_rows_reviewed',
            'verification_evidence':coverage['review_file'],'academic_year':'2026-2027'}})
    counts=dict(Counter(d['completion_status'] for d in catalog['documents']))
    payloads={h for d in catalog['documents'] for h in d['payload_sha256']}
    catalog.update(catalog_version=5,created_at=now(),predecessor=str(previous.relative_to(previous.parent.parent)).replace('\\','/'),
        predecessor_sha256=sha(previous.read_bytes()),pipeline_status_checkpoint=rel(checkpoints[-1]))
    catalog['units'].update(source_identity_candidates=len(catalog['documents']),unique_payload_hashes=len(payloads),
        completion_by_source_identity=counts,current_observation_count=len(catalog['observations']),
        curriculum_complete_reverified=checkpoint['curriculum']['complete'],
        curriculum_checked_but_incomplete=checkpoint['curriculum']['visually_checked_but_incomplete'],
        curriculum_not_yet_rechecked=checkpoint['curriculum']['not_rechecked'],
        curriculum_documents_visually_checked=91-checkpoint['curriculum']['not_rechecked'])
    catalog['observations'][:len(old['observations'])]=old['observations']
    assert catalog['observations'][:-1]==old['observations']
    assert len(catalog['documents'])==len(old['documents'])+1==2180
    assert counts=={'incomplete':2049,'complete':9,'blocked':122}
    assert set(by_identity)=={d['identity_key'] for d in catalog['documents'][:-1]}
    target=checked(previous.with_name('master_control_catalog_v5.json'));save(target,catalog)
    assert read(target)==catalog
    event('catalog-reconciled',{'catalog':rel(target),'catalog_sha256':sha(target.read_bytes()),
        'predecessor':rel(previous),'predecessor_sha256':sha(previous.read_bytes()),'source_status_counts':counts,
        'added_source':key,'pipeline_statuses_materialized':len(checkpoint['new_reviewed_documents']),
        'original_observations_unchanged':True,'independent_intellectual_documents':None})
    print({'catalog':rel(target),'sources':2180,'counts':counts})


if __name__=='__main__':main()
