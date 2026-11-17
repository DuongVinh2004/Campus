"""Materialize five fully reviewed CNTT source statuses without losing history."""
from collections import Counter
import copy
import huce_document_pipeline as p


def main():
    p.event('preflight',p.preflight())
    previous=p.checked(p.ROOT/'data/huce-discovery-20261020/reconciliation-20261021-v3/master_control_catalog_v6.json')
    old=p.read(previous);catalog=copy.deepcopy(old)
    release_file=p.PUB/'reviewed-corrections-20261021-v25.json';release=p.read(release_file)
    marker=p.read(release_file.with_suffix('.ready.json'))
    assert marker['release_sha256']==p.sha(release_file.read_bytes())
    assert marker['index_sha256']==p.sha(p.checked(p.ROOT/marker['index']).read_bytes())
    lookup={d['identity_key']:d for d in catalog['documents']};items={i['drive_id']:i for i in p.items()}
    for n,coverage in enumerate(release['pipeline_coverage'],1):
        did=coverage['drive_id'];record=p.read(p.ROOT/coverage['review_file']);fresh=p.normalize(items[did],record['review_dossier'])
        assert record==fresh
        doc=lookup['drive:'+did];assert record['source_sha256'] in doc['payload_sha256']
        doc.update(verification_status=record['verification_status'],normalization_status=record['normalization_status'],
            indexing_status='indexed_v25_readback_verified',completion_status='complete' if not record['source_issues'] else 'incomplete',
            pipeline_review_file=coverage['review_file'],verified_applicability=record['applicability'],
            verified_page_applicability=record['review_dossier'].get('page_applicability'),
            limitations=[issue['detail'] for issue in record['source_issues']],evidence_release=release['version_label'])
        observation_id=f'it-curriculum-20261022-{n:04d}';assert observation_id not in doc['observation_ids'];doc['observation_ids'].append(observation_id)
        url=next(c['download_url'] for c in release['chunks'] if c['source_sha256']==record['source_sha256'])
        catalog['observations'].append({'observation_id':observation_id,'document_id':doc['document_id'],'identity_key':doc['identity_key'],
            'legacy':{'id':observation_id,'original_url':url,'file_path':record['source_file'],'file_type':'application/pdf',
                'sha256':record['source_sha256'],'title':record['title_verbatim'],'category':'curriculum',
                'acquisition_status':'downloaded','verification_status':record['verification_status'],'verification_evidence':coverage['review_file']}})
    counts=dict(Counter(d['completion_status'] for d in catalog['documents']))
    checkpoint_file=sorted((p.BASE/'events').glob('*-checkpoint.json'))[-1];checkpoint=p.read(checkpoint_file)
    assert checkpoint['latest_index']['version']==25
    assert {c['drive_id'] for c in release['pipeline_coverage']} <= {r['drive_id'] for r in checkpoint['new_reviewed_documents']}
    curriculum=checkpoint['curriculum']
    catalog.update(catalog_version=7,created_at=p.now(),predecessor=p.rel(previous),predecessor_sha256=p.sha(previous.read_bytes()))
    catalog['units'].update(completion_by_source_identity=counts,current_observation_count=len(catalog['observations']),
        curriculum_documents_visually_checked=curriculum['downloaded']-curriculum['not_rechecked'],curriculum_complete_reverified=curriculum['complete'],
        curriculum_checked_but_incomplete=curriculum['visually_checked_but_incomplete'],curriculum_not_yet_rechecked=curriculum['not_rechecked'])
    catalog['pipeline_status_checkpoint']=p.rel(checkpoint_file)
    assert catalog['observations'][:len(old['observations'])]==old['observations']
    assert len(catalog['documents'])==len(old['documents'])==2184
    assert all(d['payload_sha256']==lookup[d['identity_key']]['payload_sha256'] for d in old['documents'])
    target=p.checked(previous.with_name('master_control_catalog_v7.json'));p.save(target,catalog)
    p.event('catalog-reconciled',{'catalog':p.rel(target),'catalog_sha256':p.sha(target.read_bytes()),'predecessor':p.rel(previous),
        'predecessor_sha256':p.sha(previous.read_bytes()),'source_status_counts':counts,'added_sources':[],
        'reviewed_sources':len(release['pipeline_coverage']),'original_observations_unchanged':True})
    print({'catalog':p.rel(target),'sources':len(catalog['documents']),'counts':counts})


if __name__=='__main__':main()
