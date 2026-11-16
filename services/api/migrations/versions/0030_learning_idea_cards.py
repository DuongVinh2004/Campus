"""Preserve idea ownership, exact citations and recipient-specific grants."""
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = depends_on = None


def upgrade():
    op.execute("""CREATE TABLE learning.idea_topics (
        tenant_id text NOT NULL REFERENCES learning.tenant_state(tenant_id),
        record_key text NOT NULL,
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload) = 'object'),
        owner_id text GENERATED ALWAYS AS (payload->>'owner_id') STORED NOT NULL,
        PRIMARY KEY (tenant_id, record_key),
        CHECK (COALESCE(payload->>'status' IN ('ACTIVE', 'ARCHIVED'), false)),
        CHECK (COALESCE((payload->>'revision')::integer > 0, false)),
        UNIQUE (tenant_id, record_key, owner_id)
    )""")
    op.execute("""CREATE TABLE learning.idea_cards (
        tenant_id text NOT NULL REFERENCES learning.tenant_state(tenant_id),
        record_key text NOT NULL,
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload) = 'object'),
        owner_id text GENERATED ALWAYS AS (payload->>'owner_id') STORED NOT NULL,
        topic_id text GENERATED ALWAYS AS (payload->>'topic_id') STORED,
        offering_id text GENERATED ALWAYS AS (payload#>>'{source,offering_id}') STORED NOT NULL,
        version_id text GENERATED ALWAYS AS (payload#>>'{source,version_id}') STORED NOT NULL,
        source_key text GENERATED ALWAYS AS (payload#>>'{source,source_key}') STORED NOT NULL,
        page_no integer GENERATED ALWAYS AS ((payload#>>'{source,page_no}')::integer) STORED NOT NULL,
        PRIMARY KEY (tenant_id, record_key),
        UNIQUE (tenant_id, record_key, owner_id, offering_id, version_id, source_key, page_no),
        CHECK (page_no BETWEEN 1 AND 500),
        CHECK (COALESCE(payload->>'status' IN ('ACTIVE', 'ARCHIVED'), false)),
        CHECK (COALESCE(payload#>>'{source,kind}' IN ('PAGE', 'TEXT', 'REGION'), false)),
        CHECK (CASE WHEN jsonb_typeof(payload->'history') = 'array'
            THEN COALESCE(jsonb_array_length(payload->'history') = (payload->>'revision')::integer
                AND jsonb_array_length(payload->'history') > 0, false) ELSE false END),
        FOREIGN KEY (tenant_id, topic_id, owner_id) REFERENCES learning.idea_topics(tenant_id, record_key, owner_id),
        FOREIGN KEY (tenant_id, version_id, offering_id) REFERENCES learning.versions(tenant_id, record_key, offering_id),
        FOREIGN KEY (tenant_id, version_id, source_key) REFERENCES learning.versions(tenant_id, record_key, feedback_source_key)
    )""")
    op.execute("""CREATE TABLE learning.idea_shares (
        tenant_id text NOT NULL REFERENCES learning.tenant_state(tenant_id),
        record_key text NOT NULL,
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload) = 'object'),
        owner_id text GENERATED ALWAYS AS (payload->>'owner_id') STORED NOT NULL,
        card_id text GENERATED ALWAYS AS (payload->>'card_id') STORED NOT NULL,
        offering_id text GENERATED ALWAYS AS (payload#>>'{source,offering_id}') STORED NOT NULL,
        version_id text GENERATED ALWAYS AS (payload#>>'{source,version_id}') STORED NOT NULL,
        source_key text GENERATED ALWAYS AS (payload#>>'{source,source_key}') STORED NOT NULL,
        page_no integer GENERATED ALWAYS AS ((payload#>>'{source,page_no}')::integer) STORED NOT NULL,
        PRIMARY KEY (tenant_id, record_key),
        CHECK (COALESCE(payload->>'status' IN ('ACTIVE', 'WITHDRAWN'), false)),
        CHECK (COALESCE((payload->>'card_revision')::integer > 0, false)),
        CHECK (COALESCE((payload->>'revision')::integer > 0, false)),
        FOREIGN KEY (tenant_id, card_id, owner_id, offering_id, version_id, source_key, page_no)
            REFERENCES learning.idea_cards(tenant_id, record_key, owner_id, offering_id, version_id, source_key, page_no)
    )""")
    op.execute("""CREATE TABLE learning.idea_grants (
        tenant_id text NOT NULL REFERENCES learning.tenant_state(tenant_id),
        record_key text NOT NULL,
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload) = 'object'),
        share_id text GENERATED ALWAYS AS (payload->>'share_id') STORED NOT NULL,
        recipient_id text GENERATED ALWAYS AS (payload->>'recipient_id') STORED NOT NULL,
        PRIMARY KEY (tenant_id, record_key),
        UNIQUE (tenant_id, share_id, recipient_id),
        CHECK (record_key = share_id || ':' || recipient_id),
        CHECK (COALESCE(payload->>'status' IN ('ACTIVE', 'SUSPENDED'), false)),
        FOREIGN KEY (tenant_id, share_id) REFERENCES learning.idea_shares(tenant_id, record_key)
    )""")
    for table in ("idea_topics", "idea_cards", "idea_shares", "idea_grants"):
        op.execute(f"""CREATE TRIGGER learning_{table}_retained BEFORE DELETE ON learning.{table}
            FOR EACH ROW EXECUTE FUNCTION learning.prevent_record_removal()""")
    op.execute("""CREATE FUNCTION learning.preserve_idea_identity() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF (TG_TABLE_NAME = 'idea_topics' AND (OLD.payload->>'owner_id' IS DISTINCT FROM NEW.payload->>'owner_id'
                    OR (NEW.payload->>'revision')::integer IS DISTINCT FROM (OLD.payload->>'revision')::integer + 1))
               OR (TG_TABLE_NAME = 'idea_cards' AND (OLD.payload->'source' IS DISTINCT FROM NEW.payload->'source'
                    OR OLD.payload->>'owner_id' IS DISTINCT FROM NEW.payload->>'owner_id'
                    OR (NEW.payload->>'revision')::integer IS DISTINCT FROM (OLD.payload->>'revision')::integer + 1
                    OR ((NEW.payload->'history') - (-1)) IS DISTINCT FROM OLD.payload->'history'))
               OR (TG_TABLE_NAME = 'idea_shares' AND
                    ((OLD.payload - ARRAY['status','revision','withdrawn_at'])
                        IS DISTINCT FROM (NEW.payload - ARRAY['status','revision','withdrawn_at'])
                     OR OLD.payload->>'status' = 'WITHDRAWN'))
               OR (TG_TABLE_NAME = 'idea_grants' AND
                    ((OLD.payload - 'status') IS DISTINCT FROM (NEW.payload - 'status')
                     OR OLD.payload->>'status' = 'SUSPENDED'))
            THEN RAISE EXCEPTION 'idea ownership, citation and released snapshot are immutable'; END IF;
            RETURN NEW;
        END $$""")
    for table in ("idea_topics", "idea_cards", "idea_shares", "idea_grants"):
        op.execute(f"""CREATE TRIGGER learning_{table}_immutable BEFORE UPDATE ON learning.{table}
            FOR EACH ROW EXECUTE FUNCTION learning.preserve_idea_identity()""")


def downgrade():
    raise RuntimeError("Learning idea cards and grants are retained; migration is forward-only")
