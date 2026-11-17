"""Versioned catalog overlay and compact restart checkpoint; no legacy rewrites."""
import hashlib,json,subprocess
from collections import Counter
from datetime import UTC,datetime
from pathlib import Path
from huce_source_registry import ROOT,checked,save
from reconcile_huce_20261021_v3 import identity

OUT=ROOT/'data/huce-discovery-20261020/reconciliation-20261021-v3'

def main():
    catalog=json.loads((OUT/'master_control_catalog_v3.json').read_text(encoding='utf-8'))
    docs={d['identity_key']:d for d in catalog['documents']}
    releases=[json.loads((ROOT/'data/huce-public-20261013'/f'reviewed-corrections-20261021-v{v}.json').read_text(encoding='utf-8')) for v in [3,4,6]]
    completed={'drive:1g6k3O-VBtvtXOS5zOPUiQw0AM2yxVMd8','drive:17OuTKVP2CL3ko8ox3XZatj7f-zzpyNYv','drive:15aajVthfvwJoRiaBFZvsje03VsAxrXci'}
    updated=set()
    for release in releases:
        for c in release['chunks']:
            key=identity(c['download_url']);updated.add(key)
            if key not in docs:
                docs[key]={'document_id':'huce-'+hashlib.sha256(key.encode()).hexdigest()[:24],
                    'identity_key':key,'identity_basis':'Direct attachment publicly embedded by retained HUCE article',
                    'observation_ids':['stem-attachment-acquisition-v3'],'urls':[c['download_url']],
                    'payload_sha256':[c['source_sha256']]}
            d=docs[key]
            d.update(acquisition_status='downloaded_hash_checked',extraction_status='all_source_pages_or_article_extracted',
                verification_status='full_source_checked' if key in completed else 'source_checked_limitations_or_followups_open',
                normalization_status='complete' if key in completed else 'normalized_with_open_source_questions',
                indexing_status='full_extracted_content_indexed_v6',degree_level=c.get('degree_level') or c.get('applicability',{}).get('degree'),
                legal_effective_from=None,completion_status='complete' if key in completed else 'incomplete',
                evidence_release=release['version_label'],source_sha256=c['source_sha256'],
                limitations=c['limitations'],published_at=c.get('published_at'))
    counts=Counter(d['completion_status'] for d in docs.values())
    catalog.update(catalog_version=4,created_at=datetime.now(UTC).isoformat(),
        documents=list(docs.values()),predecessor='reconciliation-20261021-v3/master_control_catalog_v3.json',
        completion_policy='Only 71CS, 71DS and the six-page STEM attachment package are complete in this re-audit. All other legacy completion labels remain unverified historical observations.')
    catalog['units'].update(source_identity_candidates=len(docs),completion_by_source_identity=dict(counts),
        curriculum_complete_reverified=2,curriculum_full_pages_checked=7,curriculum_checked_but_incomplete=5,
        curriculum_not_yet_rechecked=84,independent_intellectual_documents=None)
    assert sum(counts.values())==len(docs)
    save(OUT/'master_control_catalog_v4.json',catalog)
    frontier_path=ROOT/'data/huce-discovery-20261020/run-20261020T152333749632Z/frontier.json'
    frontier=json.loads(frontier_path.read_text(encoding='utf-8'))
    registry=json.loads((frontier_path.parent/'registry.json').read_text(encoding='utf-8'))
    registry_urls={r['url'] for r in registry}
    links=[]
    for row in frontier:
        key=identity(row['url']);d=docs.get(key)
        links.append({'url':row['url'],'discovered_from':row.get('discovered_from'),
            'document_id':d['document_id'] if d else None,'identity_in_catalog':d is not None,
            'exact_url_in_registry':row['url'] in registry_urls})
    frontier_counts=Counter('identity_in_catalog' if r['identity_in_catalog'] else 'not_in_catalog' for r in links)
    save(OUT/'frontier-reconciliation-v4.json',{'source_file':str(frontier_path.relative_to(ROOT)),
        'source_sha256':hashlib.sha256(frontier_path.read_bytes()).hexdigest(),
        'frontier_rows':len(frontier),'distinct_urls':len({r['url'] for r in links}),
        'counts':dict(frontier_counts),'links':links,
        'limitation':'Link membership only, not independent-document count, access status or content review.'})
    summary={'catalog_status_counts':dict(counts),'source_identity_candidates':len(docs),
        'independent_document_total':None,'reviewed_source_snapshots_this_run':len(updated),
        'curriculum':{'downloaded_pdfs':91,'complete':2,'checked_with_open_questions':5,'not_rechecked':84,
            'blocked_drive_files_outside_91':4},'frontier':dict(frontier_counts),
        'release_versions_active':[3,4,6],'release_version_5':'retained_failed_candidate_not_loaded',
        'index':json.loads((OUT/'index-receipt-v6.json').read_text(encoding='utf-8')),
        'probe':{k:v for k,v in json.loads((OUT/'retrieval-probe-v6.json').read_text(encoding='utf-8')).items() if k!='cases'}}
    save(OUT/'checkpoint-summary-v6.json',summary)
    status=subprocess.run(['git','status','--short'],cwd=ROOT,capture_output=True,text=True)
    diff=subprocess.run(['git','diff','--name-only'],cwd=ROOT,capture_output=True,text=True)
    save(OUT/'git-post-batches-v6.json',{'status':status.stdout,'warnings':status.stderr,'tracked_diff_names':diff.stdout,
        'note':'Dirty state pre-existed; this task edited only the source loader plus new scripts/data/index/logs under documented paths.'})
    print(json.dumps({k:v for k,v in summary.items() if k not in {'index','probe'}},ensure_ascii=False))

if __name__=='__main__':main()
