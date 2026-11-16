"""Add durable ingestion and release membership; preserve existing knowledge data.

Per-document vectors/manifests reuse 0002/0011/0013. A release can contain many
immutable document indexes; it does not reassign a document to the latest batch.
"""
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = depends_on = None

STATEMENTS = [
    """CREATE TABLE knowledge_artifact (
        id uuid PRIMARY KEY, tenant_id text NOT NULL, object_key text NOT NULL UNIQUE,
        sha256 varchar(64) NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
        byte_size bigint NOT NULL CHECK (byte_size >= 0 AND byte_size <= 104857600),
        media_type text NOT NULL, kind text NOT NULL,
        created_at timestamptz NOT NULL DEFAULT clock_timestamp())""",
    """CREATE TABLE knowledge_source_scope (
        source_id uuid PRIMARY KEY REFERENCES knowledge_source(id),
        tenant_id text NOT NULL, created_by uuid NOT NULL,
        UNIQUE (tenant_id, source_id))""",
    """CREATE TABLE knowledge_ingest_version (
        version_id uuid PRIMARY KEY REFERENCES document_version(id),
        tenant_id text NOT NULL, original_id uuid NOT NULL REFERENCES knowledge_artifact(id),
        filename text NOT NULL, created_by uuid NOT NULL,
        metadata_sha256 varchar(64) NOT NULL, rendition_id uuid REFERENCES knowledge_artifact(id),
        rendition_sha256 varchar(64), processor_profile text NOT NULL,
        review_state text NOT NULL DEFAULT 'DRAFT'
            CHECK (review_state IN ('DRAFT','NEEDS_REVIEW','APPROVED','REJECTED')),
        revoked_at timestamptz, revision integer NOT NULL DEFAULT 1 CHECK (revision > 0),
        UNIQUE (tenant_id, version_id))""",
    """CREATE TABLE knowledge_ingestion_job (
        id uuid PRIMARY KEY, tenant_id text NOT NULL,
        version_id uuid NOT NULL UNIQUE REFERENCES knowledge_ingest_version(version_id),
        state text NOT NULL DEFAULT 'QUEUED'
            CHECK (state IN ('QUEUED','RUNNING','RETRY_WAIT','SUCCEEDED','FAILED','CANCELLED')),
        stage text NOT NULL DEFAULT 'EXTRACT', progress integer NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
        attempts integer NOT NULL DEFAULT 0, fencing_token bigint NOT NULL DEFAULT 0,
        lease_owner text, lease_until timestamptz, heartbeat_at timestamptz,
        next_attempt_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        cancel_requested boolean NOT NULL DEFAULT false, error_code text,
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        updated_at timestamptz NOT NULL DEFAULT clock_timestamp())""",
    "CREATE INDEX ix_knowledge_jobs_poll ON knowledge_ingestion_job (next_attempt_at, created_at) WHERE state IN ('QUEUED','RUNNING','RETRY_WAIT')",
    """CREATE TABLE knowledge_job_step (
        job_id uuid NOT NULL REFERENCES knowledge_ingestion_job(id), stage text NOT NULL,
        input_sha256 varchar(64) NOT NULL, config_sha256 varchar(64) NOT NULL,
        output_sha256 varchar(64) NOT NULL, artifact_id uuid REFERENCES knowledge_artifact(id),
        result jsonb NOT NULL, completed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(job_id, stage, input_sha256, config_sha256))""",
    """CREATE TABLE knowledge_review (
        id uuid PRIMARY KEY, version_id uuid NOT NULL REFERENCES knowledge_ingest_version(version_id),
        reviewer_id uuid NOT NULL, verdict text NOT NULL CHECK (verdict IN ('APPROVED','REJECTED')),
        rendition_sha256 varchar(64) NOT NULL, metadata_sha256 varchar(64) NOT NULL,
        note text NOT NULL CHECK(length(btrim(note)) > 0),
        created_at timestamptz NOT NULL DEFAULT clock_timestamp())""",
    """CREATE TABLE knowledge_release (
        id uuid PRIMARY KEY, tenant_id text NOT NULL, campus_id text NOT NULL,
        predecessor_id uuid REFERENCES knowledge_release(id), profile jsonb NOT NULL,
        membership_sha256 varchar(64) NOT NULL, created_by uuid NOT NULL,
        created_at timestamptz NOT NULL DEFAULT clock_timestamp())""",
    """CREATE TABLE knowledge_release_member (
        release_id uuid NOT NULL REFERENCES knowledge_release(id),
        source_id uuid NOT NULL REFERENCES knowledge_source(id),
        version_id uuid NOT NULL REFERENCES knowledge_ingest_version(version_id),
        index_version varchar(128) NOT NULL REFERENCES embedding_index_manifest(index_version),
        rendition_sha256 varchar(64) NOT NULL, metadata_sha256 varchar(64) NOT NULL,
        PRIMARY KEY(release_id, source_id), UNIQUE(release_id, version_id))""",
    """CREATE TABLE knowledge_release_seal (
        release_id uuid PRIMARY KEY REFERENCES knowledge_release(id),
        sealed_at timestamptz NOT NULL DEFAULT clock_timestamp())""",
    """CREATE TABLE knowledge_release_pointer (
        tenant_id text NOT NULL, campus_id text NOT NULL,
        release_id uuid REFERENCES knowledge_release(id), generation bigint NOT NULL DEFAULT 0,
        policy_generation bigint NOT NULL DEFAULT 0,
        updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(tenant_id, campus_id))""",
    """CREATE TABLE knowledge_runtime_ack (
        tenant_id text NOT NULL, campus_id text NOT NULL, instance_id text NOT NULL, boot_id uuid NOT NULL,
        release_id uuid REFERENCES knowledge_release(id), generation bigint NOT NULL,
        policy_generation bigint NOT NULL, valid_until timestamptz NOT NULL,
        error_code text, heartbeat_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(tenant_id, campus_id, instance_id))""",
    """CREATE TABLE knowledge_platform_request (
        tenant_id text NOT NULL, actor_id uuid NOT NULL, request_key text NOT NULL,
        fingerprint varchar(64) NOT NULL, result jsonb NOT NULL,
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(tenant_id, actor_id, request_key))""",
    """CREATE TABLE knowledge_release_preview (
        id uuid PRIMARY KEY, tenant_id text NOT NULL, actor_id uuid NOT NULL,
        session_id text NOT NULL, preview jsonb NOT NULL,
        consumed_at timestamptz)""",
    """CREATE FUNCTION knowledge_member_sealed_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF EXISTS (SELECT 1 FROM knowledge_release_seal WHERE release_id = NEW.release_id) THEN
            RAISE EXCEPTION 'release membership is sealed' USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END; $$""",
    """CREATE TRIGGER knowledge_member_no_late_insert BEFORE INSERT ON knowledge_release_member
        FOR EACH ROW EXECUTE FUNCTION knowledge_member_sealed_guard()""",
]


def upgrade():
    for statement in STATEMENTS:
        op.execute(statement)
    # Reuse the existing immutable-snapshot protection; do not alter old guards.
    for table in ("knowledge_artifact", "knowledge_source_scope", "knowledge_job_step",
                  "knowledge_review", "knowledge_release", "knowledge_release_member", "knowledge_release_seal"):
        op.execute(f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
                   "FOR EACH ROW EXECUTE FUNCTION public.rag_manifest_immutable()")


def downgrade():
    raise RuntimeError("0015 is additive and forward-only; preserve originals, jobs and releases")
