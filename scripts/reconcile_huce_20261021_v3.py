"""Append-only reconciliation. Legacy completion labels are observations, not proof."""
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from huce_source_registry import ROOT, checked, save

OUT = ROOT / 'data/huce-discovery-20261020/reconciliation-20261021-v3'

def sha(value):
    return hashlib.sha256(value).hexdigest()

def identity(url):
    match = re.search(r'drive.google.com/file/d/([^/?]+)', url)
    if match:
        return 'drive:' + match[1]
    p = urlsplit(url)
    return 'url:' + urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or '/', p.query, ''))

def main():
    checked(OUT)
    if OUT.exists():
        raise FileExistsError('version already exists; choose a new version')
    old_path = ROOT / 'data/huce-discovery-20261020/catalog-20261021/master_control_catalog_v2.json'
    old = json.loads(old_path.read_text(encoding='utf-8'))
    curricula = json.loads((ROOT / 'data/huce-discovery-20261020/curricula-processed-20261021/all_91_curricula.json').read_text(encoding='utf-8'))
    groups, payloads, old_ids = defaultdict(list), defaultdict(list), defaultdict(list)
    observations = []
    for i, row in enumerate(old['entries'], 1):
        key = identity(row['original_url'])
        did = 'huce-' + sha(key.encode())[:24]
        oid = f'v2-row-{i:04d}'
        observation = {'observation_id': oid, 'document_id': did, 'identity_key': key, 'legacy': row}
        observations.append(observation)
        groups[did].append(observation)
        old_ids[row['id']].append(oid)
        if row.get('sha256'):
            payloads[row['sha256']].append(oid)
    blocked = {'http_error', 'robots_denied', 'login_required', 'unavailable'}
    documents = []
    for did, obs in groups.items():
        rows = [x['legacy'] for x in obs]
        acquisition = sorted({x.get('acquisition_status') for x in rows})
        is_blocked = all(x in blocked for x in acquisition)
        documents.append({
            'document_id': did, 'identity_key': obs[0]['identity_key'],
            'identity_basis': 'Drive file ID or exact URL without fragment; independent intellectual work not yet established',
            'observation_ids': [x['observation_id'] for x in obs],
            'urls': sorted({x['original_url'] for x in rows}),
            'payload_sha256': sorted({x['sha256'] for x in rows if x.get('sha256')}),
            'acquisition_status': 'blocked' if is_blocked else 'downloaded_unvalidated',
            'extraction_status': 'not_extracted' if is_blocked else 'legacy_extraction_requires_completeness_review',
            'verification_status': 'blocked' if is_blocked else 'not_reverified',
            'normalization_status': 'not_reverified', 'indexing_status': 'legacy_claim_not_content_coverage_evidence',
            'degree_level': None,
            'degree_level_evidence': None,
            'legal_effective_from': None,
            'completion_status': 'blocked' if is_blocked else 'incomplete',
        })
    counts = Counter(x['completion_status'] for x in documents)
    report = {
        'catalog_version': 3, 'created_at': datetime.now(UTC).isoformat(),
        'predecessor': str(old_path.relative_to(ROOT)), 'predecessor_sha256': sha(old_path.read_bytes()),
        'units': {'legacy_rows': len(observations), 'legacy_distinct_ids': len(old_ids),
                  'source_identity_candidates': len(documents),
                  'unique_payload_hashes': len(payloads),
                  'independent_intellectual_documents': None,
                  'completion_by_source_identity': dict(counts),
                  'curriculum_pdfs_downloaded': len(curricula['items']),
                  'curriculum_pdf_pages': sum(x['page_count'] for x in curricula['items']),
                  'curriculum_complete_reverified': 0},
        'count_caveat': 'URL identities are candidates, not certified independent documents. Equal payloads may be generic/error pages; never merge semantic documents on hash alone.',
        'documents': documents, 'observations': observations,
        'legacy_id_collisions': [{'legacy_id': k, 'observation_ids': v} for k, v in old_ids.items() if len(v)>1],
        'shared_payload_relations': [{'sha256': k, 'observation_ids': v, 'relation': 'byte_identical_only'} for k,v in payloads.items() if len(v)>1],
        'quality_findings': {'placeholder_degree_rows': sum(x['legacy'].get('degree_level') == 'Tải tại đây' for x in observations),
            'legacy_courses': sum(len(x['courses']) for x in curricula['items']),
            'pdfs_with_at_most_two_legacy_courses': sum(len(x['courses'])<=2 for x in curricula['items']),
            'zero_course_names': sum(c['name']=='0' for x in curricula['items'] for c in x['courses'])},
    }
    assert sum(counts.values()) == len(documents)
    assert sum(len(x['observation_ids']) for x in documents) == len(observations)
    save(OUT / 'master_control_catalog_v3.json', report)
    # Retain the exact pre-existing Git state alongside this version.
    status = subprocess.run(['git','status','--short'], cwd=ROOT, capture_output=True, text=True)
    save(OUT / 'git-preexisting-state.json', {'returncode':status.returncode,'stdout':status.stdout,'stderr':status.stderr})
    import pdfplumber
    architecture = curricula['items'][0]
    source = checked(ROOT / architecture['source_file'])
    pages = []
    with pdfplumber.open(source) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            pages.append({'page':i,'width':page.width,'height':page.height,'text':page.extract_text(),
                          'words':page.extract_words(), 'tables':page.extract_tables()})
    save(OUT / 'architecture-native-pages.json', {'source_file':str(source.relative_to(ROOT)), 'sha256':sha(source.read_bytes()), 'pages':pages})
    print(json.dumps({'units':report['units'],'quality':report['quality_findings'],'out':str(OUT)},ensure_ascii=False))

if __name__ == '__main__':
    main()
