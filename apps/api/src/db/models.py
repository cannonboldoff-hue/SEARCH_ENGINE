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
    DateTime,
    ForeignKey,
    Index,
    JSON,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship

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

    visibility_settings = relationship("VisibilitySettings", back_populates="person", uselist=False)
    contact_details = relationship("ContactDetails", back_populates="person", uselist=False)
    credit_wallet = relationship("CreditWallet", back_populates="person", uselist=False)
    bio = relationship("Bio", back_populates="person", uselist=False)
    raw_experiences = relationship("RawExperience", back_populates="person")
    experience_cards = relationship("ExperienceCard", back_populates="person")
    searches_made = relationship("Search", back_populates="searcher", foreign_keys="Search.searcher_id")


class Bio(Base):
    __tablename__ = "bios"

    id = Column(UUID(as_uuid=False), primary_key=True, default=uuid4_str)
    person_id = Column(UUID(as_uuid=False), ForeignKey("people.id", ondelete="CASCADE"), nullable=False, unique=True)

    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    date_of_birth = Column(String(20), nullable=True)  # YYYY-MM-DD or free text
    current_city = Column(String(255), nullable=True)
    profile_photo_url = Column(String(1000), nullable=True)

    school = Column(String(255), nullable=True)
    college = Column(String(255), nullable=True)

    current_company = Column(String(255), nullable=True)
    past_companies = Column(JSON, nullable=True)  # list of {company_name, role?, years?}

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))

    person = relationship("Person", back_populates="bio")


class VisibilitySettings(Base):
    __tablename__ = "visibility_settings"

    id = Column(UUID(as_uuid=False), primary_key=True, default=uuid4_str)
    person_id = Column(UUID(as_uuid=False), ForeignKey("people.id", ondelete="CASCADE"), nullable=False, unique=True)

    open_to_work = Column(Boolean, default=False)
    work_preferred_locations = Column(ARRAY(String), default=list)
    work_preferred_salary_min = Column(Numeric(12, 2), nullable=True)
    work_preferred_salary_max = Column(Numeric(12, 2), nullable=True)

    open_to_contact = Column(Boolean, default=False)
    contact_preferred_salary_min = Column(Numeric(12, 2), nullable=True)
    contact_preferred_salary_max = Column(Numeric(12, 2), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))

    person = relationship("Person", back_populates="visibility_settings")


class ContactDetails(Base):
    __tablename__ = "contact_details"

    id = Column(UUID(as_uuid=False), primary_key=True, default=uuid4_str)
    person_id = Column(UUID(as_uuid=False), ForeignKey("people.id", ondelete="CASCADE"), nullable=False, unique=True)

    email_visible = Column(Boolean, default=True)
    phone = Column(String(50), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    other = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))

    person = relationship("Person", back_populates="contact_details")


class CreditWallet(Base):
    __tablename__ = "credit_wallets"

    id = Column(UUID(as_uuid=False), primary_key=True, default=uuid4_str)
    person_id = Column(UUID(as_uuid=False), ForeignKey("people.id", ondelete="CASCADE"), nullable=False, unique=True)
    balance = Column(Integer, default=1000, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))

    person = relationship("Person", back_populates="credit_wallet")


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
    response_body = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_idempotency_keys_key_person_endpoint", "key", "person_id", "endpoint", unique=True),)


class RawExperience(Base):
    __tablename__ = "raw_experiences"

    id = Column(UUID(as_uuid=False), primary_key=True, default=uuid4_str)
    person_id = Column(UUID(as_uuid=False), ForeignKey("people.id", ondelete="CASCADE"), nullable=False)
    raw_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    person = relationship("Person", back_populates="raw_experiences")


class ExperienceCard(Base):
    __tablename__ = "experience_cards"

    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    HIDDEN = "HIDDEN"

    id = Column(UUID(as_uuid=False), primary_key=True, default=uuid4_str)
    person_id = Column(UUID(as_uuid=False), ForeignKey("people.id", ondelete="CASCADE"), nullable=False)
    raw_experience_id = Column(UUID(as_uuid=False), ForeignKey("raw_experiences.id", ondelete="SET NULL"), nullable=True)

    status = Column(String(20), default=DRAFT, nullable=False, index=True)
    human_edited = Column(Boolean, default=False, nullable=False)
    locked = Column(Boolean, default=False, nullable=False)

    title = Column(String(500), nullable=True)
    context = Column(Text, nullable=True)
    constraints = Column(Text, nullable=True)
    decisions = Column(Text, nullable=True)
    outcome = Column(Text, nullable=True)
    tags = Column(ARRAY(String), default=list)

    company = Column(String(255), nullable=True)
    team = Column(String(255), nullable=True)
    role_title = Column(String(255), nullable=True)
    time_range = Column(String(100), nullable=True)
    location = Column(String(255), nullable=True)

    embedding = Column(Vector(384), nullable=True)  # bge-base typically 384 or 768

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))

    person = relationship("Person", back_populates="experience_cards")


class Search(Base):
    __tablename__ = "searches"

    id = Column(UUID(as_uuid=False), primary_key=True, default=uuid4_str)
    searcher_id = Column(UUID(as_uuid=False), ForeignKey("people.id", ondelete="CASCADE"), nullable=False)
    query_text = Column(Text, nullable=False)
    filters = Column(JSON, nullable=True)  # company, team, open_to_work_only, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())

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
