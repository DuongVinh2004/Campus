"""Add immutable profile/index snapshots and an independent activation pointer.

Revision ID: 0011; Revises: 0010. No model is loaded and no index is activated.
Legacy vectors and rows are retained; downgrade requires a reviewed forward fix.
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = depends_on = None

# Frozen DOC-RAG-001 / ADR-005 v1.1.0 values, never imported from mutable runtime
# configuration by a historical migration. No seeded production/model artifact.
PROFILE_VALUES = {
    "profile_version": "rag-prod-v1.0.0",
    "embedding_model_id": "BAAI/bge-m3",
    "embedding_model_revision": "5617a9f61b028005a4858fdac845db406aefb181",
    "embedding_dimension": 1024, "normalization": "l2", "distance_metric": "cosine",
    "reranker_model_id": "BAAI/bge-reranker-v2-m3",
    "reranker_model_revision": "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e",
    "lexical_k": 30, "semantic_k": 30, "rrf_constant": 60, "fusion_k": 20,
    "rerank_input_limit": 20, "rerank_k": 8, "context_k": 8, "context_token_budget": 6000,
    "near_duplicate_section_limit": 3,
    "lexical_timeout_ms": 400, "semantic_timeout_ms": 700, "reranker_timeout_ms": 700,
    "overall_timeout_ms": 1800, "transient_retry_limit": 1,
    "evidence_support_threshold": 0.78, "evidence_repair_limit": 1,
    "branch_fallback": "remaining_branch_requires_sql_filter_assurance_and_evidence_gate",
    "reranker_fallback": "rrf_requires_eval_approval_and_degraded_reason",
    "recall_at_10_min": 0.90, "critical_subgroup_recall_min": 0.85,
    "citation_precision_min": 0.95, "grounded_correctness_min": 0.90,
    "exact_identifier_recall_at_5_min": 0.98, "conflict_handling_min": 0.98,
    "invalid_source_leakage_max": 0, "latency_p95_max_ms": 1800, "latency_p99_max_ms": 3000,
    "error_rate_exclusive_max": 0.01, "performance_load_profile": "TP-RAG",
}
COMPATIBILITY = ["profile_version", "embedding_model_id", "embedding_model_revision",
                 "embedding_dimension", "normalization", "distance_metric"]


def upgrade():
    columns, checks = [], []
    for name, value in PROFILE_VALUES.items():
        kind = sa.String(128) if type(value) is str else sa.Integer() if type(value) is int else sa.Double()
        columns.append(sa.Column(name, kind, primary_key=name == "profile_version", nullable=False))
        literal = repr(value)  # Reviewed constant literals only, never external SQL.
        checks.append(sa.CheckConstraint(f"{name} = {literal}", name="ck_profile_" + name))
    op.create_table("retrieval_profile", *columns, *checks,
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approval_reference", sa.String(128), nullable=False),
        sa.CheckConstraint("approved_at >= created_at AND length(btrim(approval_reference)) > 0",
                           name="ck_profile_approval"),
        sa.UniqueConstraint(*COMPATIBILITY, name="uq_profile_embedding_compatibility"))
    op.create_table("embedding_index_manifest",
        sa.Column("index_version", sa.String(128), primary_key=True),
        sa.Column("profile_version", sa.String(128), nullable=False),
        sa.Column("embedding_model_id", sa.String(128), nullable=False),
        sa.Column("embedding_model_revision", sa.String(40), nullable=False),
        sa.Column("artifact_sha256", sa.String(64), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column("normalization", sa.String(16), nullable=False),
        sa.Column("distance_metric", sa.String(16), nullable=False),
        sa.Column("corpus_version", sa.String(128), nullable=False),
        sa.Column("document_count", sa.Integer(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("content_checksum", sa.String(64), nullable=False),
        sa.Column("build_status", sa.String(16), nullable=False),
        sa.Column("built_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True)),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["profile_version", "embedding_model_id", "embedding_model_revision",
                                 "dimension", "normalization", "distance_metric"],
                                ["retrieval_profile." + name for name in COMPATIBILITY],
                                name="fk_manifest_profile_compatibility"),
        sa.UniqueConstraint("profile_version", "index_version", name="uq_manifest_profile_index"),
        sa.CheckConstraint("dimension > 0 AND document_count >= 0 AND chunk_count >= 0", name="ck_manifest_counts"),
        sa.CheckConstraint("index_version = btrim(index_version) AND length(index_version) > 0 "
                           "AND corpus_version = btrim(corpus_version) AND length(corpus_version) > 0",
                           name="ck_manifest_identifiers"),
        sa.CheckConstraint("artifact_sha256 ~ '^[0-9a-f]{64}$' AND artifact_sha256 <> repeat('0',64) "
                           "AND content_checksum ~ '^[0-9a-f]{64}$' AND content_checksum <> repeat('0',64)",
                           name="ck_manifest_checksums"),
        sa.CheckConstraint("build_status IN ('BUILDING','VALIDATING','READY','ACTIVE','RETIRED','FAILED')",
                           name="ck_manifest_build_status"),
        sa.CheckConstraint("(validated_at IS NULL OR validated_at >= built_at) "
                           "AND (activated_at IS NULL OR (validated_at IS NOT NULL AND activated_at >= validated_at)) "
                           "AND (build_status NOT IN ('READY','ACTIVE') OR validated_at IS NOT NULL) "
                           "AND (build_status <> 'ACTIVE' OR activated_at IS NOT NULL)", name="ck_manifest_timestamps"))
    op.create_table("embedding_index_active_pointer",
        sa.Column("profile_version", sa.String(128), primary_key=True),
        sa.Column("index_version", sa.String(128), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_version", "index_version"],
                                ["embedding_index_manifest.profile_version", "embedding_index_manifest.index_version"],
                                name="fk_active_manifest_profile"))
    # Nullable trace edge: existing published documents remain unchanged and
    # unclaimed by the new manifest. Ingestion/reindex wiring is a later task.
    op.add_column("document_version", sa.Column("index_version", sa.String(128), nullable=True))
    op.create_foreign_key("fk_document_version_index", "document_version", "embedding_index_manifest",
                          ["index_version"], ["index_version"])
    op.execute("""CREATE FUNCTION public.rag_manifest_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'immutable retrieval snapshot; use a new version or separate pointer'
      USING ERRCODE = '23514'; END; $$""")
    for table in ("retrieval_profile", "embedding_index_manifest"):
        op.execute(f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON public.{table} "
                   "FOR EACH ROW EXECUTE FUNCTION public.rag_manifest_immutable()")
    op.execute("""CREATE FUNCTION public.rag_active_manifest_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM public.embedding_index_manifest m
        WHERE m.index_version = NEW.index_version AND m.profile_version = NEW.profile_version
          AND m.build_status IN ('READY','ACTIVE') AND m.validated_at IS NOT NULL
          AND NEW.activated_at >= m.validated_at) THEN
        RAISE EXCEPTION 'active manifest not validated or profile/index mismatch' USING ERRCODE = '23514';
      END IF;
      RETURN NEW;
    END; $$""")
    op.execute("CREATE TRIGGER active_manifest_guard BEFORE INSERT OR UPDATE ON public.embedding_index_active_pointer "
               "FOR EACH ROW EXECUTE FUNCTION public.rag_active_manifest_guard()")


def downgrade():
    raise RuntimeError("0011 is additive and forward-only; preserve manifests and use a reviewed forward fix")
