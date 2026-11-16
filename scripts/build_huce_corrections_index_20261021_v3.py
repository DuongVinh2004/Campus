"""Append-only real embedding index; verify predecessor and every historical row."""
import asyncio
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT),str(ROOT/'services/api/src')]
from scripts.huce_source_registry import checked, save
from scripts.public_rag_retrieval import create_public_hybrid_store, public_hybrid_index_path
from campus247.ports.embedding import validate_embedding_vector

async def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version',type=int,choices=(3,4,6,7),default=3)
    version=parser.parse_args().version
    kwargs=dict(tenant_id='HUCE',campus_id='HUCE',faq_directory=ROOT/'data/huce-faq-20261013')
    old=create_public_hybrid_store(ROOT/'data/huce-public-20261013',include_reviewed_corrections=version>3,
        reviewed_corrections_version={3:3,4:3,6:4,7:6}[version],**kwargs)
    new=create_public_hybrid_store(ROOT/'data/huce-public-20261013',reviewed_corrections_version=version,**kwargs)
    pred=checked(public_hybrid_index_path(old)); before=json.loads(pred.read_text(encoding='utf-8'))
    old.load_vectors(before)
    assert old.embedding_profile==new.embedding_profile
    hashes=[hashlib.sha256(c['index_text'].encode()).hexdigest() for c in old.children]
    assert hashes==before['index_text_sha256']
    lookup={(c['id'],h):v for c,h,v in zip(old.children,hashes,old.vectors,strict=True)}
    target=checked(public_hybrid_index_path(new))
    if target.exists():
        new.load_vectors(json.loads(target.read_text(encoding='utf-8')))
        print('Validated existing',target);return
    vectors=[]; reused=0; cached=0
    cache=checked(ROOT/'data/huce-discovery-20261020/reconciliation-20261021-v3'/f'embedding-cache-{new.fingerprint}')
    cache.mkdir(exist_ok=True)
    for c in new.children:
        key=c['id'],hashlib.sha256(c['index_text'].encode()).hexdigest()
        if key in lookup:
            vectors.append(list(lookup[key]));reused+=1
        else:
            cache_file=checked(cache/f'{key[0]}-{key[1]}.json')
            if cache_file.exists():
                record=json.loads(cache_file.read_text(encoding='utf-8'))
                assert record['child_id']==key[0] and record['text_sha256']==key[1]
                value=validate_embedding_vector(record['values'],new.embedding_profile,
                    model_id=record['model_id'],model_revision=record['model_revision'])
                cached+=1
            else:
                emb=await new.embed_query(c['index_text'])
                value=validate_embedding_vector(emb.values,new.embedding_profile,
                    model_id=emb.model_id,model_revision=emb.model_revision)
                save(cache_file,{'child_id':key[0],'text_sha256':key[1],'values':list(value.values),
                    'model_id':emb.model_id,'model_revision':emb.model_revision})
            vectors.append(list(value.values))
            if (len(vectors)-reused)%10==0:
                print(json.dumps({'new_children_ready':len(vectors)-reused,'cached':cached}),flush=True)
    manifest={'fingerprint':new.fingerprint,'child_ids':[c['id'] for c in new.children],
        'index_text_sha256':[hashlib.sha256(c['index_text'].encode()).hexdigest() for c in new.children],
        'vectors':vectors,'model_id':new.embedding_profile.model_id,'model_revision':new.embedding_profile.model_revision,
        'contextual_index':'trusted_title_section_and_source_bound_question_aliases','source_text_unchanged':True,
        'predecessor_fingerprint':old.fingerprint,'predecessor_file_sha256':hashlib.sha256(pred.read_bytes()).hexdigest(),
        'reused_hash_verified_children':reused,'new_real_embeddings':len(vectors)-reused,
        'resumed_hash_verified_embeddings':cached}
    new.load_vectors(manifest)
    # Verify exact bytes and identifiers for ALL retained predecessor citations without inference calls.
    from datetime import UTC,datetime
    from campus247.domain.retrieval import AuthorizedScope,RetrievalContext,SimulationPolicy
    context=RetrievalContext(AuthorizedScope('HUCE','HUCE','actor',frozenset({'STUDENT'}),
        frozenset({'STUDENT'}),frozenset({'PUBLIC'}),frozenset({'PUBLIC'})),
        'vi',datetime.now(UTC),SimulationPolicy.DENY,'1'*32)
    for row in (*old.rows,*old.legacy_rows):
        result=await new.read(row['source_id'],row['document_version_id'],row['chunk_id'],context=context)
        assert result and result.content_text==row['content_text']
    corrected=[r for r in new.rows if r['version_label']==f'reviewed-corrections-20261021-v{version}']
    for row in corrected:
        result=await new.read(row['source_id'],row['document_version_id'],row['chunk_id'],context=context)
        assert result and result.content_text==row['content_text']
    save(target,manifest)
    receipt={k:v for k,v in manifest.items() if k not in {'vectors','child_ids','index_text_sha256'}}
    receipt.update(parent_chunks=len(new.rows),child_vectors=len(new.children),
        predecessor_citations_byte_checked=len(old.rows)+len(old.legacy_rows),corrected_chunks_byte_checked=len(corrected),
        history_rows=len(new.legacy_rows),path=str(target),document_completion_not_inferred=True)
    receipt_name='index-receipt.json' if version==3 else f'index-receipt-v{version}.json'
    save(ROOT/'data/huce-discovery-20261020/reconciliation-20261021-v3'/receipt_name,receipt)
    print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__':asyncio.run(main())
