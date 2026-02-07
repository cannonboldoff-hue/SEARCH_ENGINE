"""Drop work_preferred_salary_max from person_profiles (visibility: minimum salary only).

Revision ID: 013
Revises: 012
Create Date: 2026-02-07

"""
from typing import Sequence, Union

from alembic import op


revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("person_profiles", "work_preferred_salary_max")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE person_profiles ADD COLUMN work_preferred_salary_max NUMERIC(12, 2) NULL"
    )
