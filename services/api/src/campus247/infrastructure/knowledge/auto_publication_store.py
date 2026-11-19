"""Durable state of the automatic publication pipeline (additive tables, created idempotently).

No Alembic revision: the serving runtime accepts a fixed set of schema revisions, and these tables are additive,
tenant-scoped and independent of the knowledge tables (they only point at them).
"""
from __future__ import annotations

import json

from campus247.domain.shared.values import generate_uuid7

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS knowledge_auto_publication (
        tenant_id text NOT NULL, version_id uuid NOT NULL, source_id uuid NOT NULL,
        mode text NOT NULL CHECK (mode IN ('DIRECT','REVIEW')),
        state text NOT NULL CHECK (state IN ('PROCESSING','AWAITING_REVIEW','READY_TO_PUBLISH','WAITING_EFFECTIVE',
            'INDEXING','ACTIVE','NEEDS_ATTENTION','REJECTED')),
        origin text NOT NULL DEFAULT 'UPLOAD', author_id uuid NOT NULL, author_role text NOT NULL,
        attestation jsonb, checks jsonb, flags jsonb NOT NULL DEFAULT '[]'::jsonb,
        reviewer_id uuid, review_note text, release_id uuid, resume_state text,
        error_code text, error_detail text, not_before timestamptz, attempts integer NOT NULL DEFAULT 0,
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(), updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        state_changed_at timestamptz NOT NULL DEFAULT clock_timestamp(), published_at timestamptz, usable_at timestamptz,
        PRIMARY KEY (tenant_id, version_id))""",
    # The set of states grew after the first version of the table: bring an existing table's constraint up to date.
    "ALTER TABLE knowledge_auto_publication DROP CONSTRAINT IF EXISTS knowledge_auto_publication_state_check",
    """ALTER TABLE knowledge_auto_publication ADD CONSTRAINT knowledge_auto_publication_state_check CHECK (state IN
        ('PROCESSING','AWAITING_REVIEW','READY_TO_PUBLISH','WAITING_EFFECTIVE','INDEXING','ACTIVE','NEEDS_ATTENTION','REJECTED','REVOKED'))""",
    "CREATE INDEX IF NOT EXISTS knowledge_auto_publication_state ON knowledge_auto_publication (tenant_id, state)",
    """CREATE TABLE IF NOT EXISTS knowledge_auto_publication_event (
        id uuid PRIMARY KEY, tenant_id text NOT NULL, version_id uuid NOT NULL,
        at timestamptz NOT NULL DEFAULT clock_timestamp(), from_state text, to_state text NOT NULL,
        actor_id text, detail jsonb)""",
    "CREATE INDEX IF NOT EXISTS knowledge_auto_publication_event_version ON knowledge_auto_publication_event (tenant_id, version_id, at)",
    """CREATE TABLE IF NOT EXISTS knowledge_service_identity (
        tenant_id text NOT NULL, name text NOT NULL, subject_id uuid NOT NULL,
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(), PRIMARY KEY (tenant_id, name))""",
    """CREATE TABLE IF NOT EXISTS rag_v2_index_registry (
        id uuid PRIMARY KEY, tenant_id text NOT NULL, path text NOT NULL, release_id uuid NOT NULL,
        generation integer NOT NULL, policy_generation integer NOT NULL,
        state text NOT NULL CHECK (state IN ('BUILDING','READY','FAILED')), detail text,
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(), ready_at timestamptz)""",
    "CREATE INDEX IF NOT EXISTS rag_v2_index_registry_tenant ON rag_v2_index_registry (tenant_id, created_at DESC)",
    """CREATE TABLE IF NOT EXISTS rag_v2_index_ack (
        tenant_id text NOT NULL, instance_id text NOT NULL, registry_id uuid, loaded_path text,
        valid_until timestamptz NOT NULL, heartbeat_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY (tenant_id, instance_id))""",
)

ACTIVE_STATES = ("PROCESSING", "AWAITING_REVIEW", "READY_TO_PUBLISH", "WAITING_EFFECTIVE", "INDEXING", "NEEDS_ATTENTION")


class AutoPublicationStore:
    def __init__(self, repo):
        self.repo, self._ready = repo, False

    @property
    def tenant(self):
        return self.repo.tenant

    async def ensure(self):
        if self._ready:
            return
        async with self.repo.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("SELECT pg_advisory_xact_lock(hashtext('campus247:auto_publication_schema'))")
                for statement in SCHEMA:
                    await conn.execute(statement)
        self._ready = True

    async def service_identity(self, conn, name):
        """Stable id of a service principal (auto-publisher, crawler); created once per tenant."""
        row = await conn.fetchval("SELECT subject_id FROM knowledge_service_identity WHERE tenant_id=$1 AND name=$2", self.tenant, name)
        if row:
            return str(row)
        await conn.execute("INSERT INTO knowledge_service_identity(tenant_id,name,subject_id) VALUES ($1,$2,$3) ON CONFLICT DO NOTHING",
                           self.tenant, name, generate_uuid7())
        return str(await conn.fetchval("SELECT subject_id FROM knowledge_service_identity WHERE tenant_id=$1 AND name=$2", self.tenant, name))

    async def create(self, conn, *, version_id, source_id, mode, state, author_id, author_role, origin="UPLOAD",
                     attestation=None, flags=(), not_before=None):
        inserted = await conn.fetchval("""INSERT INTO knowledge_auto_publication
            (tenant_id,version_id,source_id,mode,state,author_id,author_role,origin,attestation,flags,not_before)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10::jsonb,$11) ON CONFLICT DO NOTHING RETURNING version_id""",
            self.tenant, version_id, source_id, mode, state, author_id, author_role, origin,
            json.dumps(attestation) if attestation is not None else None, json.dumps(list(flags)), not_before)
        if inserted:
            await self._event(conn, version_id, None, state, author_id, {"mode": mode, "origin": origin})
        return bool(inserted)

    async def _event(self, conn, version_id, from_state, to_state, actor_id, detail):
        await conn.execute("""INSERT INTO knowledge_auto_publication_event(id,tenant_id,version_id,from_state,to_state,actor_id,detail)
            VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb)""", generate_uuid7(), self.tenant, version_id, from_state, to_state,
            actor_id, json.dumps(detail or {}, default=str))

    async def get(self, conn, version_id, *, lock=False):
        row = await conn.fetchrow("SELECT * FROM knowledge_auto_publication WHERE tenant_id=$1 AND version_id=$2"
                                  + (" FOR UPDATE" if lock else ""), self.tenant, version_id)
        return dict(row) if row else None

    async def in_states(self, conn, states, *, limit=200):
        rows = await conn.fetch("""SELECT * FROM knowledge_auto_publication WHERE tenant_id=$1 AND state=ANY($2::text[])
            ORDER BY state_changed_at, version_id LIMIT $3""", self.tenant, list(states), limit)
        return [dict(r) for r in rows]

    async def listing(self, conn, *, author_id=None, limit=200):
        rows = await conn.fetch("""SELECT p.*, x.filename, s.title, s.canonical_uri, v.effective_from
            FROM knowledge_auto_publication p
            JOIN knowledge_ingest_version x ON x.tenant_id=p.tenant_id AND x.version_id=p.version_id
            JOIN document_version v ON v.id=p.version_id JOIN knowledge_source s ON s.id=p.source_id
            WHERE p.tenant_id=$1 AND ($2::uuid IS NULL OR p.author_id=$2) ORDER BY p.created_at DESC LIMIT $3""",
            self.tenant, author_id, limit)
        return [dict(r) for r in rows]

    # --- RAG v2 index registry (built by the worker, loaded by every API process) and per-process acknowledgements
    async def registry_latest_ready(self, conn):
        row = await conn.fetchrow("""SELECT * FROM rag_v2_index_registry WHERE tenant_id=$1 AND state='READY'
            ORDER BY created_at DESC, id DESC LIMIT 1""", self.tenant)
        return dict(row) if row else None

    async def registry_for(self, conn, release_id, generation, policy_generation):
        row = await conn.fetchrow("""SELECT * FROM rag_v2_index_registry WHERE tenant_id=$1 AND state='READY'
            AND release_id=$2 AND generation=$3 AND policy_generation=$4 ORDER BY created_at DESC LIMIT 1""",
            self.tenant, release_id, generation, policy_generation)
        return dict(row) if row else None

    async def registry_building(self, conn, *, max_age_seconds=900):
        row = await conn.fetchrow("""SELECT * FROM rag_v2_index_registry WHERE tenant_id=$1 AND state='BUILDING'
            AND created_at > clock_timestamp() - make_interval(secs => $2) ORDER BY created_at DESC LIMIT 1""",
            self.tenant, float(max_age_seconds))
        return dict(row) if row else None

    async def registry_recent_failures(self, conn, release_id, generation, policy_generation, *, within_seconds=600):
        return await conn.fetchval("""SELECT count(*) FROM rag_v2_index_registry WHERE tenant_id=$1 AND state='FAILED'
            AND release_id=$2 AND generation=$3 AND policy_generation=$4
            AND created_at > clock_timestamp() - make_interval(secs => $5)""",
            self.tenant, release_id, generation, policy_generation, float(within_seconds))

    async def registry_start(self, conn, *, release_id, generation, policy_generation, path):
        identifier = generate_uuid7()
        await conn.execute("""INSERT INTO rag_v2_index_registry(id,tenant_id,path,release_id,generation,policy_generation,state)
            VALUES ($1,$2,$3,$4,$5,$6,'BUILDING')""", identifier, self.tenant, path, release_id, generation, policy_generation)
        return identifier

    async def registry_finish(self, conn, identifier, state, detail=None, *, path=None):
        await conn.execute("""UPDATE rag_v2_index_registry SET state=$2, detail=$3, path=COALESCE($4,path),
            ready_at=CASE WHEN $2='READY' THEN clock_timestamp() ELSE ready_at END WHERE id=$1""",
            identifier, state, detail, path)

    async def registry_adopt_baseline(self, conn, *, release_id, generation, policy_generation, path):
        """Record the index the runtime was started with, once, when it provably matches the serving release."""
        if await conn.fetchval("SELECT count(*) FROM rag_v2_index_registry WHERE tenant_id=$1", self.tenant):
            return None
        identifier = generate_uuid7()
        await conn.execute("""INSERT INTO rag_v2_index_registry(id,tenant_id,path,release_id,generation,policy_generation,state,detail,ready_at)
            VALUES ($1,$2,$3,$4,$5,$6,'READY','baseline',clock_timestamp())""", identifier, self.tenant, path, release_id,
            generation, policy_generation)
        return identifier

    async def ack_instance(self, conn, instance_id, registry_id, loaded_path, *, ttl_seconds=30):
        await conn.execute("""INSERT INTO rag_v2_index_ack(tenant_id,instance_id,registry_id,loaded_path,valid_until)
            VALUES ($1,$2,$3,$4,clock_timestamp() + make_interval(secs => $5))
            ON CONFLICT (tenant_id,instance_id) DO UPDATE SET registry_id=EXCLUDED.registry_id,
            loaded_path=EXCLUDED.loaded_path, valid_until=EXCLUDED.valid_until, heartbeat_at=clock_timestamp()""",
            self.tenant, instance_id, registry_id, loaded_path, float(ttl_seconds))

    async def acks(self, conn):
        """(ever_seen, live) acknowledgements: no row ever means no v2 API is attached to this tenant."""
        rows = await conn.fetch("""SELECT instance_id, registry_id, loaded_path, valid_until > clock_timestamp() AS live
            FROM rag_v2_index_ack WHERE tenant_id=$1""", self.tenant)
        return [dict(r) for r in rows]

    async def transition(self, conn, version_id, to_state, *, from_states=None, actor_id=None, detail=None, **fields):
        """Guarded state change plus an event row; returns False when the row is not in an expected state."""
        current = await self.get(conn, version_id, lock=True)
        if not current or (from_states is not None and current["state"] not in from_states):
            return False
        assignments, values = ["state=$3", "updated_at=clock_timestamp()"], [self.tenant, version_id, to_state]
        if to_state != current["state"]:
            assignments.append("state_changed_at=clock_timestamp()")
        for name, value in fields.items():
            values.append(json.dumps(value, default=str) if name in {"checks", "flags", "attestation"} else value)
            assignments.append(f"{name}=${len(values)}" + ("::jsonb" if name in {"checks", "flags", "attestation"} else ""))
        await conn.execute(f"UPDATE knowledge_auto_publication SET {', '.join(assignments)} WHERE tenant_id=$1 AND version_id=$2", *values)
        await self._event(conn, version_id, current["state"], to_state, actor_id, detail)
        return True
