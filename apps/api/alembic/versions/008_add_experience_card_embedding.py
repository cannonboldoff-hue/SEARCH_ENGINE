"""Add embedding column to experience_cards.

Revision ID: 008
Revises: 007
Create Date: 2026-02-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("experience_cards", sa.Column("embedding", Vector(384), nullable=True))


def downgrade() -> None:
    op.drop_column("experience_cards", "embedding")
