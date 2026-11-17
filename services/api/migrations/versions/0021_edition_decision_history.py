"""Append-only edition and relation decisions; no serving-policy change."""
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = depends_on = None


def upgrade():
    op.execute("""CREATE TABLE knowledge_edition_decision (
        id uuid PRIMARY KEY, tenant_id text NOT NULL, edition_id uuid NOT NULL,
        revision integer NOT NULL CHECK(revision>0), identity jsonb NOT NULL CHECK(jsonb_typeof(identity)='object'),
        identity_sha256 varchar(64) NOT NULL CHECK(identity_sha256 ~ '^[0-9a-f]{64}$'),
        basis_note text NOT NULL CHECK(length(basis_note) BETWEEN 10 AND 2000), created_by uuid NOT NULL,
        recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(), UNIQUE(tenant_id,edition_id,revision),
        FOREIGN KEY(tenant_id,edition_id) REFERENCES knowledge_document_edition(tenant_id,id))""")
    op.execute("""CREATE TABLE knowledge_edition_relation_decision (
        id uuid PRIMARY KEY, tenant_id text NOT NULL, relation_id uuid NOT NULL,
        revision integer NOT NULL CHECK(revision>0), from_edition uuid NOT NULL, to_edition uuid NOT NULL,
        decision_state text NOT NULL CHECK(decision_state IN ('PROPOSED','VERIFIED','REJECTED')),
        relation jsonb NOT NULL CHECK(jsonb_typeof(relation)='object'),
        relation_sha256 varchar(64) NOT NULL CHECK(relation_sha256 ~ '^[0-9a-f]{64}$'),
        basis_note text NOT NULL CHECK(length(basis_note) BETWEEN 10 AND 2000), created_by uuid NOT NULL,
        recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(), UNIQUE(tenant_id,relation_id,revision),
        CHECK(from_edition<>to_edition),
        FOREIGN KEY(tenant_id,from_edition) REFERENCES knowledge_document_edition(tenant_id,id),
        FOREIGN KEY(tenant_id,to_edition) REFERENCES knowledge_document_edition(tenant_id,id))""")
    for table in ("knowledge_edition_decision", "knowledge_edition_relation_decision"):
        op.execute(f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
                   "FOR EACH ROW EXECUTE FUNCTION public.rag_manifest_immutable()")
    op.execute("CREATE INDEX ix_knowledge_edition_decision_history ON knowledge_edition_decision(tenant_id,edition_id,recorded_at DESC,revision DESC)")
    op.execute("CREATE INDEX ix_knowledge_relation_decision_history ON knowledge_edition_relation_decision(tenant_id,relation_id,recorded_at DESC,revision DESC)")


def downgrade():
    raise RuntimeError("0021 is forward-only; preserve identity and relation decisions")
