"""Native grid candidates for the next five PDFs; no automatic review claims."""
import hashlib
import json
import subprocess
import pdfplumber
from huce_source_registry import ROOT,checked,save

def main():
    data=json.loads((ROOT/'data/huce-discovery-20261020/curricula-processed-20261021/all_91_curricula.json').read_text(encoding='utf-8'))
    out=checked(ROOT/'data/huce-discovery-20261020/reconciliation-20261021-v3/batch-next')
    out.mkdir(exist_ok=False)
    for index in [11,12,13,15,16]:
        item=data['items'][index]; source=checked(ROOT/item['source_file'])
        assert hashlib.sha256(source.read_bytes()).hexdigest()==item['source_sha256']
        dest=checked(out/item['drive_id']);dest.mkdir(exist_ok=False)
        pages=[]
        with pdfplumber.open(source) as pdf:
            for i,page in enumerate(pdf.pages,1):
                tables=[{'bbox':t.bbox,'rows':[{'cells':r.cells,'values':v} for r,v in zip(t.rows,t.extract(),strict=True)]} for t in page.find_tables()]
                pages.append({'page':i,'width':page.width,'height':page.height,'text':page.extract_text(),
                              'words':page.extract_words(),'tables':tables,'lines':page.lines,'curves':page.curves})
        save(dest/'native-grid-unreviewed.json',{'drive_id':item['drive_id'],'source_file':item['source_file'],
            'source_sha256':item['source_sha256'],'pages':pages,'review_status':'not_reviewed','index_status':'not_admitted'})
        subprocess.run(['pdftoppm','-scale-to','2300','-png',str(source),str(checked(dest/'page'))],check=True)
        print(index,item['drive_id'],len(pages),len(pages[0]['tables']),flush=True)

if __name__=='__main__':main()
