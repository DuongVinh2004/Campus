"""Persist class-wide explanations on an exact session and rendition."""
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = depends_on = None


def upgrade():
    op.execute("""CREATE TABLE learning.page_explanations (
        tenant_id text NOT NULL REFERENCES learning.tenant_state(tenant_id),
        record_key text NOT NULL,
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload) = 'object'),
        session_id text GENERATED ALWAYS AS (payload->>'session_id') STORED NOT NULL,
        offering_id text GENERATED ALWAYS AS (payload->>'offering_id') STORED NOT NULL,
        material_id text GENERATED ALWAYS AS (payload->>'material_id') STORED NOT NULL,
        version_id text GENERATED ALWAYS AS (payload->>'version_id') STORED NOT NULL,
        source_key text GENERATED ALWAYS AS (payload->>'source_key') STORED NOT NULL,
        link_key text GENERATED ALWAYS AS ((payload->>'session_id') || ':' || (payload->>'material_id')) STORED NOT NULL,
        PRIMARY KEY (tenant_id, record_key),
        CHECK (COALESCE((payload->>'page_no')::integer BETWEEN 1 AND 500, false)),
        CHECK (COALESCE(payload->>'status' IN ('DRAFT', 'PUBLISHED'), false)),
        CHECK (COALESCE(payload->>'category' IN ('RETEACH', 'ADD_EXAMPLE', 'CORRECTION'), false)),
        FOREIGN KEY (tenant_id, session_id, offering_id)
            REFERENCES learning.sessions(tenant_id, record_key, offering_id) DEFERRABLE INITIALLY DEFERRED,
        FOREIGN KEY (tenant_id, version_id, offering_id)
            REFERENCES learning.versions(tenant_id, record_key, offering_id) DEFERRABLE INITIALLY DEFERRED,
        FOREIGN KEY (tenant_id, version_id, material_id)
            REFERENCES learning.versions(tenant_id, record_key, material_id) DEFERRABLE INITIALLY DEFERRED,
        FOREIGN KEY (tenant_id, version_id, source_key)
            REFERENCES learning.versions(tenant_id, record_key, feedback_source_key) DEFERRABLE INITIALLY DEFERRED,
        FOREIGN KEY (tenant_id, link_key, session_id, material_id)
            REFERENCES learning.links(tenant_id, record_key, session_id, material_id) DEFERRABLE INITIALLY DEFERRED
    )""")
    op.execute("CREATE INDEX ix_learning_page_explanations_session ON learning.page_explanations(tenant_id, session_id)")
    op.execute("""CREATE TRIGGER learning_page_explanations_retained BEFORE DELETE ON learning.page_explanations
        FOR EACH ROW EXECUTE FUNCTION learning.prevent_record_removal()""")
    op.execute("""CREATE FUNCTION learning.preserve_page_explanation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.payload->>'status' = 'PUBLISHED'
                OR (NEW.payload - ARRAY['body','category','status','published_at','revision'])
                   IS DISTINCT FROM (OLD.payload - ARRAY['body','category','status','published_at','revision'])
            THEN RAISE EXCEPTION 'learning explanation source and published content are immutable'; END IF;
            RETURN NEW;
        END $$""")
    op.execute("""CREATE TRIGGER learning_page_explanation_immutable BEFORE UPDATE ON learning.page_explanations
        FOR EACH ROW EXECUTE FUNCTION learning.preserve_page_explanation()""")


def downgrade():
    raise RuntimeError("Learning page explanations are retained; migration is forward-only")
