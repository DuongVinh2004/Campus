"""Bind the primary agent's seven-page CNTT diagram review to source evidence."""
import copy
import re
import huce_document_pipeline as p


IDS=['1YZntIejfEoVA8o_cLn0aACsy5ovMtgb9','1hybvz33Pz06TvlQsRL0iQjLrqEwwrB5Q',
     '1UmX4sEMjVqYZCyEiyfCTcp5LYVGsZ_iT','1LEFI1LGfP_HtTkz2EdxNbyj_KYBnojAL','1FI121taIrmgIOxS_slRCx5RuZ0fDP2wZ']


def relation(kind,a,sa,b,sb,page=1):
    return dict(type=kind,from_code=a,from_semester=sa,to_code=b,to_semester=sb,from_page=page,to_page=page,
                legend_page=page,arrow_page=page,trace_note='Original diagram and enlarged upper/lower image crops inspected; source cell, line, arrowhead and same-page legend traced separately.')


def main():
    p.event('preflight',p.preflight());docs=[]
    titles=['Kế hoạch giảng dạy chương trình đào tạo trình độ kỹ sư ngành Khoa học máy tính – đào tạo bằng tiếng Anh, hợp tác với ĐH Mississippi',
        'Kế hoạch giảng dạy chương trình đào tạo trình độ kỹ sư ngành Khoa học máy tính — hai trang: áp dụng cho khóa69 và từkhóa70',
        'Kế hoạch giảng dạy CTĐT trình độ cử nhân ngành Công nghệ thông tin/chuyên ngành Công nghệ đa phương tiện',
        'Kế hoạch giảng dạy CTĐT ngành Công nghệ thông tin — chuyên ngành An toàn thông tin — Hệ đào tạo: Đại học – B7 (Kỹ sư)',
        'Kế hoạch giảng dạy CTĐT trình độ cử nhân ngành Khoa học dữ liệu']
    semtotals=[[20,20,23,22,21,21,19,18,18],[17,20,22,21,23,24,19,18,18],[13,22,23,22,21,16,10],
               [17,19,22,20,21,23,21,19,18],[16,20,21,22,22,19,10]]
    programmes=['Khoa học máy tính — tiếng Anh, hợp tác ĐH Mississippi','Khoa học máy tính','Công nghệ thông tin — Công nghệ đa phương tiện','Công nghệ thông tin — An toàn thông tin','Khoa học dữ liệu']
    for n,did in enumerate(IDS):
        item=next(i for i in p.items() if i['drive_id']==did);manifest=p.read(p.cache_path(item)/'manifest.json')
        d={'drive_id':did,'source_sha256':item['sha256'],'title':titles[n],
            'applicability':{'cohort':None,'programme':programmes[n],'degree':'Cử nhân' if n in [2,4] else 'Kỹ sư','academic_year':None},
            'pages':[{'page':pg['page'],'image_sha256':pg['image_sha256'],'content_checked':True,
                      'notes':'Full original page image and all native semester columns checked; enlarged crops used for arrows and notes. Exact page-specific scope retained.' if not(n==0 and pg['page']==2) else 'Original second page is visually blank; native text and shapes must remain empty, not treated as a missing scan.'} for pg in manifest['pages']],
            'reviewer':'Codex primary agent; all seven original images inspected and all native columns compared; long arrows separately read in enlarged crops',
            'printed_total':[182,180,None,180,130][n],'printed_semester_totals':semtotals[n],
            'preserve_coded_name_codes':['4801xx','48011x','48xxxx','430120'],
            'trim_reviewed_non_course_labels':True,'source_issues':[], 'extraction_errors':[],
            'relations_checked':True,'automatic_warnings_reviewed':True,'relations':[],'uncoded_entries':[]}
        if n==3:d['applicability']['system']='Đại học – B7'
        if n!=1:d['source_issues'].append({'kind':'scope_not_printed','detail':'Bản PDF không in khóa/năm học; giữ cohort và academic_year=null, không suy khóa từ nhãn khám phá.'})
        d['source_issues'].append({'kind':'source_placeholder_code','detail':[
            'Giữ mãxx…của ba chuyên đềCS,4801xxcủaGDQP và các mã7729116/7729117bảy chữ số đúng bản in; không tự cấp mã thay thế.',
            'Cả hai trang in4801xxchoGDQP, chưa có mã đầy đủ; không tự điền.',
            'Các học phần tiếng AnhCB3,CB4,NC cùng in4402xxvàGDQP4801xx; giữ tên/kỳ riêng, không gộp theo mã placeholder.',
            'GDQP in48011x. Hai môn dùng462112và hai môn dùng428802với tên khác nhau; giữ từng lần xuất hiện đúng bản in, chưa có đính chính mã.',
            'GDQP in48xxxx; chưa có mã đầy đủ, giữ nguyên.'][n]})
        if n!=2:
            d['exclusion_verbatim']='Tổng: '+str(d['printed_total'])+(' TC (không tính HP Giáo dục thể chất và Giáo dục quốc phòng)' if n==3 else 'TC (Không tính HP giáo dục thể chất, Giáo dục quốc phòng)')
            d['excluded_codes']=['4801xx','48011x','48xxxx']
        else:
            d['exclusion_verbatim']='GD thể chất 1,2,3 vàGiáo dục quốc phòng cóôriêng; bản này không in tổngtoànchươngtrình hoặcchúthíchloạitrừtổng.'
            d['source_issues'].append({'kind':'unreconciled_printed_totals','detail':'Không in tổngtoànchươngtrình. Giữ dãy tổngkỳ13,22,23,22,21,16,10; tín chỉ trong các ô và tổngkỳkhônghoàntoànkhớp. Không tự suy thành130TC hoặc sửa số tín chỉ cho khớp.'})
            d['source_issues'].append({'kind':'unprinted_choice_count','detail':'Hai nhómTỰ CHỌN1(2TC)/2(2TC) in ngân sách2TC mỗi nhóm vàhai phươngán2TC; không in riêngsốhọcphầnphảichọn. Giữ ngân sách vàtoànbộphươngán, không dùng sốthứtựnhóm làmchoose-count.'})
        if n==1:
            d['page_titles']={str(pg):'Kế hoạch giảng dạy kỹ sư ngành Khoa học máy tính — '+scope for pg,scope in [(1,'ÁP DỤNG CHO KHÓA69'),(2,'ÁP DỤNG TỪ KHÓA70')]}
            d['page_applicability']={'1':d['applicability']|{'cohort':'K69'},'2':d['applicability']|{'cohort_min':70}}
            d['source_issues'].append({'kind':'conditional_credit_totals','detail':'Tổng in180TC, dãy tổngkỳcộng182TC; chúthíchyêucầuhọcmộttronghaihọcphầnAnhCB1*/NC*. Giữcả2ôvàđiềukiện, khôngcoi182làtổngbắtbuộchoặcsửatổngin180.'})
        if n==3:
            d['source_issues'].append({'kind':'missing_elective_catalog','detail':'Hai nhóm tự chọnkỳ8in2phươngánmỗinhóm nhưngkhônginchoose-count/tổngTCnhóm; chúgiảidẫn danh mục tự chọnkhôngcótrongPDF1trang. Khôngsuychọncảhaihoặcmộttừtổngkỳ19.'})
            d['source_issues'].append({'kind':'ambiguous_english_star_scope','detail':'ChúthíchghiHọcmộttronghaihọcphầntheophânloại,nhưngdấusaoởtênCB1,CB4,NC(cả3ô). Giữnguyêncả3dấuvàđiềukiện;chưaxácđịnhđượccặphọcphầntừbảnin,khôngtựxóadấusaoCB4.'})
            d['elective_groups']=[{'page':1,'semester':8,'group_id':'ATTT-B7-choice'+str(k),'rule_verbatim':'Tự chọn '+str(k)+':',
                                  'choice_count':None,'printed_credits':None,'option_codes':codes} for k,codes in [(1,['462117','462118']),(2,['462119','462120'])]]
        if n==2:
            d['elective_groups']=[{'page':1,'semester':sem,'group_id':'Multimedia-choice'+str(k),'rule_verbatim':'TỰ CHỌN '+str(k)+' (2TC)',
                                  'choice_count':None,'printed_credits':2,'option_codes':codes} for k,sem,codes in [(1,5,['531833','531834']),(2,6,['531835','531836'])]]
        for pg in manifest['pages']:
            raw=p.read(p.ROOT/pg['data'])
            for region in raw['semester_regions']:
                for line in region['text'].splitlines():
                    if re.fullmatch(r'(?:GD (?:thể|Thế|Thể) chất \d\*?|Giáo dục TC\d)',line):
                        # Coded PE1 in Multimedia is already represented by430120.
                        if n==2 and line=='GD thể chất 1':continue
                        entry={'page':pg['page'],'semester':region['semester'],'name_verbatim':line,
                            'credits':None,'credit_unit':'TC','requirement':'excluded_from_total' if n!=2 else 'source_no_total_exclusion_rule'}
                        if n==0 and line.endswith('*'):
                            entry['condition_verbatim']='Nếu sinh viên đi học giai đoạn 2 tại Mỹ sẽ không phải học các môn này'
                        d['uncoded_entries'].append(entry)
        if n==0:
            d.update(allow_ellipsis_codes=True,allow_spaced_credit_marker=True)
            d['credit_annotation_conditions']={'*':'Nếu sinh viên đi học giai đoạn 2 tại Mỹ sẽ không phải học các môn này'}
            for sem,code,pattern in [(3,'Writ 101',r'–\s*(?P<credits>\d+)\s*TC'),(4,'Writ 102',r'TC:\s*(?P<credits>\d+)')]:
                region=next(r for r in p.read(p.ROOT/manifest['pages'][0]['data'])['semester_regions'] if r['semester']==sem)
                start=region['text'].index(code);end=region['text'].index('478801' if sem==3 else '408809')
                name=region['text'][start:end].strip()
                d['uncoded_entries'].append({'page':1,'semester':sem,'name_verbatim':name,'external_code':code,'credits':3,'credit_unit':'TC','credit_pattern':pattern,'requirement':None,'source_basis':'Named WRIT external course, literal3TC in same yellow cell; not a numeric HUCE course code.'})
            d['source_issues'].append({'kind':'conditional_us_stage_scope','detail':'Dấusaoápdụngmiễnhọcnếusinhviênđihọcgiaiđoạn2tạiMỹ;giữđiềukiệnchoPhápluật,KTCT,CNXH,IELTS440218vàbaôGDTC;khôngcoilàmiễnchomọisinhviên.'})
        if n==1:d['credit_annotation_conditions']={'*':'Học một trong hai học phần phụ thuộc kết quả phân loại tiếng Anh đầu vào;'}
        if n==3:
            d['reviewed_course_conditions']=[{'page':1,'semester':sem,'code':code,'source_marker':'*','condition_verbatim':'Học một trong hai học phần phụ thuộc kết quả phân loại tiếng Anh đầu vào;',
                'source_basis':'Dấu*trongtênôvàchúthíchcùngtrang;baôcódấusaođượcgiữ,tínhmơhồcặphọcphầnđượcghiởsource_issues.'} for sem,code in [(1,'448803'),(4,'448808'),(5,'440218')]]
        pairs={
        0:{'prerequisite':[('362401',2,'Writ 101',3),('Writ 101',3,'Writ 102',4),('Writ 102',4,'448808',5),('448808',5,'440218',6),('440218',6,'461751',7),('538801',1,'608804',2),('608804',2,'478801',3),('608803',2,'608825',4),('608825',4,'608807',5),('608807',5,'607704',7),('608818',6,'607706',8)],
           'concurrent':[('258811',1,'258803',1),('258812',2,'258804',2),('408809',4,'408810',4),('478803',4,'478804',4),('608809',5,'608810',5),('478805',5,'478807',5),('608814',6,'608815',6),('608818',6,'608819',6),('7729116',7,'7729117',7),('607704',7,'607705',7),('607706',8,'607707',8)]},
        1:{'prerequisite':[('428801',2,'428802',3),('448803',2,'448804',3),('448804',3,'448807',4),('448807',4,'448808',5),('398803',2,'408801',3),('538801',1,'608804',2),('608804',2,'478801',3),('608803',2,'608825',4),('608825',4,'608807',5),('608820',6,'607702',7),('608818',6,'607706',8),('608816',6,'607704',7)],
           'concurrent':[('258811',1,'258803',1),('258812',2,'258804',2),('478803',4,'478804',4),('608809',5,'608810',5),('478805',5,'478807',5),('608818',6,'608819',6),('608814',6,'608815',6),('607702',7,'607703',7),('607706',8,'607707',8)]},
        2:{},
        3:{'prerequisite':[('428801',2,'428802',3),('448803',1,'448804',2),('448804',2,'448807',3),('448807',3,'448808',4),('448808',4,'440218',5),('401712',4,'461716',5),('461716',5,'462105',6),('472101',3,'462102',5),('250101',1,'250102',2),('390121',1,'396602',2),('396602',2,'400101',2),('531702',4,'462121',6),('461730',4,'471733',5),('461706',3,'461785',6),('450101',1,'461727',2),('461727',2,'478801',3),('471732',4,'462108',6)],
           'concurrent':[('471756',3,'471757',3),('461730',4,'461731',4),('471733',5,'471734',5),('461785',6,'462109',6),('467705',7,'467704',7),('462113',8,'462114',8)]},
        4:{'prerequisite':[('428801',1,'428802',2),('440211',1,'440212',2),('440212',2,'448807',3),('448807',3,'448808',4),('401704',2,'941705',3),('390121',1,'396602',2),('941714',5,'941715',6),('941723',4,'941712',5),('941712',5,'941721',6),('941713',5,'941722',6),('471706',2,'941706',3),('471706',2,'471813',4),('941707',3,'941708',4),('471754',2,'471755',3),('461706',2,'941710',4)],
           'concurrent':[('941708',4,'941709',4)]}}
        for page in ([1,2] if n==1 else [1]):
            for kind,values in pairs[n].items():d['relations'] += [relation(kind,*v,page=page) for v in values]
        docs.append(d)
    # Derive only extraction-name repairs; keep every pre-repair string and the
    # exact hand-reviewed replacement. Validation still checks both native engines.
    for d in docs:
        if d['drive_id']==IDS[0]:
            item=next(i for i in p.items() if i['drive_id']==IDS[0])
            raw=p.read(p.ROOT/p.read(p.cache_path(item)/'manifest.json')['pages'][0]['data'])
            d['course_name_repairs']=[]
            for sem,code,correct in [(3,'428802','Kinh tế chính trị Mac –\nLê Nin'),(4,'428803','Chủ nghĩa xã hội\nkhoa học')]:
                text=next(r['text'] for r in raw['semester_regions'] if r['semester']==sem)
                # Embedded WRIT cell follows this code before the next numeric course.
                start=text.index('\n',text.index(code))+1;end=text.index('478801' if sem==3 else '408809')
                d['course_name_repairs'].append({'page':1,'semester':sem,'code':code,'extracted_name_verbatim':text[start:end].strip(),
                    'source_name_verbatim':correct,'visual_and_native_basis':'Separate yellow WRIT cell retained as its own external course; remove only that cell from preceding political-course name.'})
    for d in docs:
        item=next(i for i in p.items() if i['drive_id']==d['drive_id']);record=p.normalize(item,d)
        print({'id':d['drive_id'],'courses':len(record['courses']),'relations':len(record['relations']),'warnings':record['automatic_warnings']},flush=True)
    target=p.BASE/'review-dossiers-it-related-20261022-50.json';p.save(target,{'documents':docs})
    print({'dossier':p.rel(target),'documents':len(docs)})


if __name__=='__main__':main()
