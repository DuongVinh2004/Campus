"""Draft intake and explicit edition lineage; retain existing sources and guards."""
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = depends_on = None


STATEMENTS = [
    "ALTER TABLE knowledge_artifact ADD CONSTRAINT knowledge_artifact_tenant_id UNIQUE(tenant_id,id)",
    """CREATE TABLE knowledge_document_edition (
        id uuid PRIMARY KEY, tenant_id text NOT NULL, source_id uuid NOT NULL,
        identity jsonb NOT NULL CHECK(jsonb_typeof(identity)='object'),
        identity_sha256 varchar(64) NOT NULL CHECK(identity_sha256 ~ '^[0-9a-f]{64}$'),
        created_by uuid NOT NULL, recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        UNIQUE(tenant_id,id),
        FOREIGN KEY(tenant_id,source_id) REFERENCES knowledge_source_scope(tenant_id,source_id))""",
    """CREATE TABLE knowledge_intake (
        id uuid PRIMARY KEY, tenant_id text NOT NULL, original_id uuid NOT NULL,
        filename text NOT NULL CHECK(length(filename) BETWEEN 1 AND 200),
        hints jsonb NOT NULL CHECK(jsonb_typeof(hints)='object'),
        created_by uuid NOT NULL, observed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        UNIQUE(tenant_id,id),
        FOREIGN KEY(tenant_id,original_id) REFERENCES knowledge_artifact(tenant_id,id))""",
    """CREATE TABLE knowledge_intake_resolution (
        intake_id uuid PRIMARY KEY, tenant_id text NOT NULL, version_id uuid NOT NULL,
        expected_revision integer NOT NULL CHECK(expected_revision=1),
        metadata_sha256 varchar(64) NOT NULL CHECK(metadata_sha256 ~ '^[0-9a-f]{64}$'),
        resolved_by uuid NOT NULL, recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        FOREIGN KEY(tenant_id,intake_id) REFERENCES knowledge_intake(tenant_id,id),
        FOREIGN KEY(tenant_id,version_id) REFERENCES knowledge_ingest_version(tenant_id,version_id))""",
    """CREATE TABLE knowledge_version_lineage (
        version_id uuid PRIMARY KEY, tenant_id text NOT NULL, edition_id uuid NOT NULL,
        observation_id uuid NOT NULL, rendition_identity jsonb NOT NULL,
        recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        FOREIGN KEY(tenant_id,version_id) REFERENCES knowledge_ingest_version(tenant_id,version_id),
        FOREIGN KEY(tenant_id,edition_id) REFERENCES knowledge_document_edition(tenant_id,id),
        FOREIGN KEY(tenant_id,observation_id) REFERENCES knowledge_intake(tenant_id,id))""",
    # A draft has no fabricated document_version. The existing durable queue also serves intake.
    "ALTER TABLE knowledge_ingestion_job ADD COLUMN intake_id uuid UNIQUE",
    "ALTER TABLE knowledge_ingestion_job ALTER COLUMN version_id DROP NOT NULL",
    "ALTER TABLE knowledge_ingestion_job ADD CONSTRAINT knowledge_job_target CHECK(version_id IS NOT NULL OR intake_id IS NOT NULL)",
    "ALTER TABLE knowledge_ingestion_job ADD CONSTRAINT knowledge_job_intake_tenant FOREIGN KEY(tenant_id,intake_id) REFERENCES knowledge_intake(tenant_id,id)",
    "ALTER TABLE knowledge_ingestion_job DROP CONSTRAINT knowledge_ingestion_job_state_check",
    """ALTER TABLE knowledge_ingestion_job ADD CONSTRAINT knowledge_ingestion_job_state_check
        CHECK(state IN ('QUEUED','RUNNING','RETRY_WAIT','SUCCEEDED','FAILED','CANCELLED','NEEDS_INFORMATION'))""",
    """CREATE TABLE knowledge_intake_issue (
        id uuid PRIMARY KEY, tenant_id text NOT NULL, intake_id uuid NOT NULL,
        code text NOT NULL, fields jsonb NOT NULL CHECK(jsonb_typeof(fields)='array'),
        evidence jsonb NOT NULL CHECK(jsonb_typeof(evidence)='object'),
        recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        FOREIGN KEY(tenant_id,intake_id) REFERENCES knowledge_intake(tenant_id,id))""",
    "CREATE INDEX ix_knowledge_intake_tenant ON knowledge_intake(tenant_id,observed_at DESC)",
]


def upgrade():
    for statement in STATEMENTS:
        op.execute(statement)
    for table in ("knowledge_document_edition", "knowledge_intake", "knowledge_intake_resolution",
                  "knowledge_version_lineage", "knowledge_intake_issue"):
        op.execute(f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
                   "FOR EACH ROW EXECUTE FUNCTION public.rag_manifest_immutable()")


def downgrade():
    raise RuntimeError("0019 is forward-only; preserve intake/original/edition/issue evidence")
