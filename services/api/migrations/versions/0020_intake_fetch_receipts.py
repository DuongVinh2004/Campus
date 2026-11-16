"""Append URL acquisition receipts without rewriting intake/original provenance."""
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = depends_on = None


def upgrade():
    op.execute("ALTER TABLE knowledge_intake ALTER COLUMN original_id DROP NOT NULL")
    op.execute("""ALTER TABLE knowledge_intake ADD CONSTRAINT knowledge_intake_origin
        CHECK(original_id IS NOT NULL OR (hints ? 'source_uri' AND jsonb_typeof(hints->'source_uri')='string'
            AND hints->>'source_uri' LIKE 'https://%'))""")
    op.execute("""CREATE TABLE knowledge_intake_fetch (
        intake_id uuid PRIMARY KEY, tenant_id text NOT NULL, original_id uuid NOT NULL,
        acquisition jsonb NOT NULL CHECK(jsonb_typeof(acquisition)='object'),
        recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        FOREIGN KEY(tenant_id,intake_id) REFERENCES knowledge_intake(tenant_id,id),
        FOREIGN KEY(tenant_id,original_id) REFERENCES knowledge_artifact(tenant_id,id))""")
    op.execute("""CREATE TRIGGER knowledge_intake_fetch_immutable BEFORE UPDATE OR DELETE ON knowledge_intake_fetch
        FOR EACH ROW EXECUTE FUNCTION public.rag_manifest_immutable()""")
    op.execute("""ALTER TABLE knowledge_ingestion_job ADD CONSTRAINT knowledge_job_version_tenant
        FOREIGN KEY(tenant_id,version_id) REFERENCES knowledge_ingest_version(tenant_id,version_id)""")


def downgrade():
    raise RuntimeError("0020 is forward-only; retain acquisition receipts")
