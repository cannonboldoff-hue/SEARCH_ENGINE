"""Add signup_sessions table for OTP-based signup.

Revision ID: 020
Revises: 019
Create Date: 2026-02-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "signup_sessions",
        sa.Column("id", UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("send_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_signup_sessions_email_status", "signup_sessions", ["email", "status"])
    op.create_index("ix_signup_sessions_expires_at", "signup_sessions", ["expires_at"])
    op.create_index("ix_signup_sessions_phone", "signup_sessions", ["phone"])


def downgrade() -> None:
    op.drop_index("ix_signup_sessions_phone", table_name="signup_sessions")
    op.drop_index("ix_signup_sessions_expires_at", table_name="signup_sessions")
    op.drop_index("ix_signup_sessions_email_status", table_name="signup_sessions")
    op.drop_table("signup_sessions")
