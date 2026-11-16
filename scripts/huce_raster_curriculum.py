"""Spatial OCR candidates for raster and hybrid curriculum diagrams.

Connected filled interiors propose boxes only. Reviewers must assign semester,
source text, units, colour meaning and relations from the original page.
"""
from pathlib import Path
import json
import subprocess
import re


def normalize_reviewed_cells(item, dossier, manifest):
    """Bind every reviewed transcription to an original box and retained OCR."""
    import huce_document_pipeline as p
    candidates_path=p.checked(p.ROOT/dossier['raster_candidate_file']) if dossier.get('raster_candidate_file') else p.cache_path(item)/'raster-cells-v1.json'
    candidates=p.read(candidates_path)
    assert candidates['source_sha256']==item['sha256']
    courses,regions,evidence,groups=[],[],[],[]
    ocr={}
    for path in sorted((p.BASE/'ocr'/item['drive_id']).glob('page-*.json')):
        value=p.read(path)
        if value.get('cell_id'):
            assert value['source_sha256']==item['sha256']
            ocr[(value['cell_id'],value['image_sha256'])]=(path,value)
    for page in candidates['pages']:
        number=page['page'];spec=dossier['raster_pages'][str(number)]
        ref=next(r for r in manifest['pages'] if r['page']==number)
        assert page['image_sha256']==ref['image_sha256']==p.sha((p.ROOT/ref['image']).read_bytes())
        cells={c['cell_id']:c for c in page['cells']}
        headers=spec['semester_headers'];ignored=spec['ignored_cells'];transcriptions=spec['cell_transcriptions']
        assert set(headers).isdisjoint(ignored) and set(headers).isdisjoint(transcriptions) and set(ignored).isdisjoint(transcriptions)
        assert set(cells)==set(headers)|set(ignored)|set(transcriptions), 'every raster proposal needs a reviewed disposition'
        assert sorted(headers.values())==list(range(1,10))
        assert all(reason.strip() for reason in ignored.values())
        for cell_id,transcription in transcriptions.items():
            cell=cells[cell_id];path,raw=ocr[(cell_id,cell['crop_sha256'])]
            assert raw['image_sha256']==cell['crop_sha256']==p.sha((p.ROOT/cell['crop']).read_bytes())
            assert raw['original_page_image_sha256']==ref['image_sha256']
            x0,y0,x1,y1=cell['source_bbox_pixels'];cx=(x0+x1)/2
            nearest=min(headers,key=lambda k:abs(sum(cells[k]['source_bbox_pixels'][::2])/2-cx))
            semester=headers[nearest]
            box=[x0/page['image_width']*page['pdf_width'],y0/page['image_height']*page['pdf_height'],
                 x1/page['image_width']*page['pdf_width'],y1/page['image_height']*page['pdf_height']]
            locator={'page':number,'bbox':box,'image':ref['image'],'cell_id':cell_id,
                     'crop':cell['crop'],'crop_sha256':cell['crop_sha256'],'ocr':p.rel(path),'ocr_sha256':p.sha(path.read_bytes())}
            language=dossier['languages_by_page'][str(number)]
            block=dossier.get('color_legend',{}).get(json.dumps(cell['fill_rgb']))
            match=p.CODE.match(transcription)
            slot=spec.get('elective_slot_cells',{}).get(cell_id)
            if slot is not None:
                assert match is None
                credit=re.search(r'\((\d+)\s*(?:TC|Credits)\)',transcription)
                assert credit, 'slot must retain explicit printed credits'
                code=None;credits=int(credit[1]);name=transcription
            else:
                assert match and match[2], f'reviewed code and credits required: {cell_id}'
                code=match[1];credits=int(match[2]);name=transcription[match.end():].strip()
                assert name
            courses.append({'occurrence_id':f"{item['drive_id']}:{cell_id}",'semester':semester,
                'code':code,'credits':credits,'credit_unit':'TC','name_verbatim':name,'language':language,
                'knowledge_block':block,'requirement':'elective_slot' if slot else None,
                'elective_group':f"{language}:required-elective-{slot}" if slot else None,
                'locators':[locator],'ocr_verbatim':raw['text'],'reviewed_transcription':transcription})
        raw_page=p.read(p.ROOT/ref['data'])
        table=raw_page['tables'][spec['elective_table_index']]
        assert len(table['rows'])==3 and len(table['rows'][0]['values'])==7
        for column in range(1,7):
            head=table['rows'][0]['values'][column]
            credits=re.search(r'\((\d+)\s*(?:TC|Credits)\)',head)
            assert credits
            group_id=f"{language}:required-elective-{column}"
            slots=[c for c in courses if c['language']==language and c['elective_group']==group_id]
            assert len(slots)==1 and slots[0]['credits']==int(credits[1])
            option_ids=[]
            for row_number,row in enumerate(table['rows'][1:],1):
                text=row['values'][column]
                match=re.fullmatch(r'\s*([0-9xX.]{2,9})\s*[–−-]\s*(.+)',text,re.S)
                assert match
                occurrence=f"{item['drive_id']}:p{number}:elective-{column}:option-{row_number}"
                courses.append({'occurrence_id':occurrence,'semester':slots[0]['semester'],'code':match[1],
                    'credits':int(credits[1]),'credit_unit':'TC','name_verbatim':match[2].strip(),'language':language,
                    'knowledge_block':slots[0]['knowledge_block'],'requirement':'elective','elective_group':group_id,
                    'credit_source':'explicit elective-column header: '+head,
                    'locators':[{'page':number,'bbox':row['cells'][column],'image':ref['image']}],
                    'native_table_text':text})
                option_ids.append(occurrence)
            groups.append({'group_id':group_id,'page':number,'semester':slots[0]['semester'],
                           'printed_credits':int(credits[1]),'rule_verbatim':head,'option_occurrences':option_ids})
        for semester in range(1,10):
            selected=[c for c in courses if c.get('language')==language and c['semester']==semester]
            if not selected:continue
            boxes=[c['locators'][0]['bbox'] for c in selected]
            # Option tables occupy a separate page region; keep all coordinates
            # and repeat only exact, reviewed source text in the semester unit.
            text='\n\n'.join(c.get('reviewed_transcription') or
                f"{c['code']} – {c['credits']}\n{c['name_verbatim']}\n[TC theo header nhóm: {c['credit_source']}]" for c in selected)
            regions.append({'page':number,'semester':semester,'language':language,'image':ref['image'],
                'bbox':[min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)],
                'text':text,'source_basis':'visually reviewed raster cells plus exact native elective table; OCR and original retained'})
        evidence.append({'page':number,'candidate_file':p.rel(candidates_path),'candidate_sha256':p.sha(candidates_path.read_bytes()),
                         'reviewed_cells':len(transcriptions),'headers':len(headers),'ignored_cells':ignored,
                         'native_elective_options':12,'all_candidate_dispositions_verified':True})
    return courses,regions,evidence,groups


def normalize_instruction_cells(item,dossier,manifest):
    """Preserve printed X/Y instruction quantities without credit conversion."""
    import huce_document_pipeline as p
    import numpy as np
    from PIL import Image
    path=p.checked(p.ROOT/dossier['raster_candidate_file']);candidate=p.read(path)
    assert candidate['source_sha256']==item['sha256']
    ocr={}
    for file in sorted((p.BASE/'ocr'/item['drive_id']).glob('page-*.json')):
        value=p.read(file)
        if value.get('cell_id') and value['source_sha256']==item['sha256']:
            ocr[(value['cell_id'],value['image_sha256'])]=(file,value)
    courses,regions,evidence,groups=[],[],[],[]
    for page in candidate['pages']:
        number=page['page'];spec=dossier['raster_pages'][str(number)]
        ref=next(r for r in manifest['pages'] if r['page']==number)
        assert page['image_sha256']==ref['image_sha256']==p.sha((p.ROOT/ref['image']).read_bytes())
        language=dossier['languages_by_page'][str(number)]
        headers=spec['semester_header_geometry'];ignored=spec['ignored_cells']
        assert sorted(h['semester'] for h in headers)==list(range(1,10)) and spec['reviewed_order_basis'].strip()
        legend=spec['unit_legend']
        assert legend['format']=='Code-X-Y' and legend['X_label_verbatim'].strip() and legend['Y_label_verbatim'].strip()
        assert legend['quantity_kind']=='instruction_time' and legend['unit_verbatim'].strip().lower() not in {'tc','credit','credits'}, 'instruction quantities cannot be labelled as credits'
        for h in headers:
            b=h['bbox_pixels'];assert 0<=b[0]<b[2]<=page['image_width'] and 0<=b[1]<b[3]<=page['image_height']
            assert h['transcription'].strip()
        assert set(ignored)<=set(c['cell_id'] for c in page['cells']) and all(v.strip() for v in ignored.values())
        assigned={n:[] for n in range(1,10)}
        for cell in page['cells']:
            if cell['cell_id'] in ignored:continue
            cx=sum(cell['source_bbox_pixels'][::2])/2
            header=min(headers,key=lambda h:abs(sum(h['bbox_pixels'][::2])/2-cx))
            assigned[header['semester']].append(cell)
        rendered=Image.open(p.ROOT/ref['image']).convert('RGB')
        reviewed_count=0
        for semester,cells in assigned.items():
            cells.sort(key=lambda c:c['source_bbox_pixels'][1])
            entries=spec['semester_transcriptions'][str(semester)]
            assert len(entries)==len(cells), f'all source boxes need an entry in page{number},semester{semester}: {len(entries)} vs{len(cells)}'
            region_text=[];boxes=[]
            for cell,entry in zip(cells,entries,strict=True):
                cid=cell['cell_id'];crop=p.checked(p.ROOT/cell['crop']);ocr_path,raw=ocr[(cid,cell['crop_sha256'])]
                assert p.sha(crop.read_bytes())==cell['crop_sha256']==raw['image_sha256']
                assert raw['original_page_image_sha256']==ref['image_sha256']
                x0,y0,x1,y1=cell['source_bbox_pixels']
                box=[x0/page['image_width']*page['pdf_width'],y0/page['image_height']*page['pdf_height'],
                     x1/page['image_width']*page['pdf_width'],y1/page['image_height']*page['pdf_height']]
                boxes.append(box)
                locator={'page':number,'bbox':box,'image':ref['image'],'cell_id':cid,'crop':cell['crop'],
                         'crop_sha256':cell['crop_sha256'],'ocr':p.rel(ocr_path),'ocr_sha256':p.sha(ocr_path.read_bytes())}
                rgb=np.median(np.array(rendered.crop(cell['source_bbox_pixels'])).reshape(-1,3),axis=0)
                colour=min(dossier['reviewed_color_legend'],key=lambda c:max(abs(np.array(c['rgb'])-rgb)))
                assert max(abs(np.array(colour['rgb'])-rgb))<=30, f'unreviewed box colour: {cid}'
                block=colour['label'] if colour['role']=='knowledge_block' else None
                options=entry['options'] if isinstance(entry,dict) and 'options' in entry else [entry]
                group_id=f"{language}:source-elective-{entry['group_number']}" if isinstance(entry,dict) and 'options' in entry else None
                if group_id:
                    assert colour['role']=='elective' and entry['caption'].strip()
                    region_text.append(entry['caption'])
                occurrences=[]
                for option,text in enumerate(options,1):
                    noncredit=isinstance(text,dict) and text.get('mode')=='noncredit'
                    transcription=text['text'] if noncredit else text
                    if noncredit:
                        assert colour['role']=='noncredit'
                        match=re.fullmatch(r'([0-9xX.]{2,9})\s*[–−-]\s*(\d+)\s*\n(.+)',transcription,re.S)
                        assert match
                        code=match[1];name=match[3].strip();quantities=None;annotation=int(match[2])
                    else:
                        match=re.fullmatch(r'([0-9xX.]{2,9})\s*[–−-]\s*(\d+)\s*[–−-]\s*(\d+)\s*\n(.+)',transcription,re.S)
                        assert match, f'code-X-Y and original title required: {cid}'
                        assert colour['role']!='noncredit', 'non-credit annotation cannot be interpreted as instruction hours'
                        code=match[1];name=match[4].strip();annotation=None
                        quantities={'X':int(match[2]),'Y':int(match[3]),'unit_verbatim':legend['unit_verbatim'],
                                    'X_label_verbatim':legend['X_label_verbatim'],'Y_label_verbatim':legend['Y_label_verbatim']}
                    assert name
                    occurrence=f"{item['drive_id']}:{cid}:o{option}"
                    courses.append({'occurrence_id':occurrence,'semester':semester,'language':language,'code':code,
                        'name_verbatim':name,'credits':None,'credit_unit':None,'credit_annotation':None,
                        'instruction_quantities':quantities,'printed_noncredit_numeric_annotation':annotation,
                        'knowledge_block':block,'requirement':'excluded_from_total' if noncredit else 'elective' if group_id else None,
                        'elective_group':group_id,'locators':[locator],'ocr_verbatim':raw['text'],
                        'reviewed_transcription':transcription,'source_unit_basis':legend})
                    occurrences.append(occurrence);region_text.append(transcription)
                if group_id:
                    groups.append({'group_id':group_id,'page':number,'semester':semester,'rule_verbatim':entry['caption'],
                                   'printed_credits':None,'choice_count':None,'option_occurrences':occurrences})
                reviewed_count+=1
            header=next(h for h in headers if h['semester']==semester)
            text=header['transcription']+'\n'+legend['verbatim']+'\n\n'+'\n\n'.join(region_text)
            regions.append({'page':number,'semester':semester,'language':language,'image':ref['image'],'text':text,
                'bbox':[min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)],
                'source_basis':'original code-X-Y instruction quantities; no conversion to credits; all reviewed source boxes retained'})
        rendered.close()
        assert reviewed_count+len(ignored)==len(page['cells'])
        evidence.append({'page':number,'candidate_file':p.rel(path),'candidate_sha256':p.sha(path.read_bytes()),
                         'reviewed_cells':reviewed_count,'headers':len(headers),'ignored_cells':ignored,
                         'all_candidate_dispositions_verified':True,'credit_conversion_performed':False})
    return courses,regions,evidence,groups


def raster_candidates(args):
    import huce_document_pipeline as p
    import numpy as np
    from scipy import ndimage
    from PIL import Image, ImageOps
    top=getattr(args,'top_fraction',None)
    bottom=getattr(args,'bottom_fraction',None)
    supplement_path=getattr(args,'supplement',None)
    supplement=p.read(p.ROOT/supplement_path) if supplement_path else None
    custom=top is not None or bottom is not None or supplement is not None
    top=.10 if top is None else top
    bottom=.83 if bottom is None else bottom
    assert 0<=top<bottom<=1
    if custom:
        import importlib.metadata
        configuration={'detector':'connected-fill-interiors-v2','top_fraction':top,'bottom_fraction':bottom,
                       'libraries':{k:importlib.metadata.version(k) for k in ('Pillow','numpy','scipy')}}
        if supplement is not None:
            configuration.update(detector='connected-fill-interiors-v3-reviewed-supplement',
                                 supplement_sha256=p.sha((p.ROOT/supplement_path).read_bytes()))
        suffix='v2-'+p.sha(json.dumps(configuration,sort_keys=True).encode())[:16]
    else:
        configuration={'detector':'connected-fill-interiors-v1','top_fraction':top,'bottom_fraction':bottom}
        suffix='v1'
    p.event('preflight', p.preflight())
    for item in p.items():
        if args.ids and item['drive_id'] not in args.ids:
            continue
        cache = p.cache_path(item)
        if supplement is not None:assert supplement['source_sha256']==item['sha256']
        manifest = p.read(cache/'manifest.json')
        dest = p.checked(cache/f'raster-cells-{suffix}.json')
        crop_dir = p.checked(cache/f'raster-crops-{suffix}')
        crop_dir.mkdir(exist_ok=True)
        if dest.exists():
            candidate = p.read(dest)
            assert candidate['source_sha256']==item['sha256']
            if custom:assert candidate['configuration']==configuration
            for page in candidate['pages']:
                assert p.sha((p.ROOT/page['image']).read_bytes())==page['image_sha256']
                for cell in page['cells']:
                    assert p.sha((p.ROOT/cell['crop']).read_bytes())==cell['crop_sha256']
        else:
            assert p.sha((p.ROOT/item['source_file']).read_bytes())==item['sha256']
            pages=[]
            for ref in manifest['pages']:
                assert p.sha((p.ROOT/ref['image']).read_bytes())==ref['image_sha256']
                with Image.open(p.ROOT/ref['image']) as original:
                    original=original.convert('RGB')
                    pixels=np.array(original).astype(np.int16)
                    hi,lo=pixels.max(axis=2),pixels.min(axis=2)
                    masks=[('colour',(hi-lo>30)&(hi>175)),
                           ('white',(lo>242)&(hi-lo<12))]
                    cells=[]
                    for fill,mask in masks:
                        labels,_=ndimage.label(mask)
                        sizes=np.bincount(labels.ravel())
                        for label,slices in enumerate(ndimage.find_objects(labels),1):
                            if slices is None or sizes[label]<500:
                                continue
                            ys,xs=slices; x0,x1=xs.start,xs.stop; y0,y1=ys.start,ys.stop
                            w,h=x1-x0,y1-y0
                            if not (60<w<original.width/4 and 36<h<original.height/4
                                    and y0>original.height*top and y1<original.height*bottom
                                    and sizes[label]/(w*h)>.55):
                                continue
                            box=[max(0,x0-3),max(0,y0-3),min(original.width,x1+3),min(original.height,y1+3)]
                            colour=np.median(pixels[ys,xs][labels[ys,xs]==label],axis=0).astype(int).tolist()
                            cells.append({'source_bbox_pixels':box,'fill_rgb':colour,'proposal_kind':fill})
                    if supplement is not None:
                        for entry in supplement['pages'][str(ref['page'])]:
                            box=entry['bbox_pixels'];assert len(box)==4 and entry['source_basis'].strip()
                            assert 0<=box[0]<box[2]<=original.width and 0<=box[1]<box[3]<=original.height
                            cx,cy=(box[0]+box[2])/2,(box[1]+box[3])/2
                            assert not any(c['source_bbox_pixels'][0]<=cx<=c['source_bbox_pixels'][2] and
                                           c['source_bbox_pixels'][1]<=cy<=c['source_bbox_pixels'][3] for c in cells), 'supplement overlaps an existing candidate'
                            cells.append({'source_bbox_pixels':box,'fill_rgb':entry.get('fill_rgb'),
                                          'proposal_kind':'reviewed_supplement','source_basis':entry['source_basis']})
                    cells.sort(key=lambda c:(round(c['source_bbox_pixels'][0]/12),c['source_bbox_pixels'][1]))
                    for n,cell in enumerate(cells,1):
                        cell_id=f"p{ref['page']}-c{n:03d}"
                        path=p.checked(crop_dir/f'{cell_id}.png')
                        crop=original.crop(cell['source_bbox_pixels'])
                        crop=ImageOps.expand(crop.resize((crop.width*2,crop.height*2)),border=18,fill='white')
                        # Stable proposals can resume after a partially written batch.
                        import io
                        buffer=io.BytesIO();crop.save(buffer,format='PNG');payload=buffer.getvalue()
                        if path.exists():
                            assert path.read_bytes()==payload
                        else:
                            with path.open('xb') as stream:stream.write(payload)
                        cell.update(cell_id=cell_id,crop=p.rel(path),crop_sha256=p.sha(payload))
                    raw=p.read(p.ROOT/ref['data'])
                    pages.append({'page':ref['page'],'image':ref['image'],'image_sha256':ref['image_sha256'],
                                  'image_width':original.width,'image_height':original.height,
                                  'pdf_width':raw['width'],'pdf_height':raw['height'],'cells':cells})
            candidate={'source_sha256':item['sha256'],'detector':'connected-fill-interiors-v1',
                       'configuration':configuration,'status':'unreviewed; boxes and OCR are not course or semester assertions','pages':pages}
            p.save(dest,candidate)
        jobs=[]
        for page in candidate['pages']:
            for cell in page['cells']:
                jobs.append({'page':page['page'],'cell_id':cell['cell_id'],'image':cell['crop'],
                    'image_sha256':cell['crop_sha256'],'source_bbox_pixels':cell['source_bbox_pixels'],
                    'original_page_image':page['image'],'original_page_image_sha256':page['image_sha256'],
                    'drive_id':item['drive_id'],'source_file':item['source_file'],'source_sha256':item['sha256']})
        output=p.checked(p.BASE/'ocr'/item['drive_id']);output.mkdir(parents=True,exist_ok=True)
        job=p.event('raster-ocr-jobs',{'pages':jobs,'node_package_root':args.node_package_root,
            'language_directory':str(p.ROOT/'data/huce-public-20261013'),'output_directory':str(output),
            'parameters':{'tessedit_pageseg_mode':'6'},'candidate_file':p.rel(dest)})
        result=subprocess.run([args.node,str(p.ROOT/'scripts/huce_document_ocr.mjs'),str(job)],
                              cwd=p.ROOT,capture_output=True,text=True,encoding='utf-8')
        receipt=p.event('raster-ocr-result',{'drive_id':item['drive_id'],'exit_code':result.returncode,
            'stdout':result.stdout,'stderr':result.stderr,'candidate_file':p.rel(dest),
            'candidate_cells':len(jobs),'admitted':False})
        print(json.dumps({'drive_id':item['drive_id'],'candidate_cells':len(jobs),'receipt':p.rel(receipt)}),flush=True)
        assert result.returncode==0, 'per-cell OCR failed; original and partial evidence retained'
