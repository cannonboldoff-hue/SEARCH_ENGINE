"""Bio table and experience_cards human_edited/locked.

Revision ID: 003
Revises: 002
Create Date: 2025-02-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bios",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("person_id", sa.UUID(), sa.ForeignKey("people.id", ondelete="CASCADE"), nullable=False),
        sa.Column("first_name", sa.String(255), nullable=True),
        sa.Column("last_name", sa.String(255), nullable=True),
        sa.Column("date_of_birth", sa.String(20), nullable=True),
        sa.Column("current_city", sa.String(255), nullable=True),
        sa.Column("profile_photo_url", sa.String(1000), nullable=True),
        sa.Column("school", sa.String(255), nullable=True),
        sa.Column("college", sa.String(255), nullable=True),
        sa.Column("current_company", sa.String(255), nullable=True),
        sa.Column("past_companies", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_bios_person_id", "bios", ["person_id"], unique=True)

    op.add_column(
        "experience_cards",
        sa.Column("human_edited", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "experience_cards",
        sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("experience_cards", "locked")
    op.drop_column("experience_cards", "human_edited")
    op.drop_index("ix_bios_person_id", table_name="bios")
    op.drop_table("bios")
