"""Resumable HUCE intake, page evidence, reconciliation, release and index runner.

All evidence writes are exclusive. No completion is inferred from extraction,
checksums, credit sums or a previous catalog. Review dossiers must name images
actually inspected and describe source questions separately from extraction bugs.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter, defaultdict
from datetime import UTC, datetime
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import subprocess
import sys
import time

from huce_source_registry import ROOT, checked, save as exclusive_save

BASE = ROOT / 'data/huce-document-pipeline'
PUB = ROOT / 'data/huce-public-20261013'
QUEUE = ROOT / '.tooling/huce-documents-correction-20261021-01/resume-queue-v7.json'
CATALOG = ROOT / 'data/huce-discovery-20261020/reconciliation-20261021-v3/master_control_catalog_v11.json'
CODE = re.compile(r'(?m)^[ \t]*([0-9xX.]{2,9})[ \t]*[–−-][ \t]*(?:(\d+)(\*?))?(?:[ \t]*\(([^)\n]+)\))?[ \t]*$')


def sha(b): return hashlib.sha256(b).hexdigest()
def save(path, value):
    # Validate the complete serialization before opening an exclusive destination.
    json.dumps(value,ensure_ascii=False,allow_nan=False)
    exclusive_save(path,value)
def read(p): return json.loads(checked(Path(p)).read_text(encoding='utf-8'))
def rel(p): return str(checked(p).relative_to(ROOT)).replace('\\', '/')
def now(): return datetime.now(UTC).isoformat()
def stamp(): return datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')


def config():
    return {'extractor': 'huce-page-evidence-1', 'parser': 'semester-columns-1',
            'pdfplumber': importlib.metadata.version('pdfplumber'),
            'pdfium': importlib.metadata.version('pypdfium2'),
            'render_max_dimension': 2700,
            'coordinate_system': 'PDF points, left/top/right/bottom'}


def cache_path(item):
    key = sha(json.dumps(config(), sort_keys=True).encode())[:16]
    return checked(BASE / 'cache' / f"{item['sha256']}-{key}")


def items():
    queue = read(QUEUE)
    return queue['remaining_unreviewed_pdfs']


def preflight():
    checked(BASE / 'events')
    status = subprocess.run(['git', 'status', '--short'], cwd=ROOT, capture_output=True, text=True)
    assert status.returncode == 0, 'Git preflight failed; preserve state and stop'
    return {'workspace': str(ROOT.resolve()), 'at': now(), 'git_status': status.stdout,
            'git_warnings': status.stderr, 'config': config()}


def event(kind, data):
    p = checked(BASE / 'events' / f'{stamp()}-{kind}.json')
    save(p, {'kind': kind, 'at': now(), **data})
    return p


def prepare(args):
    import pdfplumber
    import pypdfium2 as pdfium
    start = time.monotonic()
    event('preflight', preflight())
    selected = [i for i in items() if not args.ids or i['drive_id'] in args.ids]
    if args.limit: selected = selected[:args.limit]
    ready = []
    for item in selected:
        source = checked(ROOT / item['source_file'])
        assert sha(source.read_bytes()) == item['sha256'], 'payload changed'
        dest = cache_path(item)
        dest.mkdir(parents=True, exist_ok=True)
        try:
            manifest_file = checked(dest/'manifest.json')
            if manifest_file.exists():
                cached_manifest = read(manifest_file)
                assert cached_manifest['payload_sha256']==item['sha256'] and cached_manifest['config']==config()
                assert len(cached_manifest['pages'])==item['page_count']
                for cached_page in cached_manifest['pages']:
                    assert sha(checked(ROOT/cached_page['data']).read_bytes())==cached_page['data_sha256']
                    assert sha(checked(ROOT/cached_page['image']).read_bytes())==cached_page['image_sha256']
                ready.append({'drive_id':item['drive_id'],'cache':rel(dest),'pages':len(cached_manifest['pages']),'cache_reused':True})
                continue
            with pdfplumber.open(source) as pdf, pdfium.PdfDocument(str(source)) as renderer:
                assert len(pdf.pages) == item['page_count'] == len(renderer)
                columns = []
                page_refs = []
                for n, page in enumerate(pdf.pages, 1):
                    native = checked(dest / f'page-{n}.json')
                    png = checked(dest / f'page-{n}.png')
                    if native.exists():
                        try: read(native)
                        except json.JSONDecodeError:
                            # Retain a failed partial write; recover into an exact new file.
                            native = checked(dest / f'page-{n}-recovered-1.json')
                    if not native.exists():
                        tables = []
                        for table in page.find_tables():
                            values = table.extract()
                            tables.append({'bbox': table.bbox, 'rows': [
                                {'cells': r.cells, 'values': v} for r, v in zip(table.rows, values, strict=True)]})
                        if n == 1:
                            # Preserve complete columns when arrow/grid lines split cells.
                            for t in tables:
                                for r in t['rows']:
                                    found = [(int(m[1]), box) for box, value in zip(r['cells'], r['values'])
                                             if box and value and (m := re.fullmatch(r'Học\s*kỳ\s*(\d+)', ' '.join(value.split()), re.I))]
                                    if len(found) >= 4:
                                        columns = found
                                        break
                                if columns: break
                        regions = []
                        for semester, box in columns:
                            top = box[3] if n == 1 else min((t['bbox'][1] for t in tables), default=0)
                            bottom = max((t['bbox'][3] for t in tables), default=page.height)
                            bbox = (box[0] + .15, top, box[2] - .15, bottom)
                            if 0 <= bbox[0] < bbox[2] <= page.width and top < bottom:
                                regions.append({'semester': semester, 'bbox': bbox,
                                                'text': page.crop(bbox).extract_text() or ''})
                        text = page.extract_text() or ''
                        save(native, {'page': n, 'width': page.width, 'height': page.height,
                            'text': text, 'words': page.extract_words(), 'tables': tables,
                            'lines': page.lines, 'curves': page.curves,
                            'image_objects': [{k: im.get(k) for k in ('x0', 'top', 'x1', 'bottom', 'width', 'height', 'name')}
                                              for im in page.images], 'semester_header_geometry': columns,
                            'semester_regions': regions,
                            'classification': 'scan_requires_local_ocr' if len(text.strip()) < 60 and page.images
                                              else 'native_spatial' if regions else 'native_layout_requires_review'})
                    else:
                        cached = read(native)
                        if n == 1: columns = cached['semester_header_geometry']
                    if not png.exists():
                        rp = renderer[n - 1]
                        bitmap = rp.render(scale=2700 / max(rp.get_size()))
                        with png.open('xb') as stream: bitmap.to_pil().save(stream, format='PNG')
                        bitmap.close(); rp.close()
                    page_refs.append({'page': n, 'data': rel(native), 'image': rel(png),
                                      'data_sha256': sha(native.read_bytes()), 'image_sha256': sha(png.read_bytes())})
                manifest = checked(dest / 'manifest.json')
                if not manifest.exists():
                    save(manifest, {'payload_sha256': item['sha256'], 'config': config(), 'pages': page_refs})
                else: assert read(manifest)['pages'] == page_refs, 'cache readback mismatch'
            ready.append({'drive_id': item['drive_id'], 'cache': rel(dest), 'pages': len(page_refs)})
        except Exception as exc:
            event('extraction-error', {'drive_id': item['drive_id'], 'error': type(exc).__name__, 'message': str(exc)})
            print(json.dumps({'error': item['drive_id'], 'type': type(exc).__name__}), flush=True)
    event('prepared', {'documents': ready, 'elapsed_seconds': round(time.monotonic() - start, 2)})
    print(json.dumps({'ready': len(ready), 'pages': sum(x['pages'] for x in ready), 'elapsed_seconds': round(time.monotonic()-start, 2)}))


def normalize(item, dossier):
    assert all(isinstance(issue,dict) and issue.get('detail','').strip() for issue in dossier['source_issues']), 'source issues require structured, explicit details'
    dest = cache_path(item)
    manifest = read(dest / 'manifest.json')
    assert manifest['payload_sha256'] == dossier['source_sha256'] == item['sha256']
    assert sha(checked(ROOT / item['source_file']).read_bytes()) == item['sha256']
    reviews = {p['page']: p for p in dossier['pages']}
    assert sorted(reviews) == list(range(1, item['page_count'] + 1)), 'every page must be visually reviewed'
    pages = []
    courses, active = [], {}
    regions = []
    region_patch = read(dest/'semester-regions-v2.json') if (dest/'semester-regions-v2.json').exists() else None
    if region_patch: assert region_patch['source_sha256'] == item['sha256']
    for p in manifest['pages']:
        review = reviews[p['page']]
        assert review['image_sha256'] == p['image_sha256'] == sha(checked(ROOT / p['image']).read_bytes())
        assert sha(checked(ROOT / p['data']).read_bytes()) == p['data_sha256']
        assert review['content_checked'] is True and review['notes'].strip()
        raw = read(ROOT / p['data']); pages.append(raw)
        page_regions = next((x['regions'] for x in region_patch['pages'] if x['page']==p['page']), raw['semester_regions']) if region_patch else raw['semester_regions']
        if p['page'] in dossier.get('omit_default_semester_regions_for_pages',[]):
            assert any(t['page']==p['page'] for t in dossier.get('reviewed_native_option_tables',[])), 'omitted native regions need explicit table coverage'
            page_regions=[]
        overrides = [r for r in dossier.get('reviewed_region_overrides', []) if r['page']==p['page']]
        if overrides:
            import pdfplumber
            page_regions = []
            with pdfplumber.open(checked(ROOT/item['source_file'])) as override_pdf:
                source_page = override_pdf.pages[p['page']-1]
                for override in overrides:
                    box = override['bbox']
                    assert override['source_basis'].strip() and len(box)==4
                    assert 0 <= box[0] < box[2] <= source_page.width and 0 <= box[1] < box[3] <= source_page.height
                    page_regions.append({'semester':override['semester'],'bbox':box,
                                         'text':source_page.crop(box).extract_text() or '',
                                         'source_basis':override['source_basis']})
        seen_semesters = Counter()
        for region_index, region in enumerate(page_regions):
            sem = region['semester']; text = region['text']
            occurrence_suffix = f":r{region_index}" if seen_semesters[sem] else ''
            seen_semesters[sem] += 1
            branch = dossier.get('branch_by_page_region',{}).get(f"{p['page']}:{region_index}")
            locator = {'page': p['page'], 'bbox': region['bbox'], 'image': p['image']}
            regions.append({**region, **locator, **({'branch':branch} if branch else {})})
            variants=[v for v in dossier.get('reviewed_code_line_variants',[]) if v['page']==p['page'] and v['semester']==sem]
            for variant in variants:
                assert variant['source_basis'].strip() and type(variant['credits']) is int and variant['credits']>0
                literal=re.fullmatch(r'\s*([0-9xX.]{2,9})\s+(\d+)\s*',variant['source_line'])
                assert literal and literal[1]==variant['code'] and int(literal[2])==variant['credits'], 'source-line values cannot be changed by a separator repair'
                pattern=r'(?m)^'+re.escape(variant['source_line'])+r'$'
                assert len(re.findall(pattern,text))==1, 'reviewed source-line variant must occur once in its region'
                text=re.sub(pattern,f"{variant['code']} – {variant['credits']}",text)
            for variant in dossier.get('reviewed_code_only_lines',[]):
                if variant['page']!=p['page'] or variant['semester']!=sem:continue
                assert variant['source_line']==variant['code'] and re.fullmatch(r'[0-9xX.]{2,9}',variant['code']) and variant['source_basis'].strip()
                pattern=r'(?m)^'+re.escape(variant['source_line'])+r'$'
                assert len(re.findall(pattern,text))==1
                text=re.sub(pattern,variant['code']+' –',text)
            code_pattern=re.compile(CODE.pattern.replace('0-9xX.','0-9xX.…')) if dossier.get('allow_ellipsis_codes') else CODE
            if dossier.get('allow_spaced_credit_marker'):
                code_pattern=re.compile(code_pattern.pattern.replace(r'(\d+)(\*?)',r'(\d+)[ \t]*(\*?)'))
            if dossier.get('preserve_grouped_code_notation'):
                assert dossier['grouped_code_source_basis'].strip()
                code_pattern=re.compile(code_pattern.pattern.replace('{2,9})',r'{2,9}(?:\([0-9,]+\))?)'))
            matches = list(code_pattern.finditer(text))
            # A continued cell must retain both page ranges, even without a code on page 2.
            if matches and text[:matches[0].start()].strip() and sem in active:
                active[sem]['continuation_verbatim'] = text[:matches[0].start()].strip()
                active[sem]['locators'].append(locator)
            for k, m in enumerate(matches):
                end = matches[k+1].start() if k+1 < len(matches) else len(text)
                body = text[m.end():end].strip()
                if dossier.get('trim_reviewed_semester_footer'):
                    body=re.split(r'(?m)^\d+\s*TC\s*$',body)[0].strip()
                body = re.split(r'(?m)^\d{1,2}\s*$|^Tổng số tín chỉ|^Tự chọn\b|^HP tự chọn', body)[0].strip()
                preserve_name=m[1] in dossier.get('preserve_coded_name_codes',[])
                trim_pattern=r'(?im)^Giáo dục (?:TC|Th[ểếe] chất)|^GDTC|^(?:GD\s+)?Th[ểếe]\s+chất'
                trim_match=re.search(trim_pattern,body)
                if trim_match and not preserve_name:body=body[:trim_match.start()].strip()
                if dossier.get('trim_reviewed_non_course_labels'):
                    label_pattern=r'(?im)^CÁC HỌC\s*$|^Chọn\s+\d+\s*TC\b|^(?:Môn|Học phần) tự chọn\b|^\d+\s+HP\s+tự chọn\b'
                    if not preserve_name:label_pattern+=r'|^Giáo dục\s+(?:TC|Th[ểếe]\s+chất)'
                    trim_match=re.search(label_pattern,body)
                    if trim_match and (trim_match.start()>0 or not preserve_name):body=body[:trim_match.start()].strip()
                record = {'occurrence_id': f"{item['drive_id']}:p{p['page']}:s{sem}:{k}{occurrence_suffix}",
                    'semester': sem, 'code': m[1], 'name_verbatim': body,
                    'credits': int(m[2]) if m[2] else None, 'credit_unit': 'TC', 'credit_annotation': ((m[3] or '') + (f' ({m[4]})' if m[4] else '')).strip() or None, 'knowledge_block': None,
                    'requirement': None, 'elective_group': None, 'locators': [locator]}
                if branch: record['branch'] = branch
                for variant in variants:
                    if record['code']==variant['code']:
                        record['code_credit_source_line']=variant['source_line']
                        record['source_format_basis']=variant['source_basis']
                for variant in dossier.get('reviewed_code_only_lines',[]):
                    if variant['page']==p['page'] and variant['semester']==sem and record['code']==variant['code']:
                        record['code_only_source_line']=variant['source_line']
                        record['source_format_basis']=variant['source_basis']
                courses.append(record); active[sem] = record
    if dossier.get('layout_mode') == 'native_diagram_cells':
        assert not regions, 'diagram override only for pages without semester grid extraction'
        spatial_file = checked(dest / 'diagram-cells-v2.json')
        spatial_data = read(spatial_file)
        assert spatial_data['source_sha256'] == item['sha256']
        for page in spatial_data['pages']:
            assert page['headers'] and page['cells'], 'every diagram page needs semester and cell coverage'
            for n, cell in enumerate(page['cells']):
                assert cell['semester'] is not None
                code, sem = cell['code'], cell['semester']
                block = dossier.get('knowledge_block_by_code', {}).get(code)
                if block is None:
                    block = dossier.get('color_legend', {}).get(json.dumps(cell['fill_color']))
                courses.append({'occurrence_id':f"{item['drive_id']}:p{page['page']}:s{sem}:b{n}",
                    'semester':sem,'code':code,'name_verbatim':cell['name_verbatim'],'credits':cell['credits'],
                    'credit_unit':'TC','knowledge_block':block,'requirement':'elective' if block=='Học phần tự chọn' else None,
                    'elective_group':None,'language':dossier.get('languages_by_page',{}).get(str(page['page'])),
                    'locators':[{'page':page['page'],'bbox':cell['bbox'],
                                 'image':next(p['image'] for p in manifest['pages'] if p['page']==page['page'])}]})
            for header in page['headers']:
                cells = [c for c in page['cells'] if c['semester']==header['semester']]
                regions.append({'page':page['page'],'semester':header['semester'],
                    'bbox':[min(c['bbox'][0] for c in cells),min(c['bbox'][1] for c in cells),max(c['bbox'][2] for c in cells),max(c['bbox'][3] for c in cells)],
                    'text':'\n\n'.join(c['text'] for c in cells),
                    'image':next(p['image'] for p in manifest['pages'] if p['page']==page['page'])})
    native_option_groups=[]
    for spec in dossier.get('reviewed_native_option_tables',[]):
        number=spec['page'];ref=next(p for p in manifest['pages'] if p['page']==number)
        raw=read(ROOT/ref['data']);table=raw['tables'][spec['table_index']]
        name_column,code_column=spec['name_column'],spec['code_column']
        rule=table['rows'][0]['values'][name_column]
        assert rule==spec['rule_verbatim'] and int(re.search(r'Chọn\s+(\d+)',rule)[1])==spec['choice_count']
        options=[];texts=[rule];bounds=[]
        for row_number,row in enumerate(table['rows'][1:],1):
            code_text=row['values'][code_column];name=row['values'][name_column]
            if not code_text and not name:continue
            match=CODE.fullmatch(code_text.strip())
            assert match and match[2] and name and name.strip(), 'every native elective row needs its printed name, code and credits'
            boxes=[row['cells'][name_column],row['cells'][code_column]]
            box=[min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)]
            occurrence=f"{item['drive_id']}:p{number}:native-choice:{spec['group_id']}:{row_number}"
            courses.append({'occurrence_id':occurrence,'semester':spec.get('semester'),'applicable_semesters':spec['applicable_semesters'],
                'code':match[1],'credits':int(match[2]),'credit_unit':'TC','credit_annotation':match[3] or None,
                'name_verbatim':name.strip(),'knowledge_block':None,'requirement':'elective','elective_group':spec['group_id'],
                'locators':[{'page':number,'bbox':box,'image':ref['image']}],'native_table_text':code_text+'\n'+name})
            options.append(occurrence);bounds.append(box);texts.append(code_text+'\n'+name)
        assert len(options)==spec['expected_option_count']
        native_option_groups.append({'group_id':spec['group_id'],'page':number,'semester':spec.get('semester'),
            'applicable_semesters':spec['applicable_semesters'],'choice_count':spec['choice_count'],'rule_verbatim':rule,
            'printed_credits':None,'option_occurrences':options})
        regions.append({'page':number,'semester':spec.get('semester'),'branch':rule,'text':'\n\n'.join(texts),
            'bbox':[min(b[0] for b in bounds),min(b[1] for b in bounds),max(b[2] for b in bounds),max(b[3] for b in bounds)],
            'image':ref['image'],'source_basis':'exact native choice table; unallocated across the explicitly reviewed semesters'})
    raster_evidence, raster_groups = [], []
    if dossier.get('layout_mode') == 'reviewed_raster_cells':
        assert not regions and not courses, 'raster override only when native semester extraction is absent'
        from huce_raster_curriculum import normalize_reviewed_cells
        courses, regions, raster_evidence, raster_groups = normalize_reviewed_cells(item,dossier,manifest)
    if dossier.get('layout_mode') == 'reviewed_raster_instruction_units':
        assert not regions and not courses
        from huce_raster_curriculum import normalize_instruction_cells
        courses,regions,raster_evidence,raster_groups=normalize_instruction_cells(item,dossier,manifest)
    for repair in dossier.get('course_name_repairs', []):
        matched = [c for c in courses if c['code']==repair['code'] and c['semester']==repair['semester']
                   and any(l['page']==repair['page'] for l in c['locators'])]
        assert len(matched)==1 and matched[0]['name_verbatim']==repair['extracted_name_verbatim']
        assert repair['source_name_verbatim'].strip() and repair['visual_and_native_basis'].strip()
        matched[0].update(extracted_name_verbatim=matched[0]['name_verbatim'],
                          name_verbatim=repair['source_name_verbatim'],
                          name_repair_basis=repair['visual_and_native_basis'])
    for n, entry in enumerate(dossier.get('uncoded_entries', [])):
        region = next(r for r in regions if r['page']==entry['page'] and r['semester']==entry['semester'])
        assert ' '.join(entry['name_verbatim'].split()).casefold() in ' '.join(region['text'].split()).casefold()
        if entry.get('external_code'):
            assert entry['external_code'] in entry['name_verbatim'] and entry['source_basis'].strip()
            assert re.fullmatch(r'[A-Za-z]+ \d+',entry['external_code'])
            assert type(entry['credits']) is int and entry['credits']>0
            credit=re.search(entry['credit_pattern'],entry['name_verbatim'])
            assert credit and int(credit['credits'])==entry['credits'], 'external identifier needs its literal printed credit quantity'
        courses.append({**entry,'occurrence_id':f"{item['drive_id']}:uncoded:{n}",'code':entry.get('external_code'),
            'knowledge_block':None,'elective_group':None,'locators':[{'page':entry['page'],'bbox':region['bbox'],'image':region['image']}]})
    for group in dossier.get('elective_groups', []):
        assert group['rule_verbatim'] and group['page'] in reviews
        for code in group.get('option_codes', []):
            matched=[c for c in courses if c['code']==code and c['semester']==group['semester']
                     and any(l['page']==group['page'] for l in c['locators'])]
            assert len(matched)==1, 'elective option needs an unambiguous occurrence'
            matched[0].update(requirement='elective',elective_group=group['group_id'])
    for c in courses:
        if c['code'] in dossier.get('excluded_codes', []):
            assert dossier.get('exclusion_verbatim')
            c['requirement']='excluded_from_total'
        condition=dossier.get('credit_annotation_conditions',{}).get(c.get('credit_annotation'))
        if condition:
            c.update(requirement='conditional',condition_verbatim=condition)
    for requirement in dossier.get('reviewed_course_requirements',[]):
        matched=[c for c in courses if c['code']==requirement['code'] and c['semester']==requirement['semester']
                 and any(l['page']==requirement['page'] for l in c['locators'])
                 and requirement.get('name_contains','') in c['name_verbatim']]
        assert len(matched)==1 and requirement['source_basis'].strip()
        assert requirement['requirement'] in {'elective','required'}
        matched[0].update(requirement=requirement['requirement'],requirement_source_basis=requirement['source_basis'])
    for condition in dossier.get('reviewed_course_conditions',[]):
        matched=[c for c in courses if c['code']==condition['code'] and c['semester']==condition['semester']
                 and any(l['page']==condition['page'] for l in c['locators'])]
        assert len(matched)==1 and condition['source_basis'].strip()
        raw_page=next(p for p in pages if p['page']==condition['page'])
        assert ' '.join(condition['condition_verbatim'].split()) in ' '.join(raw_page['text'].split()), 'condition must occur on the cited original page'
        assert condition['source_marker'] in matched[0]['name_verbatim'], 'condition marker must remain in the literal course name'
        matched[0].update(requirement='conditional',condition_verbatim=condition['condition_verbatim'],
                          condition_source_basis=condition['source_basis'])
    by_code = defaultdict(set)
    for c in courses:
        if c['code'] is not None: by_code[(c['code'],c.get('language'))].add(' '.join(c['name_verbatim'].split()))
    warnings = [{'kind': 'duplicate_code_different_names', 'code': code, 'names': sorted(names),
                 'locators': [l for c in courses if c['code'] == code for l in c['locators']]}
                for (code, language), names in by_code.items() if len(names) > 1]
    warnings += [{'kind': 'missing_or_zero_name', 'occurrence_id': c['occurrence_id'], 'locators': c['locators']}
                 for c in courses if c['name_verbatim'] in {'', '0'}]
    warnings += [{'kind':'source_credit_not_printed','occurrence_id':c['occurrence_id'],'code':c['code'],'locators':c['locators']}
                 for c in courses if c['code'] is not None and c['credits'] is None]
    assert not dossier['extraction_errors'], 'repair extraction errors before admission'
    assert dossier['relations_checked'] is True
    # A second native engine avoids self-confirming the same row-order bug.
    import pypdfium2 as pdfium
    independent_pages = []
    with pdfium.PdfDocument(str(checked(ROOT / item['source_file']))) as pdf:
        for n in range(len(pdf)):
            page = pdf[n]; textpage = page.get_textpage()
            independent_pages.append({'page': n+1, 'text': textpage.get_text_bounded().replace('\r', '')})
            textpage.close(); page.close()
    printed_code_pattern=r'(?<![\w.])([0-9xX.]{2,9})\s*[–−-]\s*(\d+)\*?'
    if dossier.get('allow_ellipsis_codes'):printed_code_pattern=printed_code_pattern.replace('0-9xX.','0-9xX.…')
    if dossier.get('preserve_grouped_code_notation'):
        printed_code_pattern=printed_code_pattern.replace('{2,9})',r'{2,9}(?:\([0-9,]+\))?)')
    printed_occurrences = Counter((m[1], int(m[2])) for p in independent_pages for m in re.finditer(printed_code_pattern,p['text']))
    for entry in dossier.get('uncoded_entries',[]):
        if not entry.get('external_code'):continue
        region=next(r for r in regions if r['page']==entry['page'] and r['semester']==entry['semester'])
        b=region['bbox'];raw_page=next(p for p in pages if p['page']==entry['page'])
        with pdfium.PdfDocument(str(checked(ROOT/item['source_file']))) as doc:
            rp=doc[entry['page']-1];tp=rp.get_textpage()
            independent=tp.get_text_bounded(b[0],raw_page['height']-b[3],b[2],raw_page['height']-b[1]).replace('\r','')
            tp.close();rp.close()
        credit=re.search(entry['credit_pattern'],independent)
        assert entry['external_code'] in independent and credit and int(credit['credits'])==entry['credits']
        printed_occurrences[(entry['external_code'],entry['credits'])]+=1
    for variant in dossier.get('reviewed_code_only_lines',[]):
        # Full-page PDFium text may join equally positioned columns into one
        # line. Check the actual semester region with the independent engine.
        source_region=next(r for r in regions if r['page']==variant['page'] and r['semester']==variant['semester'])
        b=source_region['bbox'];raw_page=next(p for p in pages if p['page']==variant['page'])
        with pdfium.PdfDocument(str(checked(ROOT/item['source_file']))) as doc:
            rp=doc[variant['page']-1];tp=rp.get_textpage()
            independent=tp.get_text_bounded(b[0],raw_page['height']-b[3],b[2],raw_page['height']-b[1]).replace('\r','')
            tp.close();rp.close()
        assert len(re.findall(r'(?m)^'+re.escape(variant['source_line'])+r'\s*$',independent))==1
    for variant in dossier.get('reviewed_code_line_variants',[]):
        independent=next(p['text'] for p in independent_pages if p['page']==variant['page'])
        count=len(re.findall(r'(?m)^'+re.escape(variant['source_line'])+r'\s*$',independent))
        assert count==1, 'second native engine must retain the exact reviewed irregular source line'
        printed_occurrences[(variant['code'],variant['credits'])]+=count
    parsed_occurrences = Counter((c['code'], c['credits']) for c in courses if c['code'] is not None and c['credits'] is not None)
    if regions and dossier.get('layout_mode') not in {'reviewed_raster_cells','reviewed_raster_instruction_units'}:
        assert printed_occurrences == parsed_occurrences, f'coded course coverage differs: {printed_occurrences - parsed_occurrences}; extra: {parsed_occurrences - printed_occurrences}'
    relations = []
    for relation in dossier.get('relations', []):
        assert relation['type'] in {'prerequisite', 'concurrent'}
        assert relation['legend_page'] in reviews and relation['arrow_page'] in reviews
        assert relation['trace_note'].strip()
        endpoints = []
        for side in ('from', 'to'):
            candidates = [c for c in courses if c['code'] == relation[f'{side}_code'] and c['semester'] == relation[f'{side}_semester']
                          and (relation.get(f'{side}_page') is None or any(l['page']==relation[f'{side}_page'] for l in c['locators']))
                          and (relation.get('language') is None or c.get('language')==relation['language'])
                          and relation.get(f'{side}_name_contains', '') in c['name_verbatim']]
            assert len(candidates) == 1, f'ambiguous arrow endpoint: {side}, {relation}'
            endpoints.append(candidates[0])
        a, b = endpoints
        relations.append({**relation, 'from_occurrence': a['occurrence_id'], 'to_occurrence': b['occurrence_id'],
                          'source_locators': a['locators'], 'target_locators': b['locators']})
    # Explicitly confirmed source uncertainties remain visible; never silently repair print errors.
    assert not warnings or dossier.get('automatic_warnings_reviewed') is True
    assert not warnings or dossier['source_issues'], 'source warnings need explicit sourced dispositions'
    assert regions and courses, 'spatial curriculum normalization required; scan OCR alone cannot define cells'
    if not dossier['source_issues']:
        assert dossier.get('completion_attestation') == {
            'all_cells_checked': True, 'all_notes_and_exceptions_checked': True,
            'all_arrows_and_legend_checked': True, 'scope_and_units_checked': True}, 'full content attestation required'
    return {'drive_id': item['drive_id'], 'source_file': item['source_file'], 'source_sha256': item['sha256'],
        'source_identity': 'drive:' + item['drive_id'], 'payload_identity': item['sha256'],
        'title_verbatim': dossier['title'], 'applicability': dossier['applicability'],
        'legal_effective_from': dossier.get('legal_effective_from'), 'published_at': dossier.get('published_at'),
        'page_evidence': manifest['pages'], 'full_semester_regions': regions,
        'courses': courses, 'relations': relations,
        'source_issues': dossier['source_issues'], 'automatic_warnings': warnings,
        'review_dossier': dossier, 'extraction_status': 'all_pages_retained',
        'normalizer_version': 'semester-occurrences-5',
        'elective_groups': [*dossier.get('elective_groups', []),*raster_groups,*native_option_groups],
        'raster_evidence':raster_evidence,
        'independent_native_page_text': independent_pages,
        'independent_code_coverage': {'method': ('Raster OCR/crop hashes and every proposed box disposition; reviewed instruction quantities or native elective-table cells; no independent engine verifies manual source transcription' if raster_evidence else 'PDFium full-page vs bounded-cell multiset using pdfplumber shapes; same text engine, NOT independent semantic verification' if dossier.get('layout_mode')=='native_diagram_cells'
                                               else 'PDFium code/credit multiset against pdfplumber semester occurrences; visual review still required'),
                                      'matched_occurrences': None if raster_evidence else sum(printed_occurrences.values()),
                                      'raster_coded_occurrences':sum(c['code'] is not None for c in courses) if raster_evidence else None},
        'printed_semester_totals': dossier.get('printed_semester_totals'),
        'printed_total': dossier.get('printed_total'), 'exclusion_verbatim': dossier.get('exclusion_verbatim'),
        'verification_status': 'all_pages_visually_checked_with_source_issues' if dossier['source_issues'] else 'all_pages_visually_checked',
        'normalization_status': 'full_regions_and_occurrences_source_uncertainties_explicit',
        'indexing_status': 'pending', 'completion_status': 'incomplete_until_index_coverage_checked'}


def review(args):
    event('preflight', preflight())
    dossiers = read(ROOT / (args.dossier or args.decisions))
    if args.decisions:
        compiled = []
        for decision in dossiers['documents']:
            d = dict(decision)
            item = items()[d.pop('queue_index')]
            manifest = read(cache_path(item) / 'manifest.json')
            notes = d.pop('page_notes')
            d.update(drive_id=item['drive_id'], source_sha256=item['sha256'], reviewer=dossiers['reviewer'],
                decision_file=args.decisions, decision_file_sha256=sha(checked(ROOT / args.decisions).read_bytes()),
                pages=[{'page': r['page'], 'image_sha256': r['image_sha256'], 'content_checked': True, 'notes': note}
                       for r, note in zip(manifest['pages'], notes, strict=True)],
                extraction_errors=[], relations_checked=True, automatic_warnings_reviewed=True)
            relations = d.pop('additional_relations', [])
            for kind, pairs in d.pop('arrow_pairs', {}).items():
                for a, sa, b, sb in pairs:
                    relations.append(dict(type=kind, from_code=a, from_semester=sa, to_code=b, to_semester=sb))
            for relation in relations:
                relation.update(legend_page=1, arrow_page=1,
                    trace_note='Direct visual trace of line and arrowhead(s), checked with same-page legend and duplicate occurrence names.')
            d['relations'] = relations; compiled.append(d)
        dossiers = {'documents': compiled}
    lookup = {i['drive_id']: i for i in items()}
    outputs = []
    for dossier in dossiers['documents']:
        normalized = normalize(lookup[dossier['drive_id']], dossier)
        path = checked(BASE / 'reviews' / f"{stamp()}-{dossier['drive_id']}.json")
        save(path, normalized); outputs.append(rel(path))
    event('reviewed', {'records': outputs, 'dossier': args.dossier, 'decisions': args.decisions})
    print(json.dumps({'reviewed': len(outputs), 'records': outputs}))


def latest_reviews():
    reviews = {}
    folder = checked(BASE / 'reviews')
    if folder.exists():
        for path in sorted(folder.glob('*.json')):
            d = read(path); reviews[d['drive_id']] = (path, d)
    return reviews


def spatial(args):
    """Recover native flowchart boxes without treating connector lines as cells."""
    import pdfplumber
    import pypdfium2 as pdfium
    event('preflight', preflight())
    for item in items():
        if args.ids and item['drive_id'] not in args.ids: continue
        cache = cache_path(item)
        target = checked(cache / 'diagram-cells-v2.json')
        if target.exists(): continue
        manifest = read(cache / 'manifest.json')
        raw_pages = [read(ROOT / p['data']) for p in manifest['pages']]
        if any(p['semester_regions'] for p in raw_pages) or any(p['classification']=='scan_requires_local_ocr' for p in raw_pages): continue
        extracted = []
        with pdfplumber.open(checked(ROOT / item['source_file'])) as pdf, pdfium.PdfDocument(str(checked(ROOT / item['source_file']))) as doc:
            for n, raw in enumerate(raw_pages):
                page = pdf.pages[n]; rp = doc[n]; tp = rp.get_textpage()
                headers = []
                words = raw['words']
                for word in words:
                    if word['text'].lower() not in {'kỳ', 'semester'}: continue
                    right = sorted((w for w in words if abs(w['top']-word['top'])<1 and w['x0']>=word['x1']), key=lambda w:w['x0'])
                    if right and re.fullmatch(r'[1-9]|1[0-2]', right[0]['text']) and right[0]['x0']-word['x1'] < 12:
                        headers.append({'semester':int(right[0]['text']), 'center_x':(word['x0']+right[0]['x1'])/2-4, 'bbox':[word['x0'],word['top'],right[0]['x1'],right[0]['bottom']]})
                candidates=[]
                for rect in [*page.rects, *page.curves]:
                    box=(rect['x0'],rect['top'],rect['x1'],rect['bottom'])
                    if not (25<rect['width']<page.width/4 and 12<rect['height']<page.height/2): continue
                    text=tp.get_text_bounded(box[0],page.height-box[3],box[2],page.height-box[1]).replace('\r','').strip()
                    matches=list(CODE.finditer(text))
                    if len(matches)!=1 or matches[0].start()>3: continue
                    match=matches[0]
                    name=text[match.end():].strip()
                    if not name: continue
                    sem=min(headers,key=lambda h:abs(h['center_x']-(box[0]+box[2])/2))['semester'] if headers else None
                    candidates.append({'page':n+1,'bbox':box,'text':text,'code':match[1], 'credits':int(match[2]) if match[2] else None,
                        'name_verbatim':name,'semester':sem,'fill_color':rect.get('non_stroking_color'),
                        'area':rect['width']*rect['height']})
                # PDF producers often draw an outer box and a text box. Keep the enclosing one once.
                cells=[]
                for candidate in sorted(candidates,key=lambda c:-c['area']):
                    x0,y0,x1,y1=candidate['bbox']; cx,cy=(x0+x1)/2,(y0+y1)/2
                    if any(c['bbox'][0]-.5<=cx<=c['bbox'][2]+.5 and c['bbox'][1]-.5<=cy<=c['bbox'][3]+.5 for c in cells): continue
                    cells.append(candidate)
                cells.sort(key=lambda c:(c['semester'] or 0,c['bbox'][1]))
                extracted.append({'page':n+1,'headers':headers,'cells':cells,
                    'full_text':tp.get_text_bounded().replace('\r',''), 'lines':raw['lines'],'curves':raw['curves'],
                    'status':'candidate_boxes_require_every_page_visual_review; no arrow or color semantics inferred'})
                tp.close(); rp.close()
        if not any(p['cells'] for p in extracted): continue
        save(target,{'source_sha256':item['sha256'],'extractor':'native-closed-shapes-pdfium-bounded-2','pages':extracted})
        event('spatial-candidate',{'drive_id':item['drive_id'],'evidence':rel(target),'cells':sum(len(p['cells']) for p in extracted)})
        print(json.dumps({'drive_id':item['drive_id'],'cells':sum(len(p['cells']) for p in extracted),'headers':[len(p['headers']) for p in extracted]}),flush=True)


def repair_regions(args):
    """Use each page's actual headers, including two alternate branches of one semester."""
    import pdfplumber
    event('preflight', preflight())
    for item in items():
        if args.ids and item['drive_id'] not in args.ids: continue
        cache = cache_path(item); target = checked(cache/'semester-regions-v2.json')
        if target.exists(): continue
        manifest = read(cache/'manifest.json'); patches=[]
        with pdfplumber.open(checked(ROOT/item['source_file'])) as pdf:
            for ref in manifest['pages']:
                raw = read(ROOT/ref['data']); found=[]; table_bottom=None
                for table in raw['tables']:
                    for row in table['rows']:
                        candidates=[(int(m[1]),box) for box,value in zip(row['cells'],row['values'])
                            if box and value and (m:=re.fullmatch(r'Học\s*kỳ\s*(\d+)', ' '.join(value.split()),re.I))]
                        if len(candidates)>=2:
                            found=candidates; table_bottom=table['bbox'][3];break
                    if found:break
                if not found:continue
                page=pdf.pages[ref['page']-1]; regions=[]
                for sem,box in found:
                    bbox=(box[0]+.15,box[3],box[2]-.15,table_bottom)
                    regions.append({'semester':sem,'bbox':bbox,'text':page.crop(bbox).extract_text() or ''})
                if regions!=raw['semester_regions']:
                    patches.append({'page':ref['page'],'regions':regions,'previous_regions_preserved_at':ref['data']})
        if patches:
            save(target,{'source_sha256':item['sha256'],'extractor':'page-local-semester-headers-2','pages':patches})
            event('region-repair',{'drive_id':item['drive_id'],'evidence':rel(target),'pages':[p['page'] for p in patches]})
            print(json.dumps({'drive_id':item['drive_id'],'repaired_pages':[p['page'] for p in patches]}))


def ocr(args):
    event('preflight', preflight())
    jobs = []
    for item in items():
        if args.ids and item['drive_id'] not in args.ids: continue
        manifest = read(cache_path(item) / 'manifest.json')
        for page in manifest['pages']:
            raw = read(ROOT / page['data'])
            if raw['classification'] != 'scan_requires_local_ocr' and not (args.include_embedded and raw['image_objects']): continue
            jobs.append({**page, 'drive_id': item['drive_id'], 'source_file': item['source_file'],
                         'source_sha256': item['sha256']})
    assert jobs, 'no scan pages selected'
    for did in dict.fromkeys(j['drive_id'] for j in jobs):
        output = checked(BASE / 'ocr' / did); output.mkdir(parents=True, exist_ok=True)
        batch = {'pages': [j for j in jobs if j['drive_id'] == did],
                 'node_package_root': args.node_package_root, 'language_directory': str(checked(ROOT / 'data/huce-public-20261013')),
                 'output_directory': str(output)}
        jobfile = event('ocr-jobs', batch)
        result = subprocess.run([args.node, str(checked(ROOT / 'scripts/huce_document_ocr.mjs')), str(jobfile)],
                                cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
        event('ocr-result', {'drive_id': did, 'exit_code': result.returncode, 'stdout': result.stdout,
                             'stderr': result.stderr, 'semantics_not_inferred': True})
        print(result.stdout, flush=True)
        assert result.returncode == 0, 'local OCR failed; evidence retained'


def publish(args):
    event('preflight', preflight())
    assert args.version >= 8
    path = checked(PUB / f'reviewed-corrections-20261021-v{args.version}.json')
    assert not path.exists(), 'release already exists'
    previous = []
    for name in ['reviewed-expansion-20261020.json', 'reviewed-expansion-20261020-batch2.json',
                 'reviewed-curricula-batch3-verified-20261021.json']:
        previous += read(PUB / name)['chunks']
    chunks, coverage = [], []
    published_reviews = set()
    published_content = []
    for prior_release in PUB.glob('reviewed-corrections-20261021-v*.json'):
        if not re.fullmatch(r'reviewed-corrections-20261021-v\d+\.json',prior_release.name): continue
        if prior_release.with_suffix('.withdrawn.json').exists(): continue
        for record in read(prior_release).get('pipeline_coverage', []):
            if record.get('kind') in {'calendar_cntt_rows','reviewed_public_document'}:continue
            published_reviews.add(record['review_file'])
            published_content.append(read(ROOT / record['review_file']))
    for did, (review_file, d) in latest_reviews().items():
        if args.ids and did not in args.ids: continue
        if rel(review_file) in published_reviews: continue
        # Parsed field repairs do not require re-embedding unchanged, full source transcripts.
        def transcript_signature(record):
            return {'source_sha256':record['source_sha256'],'regions':record['full_semester_regions'],
                    'issues':record['source_issues'],'scope':record['applicability'],
                    'title':record['title_verbatim'],'page_scope':record['review_dossier'].get('page_applicability'),
                    'page_titles':record['review_dossier'].get('page_titles'),
                    'relations':[{k:r[k] for k in ('type','from_code','to_code','from_semester','to_semester')}
                                 for r in record['relations']]}
        if any(transcript_signature(prior)==transcript_signature(d) for prior in published_content): continue
        # Revalidate evidence immediately before publication.
        item = next(i for i in items() if i['drive_id'] == did)
        validated = normalize(item, d['review_dossier'])
        for field in ('source_sha256','page_evidence','title_verbatim','applicability','courses','relations','source_issues','full_semester_regions','review_dossier'):
            assert validated[field] == d[field], f'reviewed content changed: {field}'
        d = validated
        historical = next(c for c in previous if c['source_sha256'] == d['source_sha256'])
        # Reuse source discovery links and the exact retired excerpt hash only.
        # Academic facts from historical extraction are not verified metadata.
        base = {key:historical[key] for key in ('url','download_url','text_sha256')}
        head = d['title_verbatim']
        foot = '\n'.join(i['detail'] for i in d['source_issues'])
        relation_text = '\n'.join(f"{r['from_code']} (kỳ {r['from_semester']}) {'→' if r['type']=='prerequisite' else '↔'} {r['to_code']} (kỳ {r['to_semester']}): "
            + ('tiên quyết' if r['type']=='prerequisite' else 'song hành') + f"; mũi tên trang {r['arrow_page']}, chú giải trang {r['legend_page']}." for r in d['relations'])
        regions = d['full_semester_regions']
        independent = {p['page']: p['text'] for p in d.get('independent_native_page_text', [])}
        units = [({'page': p['page'], 'bbox': [0, 0, p['width'], p['height']]}, independent.get(p['page'], p['text']), None)
                 for p in [read(ROOT / r['data']) for r in d['page_evidence']] if p['text'].strip()]
        # Full page chunks retain all headings, footnotes and cells. Additional columns give unambiguous semester context.
        units += [(r, r['text'], r['semester']) for r in regions if r['text'].strip()]
        for region, verbatim, sem in units:
            page_scope = d['review_dossier'].get('page_applicability',{}).get(str(region['page']),d['applicability'])
            page_title = d['review_dossier'].get('page_titles',{}).get(str(region['page']),head)
            section = f"{page_title} — trang {region['page']}" + (f' — học kỳ {sem}' if sem else ' — toàn trang')
            if region.get('branch'): section += ' — ' + region['branch']
            text = page_title + '\n' + section + '\n' + verbatim
            text += '\nPhạm vi: ' + json.dumps(page_scope, ensure_ascii=False)
            unit_relations=relation_text
            if d['review_dossier'].get('page_applicability'):
                unit_relations='\n'.join(f"{r['from_code']} (kỳ {r['from_semester']}) {'→' if r['type']=='prerequisite' else '↔'} {r['to_code']} (kỳ {r['to_semester']}): "
                    + ('tiên quyết' if r['type']=='prerequisite' else 'song hành') + f"; mũi tên trang {r['arrow_page']}, chú giải trang {r['legend_page']}."
                    for r in d['relations'] if r['arrow_page']==region['page'])
            if unit_relations: text += '\nQuan hệ đã đối chiếu đường nối, đầu mũi tên và chú giải:\n' + unit_relations
            if foot: text += '\nVẤN ĐỀ NGUỒN CHƯA RÕ, GIỮ NGUYÊN BẢN IN:\n' + foot
            image = next(p['image'] for p in d['page_evidence'] if p['page'] == region['page'])
            chunks.append(dict(base, title=page_title, section=section, text=text, text_sha256=sha(text.encode()),
                source_file=str(Path(d['source_file']).relative_to('data')).replace('\\', '/'),
                source_sha256=d['source_sha256'], issuer='Trường Đại học Xây dựng Hà Nội',
                published_at=d['published_at'], collected_at=now(), applicability=page_scope,
                cohort=page_scope.get('cohort'),degree_level=page_scope.get('degree'),academic_year=page_scope.get('academic_year'),
                total_credits=d['review_dossier'].get('printed_totals_by_page',{}).get(str(region['page']),d.get('printed_total')),
                total_credit_basis='Only explicitly reviewed printed total; null when not supplied in the review dossier',
                legal_effective_from=d['legal_effective_from'], effective_from=now(),
                effective_date_basis='retrieval admission only; not legal effectiveness',
                supersedes=[], limitations=[i['detail'] for i in d['source_issues']],
                ocr_quality=('local_cell_ocr_original_images_and_reviewed_instruction_units' if d['review_dossier'].get('layout_mode')=='reviewed_raster_instruction_units' else 'local_cell_ocr_and_every_page_visual_review_plus_native_elective_tables' if d['review_dossier'].get('layout_mode')=='reviewed_raster_cells' else 'native_geometry_and_every_page_visual_review'), visual_evidence=[image],
                page=region['page'], page_end=region['page'], region_bbox=region['bbox'],
                review_status=d['verification_status'], review_scope='Every original page checked; full text and semester columns retained',
                replaces_excerpt_text_sha256=base['text_sha256']))
        coverage.append({'drive_id': did, 'review_file': rel(review_file), 'pages': len(d['page_evidence']),
                         'source_issues': d['source_issues'], 'complete_eligible_after_index': not d['source_issues']})
    assert chunks
    save(path, {'public_only': True, 'acquired_at': now(), 'version_label': path.stem,
                'verification': 'source_verified_excerpts', 'chunks': chunks, 'pipeline_coverage': coverage})
    event('published', {'release': rel(path), 'documents': len(coverage), 'chunks': len(chunks)})
    print(json.dumps({'release': rel(path), 'documents': len(coverage), 'chunks': len(chunks)}))


async def build(args):
    sys.path[:0] = [str(ROOT), str(ROOT / 'services/api/src')]
    from scripts.public_rag_retrieval import create_public_hybrid_store, public_hybrid_index_path
    from campus247.ports.embedding import validate_embedding_vector
    from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy
    event('preflight', preflight())
    kwargs = dict(tenant_id='HUCE', campus_id='HUCE', faq_directory=ROOT / 'data/huce-faq-20261013')
    old = create_public_hybrid_store(PUB, reviewed_corrections_version=args.predecessor, **kwargs)
    new = create_public_hybrid_store(PUB, reviewed_corrections_version=args.version, **kwargs)
    pred = checked(public_hybrid_index_path(old)); before = read(pred); old.load_vectors(before)
    assert old.embedding_profile == new.embedding_profile
    hashes = [sha(c['index_text'].encode()) for c in old.children]
    assert hashes == before['index_text_sha256']
    lookup = {(c['id'], h): v for c, h, v in zip(old.children, hashes, old.vectors, strict=True)}
    target = checked(public_hybrid_index_path(new))
    existing_manifest = read(target) if target.exists() else None
    existing_vectors = {}
    if existing_manifest is not None:
        new.load_vectors(existing_manifest)
        assert existing_manifest['predecessor_fingerprint'] == old.fingerprint
        existing_vectors = {(c['id'],sha(c['index_text'].encode())):v for c,v in zip(new.children,new.vectors,strict=True)}
    vectors, reused, resumed = [], 0, 0
    for child in new.children:
        key = child['id'], sha(child['index_text'].encode())
        if key in lookup:
            vectors.append(list(lookup[key])); reused += 1; continue
        if key in existing_vectors:
            vectors.append(list(existing_vectors[key])); resumed += 1; continue
        cache = checked(BASE / 'vectors' / new.fingerprint / f'{key[0]}-{key[1]}.json')
        if cache.exists():
            record = read(cache)
            assert record['text_sha256'] == key[1] and record['child_id'] == key[0]
            value = validate_embedding_vector(record['values'], new.embedding_profile,
                model_id=record['model_id'], model_revision=record['model_revision'])
            resumed += 1
        else:
            emb = await new.embed_query(child['index_text'])
            value = validate_embedding_vector(emb.values, new.embedding_profile,
                model_id=emb.model_id, model_revision=emb.model_revision)
            save(cache, {'child_id': key[0], 'text_sha256': key[1], 'values': list(value.values),
                         'model_id': emb.model_id, 'model_revision': emb.model_revision})
        vectors.append(list(value.values))
        if (len(vectors) - reused) % 10 == 0:
            print(json.dumps({'new_vectors_ready': len(vectors)-reused, 'resumed': resumed}), flush=True)
    manifest = {'fingerprint': new.fingerprint, 'child_ids': [c['id'] for c in new.children],
        'index_text_sha256': [sha(c['index_text'].encode()) for c in new.children], 'vectors': vectors,
        'model_id': new.embedding_profile.model_id, 'model_revision': new.embedding_profile.model_revision,
        'source_text_unchanged': True, 'predecessor_fingerprint': old.fingerprint,
        'predecessor_file_sha256': sha(pred.read_bytes())}
    new.load_vectors(manifest)
    context = RetrievalContext(AuthorizedScope('HUCE', 'HUCE', 'actor', frozenset({'STUDENT'}),
        frozenset({'STUDENT'}), frozenset({'PUBLIC'}), frozenset({'PUBLIC'})), 'vi', datetime.now(UTC), SimulationPolicy.DENY, '1'*32)
    retained = [*old.rows, *old.legacy_rows]
    added = [r for r in new.rows if r['version_label'] == f'reviewed-corrections-20261021-v{args.version}']
    release_data = read(PUB / f'reviewed-corrections-20261021-v{args.version}.json')
    assert len(added) == len(release_data['chunks']), 'every reviewed chunk must be admitted exactly once'
    for row in [*retained, *added]:
        result = await new.read(row['source_id'], row['document_version_id'], row['chunk_id'], context=context)
        assert result and result.content_text == row['content_text']
    if existing_manifest is None: save(target, manifest)
    else:
        assert existing_manifest['vectors'] == manifest['vectors']
        assert existing_manifest['index_text_sha256'] == manifest['index_text_sha256']
    receipt = {'version': args.version, 'index': rel(target), 'fingerprint': new.fingerprint,
        'parent_chunks': len(new.rows), 'vectors': len(vectors), 'reused': reused, 'resumed': resumed,
        'new_inferences_this_successful_attempt': len(vectors)-reused-resumed,
        'retained_citations_byte_checked': len(retained), 'new_chunks_byte_checked': len(added),
        'history_rows': len(new.legacy_rows), 'semantic_completeness_not_inferred_from_readback': True}
    event('indexed', receipt); print(json.dumps(receipt))
    release = checked(PUB / f'reviewed-corrections-20261021-v{args.version}.json')
    marker = checked(PUB / f'reviewed-corrections-20261021-v{args.version}.ready.json')
    marker_data = {'release_sha256': sha(release.read_bytes()), 'index_sha256': sha(target.read_bytes()),
                   'index': rel(target), 'fingerprint': new.fingerprint}
    if marker.exists(): assert read(marker) == marker_data
    else: save(marker, marker_data)


def source_status_counts(catalog, completed, reviewed):
    states={d['identity_key']:d['completion_status'] for d in catalog['documents']}
    for did in reviewed:
        assert 'drive:'+did in states
        states['drive:'+did]='complete' if did in completed else 'incomplete'
    return dict(Counter(states.values()))


def checkpoint(args):
    reviews = latest_reviews(); queue = items()
    priorities=sorted([*BASE.glob('it-priority-*.json'),*BASE.glob('it-common-priority-*.json')],key=lambda f:read(f).get('at',''))
    priority_file=priorities[-1] if priorities else None
    priority=read(priority_file) if priority_file else {}
    indexed = {}
    folder = checked(BASE / 'events')
    if folder.exists():
        for file in sorted(folder.glob('*-indexed.json')):
            e = read(file)
            marker = checked(PUB/f"reviewed-corrections-20261021-v{e['version']}.ready.json")
            if not marker.exists(): continue
            receipt = read(marker)
            assert sha(checked(ROOT/receipt['index']).read_bytes())==receipt['index_sha256']
            assert sha(checked(PUB/f"reviewed-corrections-20261021-v{e['version']}.json").read_bytes())==receipt['release_sha256']
            indexed[e['version']] = e
    admitted = {}
    for version, receipt in indexed.items():
        release = read(PUB / f'reviewed-corrections-20261021-v{version}.json')
        for record in release['pipeline_coverage']: admitted[record['drive_id']] = record
    complete = [did for did, record in admitted.items() if record['complete_eligible_after_index']
                and did in reviews and not reviews[did][1]['source_issues']
                and read(ROOT/record['review_file'])['review_dossier']==reviews[did][1]['review_dossier']]
    checked_ids = set(reviews)
    remaining = [i for i in queue if i['drive_id'] not in checked_ids]
    catalog = read(CATALOG)
    counts = source_status_counts(catalog,set(complete),set(reviews))
    assert sum(counts.values()) == catalog['units']['source_identity_candidates']
    data = {'baseline_catalog': rel(CATALOG), 'baseline_queue': rel(QUEUE),
        'source_identity_candidates': catalog['units']['source_identity_candidates'],
        'source_status_counts': counts, 'intellectual_document_count': None,
        'curriculum': {'downloaded': 91, 'complete': 2 + len(complete),
            'visually_checked_but_incomplete': 5 + len(checked_ids) - len(complete), 'not_rechecked': len(remaining)},
        'new_reviewed_documents': [{'drive_id': did, 'review': rel(path), 'source_issues': d['source_issues'],
            'acquisition_status':'downloaded_original_hash_verified','extraction_status':d['extraction_status'],
            'verification_status':d['verification_status'],'normalization_status':d['normalization_status'],
            'indexing_status':'indexed' if did in admitted else 'prepared_not_indexed',
            'completion_status':'complete' if did in complete else 'incomplete',
            'index_coverage': admitted.get(did)} for did, (path, d) in reviews.items()],
        'full_pages_newly_checked':sum(len(d['page_evidence']) for path,d in reviews.values()),
        'content_ready_but_not_complete_until_index':[did for did,(path,d) in reviews.items() if not d['source_issues'] and did not in complete],
        'latest_index': list(indexed.values())[-1] if indexed else None,
        'baseline_index_receipt': 'data/huce-discovery-20261020/reconciliation-20261021-v3/index-receipt-v7.json',
        'baseline_index_still_active_unless_runtime_verified': True,
        'prepared_documents': sum((cache_path(i)/'manifest.json').exists() for i in queue),
        'source_urls_in_catalog': len({url for d in catalog['documents'] for url in d['urls']}),
        'legacy_five_source_followups_still_open': ['1CoFsdOzqixs2B5srF8bFE8mvg3lw1llE','1Y7H3dKHxQYqFNH9niIBZkAVpbPWRA47d',
            '1nL31OteEeU7ZkRwIxwjrgP_hJO3MK6Ux','1elVn8XX32jXyYo5eoHfznQ9PFLh01FmF','1hu58jGFk5Ue0gekWY-9WA-1wFnX7WklU'],
        'remaining_unreviewed_pdfs': remaining,
        'next': (next((item for did in priority.get('next_curriculum_drive_ids',[])
                      for item in remaining if item['drive_id']==did),None)
                 if priority_file else remaining[0] if remaining else None),
        'next_unprioritized_queue_item':remaining[0] if remaining else None,
        'non_curriculum_index_coverage':[r for r in admitted.values() if r.get('kind') in {'calendar_cntt_rows','reviewed_public_document'}],
        'active_priority_manifest':rel(priority_file) if priority_file else None,
        'next_priority':priority.get('next_priority')}
    assert sum(data['curriculum'][k] for k in ['complete','visually_checked_but_incomplete','not_rechecked']) == 91
    path = event('checkpoint', data)
    print(json.dumps({'checkpoint': rel(path), **{k:data[k] for k in ['curriculum','source_status_counts','next']}}, ensure_ascii=False))


def verify(args):
    """Verify retained real documents and admission rejection paths; no fake source truth."""
    import copy
    event('preflight', preflight())
    pages = 0
    for item in items():
        assert sha(checked(ROOT/item['source_file']).read_bytes()) == item['sha256']
        manifest = read(cache_path(item)/'manifest.json')
        assert len(manifest['pages']) == item['page_count']
        for page in manifest['pages']:
            assert sha(checked(ROOT/page['data']).read_bytes()) == page['data_sha256']
            assert sha(checked(ROOT/page['image']).read_bytes()) == page['image_sha256']
            pages += 1
    reviews = latest_reviews()
    for did, (path, record) in reviews.items():
        item = next(i for i in items() if i['drive_id']==did)
        actual = normalize(item, record['review_dossier'])
        # Earlier immutable records predate added PDFium fields; compare their recorded content, never rewrite.
        assert actual['courses'] == record['courses']
        assert actual['relations'] == record['relations']
        assert actual['source_issues'] == record['source_issues']
    csqt = reviews['1FTAgZv9sYoccmY3l-yoFLoKlx0KsaCUS'][1]
    item = next(i for i in items() if i['drive_id']==csqt['drive_id'])
    rejected = []
    for case in ('missing_page','wrong_image','wrong_payload','incomplete_cells','unresolved_extraction'):
        dossier = copy.deepcopy(csqt['review_dossier'])
        if case=='missing_page': dossier['pages']=[]
        if case=='wrong_image': dossier['pages'][0]['image_sha256']='0'*64
        if case=='wrong_payload': dossier['source_sha256']='0'*64
        if case=='incomplete_cells': dossier['completion_attestation']['all_cells_checked']=False
        if case=='unresolved_extraction': dossier['extraction_errors']=['missing course cell']
        try: normalize(item,dossier)
        except AssertionError: rejected.append(case)
        else: raise AssertionError('invalid dossier admitted: '+case)
    sys.path[:0]=[str(ROOT),str(ROOT/'services/api/src')]
    from scripts.public_rag_retrieval import create_public_hybrid_store, public_hybrid_index_path
    kwargs=dict(tenant_id='HUCE',campus_id='HUCE',faq_directory=ROOT/'data/huce-faq-20261013')
    available_versions=sorted(int(m[1]) for f in PUB.glob('reviewed-corrections-20261021-v*.json')
        if (m:=re.fullmatch(r'reviewed-corrections-20261021-v(\d+)\.json',f.name)) and int(m[1])>=8 and not f.with_suffix('.withdrawn.json').exists())
    ready_versions=[v for v in available_versions if (PUB/f'reviewed-corrections-20261021-v{v}.ready.json').exists()]
    baseline=create_public_hybrid_store(PUB,reviewed_corrections_version=max([7,*ready_versions]),**kwargs)
    active=create_public_hybrid_store(PUB,**kwargs)
    assert active.fingerprint==baseline.fingerprint, 'only indexed releases may activate'
    baseline.load_vectors(read(public_hybrid_index_path(baseline)))
    releases=[]
    rejected_candidates=[]
    for marker in PUB.glob('reviewed-corrections-20261021-v*.withdrawn.json'):
        version=int(re.search(r'-v(\d+)\.withdrawn\.json$',marker.name)[1])
        source=marker.with_name(marker.name.replace('.withdrawn.json','.json'))
        assert sha(source.read_bytes())==read(marker)['release_sha256']
        try:create_public_hybrid_store(PUB,reviewed_corrections_version=version,**kwargs)
        except ValueError:rejected_candidates.append(version)
        else:raise AssertionError('withdrawn candidate admitted')
    for version in available_versions:
        candidate=create_public_hybrid_store(PUB,reviewed_corrections_version=version,**kwargs)
        predecessor_version=max([7,*[v for v in ready_versions if v < version]])
        predecessor=create_public_hybrid_store(PUB,reviewed_corrections_version=predecessor_version,**kwargs)
        release=read(PUB/f'reviewed-corrections-20261021-v{version}.json')
        for coverage in release['pipeline_coverage']:
            if coverage.get('kind')=='calendar_cntt_rows':
                from huce_calendar_pipeline import validate_release
                validate_release(release,coverage)
            elif coverage.get('kind')=='reviewed_public_document':
                from huce_public_document_pipeline import validate_release
                validate_release(release,coverage)
            elif coverage.get('kind')=='reviewed_common_source_slices':
                from huce_common_source_slices import validate_release
                validate_release(release,coverage)
        added=[r for r in candidate.rows if r['version_label']==f'reviewed-corrections-20261021-v{version}']
        assert len(added)==len(release['chunks'])
        for chunk in release['chunks']:
            assert chunk['cohort']==chunk['applicability'].get('cohort')
            assert chunk['degree_level']==chunk['applicability'].get('degree')
            assert chunk['academic_year']==chunk['applicability'].get('academic_year')
            record=next(read(ROOT/r['review_file']) for r in release['pipeline_coverage'] if r['drive_id'] in chunk['download_url'])
            expected_total=record['review_dossier'].get('printed_totals_by_page',{}).get(str(chunk['page']),record.get('printed_total'))
            assert chunk['total_credits']==expected_total
            assert chunk['legal_effective_from']==record['legal_effective_from']
        citation_key=lambda r:(r['source_id'],r['document_version_id'],r['chunk_id'],r['content_text'])
        inherited={citation_key(r) for r in (*predecessor.rows,*predecessor.legacy_rows)}
        retained={citation_key(r) for r in (*candidate.rows,*candidate.legacy_rows)}
        assert inherited <= retained, f'predecessor citations lost in release {version}'
        if version in ready_versions:
            assert retained <= {citation_key(r) for r in (*active.rows,*active.legacy_rows)}, 'active index lost a historical ready citation'
        releases.append({'version':version,'reviewed_chunks_loaded':len(added),
                         'predecessor_version':predecessor_version,'retained_predecessor_citations':len(inherited),
                         'index_state':'indexed_ready' if version in ready_versions else 'not_built_not_active'})
    receipt={'verified_original_pdfs':len(items()),'verified_page_pairs':pages,'reviewed_documents_reconciled':len(reviews),
             'rejected_invalid_dossiers':rejected,'baseline_fingerprint':baseline.fingerprint,
             'baseline_vectors':len(baseline.vectors),'pending_releases':releases,
             'withdrawn_unindexed_candidates_rejected':sorted(rejected_candidates),
             'limitation':'Coverage, original hashes and admission checks; not evidence of unanswered source questions being resolved or semantic answer accuracy.'}
    event('verification',receipt);print(json.dumps(receipt))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare'); p.add_argument('--ids', nargs='+'); p.add_argument('--limit', type=int)
    p = sub.add_parser('review'); group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--dossier'); group.add_argument('--decisions')
    p = sub.add_parser('ocr'); p.add_argument('--ids', nargs='+'); p.add_argument('--node', required=True); p.add_argument('--node-package-root', required=True)
    p.add_argument('--include-embedded', action='store_true', help='OCR image diagrams even when native headers or footers are present')
    p = sub.add_parser('raster-candidates'); p.add_argument('--ids', nargs='+'); p.add_argument('--node', required=True); p.add_argument('--node-package-root', required=True)
    p.add_argument('--top-fraction',type=float);p.add_argument('--bottom-fraction',type=float)
    p.add_argument('--supplement',help='Reviewed additional box coordinates bound to one source SHA')
    p = sub.add_parser('spatial'); p.add_argument('--ids', nargs='+')
    p = sub.add_parser('repair-regions'); p.add_argument('--ids', nargs='+')
    p = sub.add_parser('publish'); p.add_argument('--version', type=int, required=True); p.add_argument('--ids', nargs='+')
    p = sub.add_parser('index'); p.add_argument('--version', type=int, required=True); p.add_argument('--predecessor', type=int, required=True)
    sub.add_parser('checkpoint')
    sub.add_parser('verify')
    args = parser.parse_args()
    if args.command == 'index':
        try: asyncio.run(build(args))
        except Exception as exc:
            event('index-failure', {'version': args.version, 'error_type': type(exc).__name__,
                                   'reason': str(exc), 'successful_vectors_retained': True})
            raise
    else:
        from huce_raster_curriculum import raster_candidates
        {'prepare': prepare, 'spatial': spatial,'repair-regions':repair_regions, 'ocr': ocr,
         'raster-candidates':raster_candidates, 'review': review, 'publish': publish,
         'checkpoint': checkpoint,'verify':verify}[args.command](args)


if __name__ == '__main__': main()
