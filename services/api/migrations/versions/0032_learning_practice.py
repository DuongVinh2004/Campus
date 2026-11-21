"""Practice questions: lecturer-written question sets per session file, student attempts and spaced-review state.

Same storage shape as the other learning collections (tenant_id, record_key, payload jsonb), so
`PostgresLearningRepository` reads and writes them like the SQLite state (`application/learning/practice_sets.py`).
Generated columns tie every row to its class, session and lecture version; the database refuses what the
application already refuses:
  - a set only changes forward (revision + 1), keeps its identity and source, and is frozen once PUBLISHED
    (only PUBLISHED -> RETIRED is allowed afterwards);
  - a question keeps its identity, set and position, and changes only while its set is a DRAFT;
  - an answer, once recorded, is never changed;
  - nothing is deleted.
Additive only: creates four new learning.* tables, one function and triggers; nothing existing is altered.
"""
from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = depends_on = None

PRACTICE_TABLES = ("practice_sets", "practice_items", "practice_attempts", "practice_reviews")


def upgrade():
    op.execute("""CREATE TABLE learning.practice_sets (
        tenant_id text NOT NULL REFERENCES learning.tenant_state(tenant_id),
        record_key text NOT NULL CHECK(length(record_key) BETWEEN 1 AND 512),
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload) = 'object'),
        session_id text GENERATED ALWAYS AS (payload->>'session_id') STORED NOT NULL,
        offering_id text GENERATED ALWAYS AS (payload->>'offering_id') STORED NOT NULL,
        version_id text GENERATED ALWAYS AS (payload->>'version_id') STORED NOT NULL,
        material_id text GENERATED ALWAYS AS (payload->>'material_id') STORED NOT NULL,
        status text GENERATED ALWAYS AS (payload->>'status') STORED NOT NULL,
        PRIMARY KEY (tenant_id, record_key),
        UNIQUE (tenant_id, record_key, offering_id),
        CHECK (record_key = payload->>'id'),
        CHECK (status IN ('DRAFT', 'PUBLISHED', 'RETIRED')),
        CHECK (COALESCE((payload->>'revision')::integer > 0, false)),
        CHECK (COALESCE(length(btrim(payload->>'title')) BETWEEN 1 AND 200, false)),
        CHECK (COALESCE(length(payload->>'created_by') > 0, false)),
        CHECK (status = 'DRAFT' OR payload ? 'published_at'),
        CONSTRAINT fk_learning_practice_set_session_scope FOREIGN KEY (tenant_id, session_id, offering_id)
            REFERENCES learning.sessions(tenant_id, record_key, offering_id) DEFERRABLE INITIALLY DEFERRED,
        CONSTRAINT fk_learning_practice_set_version_scope FOREIGN KEY (tenant_id, version_id, offering_id)
            REFERENCES learning.versions(tenant_id, record_key, offering_id) DEFERRABLE INITIALLY DEFERRED,
        CONSTRAINT fk_learning_practice_set_version_material FOREIGN KEY (tenant_id, version_id, material_id)
            REFERENCES learning.versions(tenant_id, record_key, material_id) DEFERRABLE INITIALLY DEFERRED
    )""")
    op.execute("""CREATE TABLE learning.practice_items (
        tenant_id text NOT NULL REFERENCES learning.tenant_state(tenant_id),
        record_key text NOT NULL CHECK(length(record_key) BETWEEN 1 AND 512),
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload) = 'object'),
        set_id text GENERATED ALWAYS AS (payload->>'set_id') STORED NOT NULL,
        offering_id text GENERATED ALWAYS AS (payload->>'offering_id') STORED NOT NULL,
        ordinal integer GENERATED ALWAYS AS ((payload->>'ordinal')::integer) STORED NOT NULL,
        kind text GENERATED ALWAYS AS (payload->>'kind') STORED NOT NULL,
        PRIMARY KEY (tenant_id, record_key),
        UNIQUE (tenant_id, record_key, set_id),
        CONSTRAINT uq_learning_practice_item_order UNIQUE (tenant_id, set_id, ordinal) DEFERRABLE INITIALLY DEFERRED,
        CHECK (record_key = payload->>'id'),
        CHECK (ordinal BETWEEN 1 AND 50),
        CHECK (kind IN ('single_choice', 'multi_choice', 'short_answer')),
        CHECK (COALESCE((payload->>'revision')::integer > 0, false)),
        CHECK (COALESCE(length(btrim(payload->>'prompt')) > 0, false)),
        CHECK (CASE WHEN jsonb_typeof(payload->'citations') = 'array'
            THEN jsonb_array_length(payload->'citations') BETWEEN 1 AND 3 ELSE false END),
        CHECK (CASE WHEN jsonb_typeof(payload->'options') = 'array'
            THEN jsonb_array_length(payload->'options') <= 6 ELSE false END),
        CHECK (CASE WHEN kind = 'short_answer'
            THEN jsonb_typeof(payload->'accepted') = 'array' AND jsonb_array_length(payload->'accepted') BETWEEN 1 AND 5
            ELSE jsonb_typeof(payload->'answer') = 'array' AND jsonb_array_length(payload->'answer') >= 1 END),
        CONSTRAINT fk_learning_practice_item_set_scope FOREIGN KEY (tenant_id, set_id, offering_id)
            REFERENCES learning.practice_sets(tenant_id, record_key, offering_id) DEFERRABLE INITIALLY DEFERRED
    )""")
    op.execute("""CREATE TABLE learning.practice_attempts (
        tenant_id text NOT NULL REFERENCES learning.tenant_state(tenant_id),
        record_key text NOT NULL CHECK(length(record_key) BETWEEN 1 AND 512),
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload) = 'object'),
        item_id text GENERATED ALWAYS AS (payload->>'item_id') STORED NOT NULL,
        set_id text GENERATED ALWAYS AS (payload->>'set_id') STORED NOT NULL,
        offering_id text GENERATED ALWAYS AS (payload->>'offering_id') STORED NOT NULL,
        student_id text GENERATED ALWAYS AS (payload->>'student_id') STORED NOT NULL,
        PRIMARY KEY (tenant_id, record_key),
        CHECK (record_key = payload->>'id'),
        CHECK (length(student_id) > 0),
        CHECK (jsonb_typeof(payload->'correct') = 'boolean'),
        CHECK (COALESCE(length(payload->>'at') > 0, false)),
        CONSTRAINT fk_learning_practice_attempt_item FOREIGN KEY (tenant_id, item_id, set_id)
            REFERENCES learning.practice_items(tenant_id, record_key, set_id) DEFERRABLE INITIALLY DEFERRED,
        CONSTRAINT fk_learning_practice_attempt_set_scope FOREIGN KEY (tenant_id, set_id, offering_id)
            REFERENCES learning.practice_sets(tenant_id, record_key, offering_id) DEFERRABLE INITIALLY DEFERRED
    )""")
    # The application keys a review by "<item id>:<student id>"; the two parts become columns so the row is tied to its question.
    op.execute("""CREATE TABLE learning.practice_reviews (
        tenant_id text NOT NULL REFERENCES learning.tenant_state(tenant_id),
        record_key text NOT NULL CHECK(record_key ~ '^[^:]+:[^:]+$' AND length(record_key) <= 512),
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload) = 'object'),
        item_id text GENERATED ALWAYS AS (split_part(record_key, ':', 1)) STORED NOT NULL,
        student_id text GENERATED ALWAYS AS (split_part(record_key, ':', 2)) STORED NOT NULL,
        PRIMARY KEY (tenant_id, record_key),
        CHECK (jsonb_typeof(payload->'ease') = 'number' AND (payload->>'ease')::numeric > 0),
        CHECK (jsonb_typeof(payload->'interval_days') = 'number' AND (payload->>'interval_days')::numeric >= 0),
        CHECK (jsonb_typeof(payload->'repetitions') = 'number' AND (payload->>'repetitions')::numeric >= 0),
        CHECK (COALESCE(length(payload->>'due_at') > 0, false)),
        CONSTRAINT fk_learning_practice_review_item FOREIGN KEY (tenant_id, item_id)
            REFERENCES learning.practice_items(tenant_id, record_key) DEFERRABLE INITIALLY DEFERRED
    )""")
    op.execute("CREATE INDEX ix_learning_practice_sets_session ON learning.practice_sets(tenant_id, session_id)")
    op.execute("CREATE INDEX ix_learning_practice_items_set ON learning.practice_items(tenant_id, set_id)")
    op.execute("CREATE INDEX ix_learning_practice_attempts_set ON learning.practice_attempts(tenant_id, set_id)")
    op.execute("CREATE INDEX ix_learning_practice_attempts_student ON learning.practice_attempts(tenant_id, item_id, student_id)")
    op.execute("CREATE INDEX ix_learning_practice_reviews_student ON learning.practice_reviews(tenant_id, student_id)")

    # Generated columns of NEW are not computed yet in a BEFORE trigger, so every check reads the payload.
    op.execute("""CREATE FUNCTION learning.preserve_practice_record() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE parent_status text;
        BEGIN
            IF TG_TABLE_NAME = 'practice_sets' AND TG_OP = 'UPDATE' THEN
                IF (OLD.payload - ARRAY['title','status','revision','published_at'])
                        IS DISTINCT FROM (NEW.payload - ARRAY['title','status','revision','published_at'])
                   OR (NEW.payload->>'revision')::integer IS DISTINCT FROM (OLD.payload->>'revision')::integer + 1
                   OR (OLD.payload->>'status' = 'DRAFT' AND NEW.payload->>'status' NOT IN ('DRAFT', 'PUBLISHED'))
                   OR (OLD.payload->>'status' = 'PUBLISHED' AND (NEW.payload->>'status' IS DISTINCT FROM 'RETIRED'
                        OR (OLD.payload - ARRAY['status','revision']) IS DISTINCT FROM (NEW.payload - ARRAY['status','revision'])))
                   OR OLD.payload->>'status' = 'RETIRED'
                THEN RAISE EXCEPTION 'practice set identity is immutable and a published set is frozen'; END IF;
            END IF;
            IF TG_TABLE_NAME = 'practice_items' THEN
                IF TG_OP = 'UPDATE' AND (OLD.payload->>'id' IS DISTINCT FROM NEW.payload->>'id'
                        OR OLD.payload->>'set_id' IS DISTINCT FROM NEW.payload->>'set_id'
                        OR OLD.payload->>'offering_id' IS DISTINCT FROM NEW.payload->>'offering_id'
                        OR OLD.payload->>'ordinal' IS DISTINCT FROM NEW.payload->>'ordinal'
                        OR (NEW.payload->>'revision')::integer IS DISTINCT FROM (OLD.payload->>'revision')::integer + 1)
                THEN RAISE EXCEPTION 'practice question identity and position are immutable'; END IF;
                SELECT payload->>'status' INTO parent_status FROM learning.practice_sets
                    WHERE tenant_id = NEW.tenant_id AND record_key = NEW.payload->>'set_id';
                IF parent_status IS NOT NULL AND parent_status <> 'DRAFT'
                THEN RAISE EXCEPTION 'practice questions change only while their set is a draft'; END IF;
            END IF;
            IF TG_TABLE_NAME = 'practice_attempts' THEN
                IF TG_OP = 'UPDATE' THEN RAISE EXCEPTION 'practice answers are append-only'; END IF;
                SELECT payload->>'status' INTO parent_status FROM learning.practice_sets
                    WHERE tenant_id = NEW.tenant_id AND record_key = NEW.payload->>'set_id';
                IF parent_status IS NOT NULL AND parent_status <> 'PUBLISHED'
                THEN RAISE EXCEPTION 'practice answers are recorded only for a published set'; END IF;
            END IF;
            RETURN NEW;
        END $$""")
    op.execute("""CREATE TRIGGER learning_practice_sets_guarded BEFORE UPDATE ON learning.practice_sets
        FOR EACH ROW EXECUTE FUNCTION learning.preserve_practice_record()""")
    op.execute("""CREATE TRIGGER learning_practice_items_guarded BEFORE INSERT OR UPDATE ON learning.practice_items
        FOR EACH ROW EXECUTE FUNCTION learning.preserve_practice_record()""")
    op.execute("""CREATE TRIGGER learning_practice_attempts_guarded BEFORE INSERT OR UPDATE ON learning.practice_attempts
        FOR EACH ROW EXECUTE FUNCTION learning.preserve_practice_record()""")
    for table in PRACTICE_TABLES:
        op.execute(f"""CREATE TRIGGER learning_{table}_retained BEFORE DELETE ON learning.{table}
            FOR EACH ROW EXECUTE FUNCTION learning.prevent_record_removal()""")


def downgrade():
    raise RuntimeError("Practice questions, answers and review state are retained; migration is forward-only")
