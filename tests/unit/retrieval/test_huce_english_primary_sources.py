"""Bound primary source tables must survive normalization without scope/grade loss."""
import copy
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'scripts'))
import huce_document_pipeline as pipeline
import huce_public_document_pipeline as documents


@pytest.fixture(scope='module')
def bundle():
    return pipeline.read(pipeline.BASE/'it-english-review-bundle-20261022-42.json')['documents']


def test_primary_decision_distinguishes_standard_and_language_programmes(bundle):
    record=documents.normalize(bundle[-1])
    standard,language=record['reviewed_tables']
    assert standard['course_count']==4 and language['course_count']==9
    row=next(r for r in standard['rows'] if r['level']=='4.2')
    assert 'IELTS Academic6.0' in row['source_line'] and 'VSTEP6.5' in row['source_line']
    assert row['grades']==[10,10,10,9]
    assert next(r for r in standard['rows'] if r['level']=='4.3')['grades']==[10]*4
    assert next(r for r in language['rows'] if r['level']=='4.2')['grades']==[10]*8+[9]
    assert record['legal_effective_from']=='2026-01-13'
    assert bundle[-1]['applicability']['cohort_min']==70
    assert len(record['page_evidence'])==10 and not record['completion_eligible']
    assert any('Bảng4' in question for question in record['source_questions'])


@pytest.mark.parametrize('fault',['grade','certificate_number_confused_with_grade','lost_page','article_body','transcript_hash'])
def test_changed_source_evidence_is_rejected(bundle,fault):
    bad=copy.deepcopy(bundle[-1] if fault!='article_body' else bundle[0])
    if fault=='grade':bad['reviewed_tables'][0]['rows'][5]['grades'][-1]=10
    elif fault=='certificate_number_confused_with_grade':bad['reviewed_tables'][0]['rows'][5]['grades'][1]=8
    elif fault=='lost_page':bad['reviewed_pages'].pop()
    elif fault=='article_body':bad['reviewed_body_sha256']='0'*64
    elif fault=='transcript_hash':bad['transcript_sha256']='0'*64
    with pytest.raises(AssertionError):documents.normalize(bad)


def test_all_sources_keep_complete_bodies_and_known_source_limits(bundle):
    records=[documents.normalize(d) for d in bundle]
    assert len(records)==7 and sum(len(r['page_evidence']) for r in records)==19
    assert records[0]['completion_eligible'] and records[5]['completion_eligible']
    assert not records[1]['completion_eligible'] and not records[4]['completion_eligible']
    assert bundle[0]['applicability']['cohorts']==['K70','K71']
    assert 'K71' not in bundle[5]['applicability']['cohorts']
    assert any('120' in limit and '4kỹ năng' in limit for limit in records[5]['limitations'])
    assert sum(len(documents.chunks(r,'2026-10-22T00:00:00+00:00')) for r in records)==39
