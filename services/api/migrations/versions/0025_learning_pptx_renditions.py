"""Bind immutable PowerPoint PDF renditions and their source-specific annotations."""
from alembic import op

revision = '0025'
down_revision = '0024'
branch_labels = depends_on = None


def upgrade():
    op.execute("ALTER TABLE learning.versions ADD COLUMN rendition_id text GENERATED ALWAYS AS (payload->>'rendition_id') STORED")
    op.execute("ALTER TABLE learning.versions ADD CONSTRAINT uq_learning_rendition_version UNIQUE(tenant_id,record_key,rendition_id)")
    op.execute("""ALTER TABLE learning.versions ADD CONSTRAINT ck_learning_source_media CHECK(
        COALESCE(payload->>'source_media_type','application/pdf') IN ('application/pdf','application/vnd.openxmlformats-officedocument.presentationml.presentation')
        AND (COALESCE(payload->>'source_media_type','application/pdf')='application/pdf'
             OR payload->>'processing_state'<>'READY' OR (view_blob_id IS NOT NULL AND rendition_id IS NOT NULL)))""")
    for table in ('annotations', 'questions'):
        op.execute(f"ALTER TABLE learning.{table} ADD COLUMN rendition_id text GENERATED ALWAYS AS (payload->>'rendition_id') STORED")
        op.execute(f"ALTER TABLE learning.{table} ADD CONSTRAINT fk_learning_{table}_rendition FOREIGN KEY(tenant_id,version_id,rendition_id) REFERENCES learning.versions(tenant_id,record_key,rendition_id) DEFERRABLE INITIALLY DEFERRED")
    op.execute("""CREATE FUNCTION learning.preserve_rendition_identity() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF NEW.payload->>'source_media_type' IS DISTINCT FROM OLD.payload->>'source_media_type'
           OR (OLD.payload->>'processing_state'='READY' AND NEW.payload->>'rendition_id' IS DISTINCT FROM OLD.payload->>'rendition_id')
        THEN RAISE EXCEPTION 'learning source format and ready rendition are immutable'; END IF;
        RETURN NEW;
      END $$""")
    op.execute("CREATE TRIGGER learning_rendition_identity_immutable BEFORE UPDATE ON learning.versions FOR EACH ROW EXECUTE FUNCTION learning.preserve_rendition_identity()")


def downgrade():
    raise RuntimeError('Original PowerPoint, PDF renditions and anchors are retained; migration is forward-only')
