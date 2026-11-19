"""Actual hybrid PDF evidence must remain complete and bound to its crops."""
import copy
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
import huce_document_pipeline as pipeline


@pytest.fixture
def actual():
    did='1dAWTe8JcrV07ndAXCQjGF3liC2dd3YjW'
    item=next(i for i in pipeline.items() if i['drive_id']==did)
    dossier=copy.deepcopy(pipeline.latest_reviews()[did][1]['review_dossier'])
    return item,dossier


def test_actual_bilingual_source_retains_conflicts_and_exact_option_headers(actual):
    item,dossier=actual
    result=pipeline.normalize(item,dossier)
    assert len(result['raster_evidence'])==2
    assert all(r['reviewed_cells']==76 and r['native_elective_options']==12 for r in result['raster_evidence'])
    assert len(result['courses'])==176  # 140 coded diagram cells, 12 slots, 24 native options
    assert len(result['elective_groups'])==12
    assert result['printed_total'] is None and result['applicability']['cohort'] is None
    names={c['language']:c['name_verbatim'] for c in result['courses'] if c['code']=='060223'}
    assert names=={'vi':'Sức bền vật liệu 1 (Block 1)','en':'Laws on Construction (Block 1)'}
    options=[c for c in result['courses'] if c['code']=='521312']
    assert len(options)==2 and all(c['credits']==3 and 'credit_source' in c for c in options)
    assert all(c['locators'][0].get('crop_sha256') for c in result['courses'] if c.get('reviewed_transcription'))


@pytest.mark.parametrize('fault',['missing_cell','double_disposition','missing_header','unprinted_slot_credit','wrong_table','wrong_elective_link'])
def test_actual_raster_dossier_rejects_missing_or_ambiguous_evidence(actual,fault):
    item,dossier=actual
    page=dossier['raster_pages']['1']
    if fault=='missing_cell':
        page['cell_transcriptions'].pop('p1-c002')
    elif fault=='double_disposition':
        page['ignored_cells']['p1-c002']='pretend it is decoration'
    elif fault=='missing_header':
        page['semester_headers'].pop('p1-c001')
    elif fault=='unprinted_slot_credit':
        page['cell_transcriptions']['p1-c018']='HPTC bắt buộc 1'
    elif fault=='wrong_table':
        page['elective_table_index']=0
    else:
        page['elective_slot_cells']['p1-c018']=2
        page['elective_slot_cells']['p1-c052']=1
    with pytest.raises(AssertionError):
        pipeline.normalize(item,dossier)
