import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    Integer,
    Numeric,
    Float,
    Date,
    DateTime,
    ForeignKey,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.orm import relationship, synonym

from .session import Base

from pgvector.sqlalchemy import Vector


def uuid4_str():
    return str(uuid.uuid4())


class Person(Base):
    __tablename__ = "people"

    id = Column(UUID(as_uuid=False), primary_key=True, default=uuid4_str)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))

    profile = relationship("PersonProfile", back_populates="person", uselist=False)
    raw_experiences = relationship("RawExperience", back_populates="person")
    draft_sets = relationship("DraftSet", back_populates="person")
    experience_cards = relationship("ExperienceCard", back_populates="person")
    experience_card_children = relationship("ExperienceCardChild", back_populates="person")
    searches_made = relationship("Search", back_populates="searcher", foreign_keys="Search.searcher_id")


class PersonProfile(Base):
    """Merged profile: bio + visibility + contact prefs + wallet balance (one row per person)."""
    __tablename__ = "person_profiles"

    id = Column(UUID(as_uuid=False), primary_key=True, default=uuid4_str)
    person_id = Column(UUID(as_uuid=False), ForeignKey("people.id", ondelete="CASCADE"), nullable=False, unique=True)

    # Bio
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    date_of_birth = Column(String(20), nullable=True)
    current_city = Column(String(255), nullable=True)
    profile_photo_url = Column(String(1000), nullable=True)
    school = Column(String(255), nullable=True)
    college = Column(String(255), nullable=True)
    current_company = Column(String(255), nullable=True)
    past_companies = Column(JSONB, nullable=True)

    # Visibility
    open_to_work = Column(Boolean, default=False)
    work_preferred_locations = Column(ARRAY(String), default=list)
    work_preferred_salary_min = Column(Numeric(12, 2), nullable=True)  # minimum salary needed (₹/year)
    open_to_contact = Column(Boolean, default=False)

    # Contact
    email_visible = Column(Boolean, default=True)
    phone = Column(String(50), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    other = Column(Text, nullable=True)

    # Wallet
    balance = Column(Integer, default=1000, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))

    person = relationship("Person", back_populates="profile")


class CreditLedger(Base):
    __tablename__ = "credit_ledger"

    id = Column(UUID(as_uuid=False), primary_key=True, default=uuid4_str)
    person_id = Column(UUID(as_uuid=False), ForeignKey("people.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Integer, nullable=False)  # negative for debit
    reason = Column(String(100), nullable=False)  # signup, search, unlock_contact
    reference_type = Column(String(50), nullable=True)  # search_id, unlock_id
    reference_id = Column(UUID(as_uuid=False), nullable=True)
    balance_after = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_credit_ledger_person_id", "person_id"),)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    id = Column(UUID(as_uuid=False), primary_key=True, default=uuid4_str)
    key = Column(String(255), nullable=False, index=True)
    person_id = Column(UUID(as_uuid=False), ForeignKey("people.id", ondelete="CASCADE"), nullable=False)
    endpoint = Column(String(100), nullable=False)
    response_status = Column(Integer, nullable=True)
    response_body = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_idempotency_keys_key_person_endpoint", "key", "person_id", "endpoint", unique=True),)


class RawExperience(Base):
    __tablename__ = "raw_experiences"

    id = Column(UUID(as_uuid=False), primary_key=True, default=uuid4_str)
    person_id = Column(UUID(as_uuid=False), ForeignKey("people.id", ondelete="CASCADE"), nullable=False)
    raw_text = Column(Text, nullable=False)
    raw_text_original = Column(Text, nullable=True)
    raw_text_cleaned = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    person = relationship("Person", back_populates="raw_experiences")
    draft_sets = relationship("DraftSet", back_populates="raw_experience")


class DraftSet(Base):
    __tablename__ = "draft_sets"

    id = Column(UUID(as_uuid=False), primary_key=True, default=uuid4_str)
    person_id = Column(UUID(as_uuid=False), ForeignKey("people.id", ondelete="CASCADE"), nullable=False)
    raw_experience_id = Column(UUID(as_uuid=False), ForeignKey("raw_experiences.id", ondelete="CASCADE"), nullable=False)
    run_version = Column(Integer, nullable=False, default=1)
    extra_metadata = Column("metadata", JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    person = relationship("Person", back_populates="draft_sets")
    raw_experience = relationship("RawExperience", back_populates="draft_sets")
    experience_card_children = relationship("ExperienceCardChild", back_populates="draft_set")
    experience_cards = relationship("ExperienceCard", back_populates="draft_set")


class ExperienceCard(Base):
    __tablename__ = "experience_cards"

    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    HIDDEN = "HIDDEN"

    id = Column(UUID(as_uuid=False), primary_key=True, default=uuid4_str)
    person_id = Column(UUID(as_uuid=False), ForeignKey("people.id", ondelete="CASCADE"), nullable=False)
    draft_set_id = Column(UUID(as_uuid=False), ForeignKey("draft_sets.id", ondelete="SET NULL"), nullable=True)
    user_id = synonym("person_id")

    title = Column(Text, nullable=True)
    normalized_role = Column(Text, nullable=True)

    domain = Column(Text, nullable=True)
    sub_domain = Column(Text, nullable=True)

    company_name = Column(Text, nullable=True)
    company_norm = Column(String(255), nullable=True, index=True)  # lowercased trimmed for exact match
    company_type = Column(Text, nullable=True)
    team = Column(Text, nullable=True)
    team_norm = Column(String(255), nullable=True, index=True)  # lowercased trimmed for ILIKE

    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    is_current = Column(Boolean, nullable=True)

    location = Column(Text, nullable=True)
    employment_type = Column(Text, nullable=True)

    summary = Column(Text, nullable=True)
    raw_text = Column(Text, nullable=True)

    intent_primary = Column(Text, nullable=True)
    intent_secondary = Column(ARRAY(String), default=list)

    seniority_level = Column(Text, nullable=True)

    confidence_score = Column(Float, nullable=True)
    experience_card_visibility = Column(Boolean, default=True, nullable=False)
    search_phrases = Column(ARRAY(String), default=list)
    search_document = Column(Text, nullable=True)
    embedding = Column(Vector(324), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))

    person = relationship("Person", back_populates="experience_cards")
    draft_set = relationship("DraftSet", back_populates="experience_cards")
    children = relationship("ExperienceCardChild", back_populates="experience", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_experience_card_parent", "person_id"),)


class ExperienceCardChild(Base):
    __tablename__ = "experience_card_children"

    id = Column(UUID(as_uuid=False), primary_key=True, default=uuid4_str)
    parent_experience_id = Column(UUID(as_uuid=False), ForeignKey("experience_cards.id", ondelete="CASCADE"), nullable=False)
    person_id = Column(UUID(as_uuid=False), ForeignKey("people.id", ondelete="CASCADE"), nullable=False)
    raw_experience_id = Column(UUID(as_uuid=False), ForeignKey("raw_experiences.id", ondelete="SET NULL"), nullable=True)
    draft_set_id = Column(UUID(as_uuid=False), ForeignKey("draft_sets.id", ondelete="SET NULL"), nullable=True)

    child_type = Column(String(50), nullable=False)  
    label = Column(String(255), nullable=True)

    value = Column(JSONB, nullable=False)  # DIMENSION CONTAINER

    confidence_score = Column(Float, nullable=True)

    search_phrases = Column(ARRAY(String), default=list)
    search_document = Column(Text, nullable=True)
    embedding = Column(Vector(324), nullable=True)

    extra = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))

    person = relationship("Person", back_populates="experience_card_children")
    draft_set = relationship("DraftSet", back_populates="experience_card_children")
    experience = relationship("ExperienceCard", back_populates="children")

    __table_args__ = (
        Index("uq_experience_card_child_type", "parent_experience_id", "child_type", unique=True),
    )

class Search(Base):
    __tablename__ = "searches"

    id = Column(UUID(as_uuid=False), primary_key=True, default=uuid4_str)
    searcher_id = Column(UUID(as_uuid=False), ForeignKey("people.id", ondelete="CASCADE"), nullable=False)
    query_text = Column(Text, nullable=False)  # raw_query
    parsed_constraints_json = Column(JSONB, nullable=True)
    filters = Column(JSONB, nullable=True)  # legacy / extra
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)

    searcher = relationship("Person", back_populates="searches_made", foreign_keys=[searcher_id])
    results = relationship("SearchResult", back_populates="search")


class SearchResult(Base):
    __tablename__ = "search_results"

    id = Column(UUID(as_uuid=False), primary_key=True, default=uuid4_str)
    search_id = Column(UUID(as_uuid=False), ForeignKey("searches.id", ondelete="CASCADE"), nullable=False)
    person_id = Column(UUID(as_uuid=False), ForeignKey("people.id", ondelete="CASCADE"), nullable=False)
    rank = Column(Integer, nullable=False)
    score = Column(Numeric(10, 6), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    search = relationship("Search", back_populates="results")
    __table_args__ = (Index("ix_search_results_search_person", "search_id", "person_id", unique=True),)


class UnlockContact(Base):
    __tablename__ = "unlock_contacts"

    id = Column(UUID(as_uuid=False), primary_key=True, default=uuid4_str)
    searcher_id = Column(UUID(as_uuid=False), ForeignKey("people.id", ondelete="CASCADE"), nullable=False)
    target_person_id = Column(UUID(as_uuid=False), ForeignKey("people.id", ondelete="CASCADE"), nullable=False)
    search_id = Column(UUID(as_uuid=False), ForeignKey("searches.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_unlock_contacts_searcher_target", "searcher_id", "target_person_id", "search_id", unique=True),
    )
