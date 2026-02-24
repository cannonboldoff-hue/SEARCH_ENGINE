"""Add location fields and normalization columns to experience_cards.

Revision ID: 024
Revises: 023
Create Date: 2026-02-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add structured location fields
    op.add_column(
        "experience_cards",
        sa.Column("city", sa.String(255), nullable=True),
    )
    op.add_column(
        "experience_cards",
        sa.Column("country", sa.String(255), nullable=True),
    )
    op.add_column(
        "experience_cards",
        sa.Column("is_remote", sa.Boolean(), nullable=True),
    )
    
    # Add normalization fields for better filtering
    op.add_column(
        "experience_cards",
        sa.Column("domain_norm", sa.String(255), nullable=True),
    )
    op.add_column(
        "experience_cards",
        sa.Column("sub_domain_norm", sa.String(255), nullable=True),
    )
    
    # Create indexes on new fields for better query performance
    op.create_index(
        "ix_experience_cards_city",
        "experience_cards",
        ["city"],
        postgresql_ops={"city": "gin_trgm_ops"},
        postgresql_using="gin",
    )
    op.create_index(
        "ix_experience_cards_country",
        "experience_cards",
        ["country"],
    )
    op.create_index(
        "ix_experience_cards_domain_norm",
        "experience_cards",
        ["domain_norm"],
    )
    op.create_index(
        "ix_experience_cards_sub_domain_norm",
        "experience_cards",
        ["sub_domain_norm"],
    )
    
    # Populate company_norm and team_norm for existing records where they're NULL
    op.execute("""
        UPDATE experience_cards
        SET company_norm = LOWER(TRIM(company_name))
        WHERE company_name IS NOT NULL AND company_norm IS NULL
    """)
    
    op.execute("""
        UPDATE experience_cards
        SET team_norm = LOWER(TRIM(team))
        WHERE team IS NOT NULL AND team_norm IS NULL
    """)
    
    # Populate domain_norm and sub_domain_norm for existing records
    op.execute("""
        UPDATE experience_cards
        SET domain_norm = LOWER(TRIM(domain))
        WHERE domain IS NOT NULL
    """)
    
    op.execute("""
        UPDATE experience_cards
        SET sub_domain_norm = LOWER(TRIM(sub_domain))
        WHERE sub_domain IS NOT NULL
    """)


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_experience_cards_sub_domain_norm", table_name="experience_cards")
    op.drop_index("ix_experience_cards_domain_norm", table_name="experience_cards")
    op.drop_index("ix_experience_cards_country", table_name="experience_cards")
    op.drop_index("ix_experience_cards_city", table_name="experience_cards")
    
    # Drop columns
    op.drop_column("experience_cards", "sub_domain_norm")
    op.drop_column("experience_cards", "domain_norm")
    op.drop_column("experience_cards", "is_remote")
    op.drop_column("experience_cards", "country")
    op.drop_column("experience_cards", "city")
