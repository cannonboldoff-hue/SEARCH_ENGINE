"""Add location to experience_cards.

Revision ID: 004
Revises: 003
Create Date: 2025-02-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def downgrade() -> None:
    op.drop_olumn("experience_cards", "location")


def upgrade() -> None:
    op.add_column(
        "experience_cards",
        sa.Column("location", sa.String(255), nullable=True),
    )

