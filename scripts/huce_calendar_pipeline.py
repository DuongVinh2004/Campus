"""Source-bound calendar rows: dates, merged colours and provisional scope."""
import argparse
from datetime import date, timedelta
import json

import pdfplumber

from huce_document_pipeline import ROOT, BASE, PUB, checked, event, preflight, read, rel, save, sha, stamp


def normalize(dossier):
    source=checked(ROOT/dossier['source_file'])
    assert sha(source.read_bytes())==dossier['source_sha256']
    geometry=checked(ROOT/dossier['geometry_file']);assert sha(geometry.read_bytes())==dossier['geometry_sha256']
    image=checked(ROOT/dossier['image']);assert sha(image.read_bytes())==dossier['image_sha256']
    publisher=checked(ROOT/dossier['publisher_file']);assert sha(publisher.read_bytes())==dossier['publisher_sha256']
    assert dossier['download_url'] in publisher.read_text(encoding='utf8')
    assert dossier['all_cntt_week_cells_visually_checked'] and dossier['headers_legend_and_footer_visually_checked']
    assert dossier['review_scope']=='CNTT rows K68,K69,K70,K71 and relevant common notes; other-major rows not certified'
    with pdfplumber.open(source) as pdf:
        assert len(pdf.pages)==1
        page=pdf.pages[0];table=page.find_tables()[0];values=table.extract();raw=read(geometry)
        assert values==[r['values_verbatim'] for r in raw['rows']]
        assert len(table.columns)==55 and values[1][3:]==values[85][3:]==[str(n) for n in range(1,53)]
        text=page.extract_text() or ''
        legend=page.crop((965,2290,1290,2384)).extract_text() or ''
        for marker,meaning in dossier['marker_legend'].items():
            assert ''.join((marker+' - '+meaning).split()) in ''.join(legend.split()), 'marker meaning must match printed legend'
        for note in dossier['common_notes']:
            assert ''.join(note['source_verbatim'].split()) in ''.join(text.split()), 'note must be literal source text'
        rows=[]
        for spec in dossier['rows']:
            candidate=next(r for r in raw['cntt_row_candidates'] if r['row_index']==spec['row_index'])
            cohort=candidate['cohort_candidate'];label=cohort['label_verbatim']
            assert label==spec['cohort_label_verbatim'] and spec['cohort']==label.split()[0]
            assert spec['provisional']==('DỰ' in label), 'source provisional scope cannot be removed'
            assert values[spec['row_index']][1]=='Công nghệ thông tin'
            assert int(values[spec['row_index']][2])==spec['class_count']
            header=candidate['week_header_row'];month=None;year=2026;weeks=[]
            row_box=candidate['cell_bboxes'][1];cy=(row_box[1]+row_box[3])/2
            expected={w:k for k,ws in spec['printed_markers'].items() for w in ws}
            assert len(expected)==sum(len(v) for v in spec['printed_markers'].values())
            for number in range(1,53):
                column=number+2;month_label=values[header-1][column]
                if month_label:
                    if '-' in month_label:month,year=map(int,month_label.split('-'))
                    else:month=int(month_label)
                start=date(year,month,int(values[header+1][column]))
                if weeks:assert start==date.fromisoformat(weeks[-1]['start_date'])+timedelta(days=7)
                b=raw['rows'][header]['cell_bboxes'][column];cx=(b[0]+b[2])/2
                colors=[r['non_stroking_color'] for r in page.rects if r['fill'] and r['x0']<cx<r['x1'] and r['top']<cy<r['bottom']]
                assert len(colors)<=1
                color=list(colors[0]) if colors else [1.,1.,1.]
                marker=values[spec['row_index']][column] or ''
                assert marker==expected.get(number,''), 'every printed marker, including blanks, must match review'
                roles=[role for role,entry in dossier['reviewed_colour_roles'].items() if entry['rgb']==color]
                assert len(roles)==1, 'unreviewed fill colour'
                role=roles[0]
                assert role==next((r for r,ws in spec['colour_weeks'].items() if number in ws),'unmarked'), 'colour disposition differs from visual review'
                assert marker in dossier['marker_legend'] or not marker
                weeks.append({'week':number,'start_date':start.isoformat(),'printed_day':values[header+1][column],
                    'printed_marker':marker,'marker_meaning':dossier['marker_legend'].get(marker),
                    'colour_role':role,'fill_rgb':color,'semester':1 if number<=23 else 2 if number<=48 else None,
                    'bbox':[b[0],row_box[1],b[2],row_box[3]]})
            assert weeks[0]['start_date']=='2026-08-03' and weeks[23]['start_date']=='2027-01-11'
            rows.append({'cohort':spec['cohort'],'cohort_label_verbatim':label,'provisional':spec['provisional'],
                'programme':'Công nghệ thông tin','class_count':spec['class_count'],'weeks':weeks,
                'row_index':spec['row_index'],'row_bbox':[candidate['cell_bboxes'][1][0],row_box[1],weeks[-1]['bbox'][2],row_box[3]],
                'cohort_bbox':cohort['bbox']})
        assert [r['cohort'] for r in rows]==['K68','K69','K70','K71'] and len(rows)==4
    return {'kind':'calendar_cntt_rows','drive_id':dossier['drive_id'],'source_file':dossier['source_file'],
        'source_sha256':dossier['source_sha256'],'title_verbatim':dossier['title'],'academic_year':'2026-2027',
        'rows':rows,'common_notes':dossier['common_notes'],'review_dossier':dossier,
        'printed_total':None,'legal_effective_from':None,'completion_status':'incomplete_other_major_rows_not_reviewed',
        'verification_status':'selected_CNTT_rows_headers_colours_and_notes_visually_reconciled',
        'limitations':['Chỉ đối chiếu bốn dòng CNTT và ghi chú chung; các ngành khác trên trang chưa được chứng nhận.',
                        'K71 ghi DỰ KIẾN; đây là kế hoạch khung, không phải thời khóa biểu từng sinh viên.',
                        'Ô trống chỉ được giữ là không có ký hiệu; không suy ra lịch học chi tiết.']}


def chunks(record,acquired_at):
    dossier=record['review_dossier'];notes='\n'.join(n['source_verbatim'] for n in record['common_notes'])
    units=[]
    for row in record['rows']:
        scope={'cohort':row['cohort'],'programme':'Công nghệ thông tin','degree':None,'system':None,'academic_year':'2026-2027','provisional':row['provisional']}
        title=record['title_verbatim']+' — CNTT '+row['cohort']+(' (DỰ KIẾN)' if row['provisional'] else '')
        lines=[title,'Số lớp in trên nguồn: '+str(row['class_count']),
               'Ngày BĐ là ngày bắt đầu tuần; không suy ra thời khóa biểu cá nhân.']
        for week in row['weeks']:
            meaning=week['marker_meaning'] or dossier['reviewed_colour_roles'][week['colour_role']]['meaning']
            lines.append(f"Tuần {week['week']}, ngày BĐ {date.fromisoformat(week['start_date']).strftime('%d/%m/%Y')}: {week['printed_marker'] or '[ô không ghi ký hiệu]'} — {meaning}.")
        lines+=['Ghi chú chung (giữ ngoại lệ tiến độ riêng):',notes,*record['limitations']]
        units.append((title,'\n'.join(lines),scope,row['row_bbox']))
    scope={'cohort':None,'programme':'Công nghệ thông tin','degree':None,'system':None,'academic_year':'2026-2027'}
    units.append((record['title_verbatim']+' — ghi chú chung CNTT',notes+'\n'+'\n'.join(record['limitations']),scope,dossier['notes_bbox']))
    return [dict(url=dossier['publisher_url'],download_url=dossier['download_url'],title=title,section=title,text=text,
        text_sha256=sha(text.encode()),source_file=str(checked(ROOT/record['source_file']).relative_to(ROOT/'data')).replace('\\','/'),
        source_sha256=record['source_sha256'],issuer='Trường Đại học Xây dựng Hà Nội',published_at=None,collected_at=acquired_at,
        applicability=scope,cohort=scope['cohort'],degree_level=None,academic_year='2026-2027',total_credits=None,
        legal_effective_from=None,effective_from=acquired_at,effective_date_basis='retrieval admission only; not legal effectiveness',
        supersedes=[],limitations=record['limitations'],ocr_quality='native_table_geometry_and_reviewed_original_colours',
        visual_evidence=[dossier['image']],page=1,page_end=1,region_bbox=box,review_status=record['verification_status'],
        review_scope=dossier['review_scope'],replaces_excerpt_text_sha256=None)
        for title,text,scope,box in units]


def validate_release(release,coverage):
    record=read(ROOT/coverage['review_file']);assert normalize(record['review_dossier'])==record
    assert release['chunks']==chunks(record,release['acquired_at'])
    assert coverage['complete_eligible_after_index'] is False
    return record


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--dossier',required=True);parser.add_argument('--version',required=True,type=int)
    args=parser.parse_args();event('preflight',preflight())
    dossier=read(ROOT/args.dossier);record=normalize(dossier)
    review_file=checked(BASE/'calendar-reviews'/f'{stamp()}-{record["drive_id"]}.json');save(review_file,record)
    from huce_document_pipeline import now
    at=now();coverage={'kind':'calendar_cntt_rows','drive_id':record['drive_id'],'review_file':rel(review_file),'pages':1,
        'complete_eligible_after_index':False,'review_scope':dossier['review_scope']}
    release={'public_only':True,'acquired_at':at,'version_label':f'reviewed-corrections-20261021-v{args.version}',
        'verification':'source_verified_excerpts','chunks':chunks(record,at),'pipeline_coverage':[coverage]}
    validate_release(release,coverage)
    target=checked(PUB/(release['version_label']+'.json'));save(target,release)
    event('published-calendar',{'release':rel(target),'review':rel(review_file),'selected_rows':4,'week_cells':208,'chunks':5,'complete':False})
    print(json.dumps({'release':rel(target),'review':rel(review_file),'chunks':5,'week_cells':208}))


if __name__=='__main__':main()
