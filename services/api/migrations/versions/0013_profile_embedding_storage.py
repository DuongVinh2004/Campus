"""Add physical storage for the current profile; preserve every legacy vector.

No backfill, conversion, activation or destructive downgrade. Other model/profile
versions can receive separate storage after comparative evaluation.
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0013"
down_revision = "0012"
branch_labels = depends_on = None


def upgrade() -> None:
    op.add_column("knowledge_chunk", sa.Column("embedding_rag_v1", Vector(1024), nullable=True))
    op.add_column("knowledge_chunk", sa.Column("embedding_model_version", sa.String(128), nullable=True))
    op.add_column("knowledge_chunk", sa.Column("embedding_dimension", sa.Integer(), nullable=True))
    op.add_column("knowledge_chunk", sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint("ck_chunk_profile_embedding", "knowledge_chunk", """
        (embedding_rag_v1 IS NULL AND embedding_model_version IS NULL
         AND embedding_dimension IS NULL AND embedded_at IS NULL)
        OR
        (embedding_rag_v1 IS NOT NULL AND embedding_model_version IS NOT NULL
         AND embedding_dimension IS NOT NULL AND embedded_at IS NOT NULL
         AND COALESCE(
             embedding_model_version = 'BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181'
             AND embedding_dimension = 1024
             AND vector_dims(embedding_rag_v1) = embedding_dimension
             AND abs(1 + (embedding_rag_v1 <#> embedding_rag_v1)) <= 0.0001,
             false))
    """)
    op.create_index("ix_chunk_embedding_rag_v1", "knowledge_chunk", ["embedding_rag_v1"],
                    postgresql_using="hnsw", postgresql_ops={"embedding_rag_v1": "vector_cosine_ops"},
                    postgresql_where=sa.text("embedding_rag_v1 IS NOT NULL"))


def downgrade() -> None:
    raise RuntimeError("0013 is additive and forward-only; preserve both vector stores")
