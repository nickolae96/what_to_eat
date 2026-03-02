"""add search_vector tsvector column to foods

Revision ID: a1b2c3d4e5f6
Revises: 77cf60207412
Create Date: 2026-03-02 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "77cf60207412"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add the tsvector column
    op.add_column("foods", sa.Column("search_vector", TSVECTOR, nullable=True))

    # 2. Back-fill existing rows from name + brand + category
    op.execute(
        """
        UPDATE foods
        SET search_vector =
            setweight(to_tsvector('english', coalesce(name, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(brand, '')), 'B') ||
            setweight(to_tsvector('english', coalesce(category, '')), 'C')
        """
    )

    # 3. Create a GIN index for fast full-text lookups
    op.create_index(
        "ix_foods_search_vector",
        "foods",
        ["search_vector"],
        postgresql_using="gin",
    )

    # 4. Create a trigger so the vector stays up-to-date on INSERT / UPDATE
    op.execute(
        """
        CREATE OR REPLACE FUNCTION foods_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english', coalesce(NEW.name, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(NEW.brand, '')), 'B') ||
                setweight(to_tsvector('english', coalesce(NEW.category, '')), 'C');
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trig_foods_search_vector
        BEFORE INSERT OR UPDATE OF name, brand, category
        ON foods
        FOR EACH ROW
        EXECUTE FUNCTION foods_search_vector_update();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trig_foods_search_vector ON foods")
    op.execute("DROP FUNCTION IF EXISTS foods_search_vector_update()")
    op.drop_index("ix_foods_search_vector", table_name="foods")
    op.drop_column("foods", "search_vector")

