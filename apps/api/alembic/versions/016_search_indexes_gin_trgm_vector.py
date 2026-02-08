"""Add search indexes: GIN on search_phrases, pg_trgm on location, HNSW on child embedding.

Revision ID: 016
Revises: 015
Create Date: 2026-02-09

"""
from typing import Sequence, Union

from alembic import op


revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # GIN on array columns for fast overlap/containment (search_phrases && / @>)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_experience_cards_search_phrases_gin "
        "ON experience_cards USING GIN (search_phrases)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_experience_card_children_search_phrases_gin "
        "ON experience_card_children USING GIN (search_phrases)"
    )

    # pg_trgm on location for ILIKE %...% (city/country/location_text filters)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_experience_cards_location_gin_trgm "
        "ON experience_cards USING GIN (location gin_trgm_ops)"
    )

    # HNSW on child embedding for vector similarity (cosine <=>); parent already in 014
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_experience_card_children_embedding_hnsw "
        "ON experience_card_children USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_experience_card_children_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_experience_cards_location_gin_trgm")
    op.execute("DROP INDEX IF EXISTS ix_experience_card_children_search_phrases_gin")
    op.execute("DROP INDEX IF EXISTS ix_experience_cards_search_phrases_gin")
