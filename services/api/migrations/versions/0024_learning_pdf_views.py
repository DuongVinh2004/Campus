"""Bind immutable web PDF views to their original blob without replacing original data."""
from alembic import op

revision = '0024'
down_revision = '0023'
branch_labels = depends_on = None


def upgrade():
    op.execute("ALTER TABLE learning.blobs ADD COLUMN derived_from_blob_id text GENERATED ALWAYS AS (payload->>'derived_from_blob_id') STORED")
    op.execute("ALTER TABLE learning.blobs ADD CONSTRAINT fk_learning_blob_derivation FOREIGN KEY(tenant_id,derived_from_blob_id) REFERENCES learning.blobs(tenant_id,record_key) DEFERRABLE INITIALLY DEFERRED")
    op.execute("ALTER TABLE learning.blobs ADD CONSTRAINT uq_learning_derived_blob UNIQUE(tenant_id,record_key,derived_from_blob_id)")
    op.execute("ALTER TABLE learning.versions ADD COLUMN view_blob_id text GENERATED ALWAYS AS (payload->>'view_blob_id') STORED")
    op.execute("ALTER TABLE learning.versions ADD CONSTRAINT fk_learning_view_source FOREIGN KEY(tenant_id,view_blob_id,blob_id) REFERENCES learning.blobs(tenant_id,record_key,derived_from_blob_id) DEFERRABLE INITIALLY DEFERRED")
    op.execute("""CREATE FUNCTION learning.preserve_ready_view() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.payload->>'processing_state' = 'READY'
             AND NEW.payload->>'view_blob_id' IS DISTINCT FROM OLD.payload->>'view_blob_id'
          THEN RAISE EXCEPTION 'published PDF view is immutable'; END IF;
          RETURN NEW;
        END $$""")
    op.execute("CREATE TRIGGER learning_ready_view_immutable BEFORE UPDATE ON learning.versions FOR EACH ROW EXECUTE FUNCTION learning.preserve_ready_view()")


def downgrade():
    raise RuntimeError('PDF views and originals are retained; this migration is forward-only')
