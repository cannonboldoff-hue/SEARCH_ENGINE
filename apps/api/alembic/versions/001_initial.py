"""Initial schema: people, visibility, contact, credits, experiences, search.

Revision ID: 001
Revises:
Create Date: 2025-02-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "people",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_people_email", "people", ["email"], unique=True)

    op.create_table(
        "visibility_settings",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("person_id", sa.UUID(), sa.ForeignKey("people.id", ondelete="CASCADE"), nullable=False),
        sa.Column("open_to_work", sa.Boolean(), default=False),
        sa.Column("work_preferred_locations", sa.ARRAY(sa.String()), nullable=True),
        sa.Column("work_preferred_salary_min", sa.Numeric(12, 2), nullable=True),
        sa.Column("work_preferred_salary_max", sa.Numeric(12, 2), nullable=True),
        sa.Column("open_to_contact", sa.Boolean(), default=False),
        sa.Column("contact_preferred_salary_min", sa.Numeric(12, 2), nullable=True),
        sa.Column("contact_preferred_salary_max", sa.Numeric(12, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_visibility_settings_person_id", "visibility_settings", ["person_id"], unique=True)

    op.create_table(
        "contact_details",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("person_id", sa.UUID(), sa.ForeignKey("people.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email_visible", sa.Boolean(), default=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("linkedin_url", sa.String(500), nullable=True),
        sa.Column("other", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_contact_details_person_id", "contact_details", ["person_id"], unique=True)

    op.create_table(
        "credit_wallets",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("person_id", sa.UUID(), sa.ForeignKey("people.id", ondelete="CASCADE"), nullable=False),
        sa.Column("balance", sa.Integer(), default=1000, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_credit_wallets_person_id", "credit_wallets", ["person_id"], unique=True)

    op.create_table(
        "credit_ledger",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("person_id", sa.UUID(), sa.ForeignKey("people.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(100), nullable=False),
        sa.Column("reference_type", sa.String(50), nullable=True),
        sa.Column("reference_id", sa.UUID(), nullable=True),
        sa.Column("balance_after", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_credit_ledger_person_id", "credit_ledger", ["person_id"])

    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("person_id", sa.UUID(), sa.ForeignKey("people.id", ondelete="CASCADE"), nullable=False),
        sa.Column("endpoint", sa.String(100), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_idempotency_keys_key", "idempotency_keys", ["key"], unique=True)

    op.create_table(
        "raw_experiences",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("person_id", sa.UUID(), sa.ForeignKey("people.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "experience_cards",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("person_id", sa.UUID(), sa.ForeignKey("people.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raw_experience_id", sa.UUID(), sa.ForeignKey("raw_experiences.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), default="DRAFT", nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("constraints", sa.Text(), nullable=True),
        sa.Column("decisions", sa.Text(), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column("tags", sa.ARRAY(sa.String()), nullable=True),
        sa.Column("company", sa.String(255), nullable=True),
        sa.Column("team", sa.String(255), nullable=True),
        sa.Column("role_title", sa.String(255), nullable=True),
        sa.Column("time_range", sa.String(100), nullable=True),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_experience_cards_status", "experience_cards", ["status"])

    op.create_table(
        "searches",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("searcher_id", sa.UUID(), sa.ForeignKey("people.id", ondelete="CASCADE"), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "search_results",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("search_id", sa.UUID(), sa.ForeignKey("searches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("person_id", sa.UUID(), sa.ForeignKey("people.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Numeric(10, 6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_search_results_search_person", "search_results", ["search_id", "person_id"], unique=True)

    op.create_table(
        "unlock_contacts",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("searcher_id", sa.UUID(), sa.ForeignKey("people.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_person_id", sa.UUID(), sa.ForeignKey("people.id", ondelete="CASCADE"), nullable=False),
        sa.Column("search_id", sa.UUID(), sa.ForeignKey("searches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_unlock_contacts_searcher_target",
        "unlock_contacts",
        ["searcher_id", "target_person_id", "search_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("unlock_contacts")
    op.drop_table("search_results")
    op.drop_table("searches")
    op.drop_table("experience_cards")
    op.drop_table("raw_experiences")
    op.drop_table("idempotency_keys")
    op.drop_table("credit_ledger")
    op.drop_table("credit_wallets")
    op.drop_table("contact_details")
    op.drop_table("visibility_settings")
    op.drop_table("people")
    op.execute("DROP EXTENSION IF EXISTS vector")
