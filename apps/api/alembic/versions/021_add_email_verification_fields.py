"""Add email verification fields to people.

Revision ID: 021
Revises: 020
Create Date: 2026-02-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("people", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("people", sa.Column("email_verification_token_hash", sa.String(length=255), nullable=True))
    op.add_column("people", sa.Column("email_verification_expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("people", "email_verification_expires_at")
    op.drop_column("people", "email_verification_token_hash")
    op.drop_column("people", "email_verified_at")
