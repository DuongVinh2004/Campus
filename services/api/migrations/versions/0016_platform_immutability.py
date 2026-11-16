"""Protect task-platform originals/locators and serialize release sealing.

Legacy source/chunk rows retain their existing behavior. No row is rewritten.
"""
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = depends_on = None


def upgrade():
    op.execute("""CREATE FUNCTION knowledge_platform_version_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF (NEW.version_id,NEW.tenant_id,NEW.original_id,NEW.filename,NEW.created_by,
              NEW.metadata_sha256,NEW.processor_profile) IS DISTINCT FROM
             (OLD.version_id,OLD.tenant_id,OLD.original_id,OLD.filename,OLD.created_by,
              OLD.metadata_sha256,OLD.processor_profile)
             OR (OLD.rendition_id IS NOT NULL AND (NEW.rendition_id,NEW.rendition_sha256)
                 IS DISTINCT FROM (OLD.rendition_id,OLD.rendition_sha256))
             OR (OLD.revoked_at IS NOT NULL AND NEW.revoked_at IS DISTINCT FROM OLD.revoked_at) THEN
            RAISE EXCEPTION 'immutable original, rendition or revocation; create a new version' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END; $$""")
    op.execute("""CREATE TRIGGER knowledge_platform_version_guard BEFORE UPDATE ON knowledge_ingest_version
        FOR EACH ROW EXECUTE FUNCTION knowledge_platform_version_guard()""")
    op.execute("""CREATE FUNCTION knowledge_platform_source_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF EXISTS(SELECT 1 FROM knowledge_source_scope WHERE source_id=OLD.id)
            AND (NEW.id,NEW.title,NEW.owner_unit,NEW.canonical_uri,NEW.authority_level,NEW.campus_scope,
                 NEW.faculty_scope,NEW.program_scope,NEW.audiences,NEW.is_synthetic) IS DISTINCT FROM
                (OLD.id,OLD.title,OLD.owner_unit,OLD.canonical_uri,OLD.authority_level,OLD.campus_scope,
                 OLD.faculty_scope,OLD.program_scope,OLD.audiences,OLD.is_synthetic) THEN
            RAISE EXCEPTION 'immutable platform source metadata' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END; $$""")
    op.execute("""CREATE TRIGGER knowledge_platform_source_guard BEFORE UPDATE ON knowledge_source
        FOR EACH ROW EXECUTE FUNCTION knowledge_platform_source_guard()""")
    op.execute("""CREATE FUNCTION knowledge_platform_chunk_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF EXISTS(SELECT 1 FROM knowledge_ingest_version WHERE version_id=OLD.document_version_id) THEN
            RAISE EXCEPTION 'immutable platform chunk; create a new version' USING ERRCODE='23514';
          END IF;
          IF TG_OP='DELETE' THEN RETURN OLD; END IF;
          RETURN NEW;
        END; $$""")
    op.execute("""CREATE TRIGGER knowledge_platform_chunk_guard BEFORE UPDATE OR DELETE ON knowledge_chunk
        FOR EACH ROW EXECUTE FUNCTION knowledge_platform_chunk_guard()""")
    # A member insertion and the seal insertion lock the same parent. Separate
    # transactions cannot race a late member into an already prepared release.
    op.execute("""CREATE FUNCTION knowledge_platform_seal_lock() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          PERFORM 1 FROM knowledge_release WHERE id=NEW.release_id FOR UPDATE;
          IF TG_TABLE_NAME='knowledge_release_member' AND EXISTS(
              SELECT 1 FROM knowledge_release_seal WHERE release_id=NEW.release_id) THEN
            RAISE EXCEPTION 'sealed release rejects late membership' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END; $$""")
    for table in ("knowledge_release_member", "knowledge_release_seal"):
        op.execute(f"CREATE TRIGGER knowledge_platform_seal_lock BEFORE INSERT ON {table} "
                   "FOR EACH ROW EXECUTE FUNCTION knowledge_platform_seal_lock()")


def downgrade():
    raise RuntimeError("0016 is additive and forward-only; preserve originals and releases")
