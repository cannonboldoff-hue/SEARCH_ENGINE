"""Add experience_card_children table for child cards.

Revision ID: 005
Revises: 004
Create Date: 2025-02-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "experience_card_children",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("parent_id", sa.UUID(), sa.ForeignKey("experience_cards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("person_id", sa.UUID(), sa.ForeignKey("people.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raw_experience_id", sa.UUID(), sa.ForeignKey("raw_experiences.id", ondelete="SET NULL"), nullable=True),
        sa.Column("depth", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("relation_type", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), default="DRAFT", nullable=False),
        sa.Column("human_edited", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("constraints", sa.Text(), nullable=True),
        sa.Column("decisions", sa.Text(), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column("tags", sa.ARRAY(sa.String()), nullable=True),
        sa.Column("company", sa.String(255), nullable=True),
        sa.Column("team", sa.String(255), nullable=True),
        sa.Column("role_title", sa.String(255), nullable=True),
        sa.Column("time_range", sa.String(100), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("tooling", sa.JSON(), nullable=True),
        sa.Column("entities", sa.JSON(), nullable=True),
        sa.Column("actions", sa.JSON(), nullable=True),
        sa.Column("outcomes", sa.JSON(), nullable=True),
        sa.Column("topics", sa.JSON(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_experience_card_children_parent_id", "experience_card_children", ["parent_id"])
    op.create_index("ix_experience_card_children_person_id", "experience_card_children", ["person_id"])


def downgrade() -> None:
    op.drop_index("ix_experience_card_children_person_id", table_name="experience_card_children")
    op.drop_index("ix_experience_card_children_parent_id", table_name="experience_card_children")
    op.drop_table("experience_card_children")
