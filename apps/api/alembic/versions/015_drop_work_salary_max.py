"""Drop work_salary_max from person_profiles.

Revision ID: 015
Revises: 014
Create Date: 2026-02-08

"""
from typing import Sequence, Union

from alembic import op


revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE person_profiles DROP COLUMN IF EXISTS work_salary_max")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE person_profiles ADD COLUMN work_salary_max NUMERIC(12, 2) NULL"
    )
