"""Add Search.extra, SearchResult.extra, and FTS GIN indexes on search_document.

Revision ID: 019
Revises: 018
Create Date: 2026-02-10

Stores fallback_tier and explainability in extra JSONB.
Adds expression GIN indexes for full-text search on search_document (no new column).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("searches", sa.Column("extra", JSONB(), nullable=True))
    op.add_column("search_results", sa.Column("extra", JSONB(), nullable=True))

    # FTS: GIN index on tsvector of search_document for hybrid lexical search (no new column)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_experience_cards_search_document_fts "
        "ON experience_cards USING GIN (to_tsvector('english', COALESCE(search_document, '')))"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_experience_card_children_search_document_fts "
        "ON experience_card_children USING GIN (to_tsvector('english', COALESCE(search_document, '')))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_experience_card_children_search_document_fts")
    op.execute("DROP INDEX IF EXISTS ix_experience_cards_search_document_fts")
    op.drop_column("search_results", "extra")
    op.drop_column("searches", "extra")
