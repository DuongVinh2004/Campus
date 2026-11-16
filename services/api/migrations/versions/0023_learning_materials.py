"""Normalized learning entities with tenant/class FKs and immutable PDF byte refs.

Metadata payloads preserve forward-compatible UI fields. Generated relational
columns enforce scope and invariants independently of application checks.
"""
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS learning")
    op.execute("""CREATE TABLE learning.tenant_state (
        tenant_id text PRIMARY KEY CHECK(length(tenant_id)>0),
        revision bigint NOT NULL CHECK(revision>0),
        updated_at timestamptz NOT NULL DEFAULT clock_timestamp())""")
    entities = ("terms", "courses", "offerings", "members", "sessions", "materials", "blobs", "links", "versions", "uploads", "reader_states", "bookmarks", "previews", "receipts", "notifications", "audit", "jobs", "outbox", "annotations", "questions", "replies", "reading_instructions", "presentations")
    columns = {
        "courses": {"code": "text"},
        "offerings": {"course_id": "text", "term_id": "text", "section_code": "text"},
        "members": {"offering_id": "text", "actor_subject_id": "text", "role": "text"},
        "sessions": {"offering_id": "text", "sequence_no": "integer"},
        "materials": {"offering_id": "text", "current_published_version_id": "text"},
        "blobs": {"storage_key": "text", "sha256": "text", "byte_size": "bigint"},
        "versions": {"material_id": "text", "offering_id": "text", "blob_id": "text", "version_no": "integer", "storage_key": "text", "sha256": "text", "byte_size": "bigint"},
        "links": {"session_id": "text", "material_id": "text", "offering_id": "text"},
        "uploads": {"material_id": "text", "offering_id": "text"},
        "reader_states": {"version_id": "text"},
        "bookmarks": {"version_id": "text"},
        "notifications": {"version_id": "text", "offering_id": "text", "event_id": "text"},
        "annotations": {"version_id": "text"},
        "questions": {"version_id": "text"},
        "replies": {"question_id": "text"},
        "reading_instructions": {"session_id": "text", "version_id": "text", "offering_id": "text"},
        "presentations": {"version_id": "text", "offering_id": "text"},
    }
    for entity in entities:
        extras = []
        for name, sql_type in columns.get(entity, {}).items():
            expr = f"(payload->>'{name}')" + (f"::{sql_type}" if sql_type != "text" else "")
            nullable = "" if name == "current_published_version_id" else " NOT NULL"
            extras.append(f"{name} {sql_type} GENERATED ALWAYS AS ({expr}) STORED{nullable}")
        suffix = "," + ",".join(extras) if extras else ""
        op.execute(f"""CREATE TABLE learning.{entity} (
            tenant_id text NOT NULL REFERENCES learning.tenant_state(tenant_id),
            record_key text NOT NULL CHECK(length(record_key) BETWEEN 1 AND 512),
            payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
            PRIMARY KEY(tenant_id,record_key){suffix})""")
    def constraint(table, name, expression):
        op.execute(f"ALTER TABLE learning.{table} ADD CONSTRAINT {name} {expression}")
    def fk(table, field, parent):
        constraint(table, f"fk_{table}_{field}", f"FOREIGN KEY(tenant_id,{field}) REFERENCES learning.{parent}(tenant_id,record_key) DEFERRABLE INITIALLY DEFERRED")
    constraint("courses", "uq_learning_course_code", "UNIQUE(tenant_id,code) DEFERRABLE INITIALLY DEFERRED")
    constraint("offerings", "uq_learning_offering", "UNIQUE(tenant_id,course_id,term_id,section_code) DEFERRABLE INITIALLY DEFERRED")
    constraint("members", "uq_learning_member", "UNIQUE(tenant_id,offering_id,actor_subject_id) DEFERRABLE INITIALLY DEFERRED")
    constraint("sessions", "uq_learning_session_order", "UNIQUE(tenant_id,offering_id,sequence_no) DEFERRABLE INITIALLY DEFERRED")
    constraint("sessions", "ck_learning_session_order", "CHECK(sequence_no>0)")
    constraint("versions", "uq_learning_version_no", "UNIQUE(tenant_id,material_id,version_no) DEFERRABLE INITIALLY DEFERRED")
    constraint("versions", "ck_learning_version_integrity", "CHECK(version_no>0 AND byte_size>0 AND sha256 ~ '^[0-9a-f]{64}$')")
    constraint("links", "uq_learning_link", "UNIQUE(tenant_id,session_id,material_id) DEFERRABLE INITIALLY DEFERRED")
    for table in ("sessions", "materials"):
        constraint(table, f"uq_learning_{table}_scope", "UNIQUE(tenant_id,record_key,offering_id)")
    constraint("versions", "uq_learning_version_material", "UNIQUE(tenant_id,record_key,material_id)")
    constraint("versions", "uq_learning_version_scope", "UNIQUE(tenant_id,record_key,offering_id)")
    constraint("blobs", "uq_learning_blob_identity", "UNIQUE(tenant_id,record_key,sha256,byte_size,storage_key)")
    fk("offerings", "course_id", "courses")
    fk("offerings", "term_id", "terms")
    for table in ("members", "sessions", "materials", "uploads", "notifications", "presentations", "reading_instructions"):
        fk(table, "offering_id", "offerings")
    constraint("versions", "fk_learning_version_material_scope", "FOREIGN KEY(tenant_id,material_id,offering_id) REFERENCES learning.materials(tenant_id,record_key,offering_id) DEFERRABLE INITIALLY DEFERRED")
    constraint("materials", "fk_learning_current_version", "FOREIGN KEY(tenant_id,current_published_version_id,record_key) REFERENCES learning.versions(tenant_id,record_key,material_id) DEFERRABLE INITIALLY DEFERRED")
    for field, parent in (("session_id", "sessions"), ("material_id", "materials")):
        constraint("links", f"fk_learning_link_{field}_scope", f"FOREIGN KEY(tenant_id,{field},offering_id) REFERENCES learning.{parent}(tenant_id,record_key,offering_id) DEFERRABLE INITIALLY DEFERRED")
    fk("uploads", "material_id", "materials")
    fk("versions", "blob_id", "blobs")
    constraint("versions", "fk_learning_version_blob_identity", "FOREIGN KEY(tenant_id,blob_id,sha256,byte_size,storage_key) REFERENCES learning.blobs(tenant_id,record_key,sha256,byte_size,storage_key) DEFERRABLE INITIALLY DEFERRED")
    constraint("uploads", "fk_learning_upload_material_scope", "FOREIGN KEY(tenant_id,material_id,offering_id) REFERENCES learning.materials(tenant_id,record_key,offering_id) DEFERRABLE INITIALLY DEFERRED")
    constraint("notifications", "fk_learning_notification_version_scope", "FOREIGN KEY(tenant_id,version_id,offering_id) REFERENCES learning.versions(tenant_id,record_key,offering_id) DEFERRABLE INITIALLY DEFERRED")
    fk("notifications", "event_id", "outbox")
    for table in ("reader_states", "bookmarks", "annotations", "questions", "notifications"):
        fk(table, "version_id", "versions")
    fk("replies", "question_id", "questions")
    fk("reading_instructions", "session_id", "sessions")
    fk("reading_instructions", "version_id", "versions")
    constraint("reading_instructions", "fk_learning_instruction_session_scope", "FOREIGN KEY(tenant_id,session_id,offering_id) REFERENCES learning.sessions(tenant_id,record_key,offering_id) DEFERRABLE INITIALLY DEFERRED")
    constraint("reading_instructions", "fk_learning_instruction_version_scope", "FOREIGN KEY(tenant_id,version_id,offering_id) REFERENCES learning.versions(tenant_id,record_key,offering_id) DEFERRABLE INITIALLY DEFERRED")
    constraint("presentations", "fk_learning_presentation_scope", "FOREIGN KEY(tenant_id,version_id,offering_id) REFERENCES learning.versions(tenant_id,record_key,offering_id) DEFERRABLE INITIALLY DEFERRED")
    for table in ("members", "sessions", "materials", "uploads", "notifications", "presentations", "reading_instructions"):
        op.execute(f"CREATE INDEX ix_learning_{table}_offering ON learning.{table}(tenant_id,offering_id)")
    op.execute("""CREATE FUNCTION learning.preserve_version_blob() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'learning versions are retained'; END IF;
          IF NEW.payload->>'storage_key' IS DISTINCT FROM OLD.payload->>'storage_key'
             OR NEW.payload->>'sha256' IS DISTINCT FROM OLD.payload->>'sha256'
             OR NEW.payload->>'byte_size' IS DISTINCT FROM OLD.payload->>'byte_size'
             OR NEW.payload->>'material_id' IS DISTINCT FROM OLD.payload->>'material_id'
             OR NEW.payload->>'offering_id' IS DISTINCT FROM OLD.payload->>'offering_id'
             OR NEW.payload->>'version_no' IS DISTINCT FROM OLD.payload->>'version_no'
          THEN RAISE EXCEPTION 'learning version blob is immutable'; END IF;
          RETURN NEW;
        END $$""")
    op.execute("CREATE TRIGGER learning_version_blob_immutable BEFORE UPDATE OR DELETE ON learning.versions FOR EACH ROW EXECUTE FUNCTION learning.preserve_version_blob()")
    op.execute("""CREATE FUNCTION learning.prevent_record_removal() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'learning records are retained'; END $$""")
    for entity in entities:
        op.execute(f"CREATE TRIGGER learning_{entity}_retained BEFORE DELETE ON learning.{entity} FOR EACH ROW EXECUTE FUNCTION learning.prevent_record_removal()")
    for entity in ("blobs", "audit"):
        op.execute(f"CREATE TRIGGER learning_{entity}_immutable BEFORE UPDATE ON learning.{entity} FOR EACH ROW EXECUTE FUNCTION learning.prevent_record_removal()")


def downgrade():
    raise RuntimeError("Learning storage is forward-only; retain materials and evidence")
