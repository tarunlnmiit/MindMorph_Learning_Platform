"""rag_chunks table + pgvector extension (P2 #9 persistence)

Revision ID: 0002_rag_chunks
Revises: 0001_initial
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0002_rag_chunks"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

# Must match rag.embeddings.EMBED_DIM (BAAI/bge-small-en-v1.5).
EMBED_DIM = 384


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "rag_chunks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBED_DIM), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rag_chunks_user_id", "rag_chunks", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_rag_chunks_user_id", table_name="rag_chunks")
    op.drop_table("rag_chunks")
