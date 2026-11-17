"""Append immutable catalog evidence for a ready release of existing source IDs."""
import argparse
from collections import Counter
import copy
import huce_document_pipeline as p
from huce_public_document_pipeline import validate_release


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--previous',type=int,required=True);parser.add_argument('--version',type=int,required=True);parser.add_argument('--release',type=int,required=True)
    args=parser.parse_args();assert args.version==args.previous+1
    p.event('preflight',p.preflight());folder=p.ROOT/'data/huce-discovery-20261020/reconciliation-20261021-v3'
    previous=p.checked(folder/f'master_control_catalog_v{args.previous}.json');old=p.read(previous);catalog=copy.deepcopy(old)
    by={d['identity_key']:d for d in catalog['documents']};release_file=p.PUB/f'reviewed-corrections-20261021-v{args.release}.json';release=p.read(release_file)
    ready=p.read(release_file.with_suffix('.ready.json'))
    assert ready['release_sha256']==p.sha(release_file.read_bytes()) and ready['index_sha256']==p.sha(p.checked(p.ROOT/ready['index']).read_bytes())
    for n,coverage in enumerate(release['pipeline_coverage'],1):
        partial=coverage['kind']=='reviewed_common_source_slices'
        if partial:
            from huce_common_source_slices import validate_release as validate_slices
            record=validate_slices(release,coverage)
        else:
            assert coverage['kind']=='reviewed_public_document'
            record=validate_release(release,coverage)
        d=record['review_dossier'];key=record['source_identity'];doc=by[key]
        assert record['source_sha256'] in doc['payload_sha256']
        doc.update(verification_status='selected_pages_visually_checked_with_source_differences' if partial else 'all_content_reviewed_with_explicit_source_variants',normalization_status='source_bound_selected_pages_and_comparison' if partial else 'full_pages_and_continued_sections_normalized',
            indexing_status=f'indexed_v{args.release}_readback_verified',evidence_release=release['version_label'],pipeline_review_file=coverage['review_file'],
            completion_status='complete' if record['completion_eligible'] else 'incomplete',source_questions=record['source_questions'],limitations=record['limitations'])
        observation=f'public-review-20261022-release{args.release}-{n:04d}';assert observation not in doc['observation_ids'];doc['observation_ids'].append(observation)
        catalog['observations'].append({'observation_id':observation,'document_id':doc['document_id'],'identity_key':key,
            'legacy':{'id':observation,'original_url':d['download_url'],'official_url':d['publisher_url'],'sha256':record['source_sha256'],
                'file_path':record['source_file'],'title':record['title_verbatim'],'category':'conference' if d['source_role'].startswith('conference_') else d.get('catalog_category','general'),
                'verification_status':doc['verification_status'],'verification_evidence':coverage['review_file']}})
    counts=dict(Counter(d['completion_status'] for d in catalog['documents']))
    catalog.update(catalog_version=args.version,created_at=p.now(),predecessor=p.rel(previous),predecessor_sha256=p.sha(previous.read_bytes()))
    catalog['units'].update(completion_by_source_identity=counts,current_observation_count=len(catalog['observations']))
    assert catalog['observations'][:len(old['observations'])]==old['observations'] and len(catalog['documents'])==len(old['documents'])
    target=p.checked(folder/f'master_control_catalog_v{args.version}.json');p.save(target,catalog)
    p.event('catalog-reconciled',{'catalog':p.rel(target),'catalog_sha256':p.sha(target.read_bytes()),'predecessor':p.rel(previous),
        'predecessor_sha256':p.sha(previous.read_bytes()),'source_status_counts':counts,'added_sources':[],
        'reviewed_sources':len(release['pipeline_coverage']),'original_observations_unchanged':True})
    print({'catalog':p.rel(target),'sources':len(catalog['documents']),'counts':counts})


if __name__=='__main__':main()
