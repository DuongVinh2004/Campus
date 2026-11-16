"""Keep each reviewed change description on the two exact learning versions."""
from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = depends_on = None


def upgrade():
    op.execute("""CREATE TABLE learning.version_change_revisions (
        tenant_id text NOT NULL REFERENCES learning.tenant_state(tenant_id),
        record_key text NOT NULL,
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload) = 'object'),
        material_id text GENERATED ALWAYS AS (payload->>'material_id') STORED NOT NULL,
        base_version_id text GENERATED ALWAYS AS (payload->>'base_version_id') STORED NOT NULL,
        target_version_id text GENERATED ALWAYS AS (payload->>'target_version_id') STORED NOT NULL,
        base_source_key text GENERATED ALWAYS AS (payload->>'base_source_key') STORED NOT NULL,
        target_source_key text GENERATED ALWAYS AS (payload->>'target_source_key') STORED NOT NULL,
        revision integer GENERATED ALWAYS AS ((payload->>'revision')::integer) STORED NOT NULL,
        PRIMARY KEY (tenant_id, record_key),
        UNIQUE (tenant_id, target_version_id, revision),
        CHECK (base_version_id <> target_version_id AND revision > 0),
        CHECK (record_key = target_version_id || ':' || revision),
        FOREIGN KEY (tenant_id, base_version_id, material_id)
            REFERENCES learning.versions(tenant_id, record_key, material_id) DEFERRABLE INITIALLY DEFERRED,
        FOREIGN KEY (tenant_id, target_version_id, material_id)
            REFERENCES learning.versions(tenant_id, record_key, material_id) DEFERRABLE INITIALLY DEFERRED,
        FOREIGN KEY (tenant_id, base_version_id, base_source_key)
            REFERENCES learning.versions(tenant_id, record_key, feedback_source_key) DEFERRABLE INITIALLY DEFERRED,
        FOREIGN KEY (tenant_id, target_version_id, target_source_key)
            REFERENCES learning.versions(tenant_id, record_key, feedback_source_key) DEFERRABLE INITIALLY DEFERRED
    )""")
    op.execute("""CREATE TRIGGER learning_version_change_revisions_retained
        BEFORE UPDATE OR DELETE ON learning.version_change_revisions
        FOR EACH ROW EXECUTE FUNCTION learning.prevent_record_removal()""")


def downgrade():
    raise RuntimeError("Learning version change revisions are retained; migration is forward-only")
