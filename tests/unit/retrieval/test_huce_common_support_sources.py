"""Real notice338 rows preserve conjunctive eligibility, proofs and merged cells."""
import copy
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'scripts'))
import huce_document_pipeline as p
import huce_public_document_pipeline as documents


@pytest.fixture(scope='module')
def bundle():return p.read(p.BASE/'common-support-review-bundle-20261022-71.json')['documents']


def test_all_annex_rows_and_distinct_identities_with_same_payload(bundle):
    a,b=[documents.normalize(d) for d in bundle[2:4]]
    assert a['source_identity']!=b['source_identity'] and a['source_sha256']==b['source_sha256']
    assert len(a['page_evidence'])==5 and len(a['units'])==22
    rows=[u for u in a['units'] if u.get('annex_cell_rows')]
    assert len(rows)==17
    children=[u for u in rows if u['annex_cell_rows']['2']==3 and u['annex_cell_rows']['1']!=3]
    assert len(children)==7
    assert all('01 lần' in u['structured_fields']['Ghi chú'] and 'Thẻ thương binh' in u['structured_fields']['Hồ sơ cần nộp'] for u in children)
    poor=next(u for u in rows if u['section'].startswith('Phụ lục — I.1.5'))
    assert 'hoặc hộ cận nghèo' in poor['text'] and 'đầu năm tài chính' in poor['text']
    assert 'Miễn học phí 100%' in poor['text']
    very_small=next(u for u in rows if u['section'].startswith('Phụ lục — I.1.6'))
    assert 'Lô Lô' in very_small['text'] and 'ở vùng' in very_small['text']
    seventy=next(u for u in rows if 'I.2 giảm70%' in u['section'])
    assert 'ngoài đối tượng' in seventy['text'] and 'Giảm 70%' in seventy['text']
    costs=next(u for u in rows if u['section']=='Phụ lục — II.1 hỗ trợ chi phí học tập')
    assert all(s in costs['text'] for s in ['không áp dụng','Cử tuyển','liên thông','văn bằng hai','dự\nbị đại học','đầu năm tài chính'])
    support=next(u for u in rows if u['section']=='Phụ lục — II.2 hỗ trợ học tập')
    assert support['structured_fields']['Ghi chú']=='' and 'hộ nghèo' not in support['text']
    assert all(not documents.normalize(d)['completion_eligible'] for d in bundle)


@pytest.mark.parametrize('fault',['lost_exclusion','wrong_proof','inherited_unmerged','wrong_rate'])
def test_annex_rejects_edited_or_misattributed_cells(bundle,fault):
    bad=copy.deepcopy(bundle[2])
    if fault=='lost_exclusion':bad['reviewed_annex_rows'][-2]['fields']['Đối tượng và điều kiện']='Sinh viên dân tộc thiểu số'
    elif fault=='wrong_proof':bad['reviewed_annex_rows'][-1]['fields']['Hồ sơ cần nộp']='Giấy xác nhận hộ nghèo'
    elif fault=='inherited_unmerged':bad['reviewed_annex_rows'][8]['cell_rows']['2']=3
    elif fault=='wrong_rate':bad['reviewed_annex_rows'][-4]['headings'][1]['text']='Miễn học phí 100%'
    with pytest.raises(AssertionError):documents.normalize(bad)


def test_forms_keep_all_text_and_source_differences_without_fake_pages(bundle):
    record=documents.normalize(bundle[4]);units=record['units']
    assert len(units)==3 and all(u['page'] is None and u['image'] is None for u in units)
    assert '81/2021' in units[0]['text'] and 'Lô Tô' in units[0]['text']
    assert 'hộ nghèo và hộ cận nghèo' in units[0]['text']
    assert '66/2013' in units[1]['text']
    assert 'sổ hộ khẩu' in units[2]['text'] and 'không cần xác nhận' in units[2]['text']
    assert not record['completion_eligible']
    chunks=documents.chunks(record,'2026-10-22T00:00:00+00:00')
    assert all(c['layout_status']=='not_verified' and c['page'] is None for c in chunks)
    assert all('đã hết hạn' in c['text'] for c in chunks)


@pytest.mark.parametrize('fault',['lost_paragraph','overlap','changed_xml','claimed_layout'])
def test_docx_rejects_loss_and_unverified_layout_claims(bundle,fault):
    bad=copy.deepcopy(bundle[4])
    if fault=='lost_paragraph':bad['reviewed_forms'][-1]['end']-=1
    elif fault=='overlap':bad['reviewed_forms'][1]['start']-=1
    elif fault=='changed_xml':bad['document_xml_sha256']='0'*64
    elif fault=='claimed_layout':bad['layout_status']='verified'
    with pytest.raises(AssertionError):documents.normalize(bad)


def test_annex_locator_matches_notice_and_complete_row_number():
    from campus247.infrastructure.retrieval.public_hybrid import _annex_locator_match
    row={'section_path':'Thông báo338/TB-ĐHXDHN — Phụ lục — II.2 hỗ trợ học tập'}
    assert _annex_locator_match('Phụ lụcII.2 thông báo338 cần hồ sơ gì?',row)
    assert not _annex_locator_match('Phụ lụcI.2 thông báo338 cần hồ sơ gì?',row)
    assert not _annex_locator_match('Phụ lụcII.2 thông báo339 cần hồ sơ gì?',row)
    assert not _annex_locator_match('Phụ lụcII.2 cần hồ sơ gì?',row)
    assert not _annex_locator_match('Phụ lụcII.2.1 thông báo338 cần hồ sơ gì?',row)
