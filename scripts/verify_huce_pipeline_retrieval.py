"""Source-specific retrieval probes; no answer-generation/provider calls."""
import argparse
import asyncio
from datetime import UTC, datetime
import json
import re
import sys

from huce_document_pipeline import ROOT, PUB, event, preflight, read

sys.path[:0] = [str(ROOT), str(ROOT / 'services/api/src')]
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy
from scripts.public_rag_retrieval import load_public_hybrid_store


async def main(cases_file=None):
    event('preflight', preflight())
    store = load_public_hybrid_store(PUB, tenant_id='HUCE', campus_id='HUCE',
                                    faq_directory=ROOT / 'data/huce-faq-20261013')
    context = RetrievalContext(AuthorizedScope('HUCE', 'HUCE', 'actor', frozenset({'STUDENT'}),
        frozenset({'STUDENT'}), frozenset({'PUBLIC'}), frozenset({'PUBLIC'})),
        'vi', datetime.now(UTC), SimulationPolicy.DENY, '1'*32)
    defaults = [
        ('K71CDS phải chọn bao nhiêu tín chỉ trong nhóm đường sắt chuyên sâu?', 'K71CDS', '8TC'),
        ('K71KEC Hóa học đại cương có mã học phần gì?', 'K71KEC', '240121'),
        ('K71MOE mã môn Điều khiển phi tuyến và ứng dụng là gì?', 'K71MOE', '26xxxx'),
    ]
    cases=read(ROOT/cases_file)['cases'] if cases_file else [dict(query=q,cohort=c,needles=[n]) for q,c,n in defaults]
    results = []
    for case in cases:
        query=case['query'];cohort=case.get('cohort');drive_id=case.get('drive_id');source_url=case.get('source_url')
        assert cohort or drive_id or source_url, 'a probe must identify its expected source'
        try:
            rows = await store.search(query, context)
            evidence = []
            for row in rows:
                source = await store.read(row['source_id'], row['document_version_id'], row['chunk_id'], context=context)
                assert source is not None and source.content_text == row['content_text']
                evidence.append({k:row.get(k) for k in ('source_id','document_version_id','chunk_id','title','section_path','provenance')})
            matching = [row for row in rows if (row.get('canonical_uri')==source_url if source_url else drive_id in row.get('provenance',{}).get('download_url','') if drive_id else
                row.get('provenance',{}).get('applicability',{}).get('cohort')==cohort)
                and (case.get('page') is None or row['page_start']==case['page'])]
            matching=[row for row in matching if all(row.get('provenance',{}).get('applicability',{}).get(key)==value
                for key,value in case.get('expected_applicability',{}).items())]
            if case.get('expected_section_contains'):
                matching=[row for row in matching if case['expected_section_contains'] in row.get('section_path','')]
            passed = any(all(needle in row['content_text'] for needle in case['needles'])
                         and all(re.search(pattern,row['content_text'],re.I) for pattern in case.get('source_patterns',[])) for row in matching)
            results.append({'query':query,'expected_cohort':cohort,'expected_drive_id':drive_id,'expected_source_url':source_url,'source_facts':case['needles'],
                            'source_patterns':case.get('source_patterns',[]),
                            'expected_applicability':case.get('expected_applicability',{}),
                            'expected_section_contains':case.get('expected_section_contains'),
                            'passed':passed,'returned_rows':len(rows),'evidence':evidence})
        except Exception as error:
            results.append({'query':query,'expected_cohort':cohort,'expected_drive_id':drive_id,'expected_source_url':source_url,'passed':False,'error_type':type(error).__name__})
    passed = all(row['passed'] for row in results)
    receipt = event('retrieval-source-probes', {'fingerprint':store.fingerprint,'results':results,
        'passed':passed,'cases_file':cases_file,'answer_generation_calls':0,'limitation':'Selected source retrieval/readback probes only; not full semantic acceptance of the corpus.'})
    print(json.dumps({'receipt':str(receipt.relative_to(ROOT)),'passed':passed,
                      'cases':[{'source':r.get('expected_source_url') or r.get('expected_drive_id') or r['expected_cohort'],'passed':r['passed']} for r in results]}))
    return 0 if passed else 1


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--cases')
    raise SystemExit(asyncio.run(main(parser.parse_args().cases)))
