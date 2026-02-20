"""Remove phone from signup_sessions.

Revision ID: 022
Revises: 021
Create Date: 2026-02-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_signup_sessions_phone", table_name="signup_sessions")
    op.drop_column("signup_sessions", "phone")


def downgrade() -> None:
    op.add_column(
        "signup_sessions",
        sa.Column("phone", sa.String(length=50), nullable=False, server_default=""),
    )
    op.alter_column("signup_sessions", "phone", server_default=None)
    op.create_index("ix_signup_sessions_phone", "signup_sessions", ["phone"])
