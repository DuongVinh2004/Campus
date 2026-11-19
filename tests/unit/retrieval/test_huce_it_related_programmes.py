"""Source-specific scope, external identifiers and printed inconsistencies."""
import copy
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'scripts'))
import huce_document_pipeline as pipeline


@pytest.fixture(scope='module')
def bundle():
    return pipeline.read(pipeline.BASE/'review-dossiers-it-related-20261022-50.json')['documents']


def normalize(d):
    return pipeline.normalize(next(i for i in pipeline.items() if i['drive_id']==d['drive_id']),d)


def test_mississippi_writ_courses_and_conditional_us_stage_are_not_lost(bundle):
    result=normalize(bundle[0])
    writ=[c for c in result['courses'] if c.get('external_code')]
    assert [(c['code'],c['credits'],c['semester']) for c in writ]==[('Writ 101',3,3),('Writ 102',3,4)]
    assert all('Mississippi' in c['name_verbatim'] for c in writ)
    assert len(result['courses'])==74 and len(result['relations'])==22
    politics=[c for c in result['courses'] if c['code'] in ['518801','428802','428803']]
    assert all(c['credits']==2 and c['requirement']=='conditional' for c in politics)
    assert all('Writ' not in c['name_verbatim'] for c in politics)
    pe=[c for c in result['courses'] if c['code'] is None]
    assert len(pe)==3 and all('giai đoạn 2 tại Mỹ' in c['condition_verbatim'] for c in pe)
    assert len(result['page_evidence'])==2 and not result['independent_native_page_text'][1]['text'].strip()


def test_computer_science_two_pages_have_independent_cohorts_and_relations(bundle):
    result=normalize(bundle[1]);d=result['review_dossier']
    assert d['page_applicability']['1']['cohort']=='K69'
    assert d['page_applicability']['2']['cohort'] is None and d['page_applicability']['2']['cohort_min']==70
    assert len(result['relations'])==42 and len(result['courses'])==151
    for r in result['relations']:
        assert {l['page'] for l in r['source_locators']}=={r['arrow_page']}
        assert {l['page'] for l in r['target_locators']}=={r['arrow_page']}
    introductions=[c for c in result['courses'] if c['code'] in ['608800','608829']]
    assert [(c['code'],c['credits'],c['locators'][0]['page']) for c in introductions]==[('608800',1,1),('608829',2,2)]
    assert result['printed_total']==180 and sum(result['printed_semester_totals'])==182


@pytest.mark.parametrize('fault',['external_credits','external_identifier','missing_page_endpoint','spaced_star'])
def test_reviewed_native_extensions_reject_number_or_coverage_changes(bundle,fault):
    d=copy.deepcopy(bundle[1] if fault=='missing_page_endpoint' else bundle[0])
    if fault=='external_credits':next(e for e in d['uncoded_entries'] if e.get('external_code'))['credits']=4
    elif fault=='external_identifier':next(e for e in d['uncoded_entries'] if e.get('external_code'))['external_code']='Writ 999'
    elif fault=='missing_page_endpoint':d['relations'][0].pop('from_page')
    elif fault=='spaced_star':d.pop('allow_spaced_credit_marker')
    with pytest.raises(AssertionError):normalize(d)


def test_unresolved_source_codes_and_choices_are_preserved(bundle):
    multimedia,security,data=[normalize(d) for d in bundle[2:]]
    assert multimedia['printed_total'] is None
    assert [(g['printed_credits'],g['choice_count']) for g in multimedia['elective_groups']]==[(2,None),(2,None)]
    assert [c['semester'] for c in multimedia['courses'] if c['code']=='4402xx']==[4,5,6]
    assert len([c for c in security['courses'] if c['code']=='462112'])==2
    assert len([c for c in security['courses'] if c['code']=='428802'])==2
    assert len([c for c in security['courses'] if c.get('condition_verbatim')])==3
    assert all(g['choice_count'] is None and g['printed_credits'] is None for g in security['elective_groups'])
    assert data['printed_total']==130 and data['applicability']['cohort'] is None
    assert any(c['code']=='471706' and 'Cơ sở dữ liệu 1' in c['name_verbatim'] for c in data['courses'])
    assert any(c['code']=='461706' and 'Mạng máy tính' in c['name_verbatim'] for c in data['courses'])
