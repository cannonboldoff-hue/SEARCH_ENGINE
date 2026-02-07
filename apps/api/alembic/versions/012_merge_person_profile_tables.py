"""Merge bios, visibility_settings, contact_details, credit_wallets into person_profiles.

Revision ID: 012
Revises: 011
Create Date: 2026-02-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB


revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "person_profiles",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("person_id", UUID(as_uuid=False), sa.ForeignKey("people.id", ondelete="CASCADE"), nullable=False),
        sa.Column("first_name", sa.String(255), nullable=True),
        sa.Column("last_name", sa.String(255), nullable=True),
        sa.Column("date_of_birth", sa.String(20), nullable=True),
        sa.Column("current_city", sa.String(255), nullable=True),
        sa.Column("profile_photo_url", sa.String(1000), nullable=True),
        sa.Column("school", sa.String(255), nullable=True),
        sa.Column("college", sa.String(255), nullable=True),
        sa.Column("current_company", sa.String(255), nullable=True),
        sa.Column("past_companies", JSONB, nullable=True),
        sa.Column("open_to_work", sa.Boolean(), server_default="false"),
        sa.Column("work_preferred_locations", ARRAY(sa.String()), server_default="{}"),
        sa.Column("work_preferred_salary_min", sa.Numeric(12, 2), nullable=True),
        sa.Column("work_preferred_salary_max", sa.Numeric(12, 2), nullable=True),
        sa.Column("open_to_contact", sa.Boolean(), server_default="false"),
        sa.Column("email_visible", sa.Boolean(), server_default="true"),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("linkedin_url", sa.String(500), nullable=True),
        sa.Column("other", sa.Text(), nullable=True),
        sa.Column("balance", sa.Integer(), server_default="1000", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_person_profiles_person_id", "person_profiles", ["person_id"], unique=True)

    # Migrate data: one row per person from people, coalescing from the four tables
    op.execute("""
        INSERT INTO person_profiles (
            id, person_id,
            first_name, last_name, date_of_birth, current_city, profile_photo_url,
            school, college, current_company, past_companies,
            open_to_work, work_preferred_locations, work_preferred_salary_min, work_preferred_salary_max, open_to_contact,
            email_visible, phone, linkedin_url, other,
            balance
        )
        SELECT
            gen_random_uuid(),
            p.id,
            b.first_name, b.last_name, b.date_of_birth, b.current_city, b.profile_photo_url,
            b.school, b.college, b.current_company, b.past_companies,
            COALESCE(vs.open_to_work, false), COALESCE(vs.work_preferred_locations, '{}'),
            vs.work_preferred_salary_min, vs.work_preferred_salary_max, COALESCE(vs.open_to_contact, false),
            COALESCE(cd.email_visible, true), cd.phone, cd.linkedin_url, cd.other,
            COALESCE(cw.balance, 1000)
        FROM people p
        LEFT JOIN bios b ON b.person_id = p.id
        LEFT JOIN visibility_settings vs ON vs.person_id = p.id
        LEFT JOIN contact_details cd ON cd.person_id = p.id
        LEFT JOIN credit_wallets cw ON cw.person_id = p.id
    """)

    op.drop_table("credit_wallets")
    op.drop_table("contact_details")
    op.drop_table("visibility_settings")
    op.drop_table("bios")


def downgrade() -> None:
    op.create_table(
        "bios",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("person_id", UUID(as_uuid=False), sa.ForeignKey("people.id", ondelete="CASCADE"), nullable=False),
        sa.Column("first_name", sa.String(255), nullable=True),
        sa.Column("last_name", sa.String(255), nullable=True),
        sa.Column("date_of_birth", sa.String(20), nullable=True),
        sa.Column("current_city", sa.String(255), nullable=True),
        sa.Column("profile_photo_url", sa.String(1000), nullable=True),
        sa.Column("school", sa.String(255), nullable=True),
        sa.Column("college", sa.String(255), nullable=True),
        sa.Column("current_company", sa.String(255), nullable=True),
        sa.Column("past_companies", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_bios_person_id", "bios", ["person_id"], unique=True)

    op.create_table(
        "visibility_settings",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("person_id", UUID(as_uuid=False), sa.ForeignKey("people.id", ondelete="CASCADE"), nullable=False),
        sa.Column("open_to_work", sa.Boolean(), server_default="false"),
        sa.Column("work_preferred_locations", ARRAY(sa.String()), server_default="{}"),
        sa.Column("work_preferred_salary_min", sa.Numeric(12, 2), nullable=True),
        sa.Column("work_preferred_salary_max", sa.Numeric(12, 2), nullable=True),
        sa.Column("open_to_contact", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_visibility_settings_person_id", "visibility_settings", ["person_id"], unique=True)

    op.create_table(
        "contact_details",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("person_id", UUID(as_uuid=False), sa.ForeignKey("people.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email_visible", sa.Boolean(), server_default="true"),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("linkedin_url", sa.String(500), nullable=True),
        sa.Column("other", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_contact_details_person_id", "contact_details", ["person_id"], unique=True)

    op.create_table(
        "credit_wallets",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("person_id", UUID(as_uuid=False), sa.ForeignKey("people.id", ondelete="CASCADE"), nullable=False),
        sa.Column("balance", sa.Integer(), server_default="1000", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_credit_wallets_person_id", "credit_wallets", ["person_id"], unique=True)

    # Copy data back from person_profiles
    op.execute("""
        INSERT INTO bios (id, person_id, first_name, last_name, date_of_birth, current_city, profile_photo_url, school, college, current_company, past_companies)
        SELECT gen_random_uuid(), person_id, first_name, last_name, date_of_birth, current_city, profile_photo_url, school, college, current_company, past_companies
        FROM person_profiles
    """)
    op.execute("""
        INSERT INTO visibility_settings (id, person_id, open_to_work, work_preferred_locations, work_preferred_salary_min, work_preferred_salary_max, open_to_contact)
        SELECT gen_random_uuid(), person_id, open_to_work, work_preferred_locations, work_preferred_salary_min, work_preferred_salary_max, open_to_contact
        FROM person_profiles
    """)
    op.execute("""
        INSERT INTO contact_details (id, person_id, email_visible, phone, linkedin_url, other)
        SELECT gen_random_uuid(), person_id, email_visible, phone, linkedin_url, other
        FROM person_profiles
    """)
    op.execute("""
        INSERT INTO credit_wallets (id, person_id, balance)
        SELECT gen_random_uuid(), person_id, balance
        FROM person_profiles
    """)

    op.drop_index("ix_person_profiles_person_id", "person_profiles")
    op.drop_table("person_profiles")
