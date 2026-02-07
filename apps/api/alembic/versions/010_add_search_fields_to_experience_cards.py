"""Add search_phrases and search_document to experience_cards.

Revision ID: 010
Revises: 009
Create Date: 2026-02-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "experience_cards",
        sa.Column("search_phrases", postgresql.ARRAY(sa.String()), nullable=True, server_default="{}"),
    )
    op.add_column(
        "experience_cards",
        sa.Column("search_document", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("experience_cards", "search_document")
    op.drop_column("experience_cards", "search_phrases")
