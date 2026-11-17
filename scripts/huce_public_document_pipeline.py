"""Reviewed public articles/PDFs, with exact snapshots, linked sources and dated facts."""
import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import re

from huce_document_pipeline import ROOT, BASE, PUB, checked, event, preflight, read, rel, save, sha, stamp, now
from huce_source_registry import Page, official


class Article(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.depth=0;self.parts=[];self.links=[];self.found=0
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='div':
            if self.depth:self.depth+=1
            elif 'post-content-area' in attrs.get('class','').split():self.depth=1;self.found+=1
        if not self.depth:return
        if tag in {'p','li','h1','h2','h3','h4','br','tr'}:self.parts.append('\n')
        if tag in {'a','iframe','img','embed'}:
            url=attrs.get('href') or attrs.get('src')
            if url:self.links.append({'tag':tag,'url':url})
    def handle_endtag(self,tag):
        if self.depth:
            if tag in {'p','li','h1','h2','h3','h4','tr'}:self.parts.append('\n')
            if tag=='div':self.depth-=1
    def handle_data(self,text):
        if self.depth:self.parts.append(text)
    def text(self):
        return '\n'.join(line for raw in ''.join(self.parts).splitlines() if (line:=' '.join(raw.split())))


def normalize(dossier):
    source=checked(ROOT/dossier['source_file']);assert sha(source.read_bytes())==dossier['source_sha256']
    assert official(dossier['publisher_url']) and dossier['all_content_checked'] is True
    assert dossier['source_role'] in {'faculty_notice','school_notice','faculty_advertorial_summary','school_decision','training_proposal','conference_programme','conference_abstract_book','school_form'}
    units=[];page_evidence=[]
    if dossier['format']=='html':
        html=source.read_text(encoding='utf8');article=Article();article.feed(html)
        assert article.found==1,'exactly one article content region required'
        all_page=Page();all_page.feed(html)
        assert dossier['title'].casefold() in all_page.text().casefold()
        assert dossier['published_date_literal'] in all_page.text()
        assert dossier['reviewed_body_sha256']==sha(article.text().encode()), 'every actual article paragraph must be retained'
        assert dossier['reviewed_body_links']==article.links
        body=article.text() or '[Nội dung bài là tệp đính kèm trong iframe; xem nguồn PDF liên kết.]'
        units.append({'page':None,'section':'Toàn bộ nội dung bài và liên kết đính kèm','text':body,
                      'links':article.links,'image':None})
    elif dossier['format']=='docx':
        from zipfile import ZipFile
        import xml.etree.ElementTree as ET
        publisher=checked(ROOT/dossier['publisher_file'])
        assert sha(publisher.read_bytes())==dossier['publisher_sha256']
        assert dossier['download_url'] in publisher.read_text(encoding='utf8')
        with ZipFile(source) as package:
            assert not any('vbaProject' in name or name.startswith('word/embeddings/') for name in package.namelist())
            xml=package.read('word/document.xml')
        assert sha(xml)==dossier['document_xml_sha256']
        ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        paragraphs=[''.join(''.join(t.itertext()) for t in para.findall('.//w:t',ns))
                    for para in ET.fromstring(xml).findall('.//w:p',ns)]
        paragraphs=[t for t in paragraphs if t.strip()]
        assert paragraphs==dossier['reviewed_paragraphs']
        covered=[]
        for form in dossier['reviewed_forms']:
            start,end=form['start'],form['end']
            assert type(start) is int and type(end) is int and 0<=start<end<=len(paragraphs)
            text='\n'.join(paragraphs[start:end])
            assert form['title'] in paragraphs[start:end] and sha(text.encode())==form['text_sha256']
            covered.extend(range(start,end))
            units.append({'page':None,'section':form['title'],'text':text,'links':[],'image':None})
        assert covered==list(range(len(paragraphs))), 'all form paragraphs must be retained exactly once'
        # Text extraction cannot establish pagination or a completed visual review.
        assert dossier['layout_status']=='not_verified' and dossier['source_questions']
    else:
        assert dossier['format']=='pdf'
        acquisition=read(ROOT/dossier['acquisition_file']);entry=next(s for s in acquisition['results'] if s.get('drive_id')==dossier['drive_id'])
        assert entry['source_sha256']==dossier['source_sha256'] and len(entry['pages'])==dossier['page_count']
        publisher=checked(ROOT/entry['publisher_file']);assert sha(publisher.read_bytes())==entry['publisher_sha256']
        assert entry['linked_url'] in publisher.read_text(encoding='utf8') and entry['publisher_url']==dossier['publisher_url']
        reviewed={p['page']:p for p in dossier['reviewed_pages']}
        assert sorted(reviewed)==list(range(1,dossier['page_count']+1)), 'every original PDF page must be reviewed'
        transcripts=None
        if dossier.get('transcript_file'):
            file=checked(ROOT/dossier['transcript_file']);assert sha(file.read_bytes())==dossier['transcript_sha256']
            transcripts={p['page']:p['text'] for p in read(file)['pages']}
            assert sorted(transcripts)==sorted(reviewed)
        for page in entry['pages']:
            image=checked(ROOT/page['image']);data=checked(ROOT/page['data']);review=reviewed[page['page']]
            assert sha(image.read_bytes())==page['image_sha256']==review['image_sha256']
            assert sha(data.read_bytes())==page['data_sha256'] and review['content_checked'] and review['notes'].strip()
            if transcripts:
                ocr=checked(ROOT/review['ocr_file']);assert sha(ocr.read_bytes())==review['ocr_sha256']
                raw=read(ocr);assert raw['image_sha256']==page['image_sha256'] and raw['source_sha256']==dossier['source_sha256']
                text=transcripts[page['page']]
            else:text=read(data)['text']
            assert text.strip()
            units.append({'page':page['page'],'section':f"Trang {page['page']}",'text':text,'links':[], 'image':page['image']})
            page_evidence.append(page)
    for fact in dossier.get('source_assertions',[]):
        relevant='\n'.join(u['text'] for u in units if fact.get('page') is None or u['page']==fact['page'])
        assert re.search(fact['pattern'],relevant,re.I), 'reviewed source assertion absent from bound content'
    # A continued paper/table row retains every original page slice, rather than
    # relying on adjacent page chunks being retrieved together.
    original_units=list(units)
    for section in dossier.get('reviewed_sections',[]):
        fragments=[];images=[];numbers=[]
        assert section['section'].strip() and section['spans']
        for span in section['spans']:
            unit=next(u for u in original_units if u['page']==span['page'])
            start,end=span['start'],span['end']
            assert type(start) is int and type(end) is int and 0<=start<end<=len(unit['text'])
            fragment=unit['text'][start:end]
            assert sha(fragment.encode())==span['text_sha256'], 'section must bind exact original page offsets'
            fragments.append(fragment);numbers.append(span['page'])
            if unit['image']:images.append(unit['image'])
        assert numbers==sorted(set(numbers)), 'section pages must be unique and in original order'
        text='\n'.join(fragments);fold=lambda value:' '.join(value.split())
        assert sha(text.encode())==section['source_text_sha256'], 'joined section content changed after review'
        for field,value in section.get('fields',{}).items():
            assert isinstance(value,str) and value.strip()
            parts=section.get('field_fragments',{}).get(field,[value])
            assert parts and fold(' '.join(parts))==fold(value) and all(fold(part) in fold(text) for part in parts), 'reviewed field absent from source section'
        if section.get('field_cells'):
            import pdfplumber
            with pdfplumber.open(source) as pdf:
                for field,cell in section['field_cells'].items():
                    literal=pdf.pages[cell['page']-1].extract_tables()[cell['table']][cell['row']][cell['column']]
                    assert literal and fold(literal)==fold(section['fields'][field]), 'table role must match its original column'
        units.append({'page':min(numbers),'page_end':max(numbers),'section':section['section'],
            'text':text,'links':[],'image':images[0] if images else None,'images':images,
            'structured_fields':section.get('fields',{}),'source_spans':section['spans']})
    if dossier.get('reviewed_annex_rows'):
        import pdfplumber
        assert dossier['format']=='pdf'
        with pdfplumber.open(source) as pdf:
            for row in dossier['reviewed_annex_rows']:
                page=next(u for u in original_units if u['page']==row['page'])
                table=pdf.pages[row['page']-1].find_tables()[row['table']]
                values=table.extract(); target=row['row']; fields={}
                # Each condition, proof and recurrence comes from its own column.
                # Cross-row inheritance is permitted only within the same merged cell.
                for label,column in [('Đối tượng và điều kiện',1),('Hồ sơ cần nộp',2),('Ghi chú',3)]:
                    origin=row['cell_rows'][str(column)]
                    assert type(origin) is int and 0<=origin<=target<len(values)
                    literal=values[origin][column]
                    if origin!=target:
                        box=table.rows[origin].cells[column]
                        target_box=table.rows[target].cells[1]
                        assert values[target][column] is None and box and target_box
                        assert box[1]<=target_box[1] and box[3]>=target_box[3], 'inheritance must follow original merged geometry'
                    assert literal==row['fields'][label], 'annex column or source wording changed'
                    fields[label]=literal or ''
                for heading in row['headings']:
                    header=pdf.pages[heading['page']-1].extract_tables()[heading['table']][heading['row']][1]
                    assert header==heading['text'] and header.strip()
                text='\n'.join([h['text'] for h in row['headings']]+[label+': '+value for label,value in fields.items()])
                units.append({'page':row['page'],'section':row['section'],'text':text,'links':[],
                              'image':page['image'],'structured_fields':fields,'annex_cell_rows':row['cell_rows']})
    tables=dossier.get('reviewed_tables',[])
    for table in tables:
        page=next(u for u in units if u['page']==table['page'])
        assert table['header'] in page['text'] and len(table['rows'])==table['expected_rows']
        assert table['scope_verbatim'] and table['legend']
        for row in table['rows']:
            assert row['source_line'] in page['text'] and len(row['grades'])==table['course_count']
            for i,grade in enumerate(row['grades'],1):
                course=re.escape(f'TA{i}') if table['grade_label'] else rf'(?:Anh ngữ{i}|(?<=[,;]){i})'
                assert re.search(course+'='+re.escape(str(grade))+r'(?!\d)',row['source_line']), 'grade must match its course token, not a certificate score'
            units.append({'page':table['page'],'section':table['header']+' — '+row['level'],
                'text':table['scope_verbatim']+'\n'+row['source_line']+'\n'+table['legend'],
                'links':[],'image':page['image']})
    for note in dossier.get('reviewed_visual_annotations',[]):
        page=next(u for u in original_units if u['page']==note['page'])
        assert sha(checked(ROOT/page['image']).read_bytes())==note['image_sha256']
        assert note['native_literal'] in page['text'] and note['review_basis'].strip() and note['reviewed_text'].strip()
        for unit in units:
            if unit['page'] is not None and unit['page']<=note['page']<=unit.get('page_end',unit['page']):
                unit['text']+='\nĐối chiếu ký hiệu với ảnh gốc, trang PDF '+str(note['page'])+': '+note['reviewed_text']
    return {'kind':'reviewed_public_document','source_file':dossier['source_file'],'source_sha256':dossier['source_sha256'],
        'source_identity':dossier['source_identity'],'title_verbatim':dossier['title'],'units':units,'page_evidence':page_evidence,
        'reviewed_tables':tables,'source_questions':dossier['source_questions'],'limitations':dossier['limitations'],
        'review_dossier':dossier,'printed_total':None,'legal_effective_from':dossier.get('legal_effective_from'),
        'completion_eligible':not dossier['source_questions']}


def chunks(record,at):
    d=record['review_dossier'];output=[]
    for unit in record['units']:
        section=d['title']+' — '+unit['section']
        text=section+'\nLoại nguồn: '+d['source_role']+'\n'+d.get('reviewed_context','')+'\n'+unit['text']
        if unit.get('structured_fields'):text+='\nCác trường đã đối chiếu theo đúng vai trò trong nguồn:\n'+json.dumps(unit['structured_fields'],ensure_ascii=False)
        if unit['links']:text+='\nLiên kết trong nội dung nguồn:\n'+'\n'.join(l['url'] for l in unit['links'])
        text+='\nPhạm vi đã đối chiếu: '+json.dumps(d['applicability'],ensure_ascii=False)
        if record['limitations']:text+='\nGiới hạn nguồn:\n'+'\n'.join(record['limitations'])
        questions=d.get('unit_source_questions',{}).get(unit['section'],d.get('default_unit_source_questions',record['source_questions']))
        if questions:text+='\nVấn đề nguồn còn mở:\n'+'\n'.join(questions)
        output.append(dict(url=d['publisher_url'],download_url=d['download_url'],title=d['title'],section=section,text=text,
            text_sha256=sha(text.encode()),source_file=str(checked(ROOT/record['source_file']).relative_to(ROOT/'data')).replace('\\','/'),
            source_sha256=record['source_sha256'],issuer=d['issuer'],published_at=d.get('published_at'),collected_at=at,
            applicability=d['applicability'],cohort=d['applicability'].get('cohort'),degree_level=d['applicability'].get('degree'),
            academic_year=d['applicability'].get('academic_year'),total_credits=None,legal_effective_from=record['legal_effective_from'],
            effective_from=at,effective_date_basis='retrieval admission only; source legal date kept separately',
            document_number=d.get('document_number'),supersedes=[],limitations=record['limitations'],ocr_quality='reviewed_manual_transcription_bound_to_OCR_and_images' if d.get('transcript_file') else 'native_source_with_full_content_review',
            visual_evidence=unit.get('images',[unit['image']] if unit['image'] else []),page=unit['page'],page_end=unit.get('page_end',unit['page']),
            review_status='source_content_checked_with_explicit_limits',review_scope=d['review_scope'],
            **({'layout_status':d['layout_status']} if d.get('layout_status') else {}),
            replaces_excerpt_text_sha256=d.get('replaces_excerpt_by_section',{}).get(unit['section'],d.get('replaces_excerpt_text_sha256'))))
    return output


def validate_release(release,coverage):
    record=read(ROOT/coverage['review_file']);assert normalize(record['review_dossier'])==record
    actual=[c for c in release['chunks'] if c['download_url']==coverage['download_url'] and c['source_sha256']==record['source_sha256']]
    assert actual==chunks(record,release['acquired_at'])
    assert coverage['complete_eligible_after_index']==record['completion_eligible']
    return record


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--dossier',required=True);parser.add_argument('--version',required=True,type=int)
    args=parser.parse_args();event('preflight',preflight());bundle=read(ROOT/args.dossier);at=now();units=[];coverage=[]
    for dossier in bundle['documents']:
        record=normalize(dossier);file=checked(BASE/'document-reviews'/f'{stamp()}-{sha(dossier["source_identity"].encode())[:20]}.json');save(file,record)
        units+=chunks(record,at);coverage.append({'kind':'reviewed_public_document','source_identity':dossier['source_identity'],
            'drive_id':dossier.get('drive_id',dossier['download_url']),'download_url':dossier['download_url'],
            'review_file':rel(file),'complete_eligible_after_index':record['completion_eligible']})
    release={'public_only':True,'acquired_at':at,'version_label':f'reviewed-corrections-20261021-v{args.version}',
        'verification':'source_verified_excerpts','chunks':units,'pipeline_coverage':coverage}
    for entry in coverage:validate_release(release,entry)
    target=checked(PUB/(release['version_label']+'.json'));save(target,release)
    event('published-documents',{'release':rel(target),'source_count':len(coverage),'chunks':len(units),'generation_calls':0})
    print(json.dumps({'release':rel(target),'sources':len(coverage),'chunks':len(units)}))


if __name__=='__main__':main()
