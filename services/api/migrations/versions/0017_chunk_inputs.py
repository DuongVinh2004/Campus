"""Retain full embedding input and parent/legacy locator provenance, additively."""
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = depends_on = None


def upgrade():
    op.execute("""CREATE TABLE knowledge_chunk_input (
        chunk_id uuid PRIMARY KEY REFERENCES knowledge_chunk(id), index_text text NOT NULL,
        input_sha256 varchar(64) NOT NULL CHECK(input_sha256 ~ '^[0-9a-f]{64}$'),
        processor_profile text NOT NULL, provenance jsonb NOT NULL,
        created_at timestamptz NOT NULL DEFAULT clock_timestamp())""")
    op.execute("""CREATE TRIGGER knowledge_chunk_input_immutable BEFORE UPDATE OR DELETE ON knowledge_chunk_input
        FOR EACH ROW EXECUTE FUNCTION public.rag_manifest_immutable()""")


def downgrade():
    raise RuntimeError("0017 is additive and forward-only; retain input hashes and provenance")
