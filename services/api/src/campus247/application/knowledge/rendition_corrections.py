"""New prose renditions after source-image comparison and independent review.

Never edits an original/rendition, clears table/arrow uncertainty, changes an
edition's dates, supplies publication review, or activates a release.
"""
import copy
import json
from pathlib import Path
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from campus247.application.knowledge.document_identity import StrictModel, RenditionIdentity
from campus247.application.knowledge.platform_models import PROCESSOR, PlatformError, digest, metadata_binding
from campus247.domain.shared.values import generate_uuid7
from campus247.application.knowledge.platform_models import json_value


def configuration_hash(base_parser_hash):
    return digest({"base_parser":base_parser_hash,"adapter_sha256":digest(Path(__file__).read_bytes()),"schema":"independent-prose-correction-v1"})


class PageCorrection(StrictModel):
    model_config=ConfigDict(extra="forbid",frozen=True,str_strip_whitespace=False)
    page: int = Field(ge=1)
    expected_page_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    preview_image_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    text: str = Field(min_length=20,max_length=200000)


class CorrectionInput(StrictModel):
    expected_revision: int = Field(ge=1)
    expected_rendition_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    pages: tuple[PageCorrection,...] = Field(min_length=1,max_length=12)
    note: str = Field(min_length=10,max_length=2000)
    confirmed_source_comparison: Literal[True]

    @model_validator(mode="after")
    def unique_pages(self):
        if len({page.page for page in self.pages})!=len(self.pages): raise ValueError("One complete proposed text per page")
        return self


class CorrectionReviewInput(StrictModel):
    expected_revision: int = Field(ge=0)
    expected_proposal_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    verdict: Literal["APPROVED","REJECTED"]
    coverage: Literal["PROSE_ONLY"] | None = None
    note: str = Field(min_length=10,max_length=2000)
    confirmed_full_page_and_conditions: bool = False

    @model_validator(mode="after")
    def approval_requires_full_comparison(self):
        if self.verdict=="APPROVED" and (self.coverage!="PROSE_ONLY" or not self.confirmed_full_page_and_conditions):
            raise ValueError("Approval requires explicit full-page prose/condition comparison")
        return self


class RenditionCorrections:
    def __init__(self, platform):
        self.platform,self.repo,self.storage=platform,platform.repo,platform.storage

    async def ready(self,conn):
        if not await conn.fetchval("SELECT to_regclass('knowledge_rendition_correction') IS NOT NULL"):
            raise PlatformError(503,"CORRECTION_SCHEMA_NOT_READY","Chưa có schema sửa bản trích xuất có lịch sử.")

    async def source(self,conn,version_id,*,lock=False):
        row=await self.repo.version(conn,version_id,lock=lock)
        if (row["publication_state"]!="DRAFT" or row["revoked_at"] or row["review_state"]=="APPROVED" or row["media_type"]!="application/pdf"
            or row["processor_profile"]!=PROCESSOR or not row["rendition_id"] or metadata_binding(row)!=row["metadata_sha256"]):
            raise PlatformError(409,"CORRECTION_SOURCE_INELIGIBLE","Cần bản PDF nháp, chưa duyệt/thu hồi và có trích xuất gắn với nguồn.")
        lineage=await conn.fetchrow("SELECT * FROM knowledge_version_lineage WHERE version_id=$1 AND tenant_id=$2",version_id,self.repo.tenant)
        if not lineage: raise PlatformError(409,"CORRECTION_LINEAGE_REQUIRED","Cần hồ sơ tiếp nhận và lineage nguồn để sửa bản trích xuất.")
        original=await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2",row["original_id"],self.repo.tenant)
        rendition=await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2",row["rendition_id"],self.repo.tenant)
        self.storage.read(original); raw=self.storage.read(rendition)
        if digest(raw)!=row["rendition_sha256"]: raise PlatformError(409,"CORRECTION_INTEGRITY","Bản trích xuất không khớp nguồn.")
        return row,lineage,json.loads(raw)

    async def page(self,conn,lineage,source,page):
        image=await conn.fetchrow("""SELECT a.* FROM knowledge_ingestion_job job JOIN knowledge_job_step step ON step.job_id=job.id
            JOIN knowledge_artifact a ON a.id=step.artifact_id AND a.tenant_id=job.tenant_id
            WHERE job.intake_id=$1 AND job.tenant_id=$2 AND step.stage=$3 AND step.input_sha256=$4
            ORDER BY step.completed_at DESC LIMIT 1""",lineage["observation_id"],self.repo.tenant,"RENDER:"+str(page),source["original_sha256"])
        if not image: raise PlatformError(409,"CORRECTION_IMAGE_REQUIRED","Cần ảnh đối chiếu đúng trang trước khi sửa chữ.")
        self.storage.read(image)
        return image

    async def preview(self,actor,version_id):
        self.platform.admin(actor)
        async with self.repo.transaction() as conn:
            await self.ready(conn)
            source,lineage,extracted=await self.source(conn,version_id)
            pages=[]
            for page in extracted["pages"]:
                if not page["page"]: continue
                try: image=await self.page(conn,lineage,source,page["page"])
                except PlatformError as error:
                    if error.code=="CORRECTION_IMAGE_REQUIRED": continue
                    raise
                pages.append({"page":page["page"],"text":page["text"],"expected_page_sha256":digest(page),"preview_image_sha256":image["sha256"]})
            return {"version_id":str(version_id),"expected_revision":source["revision"],"expected_rendition_sha256":source["rendition_sha256"],
                "intake_id":str(lineage["observation_id"]),"pages":pages,"coverage":"PROSE_ONLY","admission_granted":False}

    async def history(self,actor,version_id):
        self.platform.admin(actor)
        async with self.repo.transaction() as conn:
            await self.ready(conn)
            await self.repo.version(conn,version_id)
            rows=await conn.fetch("""SELECT c.id,c.created_by,c.proposal_sha256,c.recorded_at,c.note,
                (SELECT verdict FROM knowledge_rendition_correction_review r WHERE r.correction_id=c.id AND r.tenant_id=c.tenant_id ORDER BY revision DESC LIMIT 1) AS latest_verdict,
                COALESCE((SELECT max(revision) FROM knowledge_rendition_correction_review r WHERE r.correction_id=c.id AND r.tenant_id=c.tenant_id),0) AS revision,
                result.version_id FROM knowledge_rendition_correction c
                LEFT JOIN knowledge_rendition_correction_result result ON result.correction_id=c.id AND result.tenant_id=c.tenant_id
                WHERE c.source_version_id=$1 AND c.tenant_id=$2 ORDER BY c.recorded_at,c.id""",version_id,self.repo.tenant)
            return {"items":[json.loads(json.dumps(dict(row),default=str)) for row in rows]}

    async def detail(self,actor,correction_id):
        self.platform.admin(actor)
        async with self.repo.transaction() as conn:
            await self.ready(conn)
            row=await conn.fetchrow("SELECT * FROM knowledge_rendition_correction WHERE id=$1 AND tenant_id=$2",correction_id,self.repo.tenant)
            if not row: raise PlatformError(404,"CORRECTION_NOT_FOUND","Không tìm thấy đề xuất trong phạm vi hiện tại.")
            source=await self.repo.version(conn,row["source_version_id"])
            original=await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2",row["original_id"],self.repo.tenant)
            self.storage.read(original)
            artifact=await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2",row["proposal_id"],self.repo.tenant)
            raw=self.storage.read(artifact)
            if digest(raw)!=row["proposal_sha256"]: raise PlatformError(409,"CORRECTION_INTEGRITY","Đề xuất không khớp hash.")
            lineage=await conn.fetchrow("SELECT * FROM knowledge_version_lineage WHERE version_id=$1 AND tenant_id=$2",row["source_version_id"],self.repo.tenant)
            edits=json_value(row["pages"])
            for edit in edits:
                image=await self.page(conn,lineage,source,edit["page"])
                if image["sha256"]!=edit["preview_image_sha256"]: raise PlatformError(409,"CORRECTION_IMAGE_CHANGED","Ảnh đối chiếu không khớp.")
            return {"correction_id":str(correction_id),"source_version_id":str(row["source_version_id"]),"created_by":str(row["created_by"]),
                "proposal_sha256":row["proposal_sha256"],"intake_id":str(lineage["observation_id"]),"pages":edits,"note":row["note"],
                "revision":await conn.fetchval("SELECT COALESCE(max(revision),0) FROM knowledge_rendition_correction_review WHERE correction_id=$1 AND tenant_id=$2",correction_id,self.repo.tenant),
                "admission_granted":False}

    async def propose(self,actor,version_id,body,key):
        self.platform.admin(actor)
        fingerprint=digest({"version_id":version_id,**body.model_dump(mode="json")})
        async with self.repo.transaction() as conn:
            await self.ready(conn)
            replay=await self.repo.replay(conn,actor.subject_id,"correction:"+key,fingerprint)
            if replay: return {**replay,"is_replay":True}
            source,lineage,extracted=await self.source(conn,version_id,lock=True)
            if str(source["created_by"])!=str(actor.subject_id):
                raise PlatformError(403,"CORRECTION_AUTHOR_REQUIRED","Người tạo bản nháp gửi đề xuất sửa; người khác đối chiếu độc lập.")
            if source["revision"]!=body.expected_revision or source["rendition_sha256"]!=body.expected_rendition_sha256:
                raise PlatformError(409,"STALE_VERSION","Bản trích xuất đã đổi; tải lại trước khi sửa.")
            proposed=copy.deepcopy(extracted)
            for correction in body.pages:
                page=next((page for page in proposed["pages"] if page["page"]==correction.page),None)
                if not page or digest(page)!=correction.expected_page_sha256:
                    raise PlatformError(409,"CORRECTION_PAGE_CHANGED","Trang đề xuất không khớp bản trích xuất đã xem.")
                if (page.get("layout") or {}).get("route") in {"NATIVE_TABLE","NATIVE_GRAPHICS"} or (page.get("layout") or {}).get("tables"):
                    raise PlatformError(422,"STRUCTURED_CORRECTION_REQUIRED","Bảng hoặc quan hệ cần bằng chứng có cấu trúc; sửa chữ không xác minh được chúng.")
                image=await self.page(conn,lineage,source,correction.page)
                if image["sha256"]!=correction.preview_image_sha256:
                    raise PlatformError(409,"CORRECTION_IMAGE_CHANGED","Ảnh đối chiếu đã đổi.")
                page["text"]=correction.text
            proposed["manual_correction"]={"state":"PROPOSED","source_version_id":str(version_id),"source_sha256":source["original_sha256"],"proposed_by":actor.subject_id}
            artifact=self.storage.write_json(json.dumps(proposed,ensure_ascii=False,sort_keys=True).encode(),"correction-proposal")
            await self.repo.artifact(conn,artifact)
            identifier=generate_uuid7()
            if not extracted.get("parser_identity"):
                raise PlatformError(409,"CORRECTION_LINEAGE_REQUIRED","Thiếu parser identity gốc để xác lập rendition mới.")
            base=digest(extracted["parser_identity"])
            await conn.execute("""INSERT INTO knowledge_rendition_correction(id,tenant_id,source_version_id,source_revision,original_id,base_rendition_id,
                proposal_id,proposal_sha256,parser_config_sha256,pages,note,created_by) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb,$11,$12)""",
                identifier,self.repo.tenant,version_id,source["revision"],source["original_id"],source["rendition_id"],artifact.id,artifact.sha256,base,
                json.dumps([page.model_dump(mode="json") for page in body.pages]),body.note,actor.subject_id)
            result={"correction_id":identifier,"proposal_sha256":artifact.sha256,"revision":0,"state":"AWAITING_INDEPENDENT_REVIEW","admission_granted":False,"is_replay":False}
            await self.repo.audit(conn,actor.subject_id,"knowledge.correction.proposed",identifier,{"source_version_id":str(version_id),"proposal_sha256":artifact.sha256})
            await self.repo.remember(conn,actor.subject_id,"correction:"+key,fingerprint,result)
            return result

    async def review(self,actor,correction_id,body,key):
        self.platform.admin(actor)
        if body.verdict=="APPROVED" and (body.coverage!="PROSE_ONLY" or not body.confirmed_full_page_and_conditions):
            raise PlatformError(422,"CORRECTION_COMPARISON_REQUIRED","Cần xác nhận đối chiếu toàn trang văn xuôi và giữ đủ điều kiện/ngoại lệ.")
        fingerprint=digest({"correction_id":correction_id,**body.model_dump(mode="json")})
        async with self.repo.transaction() as conn:
            await self.ready(conn)
            replay=await self.repo.replay(conn,actor.subject_id,"correction-review:"+key,fingerprint)
            if replay: return {**replay,"is_replay":True}
            proposal=await conn.fetchrow("SELECT * FROM knowledge_rendition_correction WHERE id=$1 AND tenant_id=$2 FOR UPDATE",correction_id,self.repo.tenant)
            if not proposal: raise PlatformError(404,"CORRECTION_NOT_FOUND","Không tìm thấy đề xuất trong phạm vi hiện tại.")
            if str(proposal["created_by"])==str(actor.subject_id): raise PlatformError(403,"SEPARATION_OF_DUTIES","Người sửa chữ không được tự xác minh bản sửa.")
            source,lineage,_=await self.source(conn,proposal["source_version_id"],lock=True)
            if source["revision"]!=proposal["source_revision"] or source["rendition_id"]!=proposal["base_rendition_id"] or source["original_id"]!=proposal["original_id"]:
                raise PlatformError(409,"CORRECTION_SOURCE_CHANGED","Nguồn hoặc review đã đổi; không dùng đề xuất cũ.")
            revision=await conn.fetchval("SELECT COALESCE(max(revision),0) FROM knowledge_rendition_correction_review WHERE correction_id=$1 AND tenant_id=$2",correction_id,self.repo.tenant)
            if body.expected_revision!=revision or body.expected_proposal_sha256!=proposal["proposal_sha256"]:
                raise PlatformError(409,"CORRECTION_REVISION_CHANGED","Đề xuất hoặc quyết định đã đổi.")
            if await conn.fetchval("SELECT EXISTS(SELECT 1 FROM knowledge_rendition_correction_result WHERE correction_id=$1 AND tenant_id=$2)",correction_id,self.repo.tenant):
                raise PlatformError(409,"CORRECTION_ALREADY_MATERIALIZED","Bản sửa đã có phiên bản riêng; không ghi đè kết quả.")
            artifact=await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2",proposal["proposal_id"],self.repo.tenant)
            raw=self.storage.read(artifact)
            if digest(raw)!=proposal["proposal_sha256"]: raise PlatformError(409,"CORRECTION_INTEGRITY","Đề xuất không khớp hash.")
            corrected=json.loads(raw); edits=json_value(proposal["pages"])
            for edit in edits:
                image=await self.page(conn,lineage,source,edit["page"])
                if image["sha256"]!=edit["preview_image_sha256"]: raise PlatformError(409,"CORRECTION_IMAGE_CHANGED","Ảnh đối chiếu không khớp.")
            review_id=generate_uuid7()
            await conn.execute("""INSERT INTO knowledge_rendition_correction_review(id,tenant_id,correction_id,revision,verdict,proposal_sha256,reviewer_id,note)
                VALUES($1,$2,$3,$4,$5,$6,$7,$8)""",review_id,self.repo.tenant,correction_id,revision+1,body.verdict,proposal["proposal_sha256"],actor.subject_id,body.note)
            result={"correction_id":str(correction_id),"review_id":review_id,"revision":revision+1,"verdict":body.verdict,"admission_granted":False,"release_changed":False,"is_replay":False}
            if body.verdict=="APPROVED":
                edited={edit["page"] for edit in edits}
                allowed={"TEXT_REQUIRES_REVIEW","RASTER_COVERAGE_REQUIRES_REVIEW","LAYOUT_ADAPTER_REQUIRED"}
                if any(issue.get("page") in edited and issue["code"] not in allowed for issue in corrected["issues"]):
                    raise PlatformError(422,"STRUCTURED_CORRECTION_REQUIRED","Còn lỗi cấu trúc; duyệt chữ không được xóa điều kiện/bảng/sơ đồ chưa rõ.")
                corrected["issues"]=[issue for issue in corrected["issues"] if issue.get("page") not in edited]
                for page in corrected["pages"]:
                    if page["page"] in edited:
                        page["source_layout"]=page.pop("layout",None)
                        page["layout"]={"route":"MANUAL_VERIFIED_PROSE","review_id":review_id}
                corrected["manual_correction"].update(state="INDEPENDENT_PROSE_REVIEW",correction_id=str(correction_id),review_id=review_id,reviewer_id=actor.subject_id)
                rendition=self.storage.write_json(json.dumps(corrected,ensure_ascii=False,sort_keys=True).encode(),"corrected-prose-rendition")
                await self.repo.artifact(conn,rendition)
                identifier,job_id=generate_uuid7(),generate_uuid7()
                config=configuration_hash(proposal["parser_config_sha256"])
                await conn.execute("""INSERT INTO document_version(id,knowledge_source_id,version_label,content_checksum,status,storage_object_key,effective_from,effective_until)
                    VALUES($1,$2,$3,$4,'DRAFT',$5,$6,$7)""",identifier,source["source_id"],"rendition-"+identifier,source["original_sha256"],source["object_key"],source["effective_from"],source["effective_until"])
                # Content authorship is the immutable proposal's actual author;
                # the creation/review action is audited to the actual reviewer.
                await conn.execute("""INSERT INTO knowledge_ingest_version(version_id,tenant_id,original_id,filename,created_by,metadata_sha256,processor_profile,rendition_id,rendition_sha256,review_state)
                    VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,'NEEDS_REVIEW')""",identifier,self.repo.tenant,source["original_id"],source["filename"],proposal["created_by"],source["metadata_sha256"],PROCESSOR,rendition.id,rendition.sha256)
                identity=RenditionIdentity(edition_id=lineage["edition_id"],source_sha256=source["original_sha256"],artifact_id=rendition.id,
                    processor_revision="independent-prose-correction-v1",config_sha256=config,schema_revision="corrected-prose-v1")
                await conn.execute("INSERT INTO knowledge_version_lineage(version_id,tenant_id,edition_id,observation_id,rendition_identity) VALUES($1,$2,$3,$4,$5::jsonb)",identifier,self.repo.tenant,lineage["edition_id"],lineage["observation_id"],identity.model_dump_json())
                await conn.execute("INSERT INTO knowledge_ingestion_job(id,tenant_id,version_id,stage) VALUES($1,$2,$3,'CHUNK_EMBED')",job_id,self.repo.tenant,identifier)
                await self.repo.save_step(conn,{"id":job_id},"EXTRACT",source["original_sha256"],config,rendition.sha256,None,{"correction_id":str(correction_id),"review_id":review_id,"new_model_calls":0},artifact_ref=rendition.id)
                await conn.execute("INSERT INTO knowledge_rendition_correction_result(correction_id,tenant_id,review_id,version_id,rendition_id,rendition_sha256,config_sha256) VALUES($1,$2,$3,$4,$5,$6,$7)",correction_id,self.repo.tenant,review_id,identifier,rendition.id,rendition.sha256,config)
                result.update(version_id=identifier,job_id=job_id,edition_id=str(lineage["edition_id"]),state="QUEUED_FOR_INDEX_AND_PUBLICATION_REVIEW")
                await self.repo.outbox(conn,"knowledge.correction.index.requested",identifier,result)
            await self.repo.audit(conn,actor.subject_id,"knowledge.correction.review",review_id,{"correction_id":str(correction_id),"verdict":body.verdict,"proposal_sha256":proposal["proposal_sha256"]})
            await self.repo.remember(conn,actor.subject_id,"correction-review:"+key,fingerprint,result)
            return result


async def verified_checkpoint(repo,storage,job,parser_config):
    async with repo.pool.acquire() as conn:
        if not await conn.fetchval("SELECT to_regclass('knowledge_rendition_correction_result') IS NOT NULL"): return None,None
        row=await conn.fetchrow("""SELECT result.*,correction.parser_config_sha256,correction.created_by,review.reviewer_id,review.verdict,
            source.revoked_at AS source_revoked FROM knowledge_rendition_correction_result result
            JOIN knowledge_rendition_correction correction ON correction.id=result.correction_id AND correction.tenant_id=result.tenant_id
            JOIN knowledge_rendition_correction_review review ON review.id=result.review_id AND review.tenant_id=result.tenant_id
            JOIN knowledge_ingest_version source ON source.version_id=correction.source_version_id AND source.tenant_id=correction.tenant_id
            WHERE result.version_id=$1 AND result.tenant_id=$2""",job["version_id"],repo.tenant)
        if not row: return None,None
        config=configuration_hash(parser_config)
        if (row["parser_config_sha256"]!=parser_config or row["config_sha256"]!=config or row["verdict"]!="APPROVED"
            or row["created_by"]==row["reviewer_id"] or row["source_revoked"]):
            raise PlatformError(409,"CORRECTION_BINDING_CHANGED","Bản sửa cần đối chiếu lại profile, nguồn và review độc lập.")
        version=await repo.version(conn,job["version_id"])
        for artifact_id in (version["original_id"],row["rendition_id"]):
            artifact=await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2",artifact_id,repo.tenant)
            storage.read(artifact)
        if version["rendition_id"]!=row["rendition_id"] or version["rendition_sha256"]!=row["rendition_sha256"]:
            raise PlatformError(409,"CORRECTION_INTEGRITY","Rendition không khớp quyết định sửa.")
    step=await repo.checkpoint(job,"EXTRACT",version["original_sha256"],config)
    if not step or step["artifact_id"]!=row["rendition_id"] or step["output_sha256"]!=row["rendition_sha256"]:
        raise PlatformError(409,"CORRECTION_INTEGRITY","Thiếu checkpoint đúng bản sửa đã đối chiếu.")
    return step,config
