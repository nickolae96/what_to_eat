"""add food_embeddings table with pgvector

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-03 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DIMENSIONS = 768


def upgrade() -> None:
    # 1. Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2. Create the food_embeddings table
    op.create_table(
        "food_embeddings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("food_id", sa.UUID(), nullable=False),
        sa.Column("embedding", Vector(DIMENSIONS), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["food_id"], ["foods.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("food_id"),
    )

    # 3. HNSW index for fast cosine-distance lookups
    op.execute(
        """
        CREATE INDEX ix_food_embeddings_hnsw
        ON food_embeddings
        USING hnsw (embedding vector_cosine_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_food_embeddings_hnsw")
    op.drop_table("food_embeddings")

