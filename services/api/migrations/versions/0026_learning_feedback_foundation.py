"""Add session-context lookup and private page feedback storage."""
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = depends_on = None


def upgrade():
    op.execute("CREATE INDEX ix_learning_links_material_scope ON learning.links(tenant_id,material_id,offering_id)")
    op.execute("""ALTER TABLE learning.links ADD CONSTRAINT uq_learning_feedback_link
        UNIQUE (tenant_id, record_key, session_id, material_id)""")
    op.execute("""ALTER TABLE learning.versions ADD COLUMN feedback_source_key text GENERATED ALWAYS AS
        (COALESCE(payload->>'rendition_id', 'legacy:' || record_key)) STORED NOT NULL""")
    op.execute("""ALTER TABLE learning.versions ADD CONSTRAINT uq_learning_feedback_source
        UNIQUE (tenant_id, record_key, feedback_source_key)""")
    op.execute("""CREATE TABLE learning.feedback_windows (
        tenant_id text NOT NULL REFERENCES learning.tenant_state(tenant_id),
        record_key text NOT NULL,
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload) = 'object'),
        offering_id text GENERATED ALWAYS AS (payload->>'offering_id') STORED NOT NULL,
        PRIMARY KEY (tenant_id, record_key),
        UNIQUE (tenant_id, record_key, offering_id),
        FOREIGN KEY (tenant_id, record_key, offering_id)
            REFERENCES learning.sessions(tenant_id, record_key, offering_id) DEFERRABLE INITIALLY DEFERRED
    )""")
    op.execute("""CREATE TABLE learning.page_feedback (
        tenant_id text NOT NULL REFERENCES learning.tenant_state(tenant_id),
        record_key text NOT NULL,
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload) = 'object'),
        actor_subject_id text GENERATED ALWAYS AS (payload->>'actor_subject_id') STORED NOT NULL,
        session_id text GENERATED ALWAYS AS (payload->>'session_id') STORED NOT NULL,
        offering_id text GENERATED ALWAYS AS (payload->>'offering_id') STORED NOT NULL,
        material_id text GENERATED ALWAYS AS (payload->>'material_id') STORED NOT NULL,
        version_id text GENERATED ALWAYS AS (payload->>'version_id') STORED NOT NULL,
        source_key text GENERATED ALWAYS AS (payload->>'source_key') STORED NOT NULL,
        link_key text GENERATED ALWAYS AS ((payload->>'session_id') || ':' || (payload->>'material_id')) STORED NOT NULL,
        page_no integer GENERATED ALWAYS AS ((payload->>'page_no')::integer) STORED NOT NULL,
        category text GENERATED ALWAYS AS (payload->>'category') STORED NOT NULL,
        status text GENERATED ALWAYS AS (payload->>'status') STORED NOT NULL,
        revision integer GENERATED ALWAYS AS ((payload->>'revision')::integer) STORED NOT NULL,
        PRIMARY KEY (tenant_id, record_key),
        UNIQUE (tenant_id, actor_subject_id, version_id, page_no),
        CHECK (page_no BETWEEN 1 AND 500 AND revision >= 1),
        CHECK (category IN ('HARD_TO_UNDERSTAND', 'NEED_EXAMPLE', 'POSSIBLE_ERROR')),
        CHECK (status IN ('ACTIVE', 'WITHDRAWN')),
        FOREIGN KEY (tenant_id, session_id, offering_id)
            REFERENCES learning.feedback_windows(tenant_id, record_key, offering_id) DEFERRABLE INITIALLY DEFERRED,
        FOREIGN KEY (tenant_id, version_id, offering_id)
            REFERENCES learning.versions(tenant_id, record_key, offering_id) DEFERRABLE INITIALLY DEFERRED,
        FOREIGN KEY (tenant_id, version_id, material_id)
            REFERENCES learning.versions(tenant_id, record_key, material_id) DEFERRABLE INITIALLY DEFERRED,
        FOREIGN KEY (tenant_id, version_id, source_key)
            REFERENCES learning.versions(tenant_id, record_key, feedback_source_key) DEFERRABLE INITIALLY DEFERRED,
        FOREIGN KEY (tenant_id, link_key, session_id, material_id)
            REFERENCES learning.links(tenant_id, record_key, session_id, material_id) DEFERRABLE INITIALLY DEFERRED
    )""")
    op.execute("CREATE INDEX ix_learning_page_feedback_session ON learning.page_feedback(tenant_id, session_id)")
    for table in ("feedback_windows", "page_feedback"):
        op.execute(f"""CREATE TRIGGER learning_{table}_retained BEFORE DELETE ON learning.{table}
            FOR EACH ROW EXECUTE FUNCTION learning.prevent_record_removal()""")
    op.execute("""CREATE FUNCTION learning.preserve_page_feedback_source() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF ROW(NEW.payload->>'actor_subject_id', NEW.payload->>'session_id', NEW.payload->>'offering_id',
                   NEW.payload->>'material_id', NEW.payload->>'version_id', NEW.payload->>'source_key', NEW.payload->>'page_no')
                IS DISTINCT FROM
               ROW(OLD.payload->>'actor_subject_id', OLD.payload->>'session_id', OLD.payload->>'offering_id',
                   OLD.payload->>'material_id', OLD.payload->>'version_id', OLD.payload->>'source_key', OLD.payload->>'page_no')
            THEN RAISE EXCEPTION 'learning page feedback attribution is immutable'; END IF;
            RETURN NEW;
        END $$""")
    op.execute("""CREATE TRIGGER learning_page_feedback_source_immutable BEFORE UPDATE ON learning.page_feedback
        FOR EACH ROW EXECUTE FUNCTION learning.preserve_page_feedback_source()""")


def downgrade():
    raise RuntimeError("Learning feedback and attribution are retained; migration is forward-only")
