"""Retain geometry candidates for the new FIT calendar, without RAG admission."""
import pdfplumber
from huce_document_pipeline import ROOT, BASE, checked, event, preflight, rel, save, sha


def main():
    event('preflight',preflight())
    digest='f2abfee5c2ad39b20ddbbebf8e751a1dd42185e784ea41e4a105ee27e48b1b23'
    source=checked(ROOT/'data/huce-discovery-20261020/objects'/digest)
    assert sha(source.read_bytes())==digest
    with pdfplumber.open(source) as pdf:
        assert len(pdf.pages)==1
        page=pdf.pages[0];table=page.find_tables()[0];values=table.extract()
        assert len(table.columns)==55
        assert values[1][3:]==values[85][3:]==[str(n) for n in range(1,53)]
        cohorts=[{'row_index':n,'label_verbatim':r[0],'bbox':table.rows[n].cells[0]}
                 for n,r in enumerate(values) if r[0] and r[0].startswith(('K67','K68','K69','K70','K71'))]
        selected=[]
        for number,row in enumerate(values):
            if row[1]!='Công nghệ thông tin':continue
            bounds=table.rows[number].cells[1];cy=(bounds[1]+bounds[3])/2
            scope=[c for c in cohorts if c['bbox'][1]<=cy<=c['bbox'][3]]
            assert len(scope)==1
            selected.append({'row_index':number,'cohort_candidate':scope[0],
                'values_verbatim':row,'cell_bboxes':table.rows[number].cells,
                'week_header_row':1 if number<84 else 85,
                'status':'native_geometry_candidate_not_yet_all_cells_visually_reconciled'})
        assert len(selected)==4
        result={'source_file':rel(source),'source_sha256':digest,'page':1,
            'dimensions':[page.width,page.height],'table_bbox':table.bbox,
            'rows':[{'row_index':n,'values_verbatim':v,'cell_bboxes':r.cells}
                    for n,(r,v) in enumerate(zip(table.rows,values,strict=True))],
            'cntt_row_candidates':selected,'admission':'not_admitted',
            'limitation':'Source colours, merged cells, notes, provisional scope and every week require visual reconciliation; native extraction alone does not establish a study schedule.'}
    target=checked(BASE/'attachments/1Zu1VbkLNmQicqlzVEYUIbnfgCk9iKlW9'/digest/'native-calendar-table-candidates-v1.json')
    save(target,result)
    event('it-calendar-geometry',{'evidence':rel(target),'source_sha256':digest,'all_table_rows':len(values),'cntt_rows':len(selected),'rag_admitted':False})
    print({'evidence':rel(target),'cntt_scope_labels':[r['cohort_candidate']['label_verbatim'] for r in selected]})


if __name__=='__main__':main()
