"""FILTER-001: additive scope storage; legacy metadata remains unknown.

No lifecycle change, permission backfill, vector alteration or destructive recovery.
V1 has only FIT and the four DEC-006 roles; no additional cohort is approved.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("knowledge_source", sa.Column("campus_scope", sa.String(64), nullable=True))
    for name, length in (("faculty_scope", 32), ("program_scope", 64), ("audiences", 64)):
        op.add_column("knowledge_source", sa.Column(name, postgresql.ARRAY(sa.String(length)), nullable=True))
    op.add_column("document_version", sa.Column("applicability_reviewed_at", sa.DateTime(timezone=True), nullable=True))
    # SQL CHECK accepts UNKNOWN. Explicit null tests and COALESCE prevent a
    # partial tuple or malformed array from passing through three-valued logic.
    op.create_check_constraint("ck_source_retrieval_scope", "knowledge_source", """
        (campus_scope IS NULL AND faculty_scope IS NULL AND program_scope IS NULL AND audiences IS NULL)
        OR
        (campus_scope IS NOT NULL AND faculty_scope IS NOT NULL
         AND program_scope IS NOT NULL AND audiences IS NOT NULL
         AND COALESCE(
             campus_scope = 'HUCE'
             AND cardinality(faculty_scope) > 0
             AND array_ndims(faculty_scope) = 1 AND array_lower(faculty_scope, 1) = 1
             AND faculty_scope <@ ARRAY['FIT']::varchar[]
             AND array_position(faculty_scope, NULL) IS NULL
             AND cardinality(audiences) > 0
             AND array_ndims(audiences) = 1 AND array_lower(audiences, 1) = 1
             AND audiences <@ ARRAY['STUDENT','SUPPORT_OFFICER','KNOWLEDGE_ADMIN','SYSTEM_ADMIN']::varchar[]
             AND array_position(audiences, NULL) IS NULL
             AND (cardinality(program_scope) = 0
                  OR (array_ndims(program_scope) = 1 AND array_lower(program_scope, 1) = 1))
             AND array_position(program_scope, NULL) IS NULL
             AND array_position(program_scope, '') IS NULL,
             false))
    """)
    # Only rows already present may retain the all-NULL tuple. A reviewed row
    # cannot revert to unknown scope, and changing a legacy PK cannot clone it.
    op.execute("""
        CREATE FUNCTION public.enforce_source_retrieval_scope() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.campus_scope IS NULL AND NEW.faculty_scope IS NULL
               AND NEW.program_scope IS NULL AND NEW.audiences IS NULL THEN
                IF TG_OP = 'INSERT' THEN
                    RAISE EXCEPTION 'new source requires reviewed scope' USING ERRCODE = '23514';
                END IF;
                IF OLD.campus_scope IS NOT NULL OR OLD.faculty_scope IS NOT NULL
                   OR OLD.program_scope IS NOT NULL OR OLD.audiences IS NOT NULL
                   OR NEW.id IS DISTINCT FROM OLD.id THEN
                    RAISE EXCEPTION 'reviewed scope cannot revert to unknown' USING ERRCODE = '23514';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER tr_source_retrieval_scope BEFORE INSERT OR UPDATE
        ON public.knowledge_source FOR EACH ROW
        EXECUTE FUNCTION public.enforce_source_retrieval_scope()
    """)
    op.create_check_constraint("ck_document_effective_range", "document_version",
                               "effective_until IS NULL OR effective_from IS NULL OR effective_until > effective_from")
    op.create_index("ix_source_retrieval_state", "knowledge_source",
                    ["campus_scope", "approval_status", "is_synthetic"])
    for name in ("faculty_scope", "program_scope", "audiences"):
        op.create_index("ix_source_" + name, "knowledge_source", [name], postgresql_using="gin")
    op.create_index("ix_document_retrieval_effective", "document_version",
                    ["knowledge_source_id", "status", "effective_from", "effective_until"])


def downgrade() -> None:
    raise RuntimeError("FILTER-001 is forward-only; preserve scope and audit data")
