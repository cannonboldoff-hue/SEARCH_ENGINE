"""Remove search_phrases and search_document from experience_card_children.

Revision ID: 027
Revises: 026
Create Date: 2026-02-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "027"
down_revision: Union[str, None] = "026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("experience_card_children", "search_document")
    op.drop_column("experience_card_children", "search_phrases")


def downgrade() -> None:
    op.add_column(
        "experience_card_children",
        sa.Column("search_phrases", postgresql.ARRAY(sa.String()), nullable=True, server_default="{}"),
    )
    op.add_column(
        "experience_card_children",
        sa.Column("search_document", sa.Text(), nullable=True),
    )
