"""Real conference papers retain continued text, person roles and variant schedules."""
import copy
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'scripts'))
import huce_document_pipeline as p
import huce_public_document_pipeline as documents


@pytest.fixture(scope='module')
def bundle():return p.read(p.BASE/'conference-review-bundle-20261022-59.json')['documents']


def test_all_pages_31_abstracts_and_continued_graphtour_are_preserved(bundle):
    record=documents.normalize(bundle[3]);sections=[u for u in record['units'] if u.get('source_spans')]
    assert len(record['page_evidence'])==29 and len(sections)==31
    graph=sections[7]
    assert graph['page']==14 and graph['page_end']==15 and len(graph['images'])==2
    assert 'Nguyen Dinh Quy' in graph['structured_fields']['Tác giả (theo bản kỷ yếu)']
    assert '16 pseudo-tokens' in graph['text'] and 'over 95%' in graph['text']
    cnn=sections[2]
    assert cnn['page']==11 and cnn['page_end']==12 and '346/397' in cnn['text']
    assert sum(u['page_end']>u['page'] for u in sections)==7
    assert any('O(2^N)' in u['text'] for u in sections if 'PLINH' in u['section'])
    assert not record['completion_eligible']


def test_programme_continued_title_and_table_roles_are_explicit(bundle):
    record=documents.normalize(bundle[2]);sections=[u for u in record['units'] if u.get('source_spans')]
    assert len(sections)==30 and len(record['page_evidence'])==3
    row=sections[17];fields=row['structured_fields']
    assert row['page']==2 and row['page_end']==3
    assert fields['Người báo cáo']=='Nguyễn Bằng Giang'
    assert 'Human-in-the-Loop' in fields['Tên báo cáo'] and 'FIT_CMA2026' not in fields['Tên báo cáo']
    assert 'Nguyễn Trọng Nghĩa' in fields['Các tác giả']
    assert sections[23]['structured_fields']['Người báo cáo']=='Vũ Thị Thủy'
    assert sections[25]['structured_fields']['Người báo cáo']=='Vũ Thị Ngân'
    assert any('09:15' in q and '10:00' in q for q in record['source_questions'])
    chunks=documents.chunks(record,'2026-10-22T00:00:00+00:00')
    continued=next(c for c in chunks if 'tiểu ban 2, báo cáo 8, 10h30' in c['section'])
    assert continued['page']==2 and continued['page_end']==3 and len(continued['visual_evidence'])==2


@pytest.mark.parametrize('fault',['offset','lost_continuation','authors_as_presenter','wrong_image'])
def test_source_binding_rejects_changed_paper_or_person_role(bundle,fault):
    bad=copy.deepcopy(bundle[2] if fault=='authors_as_presenter' else bundle[3])
    if fault=='offset':bad['reviewed_sections'][7]['spans'][0]['start']+=1
    elif fault=='lost_continuation':bad['reviewed_sections'][7]['spans'].pop()
    elif fault=='authors_as_presenter':
        fields=bad['reviewed_sections'][0]['fields'];fields['Người báo cáo']=fields['Các tác giả']
    elif fault=='wrong_image':bad['reviewed_visual_annotations'][0]['image_sha256']='0'*64
    with pytest.raises(AssertionError):documents.normalize(bad)


def test_distinct_official_urls_and_past_event_scope_remain(bundle):
    a,b=[documents.normalize(d) for d in bundle[:2]]
    assert a['source_identity']!=b['source_identity']
    assert a['units'][0]['text']==b['units'][0]['text']
    assert all(d['applicability']['event_date']=='2026-10-06' and d['published_at']=='2026-10-04' for d in bundle[:2])
    assert a['completion_eligible'] and b['completion_eligible']
    assert sum(len(documents.chunks(documents.normalize(d),'2026-10-22T00:00:00+00:00')) for d in bundle)==95


def test_repaired_book_schedule_is_bound_to_its_own_version_and_old_citations():
    repaired=p.read(p.BASE/'conference-schedule-repair-bundle-20261022-64.json')['documents']
    a,b=[documents.normalize(d) for d in repaired]
    rows=[u for u in b['units'] if u['section'].startswith('Chương trình trong kỷ yếu')]
    assert len(rows)==30
    liouville=next(u for u in rows if 'tiểu ban 3, báo cáo 7,' in u['section'])
    assert liouville['structured_fields']['Báo cáo viên']=='Trần Văn Khiên'
    assert liouville['structured_fields']['Thời gian']=='10:15 – 10:30'
    assert liouville['page']==8
    abc=next(u for u in b['units'] if u['section'].startswith('Tóm tắt báo cáo 8:'))
    text=documents.chunks(b,'2026-10-22T00:00:00+00:00')
    graph=next(c for c in text if c['section'].endswith(abc['section']))
    assert '09:15' not in graph['text'] and '10:15' not in graph['text']
    assert graph['replaces_excerpt_text_sha256']
    assert sum(len(d['replaces_excerpt_by_section']) for d in repaired)==93
    assert sum(len(documents.chunks(r,'2026-10-22T00:00:00+00:00')) for r in [a,b])==123


def test_unchanged_replacement_keeps_new_version_and_prior_citations():
    from campus247.infrastructure.retrieval.public_knowledge import PublicKnowledgeStore
    store=PublicKnowledgeStore(p.PUB,tenant_id='HUCE',campus_id='HUCE',reviewed_corrections_version=27)
    current=[r for r in store.rows if r['version_label']=='reviewed-corrections-20261021-v27']
    history=[r for r in store.legacy_rows if r['version_label']=='reviewed-corrections-20261021-v26']
    assert len(current)==123 and len(history)==93
    unchanged=[r for r in current if any(r['quote_span_hash']==old['quote_span_hash'] for old in history)]
    assert len(unchanged)==4
    assert all(any(r['document_version_id']!=old['document_version_id'] for old in history
                   if r['quote_span_hash']==old['quote_span_hash']) for r in unchanged)


def test_requested_schedule_slot_uses_locator_not_conflict_note():
    from campus247.infrastructure.retrieval.public_hybrid import _schedule_locator_match
    row={'title':'Chương trình và báo cáo tóm tắt',
         'section_path':'Chương trình trong kỷ yếu — tiểu ban 3, báo cáo 7, 10:15–10:30',
         'content_text':'Vấn đề nguồn: dòng khác ghi09:15và10:00.'}
    query='Phần chương trình trong kỷ yếu tiểu ban 3 Liouville10:15 Trần Văn Khiên'
    assert _schedule_locator_match(query.replace('Liouville10','Liouville 10'),row)
    assert not _schedule_locator_match('Chương trình trong kỷ yếu tiểu ban 3 lúc09:15'.replace('lúc09','lúc 09'),row)
    assert not _schedule_locator_match('Chương trình bản rời tiểu ban 3 lúc10h15'.replace('lúc10','lúc 10'),row)
    assert not _schedule_locator_match('Tôi học lúc10:15'.replace('lúc10','lúc 10'),row)
