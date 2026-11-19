"""Durable state of crawl sources, pages and runs (additive tables, created idempotently like the pipeline tables)."""
from __future__ import annotations

import json

from campus247.domain.shared.values import generate_uuid7

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS knowledge_crawl_source (
        id uuid PRIMARY KEY, tenant_id text NOT NULL, name text NOT NULL CHECK (length(name) BETWEEN 3 AND 160),
        seed_urls jsonb NOT NULL, kind text NOT NULL DEFAULT 'LIST' CHECK (kind IN ('LIST','SITEMAP','PAGE')),
        include jsonb NOT NULL DEFAULT '[]'::jsonb, exclude jsonb NOT NULL DEFAULT '[]'::jsonb,
        max_depth integer NOT NULL DEFAULT 2 CHECK (max_depth BETWEEN 0 AND 4),
        max_pages integer NOT NULL DEFAULT 200 CHECK (max_pages BETWEEN 1 AND 1000),
        interval_hours integer NOT NULL DEFAULT 24 CHECK (interval_hours BETWEEN 1 AND 720),
        owner_unit text NOT NULL, programs jsonb NOT NULL DEFAULT '["PUBLIC"]'::jsonb,
        audiences jsonb NOT NULL DEFAULT '["STUDENT","KNOWLEDGE_ADMIN","SYSTEM_ADMIN"]'::jsonb,
        mode text NOT NULL DEFAULT 'REVIEW' CHECK (mode IN ('REVIEW','DIRECT')),
        active boolean NOT NULL DEFAULT true, ingest_enabled boolean NOT NULL DEFAULT false,
        pending_run text CHECK (pending_run IN ('DRY','RUN')), configured_by uuid NOT NULL, next_run_at timestamptz, last_run_at timestamptz, last_status text,
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(), updated_at timestamptz NOT NULL DEFAULT clock_timestamp())""",
    """CREATE TABLE IF NOT EXISTS knowledge_crawl_page (
        source_id uuid NOT NULL, tenant_id text NOT NULL, url text NOT NULL, kind text NOT NULL, content_sha text,
        etag text, last_modified text, status text NOT NULL, reason text, version_id uuid, knowledge_source_id uuid, title text,
        first_seen_at timestamptz NOT NULL DEFAULT clock_timestamp(), last_seen_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY (source_id, url))""",
    """CREATE TABLE IF NOT EXISTS knowledge_crawl_run (
        id uuid PRIMARY KEY, tenant_id text NOT NULL, source_id uuid NOT NULL, trigger text NOT NULL, dry_run boolean NOT NULL,
        state text NOT NULL CHECK (state IN ('RUNNING','DONE','FAILED')), counts jsonb, decisions jsonb, error text,
        started_at timestamptz NOT NULL DEFAULT clock_timestamp(), finished_at timestamptz)""",
    "CREATE INDEX IF NOT EXISTS knowledge_crawl_run_source ON knowledge_crawl_run (tenant_id, source_id, started_at DESC)",
)


class CrawlStore:
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
                await conn.execute("SELECT pg_advisory_xact_lock(hashtext('campus247:crawl_schema'))")
                for statement in SCHEMA:
                    await conn.execute(statement)
        self._ready = True

    async def create_source(self, conn, *, name, seed_urls, kind, include, exclude, max_depth, max_pages, interval_hours, owner_unit,
                            programs, audiences, mode, configured_by):
        identifier = generate_uuid7()
        await conn.execute("""INSERT INTO knowledge_crawl_source(id,tenant_id,name,seed_urls,kind,include,exclude,max_depth,max_pages,
            interval_hours,owner_unit,programs,audiences,mode,configured_by,next_run_at)
            VALUES ($1,$2,$3,$4::jsonb,$5,$6::jsonb,$7::jsonb,$8,$9,$10,$11,$12::jsonb,$13::jsonb,$14,$15,clock_timestamp())""",
            identifier, self.tenant, name, json.dumps(seed_urls), kind, json.dumps(include), json.dumps(exclude), max_depth, max_pages,
            interval_hours, owner_unit, json.dumps(programs), json.dumps(audiences), mode, configured_by)
        return identifier

    @staticmethod
    def _source(row):
        if row is None:
            return None
        value = dict(row)
        for name in ("seed_urls", "include", "exclude", "programs", "audiences"):
            if isinstance(value[name], str):
                value[name] = json.loads(value[name])
        return value

    async def source(self, conn, identifier):
        return self._source(await conn.fetchrow("SELECT * FROM knowledge_crawl_source WHERE tenant_id=$1 AND id=$2", self.tenant, identifier))

    async def sources(self, conn):
        return [self._source(r) for r in await conn.fetch("SELECT * FROM knowledge_crawl_source WHERE tenant_id=$1 ORDER BY created_at", self.tenant)]

    async def due(self, conn):
        return [self._source(r) for r in await conn.fetch("""SELECT * FROM knowledge_crawl_source WHERE tenant_id=$1 AND active
            AND next_run_at IS NOT NULL AND next_run_at <= clock_timestamp() ORDER BY next_run_at LIMIT 5""", self.tenant)]

    async def update_source(self, conn, identifier, **fields):
        allowed = {"active", "ingest_enabled", "mode", "interval_hours", "max_pages", "max_depth", "name", "next_run_at", "last_run_at", "last_status", "pending_run"}
        assignments, values = ["updated_at=clock_timestamp()"], [self.tenant, identifier]
        for name, value in fields.items():
            if name not in allowed:
                raise ValueError("field not updatable: " + name)
            values.append(value)
            assignments.append(f"{name}=${len(values)}")
        await conn.execute(f"UPDATE knowledge_crawl_source SET {', '.join(assignments)} WHERE tenant_id=$1 AND id=$2", *values)

    async def page(self, conn, source_id, url):
        row = await conn.fetchrow("SELECT * FROM knowledge_crawl_page WHERE source_id=$1 AND url=$2", source_id, url)
        return dict(row) if row else None

    async def pages(self, conn, source_id, *, limit=500):
        return [dict(r) for r in await conn.fetch("SELECT * FROM knowledge_crawl_page WHERE source_id=$1 ORDER BY last_seen_at DESC LIMIT $2", source_id, limit)]

    async def save_page(self, conn, source_id, url, *, kind, status, reason=None, content_sha=None, etag=None, last_modified=None,
                        version_id=None, knowledge_source_id=None, title=None):
        await conn.execute("""INSERT INTO knowledge_crawl_page(source_id,tenant_id,url,kind,content_sha,etag,last_modified,status,reason,version_id,knowledge_source_id,title)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            ON CONFLICT (source_id,url) DO UPDATE SET kind=EXCLUDED.kind, status=EXCLUDED.status, reason=EXCLUDED.reason, last_seen_at=clock_timestamp(),
              content_sha=COALESCE(EXCLUDED.content_sha, knowledge_crawl_page.content_sha), etag=COALESCE(EXCLUDED.etag, knowledge_crawl_page.etag),
              last_modified=COALESCE(EXCLUDED.last_modified, knowledge_crawl_page.last_modified),
              version_id=COALESCE(EXCLUDED.version_id, knowledge_crawl_page.version_id),
              knowledge_source_id=COALESCE(EXCLUDED.knowledge_source_id, knowledge_crawl_page.knowledge_source_id),
              title=COALESCE(EXCLUDED.title, knowledge_crawl_page.title)""",
            source_id, self.tenant, url, kind, content_sha, etag, last_modified, status, reason, version_id, knowledge_source_id, title)

    async def start_run(self, conn, source_id, *, trigger, dry_run):
        identifier = generate_uuid7()
        await conn.execute("INSERT INTO knowledge_crawl_run(id,tenant_id,source_id,trigger,dry_run,state) VALUES ($1,$2,$3,$4,$5,'RUNNING')",
                           identifier, self.tenant, source_id, trigger, dry_run)
        return identifier

    async def finish_run(self, conn, identifier, state, counts, decisions, error=None):
        await conn.execute("""UPDATE knowledge_crawl_run SET state=$2, counts=$3::jsonb, decisions=$4::jsonb, error=$5, finished_at=clock_timestamp() WHERE id=$1""",
                           identifier, state, json.dumps(counts), json.dumps(decisions, default=str), error)

    async def runs(self, conn, source_id, *, limit=20):
        rows = await conn.fetch("SELECT * FROM knowledge_crawl_run WHERE tenant_id=$1 AND source_id=$2 ORDER BY started_at DESC LIMIT $3", self.tenant, source_id, limit)
        result = []
        for row in rows:
            value = dict(row)
            for name in ("counts", "decisions"):
                if isinstance(value[name], str):
                    value[name] = json.loads(value[name])
            result.append(value)
        return result

    async def stale_running(self, conn, source_id, *, minutes=45):
        return await conn.fetchval("""UPDATE knowledge_crawl_run SET state='FAILED', error='interrupted', finished_at=clock_timestamp()
            WHERE tenant_id=$1 AND source_id=$2 AND state='RUNNING' AND started_at < clock_timestamp() - make_interval(mins => $3)
            RETURNING id""", self.tenant, source_id, minutes)
