"""Correct a cross-page elective-cell locator without overwriting the release."""
import hashlib,json
from datetime import UTC,datetime
from huce_source_registry import ROOT,save

def main():
    pub=ROOT/'data/huce-public-20261013'
    old=json.loads((pub/'reviewed-corrections-20261021-v3.json').read_text(encoding='utf-8'))
    c=next(c for c in old['chunks'] if c.get('page')==2 and c['source_sha256']=='e8f2155a406da323787c04abaf292bf2c98ae0d6d014e793eb42e9702efe65d7')
    c=dict(c);prior=c['text_sha256'];now=datetime.now(UTC).isoformat()
    c.update(page_end=3,section='Kiến trúc phiên bản 2025 — trang 2 và phần ô tự chọn tiếp nối trang 3',
        text=c['text']+'\nĐịnh vị: ô Chuyên đề chuyên ngành (tự chọn), kỳ 8, bắt đầu ở trang 2 và tiếp tục các mã 331673, 341617, 351643 trên trang 3.',
        visual_evidence=['data/huce-discovery-20261020/reconciliation-20261021-v3/architecture-2.png',
                         'data/huce-discovery-20261020/reconciliation-20261021-v3/architecture-3.png'],
        replaces_excerpt_text_sha256=prior,collected_at=now,effective_from=now)
    c['text_sha256']=hashlib.sha256(c['text'].encode()).hexdigest()
    save(pub/'reviewed-corrections-20261021-v7.json',{'public_only':True,'acquired_at':now,
        'version_label':'reviewed-corrections-20261021-v7','verification':'source_verified_excerpts','chunks':[c]})

if __name__=='__main__':main()
