"""Remove label column from experience_card_children; derive from value.headline.

Revision ID: 028
Revises: 027
Create Date: 2026-02-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = "028"
down_revision: Union[str, None] = "027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    # Backfill value.items from label for rows that only had label (no items).
    # Runtime get_child_label reads items[0].title; we create items=[{title: label}]
    # so display title is preserved after dropping the label column.
    conn.execute(
        text("""
            UPDATE experience_card_children
            SET value = jsonb_set(
                COALESCE(value, '{}'::jsonb),
                '{items}',
                jsonb_build_array(jsonb_build_object('title', label))
            )
            WHERE label IS NOT NULL AND label != ''
              AND (value->'items' IS NULL OR jsonb_array_length(COALESCE(value->'items', '[]'::jsonb)) = 0)
        """)
    )
    op.drop_column("experience_card_children", "label")


def downgrade() -> None:
    op.add_column(
        "experience_card_children",
        sa.Column("label", sa.String(255), nullable=True),
    )
    conn = op.get_bind()
    # Populate label from value->headline or value->items->0->title/subtitle
    conn.execute(
        text("""
            UPDATE experience_card_children
            SET label = COALESCE(
                NULLIF(TRIM(value->>'headline'), ''),
                value->'items'->0->>'title',
                value->'items'->0->>'subtitle'
            )
        """)
    )
