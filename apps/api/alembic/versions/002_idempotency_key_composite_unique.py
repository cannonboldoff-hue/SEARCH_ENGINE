"""Idempotency: unique on (key, person_id, endpoint) instead of key only.

Revision ID: 002
Revises: 001
Create Date: 2025-02-02

"""
from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_idempotency_keys_key", table_name="idempotency_keys")
    op.create_index(
        "ix_idempotency_keys_key",
        "idempotency_keys",
        ["key"],
        unique=False,
    )
    op.create_index(
        "ix_idempotency_keys_key_person_endpoint",
        "idempotency_keys",
        ["key", "person_id", "endpoint"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_idempotency_keys_key_person_endpoint", table_name="idempotency_keys")
    op.drop_index("ix_idempotency_keys_key", table_name="idempotency_keys")
    op.create_index("ix_idempotency_keys_key", "idempotency_keys", ["key"], unique=True)
