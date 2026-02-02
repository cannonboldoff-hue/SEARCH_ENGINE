from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, EmailStr
from uuid import UUID


# Auth
class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# Me
class PersonResponse(BaseModel):
    id: str
    email: str
    display_name: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PatchMeRequest(BaseModel):
    display_name: Optional[str] = None


class VisibilitySettingsResponse(BaseModel):
    open_to_work: bool
    work_preferred_locations: list[str]
    work_preferred_salary_min: Optional[Decimal] = None
    work_preferred_salary_max: Optional[Decimal] = None
    open_to_contact: bool
    contact_preferred_salary_min: Optional[Decimal] = None
    contact_preferred_salary_max: Optional[Decimal] = None


class PatchVisibilityRequest(BaseModel):
    open_to_work: Optional[bool] = None
    work_preferred_locations: Optional[list[str]] = None
    work_preferred_salary_min: Optional[Decimal] = None
    work_preferred_salary_max: Optional[Decimal] = None
    open_to_contact: Optional[bool] = None
    contact_preferred_salary_min: Optional[Decimal] = None
    contact_preferred_salary_max: Optional[Decimal] = None


# Contact
class ContactDetailsResponse(BaseModel):
    email_visible: bool
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    other: Optional[str] = None


class PatchContactRequest(BaseModel):
    email_visible: Optional[bool] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    other: Optional[str] = None


# Credits
class CreditsResponse(BaseModel):
    balance: int


class LedgerEntryResponse(BaseModel):
    id: str
    amount: int
    reason: str
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    balance_after: Optional[int] = None
    created_at: datetime


# Builder
class RawExperienceCreate(BaseModel):
    raw_text: str


class RawExperienceResponse(BaseModel):
    id: str
    raw_text: str
    created_at: Optional[datetime] = None


class DraftCardResponse(BaseModel):
    draft_card_id: str
    title: Optional[str] = None
    context: Optional[str] = None
    constraints: Optional[str] = None
    decisions: Optional[str] = None
    outcome: Optional[str] = None
    tags: list[str]
    company: Optional[str] = None
    team: Optional[str] = None
    role_title: Optional[str] = None
    time_range: Optional[str] = None
    source_span: Optional[str] = None


class DraftSetResponse(BaseModel):
    draft_set_id: str
    raw_experience_id: str
    cards: list[DraftCardResponse]


class ExperienceCardCreate(BaseModel):
    draft_card_id: Optional[str] = None
    raw_experience_id: Optional[str] = None
    title: Optional[str] = None
    context: Optional[str] = None
    constraints: Optional[str] = None
    decisions: Optional[str] = None
    outcome: Optional[str] = None
    tags: list[str] = []
    company: Optional[str] = None
    team: Optional[str] = None
    role_title: Optional[str] = None
    time_range: Optional[str] = None


class ExperienceCardPatch(BaseModel):
    title: Optional[str] = None
    context: Optional[str] = None
    constraints: Optional[str] = None
    decisions: Optional[str] = None
    outcome: Optional[str] = None
    tags: Optional[list[str]] = None
    company: Optional[str] = None
    team: Optional[str] = None
    role_title: Optional[str] = None
    time_range: Optional[str] = None


class ExperienceCardResponse(BaseModel):
    id: str
    person_id: str
    raw_experience_id: Optional[str] = None
    status: str
    title: Optional[str] = None
    context: Optional[str] = None
    constraints: Optional[str] = None
    decisions: Optional[str] = None
    outcome: Optional[str] = None
    tags: list[str]
    company: Optional[str] = None
    team: Optional[str] = None
    role_title: Optional[str] = None
    time_range: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Search
class SearchRequest(BaseModel):
    query: str
    open_to_work_only: Optional[bool] = None
    preferred_locations: Optional[list[str]] = None
    salary_min: Optional[Decimal] = None
    salary_max: Optional[Decimal] = None


class PersonSearchResult(BaseModel):
    id: str
    display_name: Optional[str] = None
    open_to_work: bool
    open_to_contact: bool


class SearchResponse(BaseModel):
    search_id: str
    people: list[PersonSearchResult]


class PersonProfileResponse(BaseModel):
    id: str
    display_name: Optional[str] = None
    open_to_work: bool
    open_to_contact: bool
    work_preferred_locations: list[str]
    work_preferred_salary_min: Optional[Decimal] = None
    work_preferred_salary_max: Optional[Decimal] = None
    contact_preferred_salary_min: Optional[Decimal] = None
    contact_preferred_salary_max: Optional[Decimal] = None
    experience_cards: list[ExperienceCardResponse]
    contact: Optional[ContactDetailsResponse] = None  # only if unlocked


class UnlockContactResponse(BaseModel):
    unlocked: bool
    contact: ContactDetailsResponse
