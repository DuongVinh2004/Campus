"""Retain fenced OCR candidates and revisioned accessible text for learning PDFs."""
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = depends_on = None


def upgrade():
    op.execute("""CREATE TABLE learning.ocr_jobs (
        tenant_id text NOT NULL REFERENCES learning.tenant_state(tenant_id),
        record_key text NOT NULL,
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload) = 'object'),
        offering_id text GENERATED ALWAYS AS (payload->>'offering_id') STORED NOT NULL,
        material_id text GENERATED ALWAYS AS (payload->>'material_id') STORED NOT NULL,
        version_id text GENERATED ALWAYS AS (payload->>'version_id') STORED NOT NULL,
        source_key text GENERATED ALWAYS AS (coalesce(payload->>'rendition_id', 'legacy:' || (payload->>'version_id'))) STORED NOT NULL,
        source_sha256 text GENERATED ALWAYS AS (payload->>'source_sha256') STORED NOT NULL CHECK(source_sha256 ~ '^[0-9a-f]{64}$'),
        profile_sha256 text GENERATED ALWAYS AS (payload->>'profile_sha256') STORED NOT NULL CHECK(profile_sha256 ~ '^[0-9a-f]{64}$'),
        PRIMARY KEY (tenant_id, record_key),
        UNIQUE (tenant_id, record_key, version_id, source_key, source_sha256),
        UNIQUE (tenant_id, version_id, source_key, source_sha256, profile_sha256),
        FOREIGN KEY (tenant_id, version_id, offering_id)
            REFERENCES learning.versions(tenant_id, record_key, offering_id) DEFERRABLE INITIALLY DEFERRED,
        FOREIGN KEY (tenant_id, version_id, material_id)
            REFERENCES learning.versions(tenant_id, record_key, material_id) DEFERRABLE INITIALLY DEFERRED,
        FOREIGN KEY (tenant_id, version_id, source_key)
            REFERENCES learning.versions(tenant_id, record_key, feedback_source_key) DEFERRABLE INITIALLY DEFERRED,
        CHECK (coalesce(payload->>'state' IN ('QUEUED','RUNNING','PAUSED','CANCELLED','FAILED','NEEDS_REVIEW'), false)),
        CHECK (coalesce((payload->>'reserved_bytes')::bigint >= 0 AND (payload->>'retained_bytes')::bigint >= 0, false))
    )""")
    op.execute("CREATE INDEX ix_learning_ocr_jobs_offering ON learning.ocr_jobs(tenant_id, offering_id)")
    op.execute("""CREATE TABLE learning.ocr_page_results (
        tenant_id text NOT NULL REFERENCES learning.tenant_state(tenant_id),
        record_key text NOT NULL,
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload) = 'object'),
        job_id text GENERATED ALWAYS AS (payload->>'job_id') STORED NOT NULL,
        page_no integer GENERATED ALWAYS AS ((payload->>'page_no')::integer) STORED NOT NULL CHECK(page_no BETWEEN 1 AND 500),
        PRIMARY KEY (tenant_id, record_key),
        UNIQUE (tenant_id, job_id, page_no),
        FOREIGN KEY (tenant_id, job_id)
            REFERENCES learning.ocr_jobs(tenant_id, record_key) DEFERRABLE INITIALLY DEFERRED,
        CHECK (record_key = job_id || ':' || page_no),
        CHECK (coalesce(payload->>'sha256' ~ '^[0-9a-f]{64}$' AND (payload->>'byte_size')::integer > 0, false))
    )""")
    op.execute("""CREATE TABLE learning.ocr_releases (
        tenant_id text NOT NULL REFERENCES learning.tenant_state(tenant_id),
        record_key text NOT NULL,
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload) = 'object'),
        job_id text GENERATED ALWAYS AS (payload->>'job_id') STORED NOT NULL,
        version_id text GENERATED ALWAYS AS (payload->>'version_id') STORED NOT NULL,
        source_key text GENERATED ALWAYS AS (coalesce(payload->>'rendition_id', 'legacy:' || (payload->>'version_id'))) STORED NOT NULL,
        source_sha256 text GENERATED ALWAYS AS (payload->>'source_sha256') STORED NOT NULL,
        PRIMARY KEY (tenant_id, record_key),
        UNIQUE (tenant_id, record_key, version_id),
        FOREIGN KEY (tenant_id, job_id, version_id, source_key, source_sha256)
            REFERENCES learning.ocr_jobs(tenant_id, record_key, version_id, source_key, source_sha256) DEFERRABLE INITIALLY DEFERRED,
        CHECK (coalesce(payload->>'state' IN ('DRAFT','PUBLISHED','SUPERSEDED','WITHDRAWN'), false))
    )""")
    op.execute("""CREATE TABLE learning.ocr_release_pages (
        tenant_id text NOT NULL REFERENCES learning.tenant_state(tenant_id),
        record_key text NOT NULL,
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload) = 'object'),
        release_id text GENERATED ALWAYS AS (payload->>'release_id') STORED NOT NULL,
        page_no integer GENERATED ALWAYS AS ((payload->>'page_no')::integer) STORED NOT NULL CHECK(page_no BETWEEN 1 AND 500),
        PRIMARY KEY (tenant_id, record_key),
        UNIQUE (tenant_id, release_id, page_no),
        FOREIGN KEY (tenant_id, release_id)
            REFERENCES learning.ocr_releases(tenant_id, record_key) DEFERRABLE INITIALLY DEFERRED,
        CHECK (record_key = release_id || ':' || page_no),
        CHECK (coalesce(payload->>'sha256' ~ '^[0-9a-f]{64}$' AND jsonb_typeof(payload->'blocks') = 'array', false))
    )""")
    op.execute("""ALTER TABLE learning.versions ADD COLUMN accessible_text_release_id text
        GENERATED ALWAYS AS (payload->>'accessible_text_release_id') STORED""")
    op.execute("""ALTER TABLE learning.versions ADD CONSTRAINT fk_learning_version_ocr_release
        FOREIGN KEY (tenant_id, accessible_text_release_id, record_key)
            REFERENCES learning.ocr_releases(tenant_id, record_key, version_id) DEFERRABLE INITIALLY DEFERRED""")
    for table in ("ocr_jobs", "ocr_releases", "ocr_release_pages"):
        op.execute(f"""CREATE TRIGGER learning_{table}_retained BEFORE DELETE ON learning.{table}
            FOR EACH ROW EXECUTE FUNCTION learning.prevent_record_removal()""")
    op.execute("""CREATE TRIGGER learning_ocr_candidate_immutable BEFORE UPDATE OR DELETE ON learning.ocr_page_results
        FOR EACH ROW EXECUTE FUNCTION learning.prevent_record_removal()""")
    op.execute("""CREATE FUNCTION learning.protect_ocr_snapshot() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF (OLD.payload - ARRAY['state','revision','published_pages','published_source_at','source_visibility_epoch','source_access_epoch'])
                IS DISTINCT FROM (NEW.payload - ARRAY['state','revision','published_pages','published_source_at','source_visibility_epoch','source_access_epoch'])
                OR (OLD.payload->>'state' <> 'DRAFT'
                    AND (OLD.payload - ARRAY['state','revision']) IS DISTINCT FROM (NEW.payload - ARRAY['state','revision']))
                OR (OLD.payload->>'state' <> 'DRAFT' AND NEW.payload->>'state' IN ('DRAFT','PUBLISHED'))
            THEN RAISE EXCEPTION 'learning OCR release binding and published snapshot are immutable'; END IF;
            RETURN NEW;
        END $$""")
    op.execute("""CREATE TRIGGER learning_ocr_release_immutable BEFORE UPDATE ON learning.ocr_releases
        FOR EACH ROW EXECUTE FUNCTION learning.protect_ocr_snapshot()""")
    op.execute("""CREATE FUNCTION learning.protect_ocr_review_page() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM learning.ocr_releases
                WHERE tenant_id = NEW.tenant_id AND record_key = NEW.payload->>'release_id' AND payload->>'state' = 'DRAFT'
            ) OR (TG_OP = 'UPDATE' AND
                (NEW.payload->>'release_id', NEW.payload->>'page_no') IS DISTINCT FROM
                (OLD.payload->>'release_id', OLD.payload->>'page_no'))
            THEN RAISE EXCEPTION 'published learning OCR pages are immutable'; END IF;
            RETURN NEW;
        END $$""")
    op.execute("""CREATE TRIGGER learning_ocr_review_page_immutable BEFORE INSERT OR UPDATE ON learning.ocr_release_pages
        FOR EACH ROW EXECUTE FUNCTION learning.protect_ocr_review_page()""")


def downgrade():
    raise RuntimeError("Learning accessible-text artefacts are retained; migration is forward-only")
