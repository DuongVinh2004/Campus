"""Real calendar rows must retain dates, colour-only meaning and planned scope."""
import copy
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'scripts'))
import huce_document_pipeline as pipeline
import huce_calendar_pipeline as calendar


@pytest.fixture(scope='module')
def dossier():
    return pipeline.read(pipeline.BASE/'calendar-cntt-review-bound-20261022-35.json')


def test_real_cntt_calendar_208_cells_and_provisional_dates(dossier):
    result=calendar.normalize(dossier)
    assert len(result['rows'])==4 and sum(len(r['weeks']) for r in result['rows'])==208
    assert result['completion_status']=='incomplete_other_major_rows_not_reviewed'
    for row in result['rows']:
        assert row['weeks'][0]['start_date']=='2026-08-03'
        assert row['weeks'][23]['start_date']=='2027-01-11'
        assert [w['week'] for w in row['weeks'] if w['colour_role']=='tet_break']==[27,28]
        assert all(not w['printed_marker'] for w in row['weeks'] if w['colour_role']=='tet_break')
        assert [w['week'] for w in row['weeks'] if w['colour_role']=='summer_break']==[49,50,51,52]
    planned=result['rows'][3]
    assert planned['cohort']=='K71' and planned['provisional']
    assert [(w['week'],w['start_date']) for w in planned['weeks'] if w['printed_marker']=='Q']==[(40,'2027-05-03'),(41,'2027-05-10'),(42,'2027-05-17')]
    assert planned['weeks'][3]['colour_role']=='intake' and planned['weeks'][3]['printed_marker']==''
    chunks=calendar.chunks(result,'2026-10-22T00:00:00+00:00')
    assert len(chunks)==5 and all(c['replaces_excerpt_text_sha256'] is None for c in chunks)
    assert chunks[3]['applicability']['provisional'] and 'DỰ KIẾN' in chunks[3]['text']
    assert all(c['total_credits'] is None for c in chunks)


@pytest.mark.parametrize('fault',['provisional','missing_week_marker','wrong_colour','wrong_legend','changed_note','wrong_payload'])
def test_source_calendar_review_fails_on_changed_fact(dossier,fault):
    bad=copy.deepcopy(dossier)
    if fault=='provisional':bad['rows'][3]['provisional']=False
    elif fault=='missing_week_marker':bad['rows'][3]['printed_markers']['Q'].remove(40)
    elif fault=='wrong_colour':bad['rows'][3]['colour_weeks']['defence'].remove(40)
    elif fault=='wrong_legend':bad['marker_legend']['Q']='Thi hết HP'
    elif fault=='changed_note':bad['common_notes'][0]['source_verbatim']='Ngày bắt đầu học kỳ I : 04/8/2026 (tuần 1)'
    elif fault=='wrong_payload':bad['source_sha256']='0'*64
    with pytest.raises(AssertionError):calendar.normalize(bad)


def test_catalog_projection_does_not_count_materialized_completions_twice():
    catalog={'documents':[{'identity_key':'drive:a','completion_status':'complete'},
                          {'identity_key':'drive:b','completion_status':'incomplete'},
                          {'identity_key':'drive:calendar','completion_status':'incomplete'}]}
    assert pipeline.source_status_counts(catalog,{'a'},{'a','b'})=={'complete':1,'incomplete':2}
    assert pipeline.source_status_counts(catalog,set(),{'a','b'})=={'incomplete':3}
