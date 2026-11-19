"""Common handbook conflicts replace active summaries while retaining old citations."""
import copy
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'scripts'))
import huce_document_pipeline as p
import huce_common_source_slices as slices


def test_comparison_binds_original_pages_and_never_claims_full_completion():
    release=p.read(p.PUB/'reviewed-corrections-20261021-v30.json')
    records=[slices.validate_release(release,c) for c in release['pipeline_coverage']]
    assert len(records)==2 and all(not r['completion_eligible'] for r in records)
    text=release['chunks'][0]['text']
    assert '≥5%' in text and 'vượt quá5%' in text and '>45day' in text
    assert '3.6–4.0: Xuất sắc' in text and 'TOEIC2skills' in text
    assert release['chunks'][1]['page']==18 and release['chunks'][1]['page_end']==19
    assert len(release['chunks'][1]['visual_evidence'])==2


def test_unhashed_legacy_handbook_summary_is_retired_but_readback_preserved():
    from campus247.infrastructure.retrieval.public_knowledge import PublicKnowledgeStore
    before=PublicKnowledgeStore(p.PUB,tenant_id='HUCE',campus_id='HUCE',reviewed_corrections_version=29)
    after=PublicKnowledgeStore(p.PUB,tenant_id='HUCE',campus_id='HUCE',reviewed_corrections_version=30)
    old=next(r for r in before.rows if r['title'].startswith('Sổ tay') and r['page_start']==31)
    identity=lambda r:tuple(r[k] for k in ['source_id','document_version_id','chunk_id','content_text'])
    assert identity(old) in {identity(r) for r in after.legacy_rows}
    assert identity(old) not in {identity(r) for r in after.rows}
    assert len([r for r in after.rows if r['version_label']=='reviewed-corrections-20261021-v30'])==2


@pytest.mark.parametrize('fault',['image_scope','audit_hash','source_hash','full_completion'])
def test_comparison_rejects_unbound_or_overclaimed_slices(fault):
    release=p.read(p.PUB/'reviewed-corrections-20261021-v30.json')
    record=p.read(p.ROOT/release['pipeline_coverage'][0]['review_file']);bad=copy.deepcopy(record['review_dossier'])
    if fault=='image_scope':bad['selected_pages']=[32]
    elif fault=='audit_hash':bad['audit_sha256']='0'*64
    elif fault=='source_hash':bad['source_sha256']='0'*64
    elif fault=='full_completion':bad['whole_document_complete']=True
    with pytest.raises((AssertionError,StopIteration)):slices.normalize(bad)


def test_vietnamese_comparison_preserves_thresholds_scope_and_source_bytes():
    release=p.read(p.PUB/'reviewed-corrections-20261021-v31.json')
    record=slices.validate_release(release,release['pipeline_coverage'][0]);d=record['review_dossier']
    assert 'toàn chương trình' in record['units'][0]['text']
    assert all(t in d['reviewed_comparison_vi'] for t in ['ngưỡng ≥5%','ngưỡng vượt quá5%','xuất sắc và giỏi','không tự coi'])
    previous=p.read(p.PUB/'reviewed-corrections-20261021-v30.json')['chunks'][0]
    assert d['source_sha256']==previous['source_sha256']
    assert release['chunks'][0]['replaces_excerpt_text_sha256']==previous['text_sha256']
    assert not record['completion_eligible']
    bad=copy.deepcopy(d);bad['reviewed_comparison_vi']=bad['reviewed_comparison_vi'].replace('≥5%','>5%')
    with pytest.raises(AssertionError):slices.normalize(bad)
