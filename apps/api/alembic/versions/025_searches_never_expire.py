"""Set all searches to never expire (far-future expires_at).

Revision ID: 025
Revises: 024
Create Date: 2026-02-27

"""
from typing import Sequence, Union

from alembic import op


revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Set all searches to never expire (year 9999) until user deletes them
    op.execute(
        "UPDATE searches SET expires_at = '9999-12-31 23:59:59+00'::timestamptz"
    )


def downgrade() -> None:
    # Cannot reliably restore previous expiry; no-op
    pass
