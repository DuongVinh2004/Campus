"""Real native source variants retain names, choices and missing credits."""
import copy
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'scripts'))
import huce_document_pipeline as pipeline


def actual(did):
    return next(i for i in pipeline.items() if i['drive_id']==did),copy.deepcopy(pipeline.latest_reviews()[did][1]['review_dossier'])


def test_native_appendix_options_keep_explicit_counts_and_conditional_english():
    item,dossier=actual('1TLsDCnQTfTIFQUVTXwGpRSgSc8nT4mVJ')
    result=pipeline.normalize(item,dossier)
    groups={g['group_id']:g for g in result['elective_groups']}
    assert groups['K71MSE-choice-slots1-2']['choice_count']==2
    assert len(groups['K71MSE-choice-slots1-2']['option_occurrences'])==6
    assert groups['K71MSE-choice-slots3-6']['choice_count']==4
    assert len(groups['K71MSE-choice-slots3-6']['option_occurrences'])==14
    options=[c for c in result['courses'] if c.get('native_table_text')]
    assert len(options)==20 and all(c['semester'] is None and c['credits']==2 for c in options)
    english=[c for c in result['courses'] if c.get('credit_annotation')=='*']
    assert len(english)==4 and all(c['requirement']=='conditional' and 'phân loại' in c['condition_verbatim'] for c in english)
    assert any(c['code']=='43010…' and c['name_verbatim'].startswith('GD') for c in result['courses'])


def test_code_only_native_cells_remain_null_credit_and_do_not_merge_names():
    item,dossier=actual('1-Mtww0ZvhodriXZqLlsuiMEk9fx-YxEZ')
    result=pipeline.normalize(item,dossier)
    for code in ['200812','200813','200814','200765']:
        record=next(c for c in result['courses'] if c['code']==code)
        assert record['credits'] is None and record['name_verbatim'] and record['code_only_source_line']==code
        assert record['requirement']=='elective'
    assert next(c for c in result['courses'] if c['code']=='200811')['credits']==2
    assert next(c for c in result['courses'] if c['code']=='43010…')['name_verbatim']=='GDTC1,2,3'


def test_coded_education_name_repairs_do_not_change_any_number_or_other_course():
    bundle=pipeline.read(pipeline.BASE/'review-dossiers-coded-education-name-repair-21.json')
    latest=pipeline.latest_reviews();fixed=0
    for audit in bundle['repair_audit']:
        old=pipeline.read(pipeline.ROOT/audit['prior_review']);new=latest[audit['drive_id']][1]
        assert len(old['courses'])==len(new['courses']) and old['relations']==new['relations']
        for before,after in zip(old['courses'],new['courses'],strict=True):
            if before['name_verbatim']=='':
                assert after['name_verbatim'] and before|{'name_verbatim':after['name_verbatim']}==after
                fixed+=1
            else:assert before==after
    assert fixed==30


@pytest.mark.parametrize('did,expected_courses,expected_options',[
    ('1a6zxKDbwiQR4ECmuU4IuuGgM-Z3K1waR',98,[4,3,3,4,4]),
    ('1k8sgNccSW08U2ipvdXu7oZhJzrGQyNKB',95,[4,3,3,3,4]),
])
def test_ten_semester_grouped_codes_keep_multiline_names_and_literal_annotations(did,expected_courses,expected_options):
    item,dossier=actual(did)
    result=pipeline.normalize(item,dossier)
    assert len(result['courses'])==expected_courses
    assert {c['semester'] for c in result['courses']}==set(range(1,11))
    grouped=[c for c in result['courses'] if '(' in (c['code'] or '')]
    assert [c['code'] for c in grouped]==['430106(07,08)','430110(11,12,13)','430114(15,16)']
    for index,course in enumerate(grouped,1):
        assert course['name_verbatim']==f'Giáo dục\nThể chất {index}'
        assert course['credits']==2 and course['requirement']=='excluded_from_total'
    assert [len(g['option_codes']) for g in result['elective_groups']]==expected_options
    assert all(g['choice_count']==1 for g in result['elective_groups'])
    assert result['printed_total']==185
    if expected_courses==98:
        assert [c['credit_annotation'] for c in result['courses'] if c['semester']==5 and c['requirement']=='elective']==['(2.5)']*4
        assert all(c['credits']==2 for c in result['courses'] if c['semester']==5 and c['requirement']=='elective')
    dossier.pop('grouped_code_source_basis')
    with pytest.raises(KeyError):pipeline.normalize(item,dossier)


@pytest.mark.parametrize('fault',['choice_count','missing_option','bare_code_change'])
def test_native_table_and_bare_code_dispositions_fail_closed(fault):
    if fault=='bare_code_change':
        item,dossier=actual('1-Mtww0ZvhodriXZqLlsuiMEk9fx-YxEZ')
        dossier['reviewed_code_only_lines'][0]['code']='999999'
    else:
        item,dossier=actual('1TLsDCnQTfTIFQUVTXwGpRSgSc8nT4mVJ')
        group=dossier['reviewed_native_option_tables'][0]
        group['choice_count' if fault=='choice_count' else 'expected_option_count']=99
    with pytest.raises(AssertionError):pipeline.normalize(item,dossier)


@pytest.mark.parametrize('did,course_count,ai_code',[
    ('1M2Yl2hr2iyLL-O3HwyYWLraPrmm66LFG',79,'61716'),
    ('10zog4q-v_5cKsmcRCcFwLJXFU5tkTF6B',78,'461716'),
])
def test_it_b7_keeps_scope_conditional_english_and_unprinted_choice_counts(did,course_count,ai_code):
    item,dossier=actual(did)
    result=pipeline.normalize(item,dossier)
    assert len(result['courses'])==course_count
    assert result['applicability']['cohort'] is None and result['applicability']['system']=='Đại học – B7'
    assert next(c for c in result['courses'] if c['code']==ai_code)['semester']==6
    english=[c for c in result['courses'] if c['requirement']=='conditional']
    assert [(c['code'],c['semester'],c['credits']) for c in english]==[('448803',2,2),('440218',6,2)]
    assert all('*' in c['name_verbatim'] and 'một trong hai' in c['condition_verbatim'] for c in english)
    assert len(result['elective_groups'])==2
    assert all(g['choice_count'] is None and len(g['option_codes'])==2 for g in result['elective_groups'])
    assert result['elective_groups'][1]['printed_credits'] is None
    assert result['elective_groups'][0]['printed_credits']==(5 if ai_code=='61716' else None)
    education=[c for c in result['courses'] if c['code'] in ['430120','420102','430103']]
    assert len(education)==3 and all(c['name_verbatim'].startswith('Giáo dục TC') and c['requirement']=='excluded_from_total' for c in education)
    if ai_code=='61716':
        assert len(result['page_evidence'])==2
        assert not next(p for p in result['independent_native_page_text'] if p['page']==2)['text'].strip()
    dossier['reviewed_course_conditions'][0]['condition_verbatim']='Chọn cả hai học phần'
    with pytest.raises(AssertionError,match='condition must occur'):pipeline.normalize(item,dossier)
