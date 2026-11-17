"""Short PostgreSQL transactions for intake, fenced jobs and release operations."""
from __future__ import annotations

import json
from contextlib import asynccontextmanager

from campus247.application.knowledge.platform_models import PlatformError, json_value  # noqa: F401 -- re-exported
from campus247.application.knowledge.release_members import member_reads
from campus247.domain.shared.values import generate_uuid7


from campus247.application.knowledge.values import public_row  # noqa: E402,F401 -- re-exported


class LeaseLost(RuntimeError):
    pass


class KnowledgeRepository:
    def __init__(self, pool, tenant_id: str, campus_id: str = "HUCE"):
        if pool is None or not tenant_id or campus_id != "HUCE":
            raise ValueError("Explicit PostgreSQL pool and scope required")
        self.pool, self.tenant, self.campus = pool, tenant_id, campus_id

    @asynccontextmanager
    async def transaction(self, connection=None):
        if connection is not None:
            # An application command may compose an intake resolution and the
            # existing upload atomically; nested transactions are savepoints.
            async with connection.transaction():
                yield connection
            return
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                yield conn

    async def artifact(self, conn, value):
        await conn.execute("""INSERT INTO knowledge_artifact
            (id,tenant_id,object_key,sha256,byte_size,media_type,kind) VALUES ($1,$2,$3,$4,$5,$6,$7)""",
            value.id, self.tenant, value.object_key, value.sha256, value.byte_size, value.media_type, value.kind)

    async def audit(self, conn, actor, action, target, details):
        await conn.execute("""INSERT INTO audit_event
            (id,actor_type,actor_id,action_code,resource_type,resource_id,outcome,metadata_safe)
            VALUES ($1,'USER',$2,$3,'knowledge_platform',$4,'SUCCESS',$5)""",
            generate_uuid7(), actor, action, target, json.dumps(details, default=str))

    async def outbox(self, conn, event_type, target, payload):
        await conn.execute("""INSERT INTO outbox_event
            (id,event_type,aggregate_type,aggregate_id,partition_key,payload)
            VALUES ($1,$2,'knowledge_platform',$3,$3,$4)""",
            generate_uuid7(), event_type, target, json.dumps(payload, default=str))

    async def replay(self, conn, actor, key, fingerprint):
        if not key or len(key) > 128 or not key.strip():
            raise PlatformError(422, "IDEMPOTENCY_REQUIRED", "Cần Idempotency-Key hợp lệ.")
        # Serializes the same scoped request without holding any OCR/model transaction.
        await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1,0))",
                           self.tenant + ":" + actor + ":" + key)
        row = await conn.fetchrow("""SELECT fingerprint,result FROM knowledge_platform_request
            WHERE tenant_id=$1 AND actor_id=$2 AND request_key=$3""", self.tenant, actor, key)
        if row and row["fingerprint"] != fingerprint:
            raise PlatformError(409, "IDEMPOTENCY_CONFLICT", "Mã yêu cầu đã dùng với nội dung khác.")
        return json_value(row["result"]) if row else None

    async def remember(self, conn, actor, key, fingerprint, result):
        await conn.execute("""INSERT INTO knowledge_platform_request
            (tenant_id,actor_id,request_key,fingerprint,result) VALUES ($1,$2,$3,$4,$5::jsonb)""",
            self.tenant, actor, key, fingerprint, json.dumps(result, default=str))

    async def pointer(self, conn, *, lock=False):
        if lock:
            await conn.execute("""INSERT INTO knowledge_release_pointer(tenant_id,campus_id)
                VALUES ($1,$2) ON CONFLICT DO NOTHING""", self.tenant, self.campus)
        row = await conn.fetchrow("""SELECT * FROM knowledge_release_pointer
            WHERE tenant_id=$1 AND campus_id=$2""" + (" FOR UPDATE" if lock else ""), self.tenant, self.campus)
        return public_row(row) or {"tenant_id": self.tenant, "campus_id": self.campus,
                                  "release_id": None, "generation": 0, "policy_generation": 0}

    async def version(self, conn, identifier, *, lock=False):
        row = await conn.fetchrow("""SELECT x.*,v.knowledge_source_id AS source_id,
            v.effective_from,v.effective_until,v.index_version,v.status AS publication_state,
            s.title,s.owner_unit,s.canonical_uri,s.authority_level,s.campus_scope,s.faculty_scope,s.program_scope,s.audiences,
            a.sha256 AS original_sha256,a.media_type,a.byte_size,a.object_key
            FROM knowledge_ingest_version x JOIN document_version v ON v.id=x.version_id
            JOIN knowledge_source s ON s.id=v.knowledge_source_id
            JOIN knowledge_source_scope scope ON scope.source_id=s.id AND scope.tenant_id=x.tenant_id
            JOIN knowledge_artifact a ON a.id=x.original_id AND a.tenant_id=x.tenant_id
            WHERE x.version_id=$1 AND x.tenant_id=$2""" + (" FOR UPDATE OF x" if lock else ""), identifier, self.tenant)
        if not row:
            raise PlatformError(404, "VERSION_NOT_FOUND", "Không tìm thấy phiên bản trong phạm vi hiện tại.")
        return dict(row)

    async def release_versions(self, conn, release_id):
        """One tenant-bound metadata query instead of one lookup per member."""
        rows = await conn.fetch(member_reads("""SELECT x.*,v.knowledge_source_id AS source_id,
            v.effective_from,v.effective_until,v.index_version,v.status AS publication_state,
            s.title,s.owner_unit,s.canonical_uri,s.authority_level,s.campus_scope,s.faculty_scope,s.program_scope,s.audiences,
            a.sha256 AS original_sha256,a.media_type,a.byte_size,a.object_key
            FROM knowledge_release_member member JOIN knowledge_release release ON release.id=member.release_id
            JOIN knowledge_ingest_version x ON x.version_id=member.version_id AND x.tenant_id=release.tenant_id
            JOIN document_version v ON v.id=x.version_id
            JOIN knowledge_source s ON s.id=v.knowledge_source_id AND s.id=member.source_id
            JOIN knowledge_source_scope scope ON scope.source_id=s.id AND scope.tenant_id=x.tenant_id
            JOIN knowledge_artifact a ON a.id=x.original_id AND a.tenant_id=x.tenant_id
            WHERE member.release_id=$1 AND release.tenant_id=$2 ORDER BY x.version_id"""), release_id, self.tenant)
        return [dict(row) for row in rows]

    async def claim(self, owner: str, lease_seconds: int = 90, *, target_job_id=None):
        if target_job_id is not None:
            from uuid import UUID
            target_job_id = UUID(str(target_job_id))
        async with self.transaction() as conn:
            # One heavy job across this database's workers/tenants on the local host.
            await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1,0))", "knowledge-heavy:single-host-v1")
            if await conn.fetchval("""SELECT EXISTS(SELECT 1 FROM knowledge_ingestion_job
                WHERE state='RUNNING' AND lease_until>clock_timestamp())"""):
                return None
            row = await conn.fetchrow("""SELECT id,attempts,version_id,cancel_requested,
                to_jsonb(knowledge_ingestion_job)->>'intake_id' AS intake_id FROM knowledge_ingestion_job WHERE tenant_id=$1
                AND ($2::uuid IS NULL OR id=$2::uuid) AND
                ((state IN ('QUEUED','RETRY_WAIT') AND next_attempt_at<=clock_timestamp())
                 OR (state='RUNNING' AND lease_until<=clock_timestamp()))
                ORDER BY created_at,id FOR UPDATE SKIP LOCKED LIMIT 1""", self.tenant, target_job_id)
            if not row:
                return None
            if row["attempts"] >= 3:
                # An expired third owner cannot reserve a fourth attempt. Keep
                # its evidence and counters, and record a terminal outcome.
                state = "CANCELLED" if row["cancel_requested"] else "FAILED"
                await conn.execute("""UPDATE knowledge_ingestion_job SET state=$3,error_code='ATTEMPTS_EXHAUSTED',
                    lease_owner=NULL,lease_until=NULL,updated_at=clock_timestamp() WHERE id=$1 AND tenant_id=$2""", row["id"], self.tenant, state)
                await self.outbox(conn, "knowledge.job."+state.lower(), row["id"], {"version_id": str(row["version_id"]) if row["version_id"] else None,
                    "intake_id": str(row["intake_id"]) if row["intake_id"] else None, "error_code": "ATTEMPTS_EXHAUSTED", "attempts": row["attempts"]})
                return None
            return dict(await conn.fetchrow("""UPDATE knowledge_ingestion_job SET
                state='RUNNING',lease_owner=$2,lease_until=clock_timestamp()+$3*interval '1 second',
                heartbeat_at=clock_timestamp(),fencing_token=fencing_token+1,attempts=attempts+1,
                updated_at=clock_timestamp(),error_code=NULL WHERE id=$1 RETURNING *""", row["id"], owner, lease_seconds))

    async def heartbeat(self, job, lease_seconds=90):
        async with self.transaction() as conn:
            result = await conn.fetchval("""UPDATE knowledge_ingestion_job SET
                lease_until=clock_timestamp()+$5*interval '1 second',heartbeat_at=clock_timestamp()
                WHERE id=$1 AND tenant_id=$2 AND lease_owner=$3 AND fencing_token=$4
                AND state='RUNNING' AND lease_until>clock_timestamp() AND NOT cancel_requested RETURNING id""",
                job["id"], self.tenant, job["lease_owner"], job["fencing_token"], lease_seconds)
            return result is not None

    @asynccontextmanager
    async def fenced(self, job, *, allow_cancel=False):
        async with self.transaction() as conn:
            row = await conn.fetchrow("""SELECT *,lease_until>clock_timestamp() AS live
                FROM knowledge_ingestion_job WHERE id=$1 AND tenant_id=$2 FOR UPDATE""", job["id"], self.tenant)
            if (not row or row["state"] != "RUNNING" or not row["live"]
                or row["fencing_token"] != job["fencing_token"] or row["lease_owner"] != job["lease_owner"]
                or row["cancel_requested"] and not allow_cancel):
                raise LeaseLost("Job ownership is no longer current")
            yield conn

    async def checkpoint(self, job, stage, input_hash, config_hash):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""SELECT step.* FROM knowledge_job_step step
                JOIN knowledge_ingestion_job job ON job.id=step.job_id
                WHERE step.job_id=$1 AND job.tenant_id=$5
                AND step.stage=$2 AND step.input_sha256=$3 AND step.config_sha256=$4""",
                job["id"], stage, input_hash, config_hash, self.tenant)
            return dict(row) if row else None

    async def save_step(self, conn, job, stage, input_hash, config_hash, output_hash, artifact, result, *, artifact_ref=None):
        if artifact:
            await self.artifact(conn, artifact)
        if artifact_ref and not await conn.fetchval("SELECT EXISTS(SELECT 1 FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2)", artifact_ref, self.tenant):
            raise PlatformError(409, "ARTIFACT_SCOPE_MISMATCH", "Không thể dùng artifact ngoài phạm vi.")
        await conn.execute("""INSERT INTO knowledge_job_step
            (job_id,stage,input_sha256,config_sha256,output_sha256,artifact_id,result)
            VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb) ON CONFLICT DO NOTHING""",
            job["id"], stage, input_hash, config_hash, output_hash,
            artifact.id if artifact else artifact_ref, json.dumps(result, default=str))

    async def finish(self, job, state, error=None):
        async with self.fenced(job, allow_cancel=True) as conn:
            cancelled = await conn.fetchval("SELECT cancel_requested FROM knowledge_ingestion_job WHERE id=$1", job["id"])
            state = "CANCELLED" if cancelled else state
            await conn.execute("""UPDATE knowledge_ingestion_job SET state=$2,error_code=$3,
                lease_until=NULL,lease_owner=NULL,updated_at=clock_timestamp(),
                next_attempt_at=clock_timestamp()+least(300,power(2,attempts)::integer)*interval '1 second',
                progress=CASE WHEN $2='SUCCEEDED' THEN 100 ELSE progress END WHERE id=$1""", job["id"], state, error)
            await self.outbox(conn, "knowledge.job." + state.lower(), job["id"],
                {"version_id": str(job["version_id"]) if job["version_id"] else None,
                 "intake_id": str(job.get("intake_id")) if job.get("intake_id") else None, "error_code": error})
