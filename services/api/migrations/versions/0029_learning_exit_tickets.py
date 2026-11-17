"""Keep exit ticket scope, submission identity, and revision history durable."""
from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = depends_on = None


def upgrade():
    op.execute("""CREATE TABLE learning.exit_tickets (
        tenant_id text NOT NULL REFERENCES learning.tenant_state(tenant_id),
        record_key text NOT NULL,
        payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
        session_id text GENERATED ALWAYS AS (payload->>'session_id') STORED NOT NULL,
        offering_id text GENERATED ALWAYS AS (payload->>'offering_id') STORED NOT NULL,
        version_id text GENERATED ALWAYS AS (payload->>'version_id') STORED NOT NULL,
        material_id text GENERATED ALWAYS AS (payload->>'material_id') STORED NOT NULL,
        source_key text GENERATED ALWAYS AS (payload->>'source_key') STORED NOT NULL,
        link_key text GENERATED ALWAYS AS ((payload->>'session_id') || ':' || (payload->>'material_id')) STORED NOT NULL,
        status text GENERATED ALWAYS AS (payload->>'status') STORED NOT NULL,
        published_question_revision integer GENERATED ALWAYS AS ((payload->>'published_question_revision')::integer) STORED,
        PRIMARY KEY (tenant_id, record_key),
        UNIQUE (tenant_id, record_key, offering_id, published_question_revision),
        CHECK (status IN ('DRAFT', 'PUBLISHED', 'CANCELLED')),
        CHECK ((status <> 'DRAFT' OR published_question_revision IS NULL)
            AND (status <> 'PUBLISHED' OR published_question_revision IS NOT NULL)),
        CHECK (COALESCE((payload->>'page_no')::integer BETWEEN 1 AND 500, false)),
        CHECK (COALESCE((payload->>'revision')::integer > 0, false)),
        CHECK (published_question_revision IS NULL OR published_question_revision BETWEEN 1 AND (payload->>'revision')::integer),
        CHECK (COALESCE(char_length(btrim(payload->>'question')) BETWEEN 1 AND 1000, false)),
        CHECK (COALESCE((payload #>> '{opens,utc}')::timestamptz < (payload #>> '{closes,utc}')::timestamptz, false)),
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
    op.execute("CREATE INDEX ix_learning_exit_tickets_session ON learning.exit_tickets(tenant_id, session_id)")
    op.execute("""CREATE TABLE learning.exit_submissions (
        tenant_id text NOT NULL REFERENCES learning.tenant_state(tenant_id),
        record_key text NOT NULL,
        payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
        ticket_id text GENERATED ALWAYS AS (payload->>'ticket_id') STORED NOT NULL,
        offering_id text GENERATED ALWAYS AS (payload->>'offering_id') STORED NOT NULL,
        student_id text GENERATED ALWAYS AS (payload->>'student_id') STORED NOT NULL,
        question_revision integer GENERATED ALWAYS AS ((payload->>'question_revision')::integer) STORED NOT NULL,
        receipt_id text GENERATED ALWAYS AS (payload->>'receipt_id') STORED NOT NULL,
        PRIMARY KEY (tenant_id, record_key),
        UNIQUE (tenant_id, ticket_id, student_id),
        UNIQUE (tenant_id, receipt_id),
        CHECK (record_key = ticket_id || ':' || student_id),
        CHECK (COALESCE(char_length(btrim(payload->>'answer')) BETWEEN 1 AND 1000, false)),
        CHECK (CASE WHEN jsonb_typeof(payload->'history') = 'array'
            THEN COALESCE(jsonb_array_length(payload->'history') = (payload->>'revision')::integer
                AND jsonb_array_length(payload->'history') > 0, false) ELSE false END),
        FOREIGN KEY (tenant_id, ticket_id, offering_id, question_revision)
            REFERENCES learning.exit_tickets(tenant_id, record_key, offering_id, published_question_revision)
            DEFERRABLE INITIALLY DEFERRED
    )""")
    op.execute("""CREATE TABLE learning.exit_reviews (
        tenant_id text NOT NULL REFERENCES learning.tenant_state(tenant_id),
        record_key text NOT NULL,
        payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
        PRIMARY KEY (tenant_id, record_key),
        CHECK (COALESCE(payload->>'ticket_id' = record_key AND (payload->>'revision')::integer > 0, false)),
        FOREIGN KEY (tenant_id, record_key) REFERENCES learning.exit_tickets(tenant_id, record_key)
            DEFERRABLE INITIALLY DEFERRED
    )""")
    for table in ("exit_tickets", "exit_submissions", "exit_reviews"):
        op.execute(f"""CREATE TRIGGER learning_{table}_retained BEFORE DELETE ON learning.{table}
            FOR EACH ROW EXECUTE FUNCTION learning.prevent_record_removal()""")
    op.execute("""CREATE FUNCTION learning.preserve_exit_ticket() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.payload->'id' IS DISTINCT FROM OLD.payload->'id'
                OR NEW.payload->'session_id' IS DISTINCT FROM OLD.payload->'session_id'
                OR NEW.payload->'offering_id' IS DISTINCT FROM OLD.payload->'offering_id'
                OR (NEW.payload->>'revision')::integer IS DISTINCT FROM (OLD.payload->>'revision')::integer + 1
                OR ((NEW.payload->'history') - (-1)) IS DISTINCT FROM COALESCE(OLD.payload->'history', '[]'::jsonb)
                OR OLD.payload->>'status' = 'CANCELLED'
                OR (OLD.payload->>'published_question_revision' IS NOT NULL AND
                    ((NEW.payload - ARRAY['status','closes','revision','history'])
                        IS DISTINCT FROM (OLD.payload - ARRAY['status','closes','revision','history'])
                     OR NEW.payload->>'status' NOT IN ('PUBLISHED', 'CANCELLED')
                     OR (NEW.payload #>> '{closes,utc}')::timestamptz < (OLD.payload #>> '{closes,utc}')::timestamptz))
            THEN RAISE EXCEPTION 'learning exit ticket scope and published question are immutable'; END IF;
            RETURN NEW;
        END $$""")
    op.execute("""CREATE TRIGGER learning_exit_ticket_immutable BEFORE UPDATE ON learning.exit_tickets
        FOR EACH ROW EXECUTE FUNCTION learning.preserve_exit_ticket()""")
    op.execute("""CREATE FUNCTION learning.preserve_exit_submission() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF (NEW.payload - ARRAY['answer','revision','receipt_id','submitted_at','history'])
                   IS DISTINCT FROM (OLD.payload - ARRAY['answer','revision','receipt_id','submitted_at','history'])
                OR (NEW.payload->>'revision')::integer IS DISTINCT FROM (OLD.payload->>'revision')::integer + 1
                OR ((NEW.payload->'history') - (-1)) IS DISTINCT FROM OLD.payload->'history'
            THEN RAISE EXCEPTION 'learning exit submission identity and receipt history are immutable'; END IF;
            RETURN NEW;
        END $$""")
    op.execute("""CREATE TRIGGER learning_exit_submission_immutable BEFORE UPDATE ON learning.exit_submissions
        FOR EACH ROW EXECUTE FUNCTION learning.preserve_exit_submission()""")


def downgrade():
    raise RuntimeError("Exit tickets, submissions, and review history are retained; migration is forward-only")
