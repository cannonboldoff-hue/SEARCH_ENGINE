"""Hybrid search: Search expires_at/parsed_constraints, ExperienceCard company_norm/team_norm, indexes.

Revision ID: 014
Revises: 013
Create Date: 2026-02-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ExperienceCard: normalized search fields
    op.add_column(
        "experience_cards",
        sa.Column("company_norm", sa.String(255), nullable=True),
    )
    op.add_column(
        "experience_cards",
        sa.Column("team", sa.Text(), nullable=True),
    )
    op.add_column(
        "experience_cards",
        sa.Column("team_norm", sa.String(255), nullable=True),
    )
    op.create_index("ix_experience_cards_company_norm", "experience_cards", ["company_norm"], unique=False)
    op.create_index("ix_experience_cards_team_norm", "experience_cards", ["team_norm"], unique=False)
    op.create_index("ix_experience_cards_experience_card_visibility", "experience_cards", ["experience_card_visibility"], unique=False)

    # Backfill company_norm from company_name
    op.execute(
        "UPDATE experience_cards SET company_norm = lower(trim(company_name)) WHERE company_name IS NOT NULL AND company_norm IS NULL"
    )
    op.execute(
        "UPDATE experience_cards SET team_norm = lower(trim(team)) WHERE team IS NOT NULL AND team_norm IS NULL"
    )

    # Search: expires_at and parsed_constraints_json
    op.add_column(
        "searches",
        sa.Column("parsed_constraints_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "searches",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Backfill expires_at for existing rows: created_at + 24 hours
    op.execute(
        "UPDATE searches SET expires_at = created_at + interval '24 hours' WHERE expires_at IS NULL"
    )
    op.alter_column(
        "searches",
        "expires_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )

    # pgvector: HNSW index for cosine distance (operator <=>)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_experience_cards_embedding_hnsw ON experience_cards "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_experience_cards_embedding_hnsw")
    op.drop_index("ix_experience_cards_experience_card_visibility", table_name="experience_cards")
    op.drop_index("ix_experience_cards_team_norm", table_name="experience_cards")
    op.drop_index("ix_experience_cards_company_norm", table_name="experience_cards")
    op.drop_column("experience_cards", "team_norm")
    op.drop_column("experience_cards", "team")
    op.drop_column("experience_cards", "company_norm")
    op.drop_column("searches", "expires_at")
    op.drop_column("searches", "parsed_constraints_json")
