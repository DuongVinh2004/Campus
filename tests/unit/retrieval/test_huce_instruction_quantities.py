"""Actual source X/Y quantities never become course credits or inferred choices."""
import copy
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'scripts'))
import huce_document_pipeline as pipeline


@pytest.fixture
def actual():
    did='1nPJqjaUqzlYIvT4OR1YMFoBjnP4yysxb'
    return next(i for i in pipeline.items() if i['drive_id']==did),copy.deepcopy(pipeline.latest_reviews()[did][1]['review_dossier'])


def test_actual_materials_diagram_preserves_units_and_placeholder_annotations(actual):
    item,dossier=actual;result=pipeline.normalize(item,dossier)
    assert len(result['courses'])==166 and len(result['elective_groups'])==8
    assert all(c['credits'] is None and c['credit_unit'] is None for c in result['courses'])
    assert sum(c['instruction_quantities'] is not None for c in result['courses'])==158
    for code,x,y in [('428801',42,6),('250103',4,22),('360801',29,2),('222012',0,300)]:
        courses=[c for c in result['courses'] if c['code']==code]
        assert len(courses)==2 and all(c['instruction_quantities']['X']==x and c['instruction_quantities']['Y']==y for c in courses)
    defence=[c for c in result['courses'] if c['code']=='48011...']
    assert len(defence)==2 and all(c['instruction_quantities'] is None and c['printed_noncredit_numeric_annotation']==8 for c in defence)
    assert all(g['printed_credits'] is None and g['choice_count'] is None and len(g['option_occurrences'])==2 for g in result['elective_groups'])
    assert all(e['reviewed_cells']==79 and len(e['ignored_cells'])==7 and not e['credit_conversion_performed'] for e in result['raster_evidence'])
    assert len(result['relations'])==37 and all(r['language']=='vi' for r in result['relations'])
    assert result['printed_total'] is None


@pytest.mark.parametrize('fault',['missing_box','credits_as_hours','credit_unit_label','noncredit_as_hours','ambiguous_language','missing_legend_disposition'])
def test_instruction_source_rejects_missing_evidence_or_unit_confusion(actual,fault):
    item,dossier=actual;page=dossier['raster_pages']['1']
    if fault=='missing_box':page['semester_transcriptions']['1'].pop()
    elif fault=='credits_as_hours':page['semester_transcriptions']['1'][0]='428801 – 3\nTriết học Mác - Lê Nin'
    elif fault=='credit_unit_label':page['unit_legend']['unit_verbatim']='TC'
    elif fault=='noncredit_as_hours':page['semester_transcriptions']['2'][-1]='48011... – 8 – 0\nGDQP1,2,3,4'
    elif fault=='ambiguous_language':dossier['relations'][0].pop('language')
    else:page['ignored_cells'].pop('p1-c078')
    with pytest.raises(AssertionError):pipeline.normalize(item,dossier)
