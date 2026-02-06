"""Rebuild schema from current models.

Revision ID: 007
Revises: None (root migration; 006 was removed)
Create Date: 2026-02-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector


revision: str = "007"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop everything to allow a clean rebuild.
    op.execute("DROP TABLE IF EXISTS unlock_contacts CASCADE")
    op.execute("DROP TABLE IF EXISTS search_results CASCADE")
    op.execute("DROP TABLE IF EXISTS searches CASCADE")
    op.execute("DROP TABLE IF EXISTS experience_card_children CASCADE")
    op.execute("DROP TABLE IF EXISTS experience_cards CASCADE")
    op.execute("DROP TABLE IF EXISTS draft_sets CASCADE")
    op.execute("DROP TABLE IF EXISTS raw_experiences CASCADE")
    op.execute("DROP TABLE IF EXISTS idempotency_keys CASCADE")
    op.execute("DROP TABLE IF EXISTS credit_ledger CASCADE")
    op.execute("DROP TABLE IF EXISTS credit_wallets CASCADE")
    op.execute("DROP TABLE IF EXISTS contact_details CASCADE")
    op.execute("DROP TABLE IF EXISTS visibility_settings CASCADE")
    op.execute("DROP TABLE IF EXISTS bios CASCADE")
    op.execute("DROP TABLE IF EXISTS people CASCADE")

    # Required for vector columns.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "people",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("email", name="uq_people_email"),
    )
    op.create_index("ix_people_email", "people", ["email"])

    op.create_table(
        "bios",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "person_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("first_name", sa.String(255), nullable=True),
        sa.Column("last_name", sa.String(255), nullable=True),
        sa.Column("date_of_birth", sa.String(20), nullable=True),
        sa.Column("current_city", sa.String(255), nullable=True),
        sa.Column("profile_photo_url", sa.String(1000), nullable=True),
        sa.Column("school", sa.String(255), nullable=True),
        sa.Column("college", sa.String(255), nullable=True),
        sa.Column("current_company", sa.String(255), nullable=True),
        sa.Column("past_companies", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "visibility_settings",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "person_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("open_to_work", sa.Boolean(), nullable=True),
        sa.Column("work_preferred_locations", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("work_preferred_salary_min", sa.Numeric(12, 2), nullable=True),
        sa.Column("work_preferred_salary_max", sa.Numeric(12, 2), nullable=True),
        sa.Column("open_to_contact", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "contact_details",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "person_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("email_visible", sa.Boolean(), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("linkedin_url", sa.String(500), nullable=True),
        sa.Column("other", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "credit_wallets",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "person_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("balance", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "credit_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "person_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(100), nullable=False),
        sa.Column("reference_type", sa.String(50), nullable=True),
        sa.Column("reference_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("balance_after", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_credit_ledger_person_id", "credit_ledger", ["person_id"])

    op.create_table(
        "idempotency_keys",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column(
            "person_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("endpoint", sa.String(100), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_idempotency_keys_key", "idempotency_keys", ["key"])
    op.create_index(
        "ix_idempotency_keys_key_person_endpoint",
        "idempotency_keys",
        ["key", "person_id", "endpoint"],
        unique=True,
    )

    op.create_table(
        "raw_experiences",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "person_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("raw_text_original", sa.Text(), nullable=True),
        sa.Column("raw_text_cleaned", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "draft_sets",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "person_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "raw_experience_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("raw_experiences.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("run_version", sa.Integer(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "experience_cards",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "person_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("normalized_role", sa.Text(), nullable=True),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("sub_domain", sa.Text(), nullable=True),
        sa.Column("company_name", sa.Text(), nullable=True),
        sa.Column("company_type", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("employment_type", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("intent_primary", sa.Text(), nullable=True),
        sa.Column("intent_secondary", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("seniority_level", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("visibility", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_experience_card_parent", "experience_cards", ["person_id"])

    op.create_table(
        "experience_card_children",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "parent_experience_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("experience_cards.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "person_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "raw_experience_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("raw_experiences.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "draft_set_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("draft_sets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("child_type", sa.String(50), nullable=False),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("search_phrases", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("search_document", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("extra", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_experience_card_child_type",
        "experience_card_children",
        ["parent_experience_id", "child_type"],
        unique=True,
    )

    op.create_table(
        "searches",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "searcher_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("filters", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "search_results",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "search_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("searches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "person_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Numeric(10, 6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_search_results_search_person",
        "search_results",
        ["search_id", "person_id"],
        unique=True,
    )

    op.create_table(
        "unlock_contacts",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "searcher_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_person_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "search_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("searches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_unlock_contacts_searcher_target",
        "unlock_contacts",
        ["searcher_id", "target_person_id", "search_id"],
        unique=True,
    )


def downgrade() -> None:
    # Destructive rollback: drop all tables.
    op.execute("DROP TABLE IF EXISTS unlock_contacts CASCADE")
    op.execute("DROP TABLE IF EXISTS search_results CASCADE")
    op.execute("DROP TABLE IF EXISTS searches CASCADE")
    op.execute("DROP TABLE IF EXISTS experience_card_children CASCADE")
    op.execute("DROP TABLE IF EXISTS experience_cards CASCADE")
    op.execute("DROP TABLE IF EXISTS draft_sets CASCADE")
    op.execute("DROP TABLE IF EXISTS raw_experiences CASCADE")
    op.execute("DROP TABLE IF EXISTS idempotency_keys CASCADE")
    op.execute("DROP TABLE IF EXISTS credit_ledger CASCADE")
    op.execute("DROP TABLE IF EXISTS credit_wallets CASCADE")
    op.execute("DROP TABLE IF EXISTS contact_details CASCADE")
    op.execute("DROP TABLE IF EXISTS visibility_settings CASCADE")
    op.execute("DROP TABLE IF EXISTS bios CASCADE")
    op.execute("DROP TABLE IF EXISTS people CASCADE")
