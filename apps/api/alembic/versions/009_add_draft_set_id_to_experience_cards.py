"""Add draft_set_id to experience_cards for DraftSet relationship.

Revision ID: 009
Revises: 008
Create Date: 2026-02-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "experience_cards",
        sa.Column(
            "draft_set_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("draft_sets.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_experience_cards_draft_set_id",
        "experience_cards",
        ["draft_set_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_experience_cards_draft_set_id", table_name="experience_cards")
    op.drop_column("experience_cards", "draft_set_id")
