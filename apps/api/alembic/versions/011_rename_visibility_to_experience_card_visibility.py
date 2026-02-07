"""Rename experience_cards.visibility to experience_card_visibility.

Revision ID: 011
Revises: 010
Create Date: 2026-02-07

"""
from typing import Sequence, Union

from alembic import op


revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "experience_cards",
        "visibility",
        new_column_name="experience_card_visibility",
    )


def downgrade() -> None:
    op.alter_column(
        "experience_cards",
        "experience_card_visibility",
        new_column_name="visibility",
    )
