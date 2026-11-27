"""Concepts of a class, a student's estimated mastery of each, the tutor setting of a class and the hints it gave.

Same storage shape as the other learning collections (tenant_id, record_key, payload jsonb), so
`PostgresLearningRepository` reads and writes them like the SQLite state (`application/learning/tutor.py`).
Generated columns tie every row to its class; the database refuses what the application already refuses:
  - a concept keeps its identity and class, changes forward only (revision + 1) and, once RETIRED, is frozen;
  - a mastery row keeps its concept and student; counts never go down;
  - a hint, once given, is never changed;
  - nothing is deleted.
The free text a student types in reply to a hint is never stored: a hint row keeps only its SHA-256.
Additive only: creates four new learning.* tables, one function and triggers; nothing existing is altered.
"""
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = depends_on = None

TUTOR_TABLES = ("concepts", "concept_mastery", "tutor_settings", "tutor_turns")


def upgrade():
    op.execute("""CREATE TABLE learning.concepts (
        tenant_id text NOT NULL REFERENCES learning.tenant_state(tenant_id),
        record_key text NOT NULL CHECK(length(record_key) BETWEEN 1 AND 512),
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload) = 'object'),
        offering_id text GENERATED ALWAYS AS (payload->>'offering_id') STORED NOT NULL,
        status text GENERATED ALWAYS AS (payload->>'status') STORED NOT NULL,
        PRIMARY KEY (tenant_id, record_key),
        UNIQUE (tenant_id, record_key, offering_id),
        CHECK (record_key = payload->>'id'),
        CHECK (status IN ('PROPOSED', 'APPROVED', 'RETIRED')),
        CHECK (payload->>'origin' IN ('LECTURER', 'MODEL_CANDIDATE')),
        CHECK (COALESCE((payload->>'revision')::integer > 0, false)),
        CHECK (COALESCE(length(btrim(payload->>'label')) BETWEEN 2 AND 120, false)),
        CHECK (COALESCE(length(payload->>'created_by') > 0, false)),
        CHECK (jsonb_typeof(payload->'links') = 'array' AND jsonb_array_length(payload->'links') <= 200),
        CONSTRAINT fk_learning_concept_offering FOREIGN KEY (tenant_id, offering_id)
            REFERENCES learning.offerings(tenant_id, record_key) DEFERRABLE INITIALLY DEFERRED
    )""")
    # The application keys a mastery row by "<concept id>:<student id>"; both parts become columns.
    op.execute("""CREATE TABLE learning.concept_mastery (
        tenant_id text NOT NULL REFERENCES learning.tenant_state(tenant_id),
        record_key text NOT NULL CHECK(record_key ~ '^[^:]+:[^:]+$' AND length(record_key) <= 512),
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload) = 'object'),
        concept_id text GENERATED ALWAYS AS (split_part(record_key, ':', 1)) STORED NOT NULL,
        student_id text GENERATED ALWAYS AS (split_part(record_key, ':', 2)) STORED NOT NULL,
        offering_id text GENERATED ALWAYS AS (payload->>'offering_id') STORED NOT NULL,
        PRIMARY KEY (tenant_id, record_key),
        CHECK (payload->>'concept_id' = split_part(record_key, ':', 1) AND payload->>'student_id' = split_part(record_key, ':', 2)),
        CHECK (jsonb_typeof(payload->'p_known') = 'number' AND (payload->>'p_known')::numeric BETWEEN 0 AND 1),
        CHECK (jsonb_typeof(payload->'attempts') = 'number' AND (payload->>'attempts')::numeric >= 1),
        CHECK (jsonb_typeof(payload->'correct') = 'number' AND (payload->>'correct')::numeric BETWEEN 0 AND (payload->>'attempts')::numeric),
        CHECK (COALESCE(length(payload->>'model_version') > 0, false)),
        CONSTRAINT fk_learning_mastery_concept FOREIGN KEY (tenant_id, concept_id, offering_id)
            REFERENCES learning.concepts(tenant_id, record_key, offering_id) DEFERRABLE INITIALLY DEFERRED
    )""")
    op.execute("""CREATE TABLE learning.tutor_settings (
        tenant_id text NOT NULL REFERENCES learning.tenant_state(tenant_id),
        record_key text NOT NULL CHECK(length(record_key) BETWEEN 1 AND 512),
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload) = 'object'),
        PRIMARY KEY (tenant_id, record_key),
        CHECK (record_key = payload->>'offering_id'),
        CHECK (jsonb_typeof(payload->'tutor_enabled') = 'boolean' AND jsonb_typeof(payload->'model_hints_enabled') = 'boolean'),
        CHECK (jsonb_typeof(payload->'reveal_after_attempts') = 'number' AND (payload->>'reveal_after_attempts')::numeric BETWEEN 1 AND 5),
        CHECK (COALESCE((payload->>'revision')::integer > 0, false)),
        CONSTRAINT fk_learning_tutor_settings_offering FOREIGN KEY (tenant_id, record_key)
            REFERENCES learning.offerings(tenant_id, record_key) DEFERRABLE INITIALLY DEFERRED
    )""")
    op.execute("""CREATE TABLE learning.tutor_turns (
        tenant_id text NOT NULL REFERENCES learning.tenant_state(tenant_id),
        record_key text NOT NULL CHECK(length(record_key) BETWEEN 1 AND 512),
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload) = 'object'),
        item_id text GENERATED ALWAYS AS (payload->>'item_id') STORED NOT NULL,
        offering_id text GENERATED ALWAYS AS (payload->>'offering_id') STORED NOT NULL,
        student_id text GENERATED ALWAYS AS (payload->>'student_id') STORED NOT NULL,
        PRIMARY KEY (tenant_id, record_key),
        CHECK (record_key = payload->>'id'),
        CHECK (length(student_id) > 0),
        CHECK (jsonb_typeof(payload->'level') = 'number' AND (payload->>'level')::numeric BETWEEN 1 AND 3),
        CHECK (payload->>'origin' IN ('MODEL', 'TEMPLATE')),
        CHECK (COALESCE(length(payload->>'hint') BETWEEN 1 AND 1200, false)),
        CHECK (COALESCE(payload->>'quote_sha256' ~ '^[0-9a-f]{64}$', false)),
        CHECK (NOT payload ? 'reply'),
        CHECK (COALESCE(length(payload->>'created_at') > 0 AND length(payload->>'expires_at') > 0, false)),
        CONSTRAINT fk_learning_tutor_turn_item FOREIGN KEY (tenant_id, item_id)
            REFERENCES learning.practice_items(tenant_id, record_key) DEFERRABLE INITIALLY DEFERRED
    )""")
    op.execute("CREATE INDEX ix_learning_concepts_offering ON learning.concepts(tenant_id, offering_id)")
    op.execute("CREATE INDEX ix_learning_concept_mastery_student ON learning.concept_mastery(tenant_id, offering_id, student_id)")
    op.execute("CREATE INDEX ix_learning_tutor_turns_student ON learning.tutor_turns(tenant_id, student_id, item_id)")

    # Generated columns of NEW are not computed yet in a BEFORE trigger, so every check reads the payload.
    op.execute("""CREATE FUNCTION learning.preserve_tutor_record() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_TABLE_NAME = 'concepts' THEN
                IF OLD.payload->>'id' IS DISTINCT FROM NEW.payload->>'id'
                   OR OLD.payload->>'offering_id' IS DISTINCT FROM NEW.payload->>'offering_id'
                   OR OLD.payload->>'origin' IS DISTINCT FROM NEW.payload->>'origin'
                   OR (NEW.payload->>'revision')::integer IS DISTINCT FROM (OLD.payload->>'revision')::integer + 1
                   OR OLD.payload->>'status' = 'RETIRED'
                THEN RAISE EXCEPTION 'concept identity is immutable and a retired concept is frozen'; END IF;
            END IF;
            IF TG_TABLE_NAME = 'concept_mastery' THEN
                IF OLD.payload->>'offering_id' IS DISTINCT FROM NEW.payload->>'offering_id'
                   OR (NEW.payload->>'attempts')::numeric < (OLD.payload->>'attempts')::numeric
                   OR (NEW.payload->>'correct')::numeric < (OLD.payload->>'correct')::numeric
                THEN RAISE EXCEPTION 'mastery rows keep their class and their counts only grow'; END IF;
            END IF;
            IF TG_TABLE_NAME = 'tutor_settings' THEN
                IF (NEW.payload->>'revision')::integer IS DISTINCT FROM (OLD.payload->>'revision')::integer + 1
                THEN RAISE EXCEPTION 'tutor settings change forward only'; END IF;
            END IF;
            IF TG_TABLE_NAME = 'tutor_turns' THEN
                RAISE EXCEPTION 'tutor hints are append-only';
            END IF;
            RETURN NEW;
        END $$""")
    for table in TUTOR_TABLES:
        op.execute(f"""CREATE TRIGGER learning_{table}_guarded BEFORE UPDATE ON learning.{table}
            FOR EACH ROW EXECUTE FUNCTION learning.preserve_tutor_record()""")
        op.execute(f"""CREATE TRIGGER learning_{table}_retained BEFORE DELETE ON learning.{table}
            FOR EACH ROW EXECUTE FUNCTION learning.prevent_record_removal()""")


def downgrade():
    raise RuntimeError("Concepts, mastery, tutor settings and hints are retained; migration is forward-only")
