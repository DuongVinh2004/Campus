"""Nine batch checks: expected source + requested evidence, separate from readback."""
import asyncio,hashlib,json,sys
from datetime import UTC,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'services/api/src')]
from scripts.public_rag_retrieval import load_public_hybrid_store
from scripts.huce_source_registry import save
from campus247.domain.retrieval import AuthorizedScope,RetrievalContext,SimulationPolicy

async def main():
    store=load_public_hybrid_store(ROOT/'data/huce-public-20261013',tenant_id='HUCE',campus_id='HUCE',faq_directory=ROOT/'data/huce-faq-20261013')
    context=RetrievalContext(AuthorizedScope('HUCE','HUCE','actor',frozenset({'STUDENT'}),frozenset({'STUDENT'}),
        frozenset({'PUBLIC'}),frozenset({'PUBLIC'})),'vi',datetime.now(UTC),SimulationPolicy.DENY,'1'*32)
    pub=ROOT/'data/huce-public-20261013'
    v3=json.loads((pub/'reviewed-corrections-20261021-v3.json').read_text(encoding='utf-8'))['chunks']
    cases=[('IELTS 5.0–5.5 được quy đổi bao nhiêu điểm Anh ngữ theo bài đăng ngày 19/10/2026?',v3[0]['source_sha256'],'9 – 10'),
        ('Học bổng STEM Quỹ Châu Á 2025-2026 yêu cầu kết quả học tập mấy học kỳ và TOEIC bao nhiêu?',v3[1]['source_sha256'],'450 TOEIC'),
        ('Chuẩn đầu ra PLO7 ngành Kiến trúc phiên bản 2025 nói gì về giao tiếp?',v3[-1]['source_sha256'],'PLO7'),
        ('Ngành Công nghệ đa phương tiện 71CNDPT học kỳ 6 có học phần 531831 và 531832 nào?', 'a445ba9bf610097033a8663a218792ff457cacebe90a4a08f555be779ebf9bae','531831'),
        ('Công nghệ phần mềm 71PM học kỳ 7 có học phần 477717 là gì?', 'fa9950a9f6bad5fb1c53ace794c995803f99b8b56a12a5bd09846dfe132a6f22','477717'),
        ('Mạng máy tính 71MHT học kỳ 8 nhóm tự chọn 1 ghi bao nhiêu tín chỉ và có mâu thuẫn gì?', 'e352a3231ec7304657008abf6a2e8acda2afa59a4b20e0cbfdd6c0b066091c6c','467713'),
        ('Khoa học máy tính 71CS học kỳ 8 học phần 607713 là gì?', '1678a05abdcf5e77f96aa3d13ab574a5012d619ebfa5aaf762dace12caa002e6','607713'),
        ('An toàn thông tin 71IS mã 462112 có những tên học phần nào trong học kỳ 7?', '10ac12b05b8abbdc22f417c97aa169555d34425735c07b31f1e99981a2dbc5ec','462112'),
        ('Khoa học dữ liệu 71DS học kỳ 6 học phần 941722 là gì?', 'ee6b257184cec7526b6fa0a500f3c43c0ac920492d50116ba833c2ea476fd24c','941722')]
    results=[]
    for question,sha,marker in cases:
        result={'question':question,'expected_source_sha256':sha,'expected_marker':marker}
        try:
            rows=await store.search(question,context)
            items=[]
            for row in rows:
                read=await store.read(row['source_id'],row['document_version_id'],row['chunk_id'],context=context)
                items.append({'title':row['title'],'section':row['section_path'],'source_sha256':row.get('provenance',{}).get('source_sha256'),
                    'content_text':row['content_text'],'readback_ok':bool(read and read.content_text==row['content_text'] and hashlib.sha256(read.content_text.encode()).hexdigest()==read.content_sha256)})
            result.update(rows=items,expected_evidence_in_top1=bool(items and items[0]['source_sha256']==sha and marker in items[0]['content_text']),
                expected_evidence_retrieved=any(i['source_sha256']==sha and marker in i['content_text'] for i in items))
        except Exception as exc:
            result.update(error_type=type(exc).__name__,expected_evidence_retrieved=False,expected_evidence_in_top1=False)
        results.append(result)
        print(json.dumps({k:v for k,v in result.items() if k!='rows'},ensure_ascii=False),flush=True)
    save(ROOT/'data/huce-discovery-20261020/reconciliation-20261021-v3/retrieval-probe-v6.json',
        {'fingerprint':store.fingerprint,'queries':len(cases),'expected_evidence_top1':sum(r['expected_evidence_in_top1'] for r in results),
         'expected_evidence_retrieved':sum(r['expected_evidence_retrieved'] for r in results),'cases':results,
         'limitation':'Batch source retrieval and readback, not generated answer accuracy or whole-corpus completeness.'})

if __name__=='__main__':asyncio.run(main())
