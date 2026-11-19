"""Real ICT rule evidence preserves continued articles and reviewed scan clauses."""
import copy
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'scripts'))
import huce_document_pipeline as p
import huce_public_document_pipeline as documents


@pytest.fixture(scope='module')
def bundle():return p.read(p.BASE/'ict-rules-review-bundle-20261022-78.json')['documents']


def test_security19_articles17_pages_and_continuations(bundle):
    record=documents.normalize(bundle[0]);sections=[u for u in record['units'] if u.get('source_spans')]
    assert len(record['page_evidence'])==17 and len(sections)==19
    passwords=next(u for u in sections if u['section'].startswith('Quy chế — Điều10:'))
    assert passwords['page']==8 and passwords['page_end']==9
    assert 'ít nhất 8' in passwords['text'] and '01 lần/ 06 tháng' in passwords['text']
    assert '05 ngày làm việc' in passwords['text'] and 'Không dùng chung tài khoản quản trị' in passwords['text']
    maintenance=next(u for u in sections if u['section'].startswith('Quy chế — Điều14:'))
    assert maintenance['page']==12 and maintenance['page_end']==14 and len(maintenance['images'])==3
    assert '01 lần/ngày' in maintenance['text'] and 'mỗi tháng 01 lần' in maintenance['text']
    assert 'không tự ý' in sections[16]['text'] and not record['completion_eligible']
    assert 'LAN' in record['units'][16]['text'] and 'PAT' in record['units'][16]['text']


def test_lab_full_12_clauses_and_unresolved_handwriting(bundle):
    record=documents.normalize(bundle[1]);sections=[u for u in record['units'] if u.get('source_spans')]
    assert len(record['page_evidence'])==2 and len(sections)==12
    assert 'sau 15 phút không được vào' in sections[2]['text']
    assert 'sử dụng điện thoại di động' in sections[5]['text']
    assert 'sự đồng ý của cán bộ' in sections[8]['text']
    assert 'bồi thường' in sections[11]['text'] and not record['completion_eligible']
    assert 'chưa xác định chắc chắn' in record['units'][0]['text']
    assert bundle[1].get('document_number') is None


@pytest.mark.parametrize('fault',['lost_continuation','wrong_payload','wrong_scan','changed_ocr'])
def test_rules_reject_missing_or_changed_evidence(bundle,fault):
    bad=copy.deepcopy(bundle[1] if fault in ['wrong_scan','changed_ocr'] else bundle[0])
    if fault=='lost_continuation':bad['reviewed_sections'][13]['spans'].pop()
    elif fault=='wrong_payload':bad['source_sha256']='0'*64
    elif fault=='wrong_scan':bad['reviewed_pages'][1]['image_sha256']='0'*64
    elif fault=='changed_ocr':bad['reviewed_pages'][1]['ocr_sha256']='0'*64
    with pytest.raises(AssertionError):documents.normalize(bad)


def test_lab_reranker_excerpt_keeps_numbered_clause_beside_locator(bundle):
    from campus247.infrastructure.retrieval.public_hybrid import PublicHybridKnowledgeStore
    record=documents.normalize(bundle[1]);unit=next(u for u in record['units'] if u['section']=='Nội quy — khoản3')
    content='Repeated source review header about computer rooms.\n'+unit['text']+'\nPhạm vi đã đối chiếu: sinh viên'
    store=object.__new__(PublicHybridKnowledgeStore)
    store.children=[{'parent':0,'text':content,'id':'a'*32}]
    store.rows=[{'source_id':'b'*32,'document_version_id':'c'*32,'section_path':bundle[1]['title']+' — '+unit['section'],
                 'title':bundle[1]['title'],'issuer':'HUCE','canonical_uri':bundle[1]['publisher_url'],
                 'page_start':2,'page_end':2,'version_label':'reviewed-source','source_status':'CURRENT'}]
    candidate=store._candidate(0,'Nội quy phòng máy: đến muộn sau15phút có được vào phòng không?')
    assert 'khoản3' in candidate.content_text and 'sau 15 phút không được vào phòng máy' in candidate.content_text
    assert 'Repeated source review' not in candidate.content_text and len(candidate.content_text)<=521
