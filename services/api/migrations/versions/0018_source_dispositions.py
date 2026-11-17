"""Append-only source work classifications; no review or release bypass."""
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = depends_on = None


def upgrade():
    op.execute("""CREATE TABLE knowledge_source_disposition (
        id uuid PRIMARY KEY, tenant_id text NOT NULL,
        source_id uuid NOT NULL REFERENCES knowledge_source(id),
        original_sha256 varchar(64) NOT NULL CHECK(original_sha256 ~ '^[0-9a-f]{64}$'),
        category text NOT NULL CHECK(category IN ('SOURCE_TEXT_AVAILABLE','PARTIAL_SOURCE_TEXT',
            'EQUIVALENT_SOURCE_ALIAS','SOURCE_SCOPE_UNRESOLVED','OCR_REVIEW_REQUIRED','LINKED_ORIGINAL_REQUIRED')),
        related_source_id uuid REFERENCES knowledge_source(id),
        note text NOT NULL CHECK(length(note) BETWEEN 10 AND 4000),
        evidence jsonb NOT NULL, created_by uuid NOT NULL,
        created_at timestamptz NOT NULL DEFAULT clock_timestamp())""")
    op.execute("CREATE INDEX ix_knowledge_source_disposition_latest ON knowledge_source_disposition(tenant_id,source_id,created_at DESC,id DESC)")
    op.execute("""CREATE FUNCTION knowledge_source_disposition_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'source dispositions are append-only' USING ERRCODE='23514'; END; $$""")
    op.execute("""CREATE TRIGGER knowledge_source_disposition_immutable BEFORE UPDATE OR DELETE ON knowledge_source_disposition
        FOR EACH ROW EXECUTE FUNCTION knowledge_source_disposition_immutable()""")


def downgrade():
    raise RuntimeError("0018 is additive and forward-only; preserve classification evidence")
