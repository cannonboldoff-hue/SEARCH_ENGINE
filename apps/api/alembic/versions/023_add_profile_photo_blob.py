"""Add profile_photo and profile_photo_media_type to person_profiles.

Revision ID: 023
Revises: 022
Create Date: 2026-02-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "023"
down_revision: Union[str, None] = "022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "person_profiles",
        sa.Column("profile_photo", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "person_profiles",
        sa.Column("profile_photo_media_type", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("person_profiles", "profile_photo_media_type")
    op.drop_column("person_profiles", "profile_photo")
