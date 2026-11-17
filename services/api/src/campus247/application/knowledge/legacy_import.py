"""Stage verified legacy inputs/vectors as unapproved versions, never activate them."""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict
from pydantic import ValidationError

from campus247.application.knowledge.platform_models import (
    EMBED_ARTIFACT, EMBED_MODEL, EMBED_REVISION, IntakeMetadata, PlatformError, digest,
)
from campus247.application.retrieval.profile import load_retrieval_profile
from campus247.domain.shared.values import generate_uuid7
from campus247.application.knowledge.values import stable_id, normalized

LEGACY_PROCESSOR = "legacy-public-structure-v1:exact-title-section-alias-inputs"


async def stage_legacy(platform, actor, corpus, references, *, legacy_index_sha256, embedding_artifact_sha256):
    """references maps parent ordinal to an independently verified original snapshot.

    The caller must have used the existing exact-fingerprint vector loader. The
    new index retains each input SHA256 and original parent context separately.
    Unknown legal dates remain unknown, and no legacy marker becomes a review.
    """
    platform.admin(actor)
    if (corpus.vectors is None or len(corpus.vectors) != len(corpus.children)
        or embedding_artifact_sha256 != EMBED_ARTIFACT
        or (corpus.embedding_profile.model_id,corpus.embedding_profile.model_revision,
            corpus.embedding_profile.dimension,corpus.embedding_profile.normalization) != (EMBED_MODEL,EMBED_REVISION,1024,"l2")):
        raise ValueError("Exact validated legacy vectors required")
    repo, storage = platform.repo, platform.storage
    groups, skipped = defaultdict(list), []
    for ordinal, child in enumerate(corpus.children):
        parent = corpus.rows[child["parent"]]
        reference = references.get(child["parent"])
        if not reference:
            skipped.append({"child_id":child["id"],"reason":"ORIGINAL_MAPPING_UNVERIFIED"})
            continue
        if len(parent["content_text"]) > 20_000:
            skipped.append({"child_id":child["id"],"reason":"PARENT_CONTEXT_LIMIT"})
            continue
        key = (parent["document_version_id"],reference["sha256"],reference["download_url"])
        groups[key].append((ordinal,child,parent,reference))
    results, blobs = [], {}
    source_labels = {}
    for entries in groups.values():
        parent, ref = entries[0][2:]
        source_labels.setdefault(ref["download_url"], (parent["title"],parent["issuer"]))
    for entries in groups.values():
        parent, reference = entries[0][2:]
        canonical_uri = reference["download_url"]
        group_hash = digest({"original":reference["sha256"], "processor":LEGACY_PROCESSOR,
            "model":EMBED_MODEL,"revision":EMBED_REVISION,"dimension":1024,"normalization":"l2",
            "children":[(c["id"],digest(c["index_text"].encode()),p["quote_span_hash"]) for _,c,p,_ in entries]})
        version_id = stable_id(repo.tenant + ":legacy-version:" + parent["document_version_id"] + ":" + group_hash)
        source_id = stable_id(repo.tenant + ":legacy-source:" + canonical_uri)
        async with repo.pool.acquire() as conn:
            if await conn.fetchval("SELECT EXISTS(SELECT 1 FROM knowledge_ingest_version WHERE version_id=$1 AND tenant_id=$2)",version_id,repo.tenant):
                results.append({"version_id":version_id,"state":"REUSED_EXISTING","chunks":len(entries)})
                continue
        title, issuer = source_labels[canonical_uri]
        try:
            metadata = IntakeMetadata(title=title,owner_unit=issuer,canonical_uri=canonical_uri,
                programs=["PUBLIC"],audiences=["STUDENT","KNOWLEDGE_ADMIN","SYSTEM_ADMIN"],
                effective_from=None,effective_until=None)
            if reference["sha256"] not in blobs:
                with reference["path"].open("rb") as source:
                    prefix = source.read(8)
                media = "application/pdf" if prefix.startswith(b"%PDF-") else reference.get("media_type","application/octet-stream")
                blobs[reference["sha256"]] = storage.copy_original(reference["path"],reference["sha256"],media)
            original = blobs[reference["sha256"]]
            unique_parents = {p["chunk_id"]:p for _,_,p,_ in entries}
            rendition = {"processor":LEGACY_PROCESSOR,"legacy_index_sha256":legacy_index_sha256,
                "original_sha256":original.sha256,"legacy_corpus_fingerprint":corpus.fingerprint,
                "original_mapping": reference.get("provenance", {}),
                "issues":[{"code":"LEGACY_REVIEW_AND_APPLICABILITY_REQUIRED","page":None}],
                "pages":[{"page":p["page_start"],"page_end":p["page_end"],"text":p["content_text"],
                    "section":p["section_path"],"legacy_chunk_id":p["chunk_id"],"source_uri":p["canonical_uri"],
                    "legacy_provenance":p.get("provenance")} for p in unique_parents.values()]}
            rendition_blob = storage.write_json(json.dumps(rendition,ensure_ascii=False,sort_keys=True).encode(),"legacy_extraction")
            async with repo.transaction() as conn:
                await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1,0))",repo.tenant+":legacy:"+canonical_uri)
                if await conn.fetchval("SELECT EXISTS(SELECT 1 FROM knowledge_ingest_version WHERE version_id=$1 AND tenant_id=$2)",version_id,repo.tenant):
                    results.append({"version_id":version_id,"state":"REUSED_EXISTING","chunks":len(entries)})
                    continue
                existing = await conn.fetchrow("""SELECT s.*,x.tenant_id FROM knowledge_source s
                    LEFT JOIN knowledge_source_scope x ON x.source_id=s.id WHERE canonical_uri=$1""",canonical_uri)
                if existing:
                    if existing["tenant_id"] != repo.tenant:
                        raise PlatformError(409,"SOURCE_URI_CONFLICT","Không thể hợp nhất nguồn ngoài tenant.")
                    source_id = str(existing["id"])
                    if (existing["title"],existing["owner_unit"]) != (title,issuer):
                        raise PlatformError(409,"SOURCE_METADATA_CONFLICT","Metadata nguồn đã có khác bản nhập; giữ nguyên để đối chiếu.")
                else:
                    await conn.execute("""INSERT INTO knowledge_source
                        (id,source_type,canonical_uri,title,owner_unit,authority_level,approval_status,is_synthetic,
                         campus_scope,faculty_scope,program_scope,audiences)
                        VALUES ($1,'OFFICIAL_DOCUMENT',$2,$3,$4,50,'DRAFT',false,'HUCE',ARRAY['FIT']::varchar[],
                                ARRAY['PUBLIC']::varchar[],ARRAY['KNOWLEDGE_ADMIN','STUDENT','SYSTEM_ADMIN']::varchar[])""",
                        source_id,canonical_uri,title,issuer)
                    await conn.execute("INSERT INTO knowledge_source_scope(source_id,tenant_id,created_by) VALUES ($1,$2,$3)",source_id,repo.tenant,actor.subject_id)
                if not await conn.fetchval("SELECT EXISTS(SELECT 1 FROM knowledge_artifact WHERE id=$1)",original.id):
                    await repo.artifact(conn,original)
                await repo.artifact(conn,rendition_blob)
                await conn.execute("""INSERT INTO document_version
                    (id,knowledge_source_id,version_label,content_checksum,status,storage_object_key)
                    VALUES ($1,$2,$3,$4,'DRAFT',$5)""",version_id,source_id,"legacy-"+version_id,original.sha256,original.object_key)
                await conn.execute("""INSERT INTO knowledge_ingest_version
                    (version_id,tenant_id,original_id,filename,created_by,metadata_sha256,processor_profile,
                     rendition_id,rendition_sha256,review_state)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,'NEEDS_REVIEW')""",version_id,repo.tenant,original.id,
                    reference["path"].name,actor.subject_id,digest(metadata.model_dump(mode="json",exclude={"source_id"})),
                    LEGACY_PROCESSOR,rendition_blob.id,rendition_blob.sha256)
                for ordinal,(vector_index,child,evidence,_) in enumerate(entries):
                    chunk_id = stable_id(version_id+":"+child["id"])
                    values = corpus.vectors[vector_index]
                    literal = "["+",".join(str(v) for v in values)+"]"
                    await conn.execute("""INSERT INTO knowledge_chunk
                        (id,document_version_id,ordinal,section_path,page_start,page_end,content_text,content_checksum,content_tsv,
                         embedding_rag_v1,embedding_model_version,embedding_dimension,embedded_at)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,to_tsvector('simple',$9),$10::vector(1024),$11,1024,clock_timestamp())""",
                        chunk_id,version_id,ordinal,evidence["section_path"],evidence["page_start"],evidence["page_end"],
                        evidence["content_text"],digest(evidence["content_text"].encode()),
                        normalized(child["index_text"]),
                        literal,EMBED_MODEL+"@"+EMBED_REVISION)
                    await conn.execute("""INSERT INTO knowledge_chunk_input
                        (chunk_id,index_text,input_sha256,processor_profile,provenance) VALUES ($1,$2,$3,$4,$5::jsonb)""",
                        chunk_id,child["index_text"],digest(child["index_text"].encode()),LEGACY_PROCESSOR,json.dumps({
                            "legacy_child_id":child["id"],"legacy_parent_id":evidence["chunk_id"],
                            "indexed_char_start":child["start"],"indexed_char_end":child["end"],
                            "original_sha256":original.sha256,"legacy_index_sha256":legacy_index_sha256,
                            "corpus_fingerprint":corpus.fingerprint,"legacy_review_is_new_approval":False,
                            "original_mapping":reference.get("provenance", {})}))
                profile = asdict(load_retrieval_profile())
                fields = list(profile)
                await conn.execute("INSERT INTO retrieval_profile("+",".join(fields)+",created_at,approved_at,approval_reference) VALUES ("+
                    ",".join("$"+str(i+1) for i in range(len(fields)))+",clock_timestamp(),clock_timestamp(),'KNOWLEDGE_PLATFORM_LOCAL_20261023') ON CONFLICT DO NOTHING",*profile.values())
                index_id = "legacy-"+version_id
                await conn.execute("""INSERT INTO embedding_index_manifest
                    (index_version,profile_version,embedding_model_id,embedding_model_revision,artifact_sha256,dimension,normalization,
                     distance_metric,corpus_version,document_count,chunk_count,content_checksum,build_status,built_at,validated_at)
                    VALUES ($1,$2,$3,$4,$5,1024,'l2','cosine',$6,1,$7,$8,'READY',clock_timestamp(),clock_timestamp())""",
                    index_id,profile["profile_version"],EMBED_MODEL,EMBED_REVISION,EMBED_ARTIFACT,original.sha256,len(entries),group_hash)
                await conn.execute("UPDATE document_version SET index_version=$2 WHERE id=$1",version_id,index_id)
                job_id=generate_uuid7()
                await conn.execute("""INSERT INTO knowledge_ingestion_job(id,tenant_id,version_id,state,stage,progress)
                    VALUES ($1,$2,$3,'SUCCEEDED','IMPORTED_REVIEW',100)""",job_id,repo.tenant,version_id)
                await repo.save_step(conn,{"id":job_id},"LEGACY_IMPORT",original.sha256,digest(LEGACY_PROCESSOR.encode()),group_hash,None,
                    {"legacy_index_sha256":legacy_index_sha256,"source_version":parent["document_version_id"],
                     "vectors_reused":len(entries),"new_model_calls":0,"approval":"NEEDS_REVIEW","applicability":"UNKNOWN"})
                await repo.audit(conn,actor.subject_id,"knowledge.legacy.staged",version_id,
                    {"original_sha256":original.sha256,"legacy_index_sha256":legacy_index_sha256,"group_sha256":group_hash,
                     "new_review_required":True,"new_model_calls":0,"vectors_reused":len(entries)})
                await repo.outbox(conn,"knowledge.legacy.staged",version_id,{"job_id":job_id,"state":"NEEDS_REVIEW"})
            results.append({"version_id":version_id,"state":"NEEDS_REVIEW","chunks":len(entries),"original_sha256":original.sha256})
        except PlatformError as error:
            skipped.extend({"child_id":c["id"],"reason":error.code} for _,c,_,_ in entries)
        except ValidationError:
            skipped.extend({"child_id":c["id"],"reason":"LEGACY_METADATA_REQUIRES_REVIEW"} for _,c,_,_ in entries)
    return {"versions":results,"skipped":skipped,"new_model_calls":0,
            "staged_vectors":sum(r["chunks"] for r in results),"new_human_approvals":0,"release_activations":0}
