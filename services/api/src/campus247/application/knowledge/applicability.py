"""Create an immutable applicability version while retaining exact cached inputs."""
import json

from campus247.application.knowledge.platform_models import EMBED_ARTIFACT,IntakeMetadata,PlatformError,digest,json_value
from campus247.application.retrieval.profile import load_retrieval_profile
from campus247.domain.shared.values import generate_uuid7


async def applicability_version(platform,actor,version_id,body,key):
    platform.admin(actor)
    repo=platform.repo
    async with repo.transaction() as conn:
        fingerprint=digest({"version_id":version_id,**body.model_dump(mode="json")})
        replay=await repo.replay(conn,actor.subject_id,"metadata:"+key,fingerprint)
        if replay:
            return replay
        previous=await repo.version(conn,version_id,lock=True)
        if previous["revision"] != body.expected_revision:
            raise PlatformError(409,"STALE_VERSION","Phiên bản đã đổi; tải lại.")
        if previous["revoked_at"] or not previous["index_version"]:
            raise PlatformError(409,"VERSION_NOT_REUSABLE","Cần bản đã xử lý đầy đủ và chưa bị thu hồi.")
        metadata=IntakeMetadata(title=previous["title"],owner_unit=previous["owner_unit"],
            canonical_uri=previous["canonical_uri"],authority_level=previous["authority_level"],
            campus=previous["campus_scope"],faculties=previous["faculty_scope"],programs=previous["program_scope"],
            audiences=previous["audiences"],effective_from=body.effective_from,effective_until=body.effective_until)
        chunks=await conn.fetch("""SELECT c.id,ci.index_text,ci.input_sha256,ci.processor_profile,ci.provenance
            FROM knowledge_chunk c JOIN knowledge_chunk_input ci ON ci.chunk_id=c.id
            WHERE c.document_version_id=$1 ORDER BY c.ordinal""",version_id)
        manifest=await conn.fetchrow("SELECT * FROM embedding_index_manifest WHERE index_version=$1",previous["index_version"])
        profile=load_retrieval_profile()
        if (not manifest or manifest["build_status"]!='READY' or not manifest["validated_at"]
            or manifest["artifact_sha256"] != EMBED_ARTIFACT or manifest["dimension"]!=1024
            or manifest["embedding_model_id"]!=profile.embedding_model_id
            or manifest["embedding_model_revision"]!=profile.embedding_model_revision
            or manifest["normalization"]!='l2' or manifest["distance_metric"]!='cosine'
            or not chunks or manifest["chunk_count"]!=len(chunks)
            or any(digest(c["index_text"].encode())!=c["input_sha256"] for c in chunks)):
            raise PlatformError(409,"CACHE_INPUT_MISMATCH","Không thể chứng minh cache đúng input/profile.")
        identifier=generate_uuid7()
        metadata_hash=digest(metadata.model_dump(mode="json",exclude={"source_id"}))
        await conn.execute("""INSERT INTO document_version
            (id,knowledge_source_id,version_label,content_checksum,status,storage_object_key,effective_from,effective_until)
            VALUES ($1,$2,$3,$4,'DRAFT',$5,$6,$7)""",identifier,previous["source_id"],"metadata-"+identifier,
            previous["original_sha256"],previous["object_key"],metadata.effective_from,metadata.effective_until)
        await conn.execute("""INSERT INTO knowledge_ingest_version
            (version_id,tenant_id,original_id,filename,created_by,metadata_sha256,processor_profile,
             rendition_id,rendition_sha256,review_state) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,'NEEDS_REVIEW')""",
            identifier,repo.tenant,previous["original_id"],previous["filename"],actor.subject_id,metadata_hash,
            previous["processor_profile"],previous["rendition_id"],previous["rendition_sha256"])
        # A technical/metadata copy does not become an unmapped legacy edition
        # or invent a new business issuance. Keep the exact existing lineage.
        if await conn.fetchval("SELECT to_regclass('knowledge_version_lineage') IS NOT NULL"):
            await conn.execute("""INSERT INTO knowledge_version_lineage(version_id,tenant_id,edition_id,observation_id,rendition_identity)
                SELECT $1,tenant_id,edition_id,observation_id,rendition_identity FROM knowledge_version_lineage
                WHERE version_id=$2 AND tenant_id=$3""",identifier,version_id,repo.tenant)
        for item in chunks:
            chunk_id=generate_uuid7()
            await conn.execute("""INSERT INTO knowledge_chunk
                (id,document_version_id,ordinal,section_path,page_start,page_end,content_text,content_checksum,
                 content_tsv,embedding_rag_v1,embedding_model_version,embedding_dimension,embedded_at)
                SELECT $1,$2,ordinal,section_path,page_start,page_end,content_text,content_checksum,
                    content_tsv,embedding_rag_v1,embedding_model_version,embedding_dimension,embedded_at
                FROM knowledge_chunk WHERE id=$3""",chunk_id,identifier,item["id"])
            await conn.execute("""INSERT INTO knowledge_chunk_input
                (chunk_id,index_text,input_sha256,processor_profile,provenance)
                VALUES ($1,$2,$3,$4,$5::jsonb)""",chunk_id,item["index_text"],item["input_sha256"],item["processor_profile"],
                json.dumps({**json_value(item["provenance"]),"reused_from_chunk_id":str(item["id"])}))
        index_id="metadata-"+identifier
        checksum=digest({"previous_manifest":manifest["content_checksum"],"metadata":metadata_hash,"inputs":[c["input_sha256"] for c in chunks]})
        await conn.execute("""INSERT INTO embedding_index_manifest
            (index_version,profile_version,embedding_model_id,embedding_model_revision,artifact_sha256,dimension,normalization,
             distance_metric,corpus_version,document_count,chunk_count,content_checksum,build_status,built_at,validated_at)
            SELECT $1,profile_version,embedding_model_id,embedding_model_revision,artifact_sha256,dimension,normalization,
                distance_metric,corpus_version,1,chunk_count,$2,'READY',clock_timestamp(),clock_timestamp()
            FROM embedding_index_manifest WHERE index_version=$3""",index_id,checksum,previous["index_version"])
        await conn.execute("UPDATE document_version SET index_version=$2 WHERE id=$1",identifier,index_id)
        job_id=generate_uuid7()
        await conn.execute("""INSERT INTO knowledge_ingestion_job(id,tenant_id,version_id,state,stage,progress)
            VALUES ($1,$2,$3,'SUCCEEDED','METADATA_REVIEW',100)""",job_id,repo.tenant,identifier)
        await repo.save_step(conn,{"id":job_id},"METADATA",previous["rendition_sha256"],metadata_hash,checksum,None,
            {"applicability_basis":body.basis,"previous_version_id":version_id,"vectors_reused":len(chunks),"new_model_calls":0})
        result={"version_id":identifier,"source_id":str(previous["source_id"]),"job_id":job_id,"review_state":"NEEDS_REVIEW",
                "vectors_reused":len(chunks),"new_model_calls":0}
        await repo.audit(conn,actor.subject_id,"knowledge.metadata.version",identifier,
            {"previous_version_id":version_id,"metadata_sha256":metadata_hash,"basis_sha256":digest(body.basis.encode())})
        await repo.outbox(conn,"knowledge.metadata.version",identifier,result)
        await repo.remember(conn,actor.subject_id,"metadata:"+key,fingerprint,result)
        return result
