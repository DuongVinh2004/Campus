"""New evidence from exact original spans, reusing only unchanged model inputs.

Legacy editorial notes may remain in cached index context. They are never copied
into this rendition or its evidence. Unmatched parents stay outside the release.
"""
import io
import json
import re
import unicodedata

from campus247.application.knowledge.platform_models import IntakeMetadata, PlatformError, digest
from campus247.domain.shared.values import generate_uuid7
from campus247.application.knowledge.platform_models import json_value

PROCESSOR="verified-original-span-v2:unchanged-cached-index-context"


def mapped(text):
    chars,positions=[],[]
    for position,char in enumerate(text):
        for value in unicodedata.normalize("NFKC",char).lower():
            if value.isalnum() or value=="_":
                chars.append(value);positions.append(position)
    return "".join(chars),positions


async def source_excerpt_version(platform,actor,version_id,*,expected_revision,effective_from,basis,key):
    """Explicit source-bound decisions; no generic date or scope inference."""
    from pypdf import PdfReader
    platform.admin(actor)
    repo=platform.repo
    async with repo.transaction() as conn:
        previous=await repo.version(conn,version_id,lock=True)
        fingerprint=digest({"source":version_id,"revision":expected_revision,"date":effective_from,"basis":basis,"processor":PROCESSOR})
        replay=await repo.replay(conn,actor.subject_id,key,fingerprint)
        if replay:return replay
        verified_sources={
            "a8e645484fe3bc5354edbca15fd51c8a93da6fcda90ce371aae20b52199c489d": "2024-12-30T17:00:00+00:00",
            "8a0bc59b2cc844d7f606204f8b4c3cbf6c99e023033493057f923929221810c7": "2024-04-08T17:00:00+00:00"}
        if (previous["revision"]!=expected_revision or previous["revoked_at"]
            or previous["original_sha256"] not in verified_sources):
            raise PlatformError(409,"SOURCE_CHANGED","Nguồn đã đổi hoặc không thuộc bản đối chiếu này.")
        original=await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2",previous["original_id"],repo.tenant)
        raw=platform.storage.read(original)
        reader=PdfReader(io.BytesIO(raw))
        pages=[page.extract_text() or "" for page in reader.pages]
        source_evidence={"kind":"exact_original_pdf_text_span"}
        is_lab=previous["original_sha256"].startswith("8a0bc59b2cc844d7f")
        if is_lab:
            from campus247.application.knowledge.values import checked_path
            root=platform.storage.workspace
            transcript=checked_path(root / "data/huce-document-pipeline/ict-lab-reviewed-text-20261022-77.json",root).read_bytes()
            if digest(transcript)!="2a076dea700c378bb31cf8080863fd462d122d3b94b4700b76421bee4c16ae69":
                raise PlatformError(409,"TRANSCRIPT_CHANGED","Bản chép OCR đã đổi.")
            jobs=json.loads(checked_path(root / "data/huce-document-pipeline/ict-lab-ocr-jobs-20261022-76.json",root).read_bytes())
            expected_images=["db69320bcc1e63c5b40dffcf1661dbe217e7241952eee6dce1c9fbeb6635026f",
                "55830329d3495e56018152c5791e5d597920dd8a4e944f148c3273b67bf0fcca"]
            if len(reader.pages)!=2 or len(jobs["pages"])!=2:
                raise PlatformError(409,"OCR_BINDING_CHANGED","Số trang OCR không khớp.")
            for item,checksum in zip(jobs["pages"],expected_images):
                image=checked_path(root / item["image"],root).read_bytes()
                # OCR filenames include a processing hash, so use the exact retained review binding.
                review=json.loads(checked_path(root / "data/huce-document-pipeline/ict-rules-review-bundle-20261022-78.json",root).read_bytes())["documents"][1]["reviewed_pages"][item["page"]-1]
                ocr=checked_path(root / review["ocr_file"],root).read_bytes()
                if (item["source_sha256"]!=previous["original_sha256"] or digest(image)!=checksum
                    or review["image_sha256"]!=checksum or digest(ocr)!=review["ocr_sha256"]
                    or json.loads(ocr)["source_sha256"]!=previous["original_sha256"]):
                    raise PlatformError(409,"OCR_BINDING_CHANGED","Ảnh/OCR không khớp original.")
            pages=[p["text"] for p in json.loads(transcript)["pages"]]
            source_evidence={"kind":"visually_checked_original_scan_transcript","transcript_sha256":digest(transcript),
                "page_image_sha256":expected_images,"agent_visual_review":"2026-10-23",
                "scope":"All 12 clauses on page 2; page 1 excluded because handwritten number remains uncertain"}
        full="\n".join(pages)
        normalized,_=mapped(full)
        signature="ngày09tháng4năm2024" if is_lab else "ngày31tháng12năm2024"
        if not (signature in normalized and "quyếtđịnhnàycóhiệulựckểtừngàyký" in normalized
            and effective_from.isoformat()==verified_sources[previous["original_sha256"]]):
            raise PlatformError(409,"APPLICABILITY_NOT_PROVEN","Không khớp ngày ký/điều khoản hiệu lực đã đối chiếu.")
        source_chunks=await conn.fetch("""SELECT c.*,ci.index_text,ci.input_sha256,ci.provenance FROM knowledge_chunk c
            JOIN knowledge_chunk_input ci ON ci.chunk_id=c.id WHERE c.document_version_id=$1 ORDER BY c.ordinal""",version_id)
        selected,unmatched=[],[]
        parent_cache={}
        for row in source_chunks:
            if is_lab and row["page_start"]!=2:
                unmatched.append(str(row["id"]));continue
            if digest(row["index_text"].encode())!=row["input_sha256"]:
                raise PlatformError(409,"CACHE_INPUT_MISMATCH","Cache input đã đổi.")
            parent=row["content_checksum"]
            if parent not in parent_cache:
                lines=row["content_text"].splitlines()
                # These exact three editorial lines are excluded from evidence.
                if len(lines)<4 or not lines[1].startswith("Loại nguồn:") or not lines[2].startswith("Nội dung nguồn quy định"):
                    parent_cache[parent]=None
                else:
                    body="\n".join(lines[3:]).split("\nPhạm vi đã đối chiếu:",1)[0].strip()
                    page_start,page_end=row["page_start"],row["page_end"] or row["page_start"]
                    original_span="\n".join(pages[page_start-1:page_end])
                    key_text,positions=mapped(original_span)
                    target,_=mapped(body)
                    offset=key_text.find(target) if target else -1
                    text=(original_span[positions[offset]:positions[offset+len(target)-1]+1] if offset>=0 else None)
                    body_start=row["content_text"].find(body)
                    parent_cache[parent]=(text,body,body_start) if text and body_start>=0 else None
            verified=parent_cache[parent]
            if verified is None:
                unmatched.append(str(row["id"]));continue
            text,body,body_start=verified
            provenance=json_value(row["provenance"])
            start=max(body_start,provenance["indexed_char_start"])-body_start
            end=min(body_start+len(body),provenance["indexed_char_end"])-body_start
            if end<=start:
                unmatched.append(str(row["id"]));continue  # Cached editorial context alone is not evidence.
            begin=len(mapped(body[:start])[0]);finish=len(mapped(body[:end])[0])
            _,positions=mapped(text)
            if finish<=begin:
                unmatched.append(str(row["id"]));continue
            row=dict(row)
            row["verified_rerank_span"]={"char_start":positions[begin],"char_end":positions[finish-1]+1}
            selected.append((row,text))
        if not selected:raise PlatformError(409,"NO_VERIFIED_SOURCE_SPANS","Không có đoạn gốc khớp.")
        metadata=IntakeMetadata(title=previous["title"],owner_unit=previous["owner_unit"],canonical_uri=previous["canonical_uri"],
            campus=previous["campus_scope"],faculties=previous["faculty_scope"],programs=previous["program_scope"],
            audiences=previous["audiences"],authority_level=previous["authority_level"],effective_from=effective_from)
        metadata_hash=digest(metadata.model_dump(mode="json",exclude={"source_id"}))
        identifier=generate_uuid7()
        rendition={"processor":PROCESSOR,"original_sha256":previous["original_sha256"],"issues":[],
            "source_evidence":source_evidence,
            "pages":[{"page":row["page_start"],"page_end":row["page_end"],"section":row["section_path"],"text":text}
                     for row,text in {row["content_checksum"]:(row,text) for row,text in selected}.values()],
            "mapping":("Exact normalized-text matching against the scan transcript visually checked on both original page images; editorial prefixes excluded"
                if is_lab else "Exact normalized-text matching, evidence copied from original PDF text; all editorial prefixes excluded"),
            "unmatched_chunk_ids_held_out":unmatched}
        artifact=platform.storage.write_json(json.dumps(rendition,ensure_ascii=False,sort_keys=True).encode(),"verified_extraction")
        await repo.artifact(conn,artifact)
        await conn.execute("""INSERT INTO document_version(id,knowledge_source_id,version_label,content_checksum,status,storage_object_key,effective_from)
            VALUES($1,$2,$3,$4,'DRAFT',$5,$6)""",identifier,previous["source_id"],"original-span-"+identifier,previous["original_sha256"],previous["object_key"],effective_from)
        await conn.execute("""INSERT INTO knowledge_ingest_version(version_id,tenant_id,original_id,filename,created_by,metadata_sha256,
            processor_profile,rendition_id,rendition_sha256,review_state) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,'NEEDS_REVIEW')""",
            identifier,repo.tenant,previous["original_id"],previous["filename"],actor.subject_id,metadata_hash,PROCESSOR,artifact.id,artifact.sha256)
        for ordinal,(row,text) in enumerate(selected):
            chunk_id=generate_uuid7()
            await conn.execute("""INSERT INTO knowledge_chunk(id,document_version_id,ordinal,section_path,page_start,page_end,content_text,
                content_checksum,content_tsv,embedding_rag_v1,embedding_model_version,embedding_dimension,embedded_at)
                SELECT $1,$2,$3,section_path,page_start,page_end,$4,$5,content_tsv,embedding_rag_v1,embedding_model_version,embedding_dimension,embedded_at
                FROM knowledge_chunk WHERE id=$6""",chunk_id,identifier,ordinal,text,digest(text.encode()),row["id"])
            await conn.execute("""INSERT INTO knowledge_chunk_input(chunk_id,index_text,input_sha256,processor_profile,provenance)
                VALUES($1,$2,$3,$4,$5::jsonb)""",chunk_id,row["index_text"],row["input_sha256"],PROCESSOR,
                json.dumps({"reused_from_chunk_id":str(row["id"]),"original_sha256":previous["original_sha256"],
                    "input_sha256":row["input_sha256"],"evidence_sha256":digest(text.encode()),"evidence":source_evidence,
                    "verified_rerank_span":row["verified_rerank_span"]}))
        # The existing manifest/profile must pass all normal publication guards.
        index_id="original-span-"+identifier
        await conn.execute("""INSERT INTO embedding_index_manifest(index_version,profile_version,embedding_model_id,embedding_model_revision,
            artifact_sha256,dimension,normalization,distance_metric,corpus_version,document_count,chunk_count,content_checksum,build_status,built_at,validated_at)
            SELECT $1,profile_version,embedding_model_id,embedding_model_revision,artifact_sha256,dimension,normalization,distance_metric,corpus_version,
                1,$2,$3,'READY',clock_timestamp(),clock_timestamp() FROM embedding_index_manifest WHERE index_version=$4 AND build_status='READY'""",
            index_id,len(selected),digest({"rendition":artifact.sha256,"inputs":[r["input_sha256"] for r,_ in selected]}),previous["index_version"])
        await conn.execute("UPDATE document_version SET index_version=$2 WHERE id=$1",identifier,index_id)
        job_id=generate_uuid7()
        await conn.execute("""INSERT INTO knowledge_ingestion_job(id,tenant_id,version_id,state,stage,progress)
            VALUES($1,$2,$3,'SUCCEEDED','SOURCE_SPAN_REVIEW',100)""",job_id,repo.tenant,identifier)
        await repo.save_step(conn,{"id":job_id},"METADATA",previous["rendition_sha256"],metadata_hash,artifact.sha256,None,{"applicability_basis":basis,
            "previous_version_id":version_id,"vectors_reused":len(selected),"new_model_calls":0,"excluded_unmatched_chunks":len(unmatched)})
        result={"version_id":identifier,"source_id":str(previous["source_id"]),"verified_chunks":len(selected),"held_out_chunks":len(unmatched),"new_model_calls":0}
        await repo.audit(conn,actor.subject_id,"knowledge.original_excerpt.version",identifier,result)
        await repo.remember(conn,actor.subject_id,key,fingerprint,result)
        return result
