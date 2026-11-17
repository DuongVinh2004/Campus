"""Append-only source-bound prose corrections and independent technical review."""
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = depends_on = None


def upgrade():
    op.execute("""CREATE TABLE knowledge_rendition_correction (
        id uuid PRIMARY KEY, tenant_id text NOT NULL, source_version_id uuid NOT NULL,
        source_revision integer NOT NULL CHECK(source_revision>0), original_id uuid NOT NULL, base_rendition_id uuid NOT NULL,
        proposal_id uuid NOT NULL, proposal_sha256 varchar(64) NOT NULL CHECK(proposal_sha256 ~ '^[0-9a-f]{64}$'),
        parser_config_sha256 varchar(64) NOT NULL CHECK(parser_config_sha256 ~ '^[0-9a-f]{64}$'),
        pages jsonb NOT NULL CHECK(jsonb_typeof(pages)='array'), note text NOT NULL CHECK(length(note) BETWEEN 10 AND 2000),
        created_by uuid NOT NULL, recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(), UNIQUE(tenant_id,id),
        FOREIGN KEY(tenant_id,source_version_id) REFERENCES knowledge_ingest_version(tenant_id,version_id),
        FOREIGN KEY(tenant_id,original_id) REFERENCES knowledge_artifact(tenant_id,id),
        FOREIGN KEY(tenant_id,base_rendition_id) REFERENCES knowledge_artifact(tenant_id,id),
        FOREIGN KEY(tenant_id,proposal_id) REFERENCES knowledge_artifact(tenant_id,id))""")
    op.execute("""CREATE TABLE knowledge_rendition_correction_review (
        id uuid PRIMARY KEY, tenant_id text NOT NULL, correction_id uuid NOT NULL,
        revision integer NOT NULL CHECK(revision>0), verdict text NOT NULL CHECK(verdict IN ('APPROVED','REJECTED')),
        proposal_sha256 varchar(64) NOT NULL CHECK(proposal_sha256 ~ '^[0-9a-f]{64}$'),
        reviewer_id uuid NOT NULL, note text NOT NULL CHECK(length(note) BETWEEN 10 AND 2000),
        recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(), UNIQUE(tenant_id,correction_id,revision),
        FOREIGN KEY(tenant_id,correction_id) REFERENCES knowledge_rendition_correction(tenant_id,id))""")
    op.execute("""CREATE TABLE knowledge_rendition_correction_result (
        correction_id uuid PRIMARY KEY, tenant_id text NOT NULL, review_id uuid NOT NULL,
        version_id uuid NOT NULL, rendition_id uuid NOT NULL, rendition_sha256 varchar(64) NOT NULL,
        config_sha256 varchar(64) NOT NULL, recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        FOREIGN KEY(tenant_id,correction_id) REFERENCES knowledge_rendition_correction(tenant_id,id),
        FOREIGN KEY(review_id) REFERENCES knowledge_rendition_correction_review(id),
        FOREIGN KEY(tenant_id,version_id) REFERENCES knowledge_ingest_version(tenant_id,version_id),
        FOREIGN KEY(tenant_id,rendition_id) REFERENCES knowledge_artifact(tenant_id,id))""")
    for table in ("knowledge_rendition_correction","knowledge_rendition_correction_review","knowledge_rendition_correction_result"):
        op.execute(f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION public.rag_manifest_immutable()")


def downgrade():
    raise RuntimeError("0022 is forward-only; preserve proposals, reviews and technical lineage")
