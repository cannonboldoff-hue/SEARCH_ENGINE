from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr


# -----------------------------------------------------------------------------
# Auth
# -----------------------------------------------------------------------------
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


# -----------------------------------------------------------------------------
# Me
# -----------------------------------------------------------------------------


class PersonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: Optional[str] = None
    created_at: Optional[datetime] = None


class PatchMeRequest(BaseModel):
    display_name: Optional[str] = None


class VisibilitySettingsResponse(BaseModel):
    """Matches db.models.VisibilitySettings."""

    open_to_work: bool
    work_preferred_locations: list[str]
    work_preferred_salary_min: Optional[Decimal] = None
    work_preferred_salary_max: Optional[Decimal] = None
    open_to_contact: bool


class PatchVisibilityRequest(BaseModel):
    """Optional fields for patching VisibilitySettings (matches DB columns)."""

    open_to_work: Optional[bool] = None
    work_preferred_locations: Optional[list[str]] = None
    work_preferred_salary_min: Optional[Decimal] = None
    work_preferred_salary_max: Optional[Decimal] = None
    open_to_contact: Optional[bool] = None


# -----------------------------------------------------------------------------
# Bio (onboarding + profile context)
# -----------------------------------------------------------------------------
class PastCompanyItem(BaseModel):
    company_name: str
    role: Optional[str] = None
    years: Optional[str] = None


class BioResponse(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    current_city: Optional[str] = None
    profile_photo_url: Optional[str] = None
    school: Optional[str] = None
    college: Optional[str] = None
    current_company: Optional[str] = None
    past_companies: Optional[list[PastCompanyItem]] = None
    email: Optional[str] = None  # from Person, for display
    linkedin_url: Optional[str] = None  # from ContactDetails
    phone: Optional[str] = None  # from ContactDetails
    complete: bool = False

    model_config = ConfigDict(from_attributes=True)


class BioCreateUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    current_city: Optional[str] = None
    profile_photo_url: Optional[str] = None
    school: Optional[str] = None
    college: Optional[str] = None
    current_company: Optional[str] = None
    past_companies: Optional[list[PastCompanyItem]] = None
    email: Optional[str] = None  # sync to Person.email if provided
    linkedin_url: Optional[str] = None  # sync to ContactDetails
    phone: Optional[str] = None  # sync to ContactDetails


# -----------------------------------------------------------------------------
# Contact
# -----------------------------------------------------------------------------
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


# -----------------------------------------------------------------------------
# Credits
# -----------------------------------------------------------------------------
class CreditsResponse(BaseModel):
    balance: int


class PurchaseCreditsRequest(BaseModel):
    credits: int


class LedgerEntryResponse(BaseModel):
    id: str
    amount: int
    reason: str
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    balance_after: Optional[int] = None
    created_at: datetime


# -----------------------------------------------------------------------------
# Builder
# -----------------------------------------------------------------------------
class RawExperienceCreate(BaseModel):
    raw_text: str


class RawExperienceResponse(BaseModel):
    id: str
    raw_text: str
    created_at: Optional[datetime] = None


class RewriteTextResponse(BaseModel):
    """Result of POST /experiences/rewrite: cleaned English text."""

    rewritten_text: str


class CardFamilyV1Response(BaseModel):
    """One parent Experience Card v1 + its child cards (validated)."""

    parent: dict  # Experience Card v1 parent (depth=0)
    children: list[dict] = []  # Experience Card v1 children (depth=1)


class DraftSetV1Response(BaseModel):
    """Result of Experience Card v1 pipeline: cleanup → extract-all → validate-all."""

    draft_set_id: str
    raw_experience_id: str
    card_families: list[CardFamilyV1Response]


class CommitDraftSetRequest(BaseModel):
    """Optional body for commit: approve only selected card ids, or all if omitted."""

    card_ids: Optional[list[str]] = None


class ExperienceCardCreate(BaseModel):
    title: Optional[str] = None
    normalized_role: Optional[str] = None
    domain: Optional[str] = None
    sub_domain: Optional[str] = None
    company_name: Optional[str] = None
    company_type: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: Optional[bool] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    summary: Optional[str] = None
    raw_text: Optional[str] = None
    intent_primary: Optional[str] = None
    intent_secondary: Optional[list[str]] = None
    seniority_level: Optional[str] = None
    confidence_score: Optional[float] = None
    visibility: Optional[bool] = None


class ExperienceCardPatch(BaseModel):
    title: Optional[str] = None
    normalized_role: Optional[str] = None
    domain: Optional[str] = None
    sub_domain: Optional[str] = None
    company_name: Optional[str] = None
    company_type: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: Optional[bool] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    summary: Optional[str] = None
    raw_text: Optional[str] = None
    intent_primary: Optional[str] = None
    intent_secondary: Optional[list[str]] = None
    seniority_level: Optional[str] = None
    confidence_score: Optional[float] = None
    visibility: Optional[bool] = None


class ExperienceCardResponse(BaseModel):
    id: str
    user_id: str
    title: Optional[str] = None
    normalized_role: Optional[str] = None
    domain: Optional[str] = None
    sub_domain: Optional[str] = None
    company_name: Optional[str] = None
    company_type: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: Optional[bool] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    summary: Optional[str] = None
    raw_text: Optional[str] = None
    intent_primary: Optional[str] = None
    intent_secondary: list[str] = []
    seniority_level: Optional[str] = None
    confidence_score: Optional[float] = None
    visibility: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# -----------------------------------------------------------------------------
# Experience Card Children (dimension cards stored in experience_card_children)
# -----------------------------------------------------------------------------

class ExperienceCardChildPatch(BaseModel):
    """
    Patch payload for ExperienceCardChild.

    This intentionally mirrors the "draft-v1" child DTO fields that the web builder displays.
    Updates are applied into ExperienceCardChild.label and ExperienceCardChild.value (dimension container).
    """

    title: Optional[str] = None
    summary: Optional[str] = None
    tags: Optional[list[str]] = None
    time_range: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None


class ExperienceCardChildResponse(BaseModel):
    """
    Response DTO for ExperienceCardChild.

    Kept compatible with the structure returned inside draft-v1 `card_families[].children[]`.
    """

    id: str
    title: str = ""
    context: str = ""
    tags: list[str] = []
    headline: str = ""
    summary: str = ""
    topics: list[dict] = []
    time_range: Optional[str] = None
    role_title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CardFamilyResponse(BaseModel):
    """One parent experience card and its child cards (for saved cards list)."""

    parent: ExperienceCardResponse
    children: list[ExperienceCardChildResponse] = []


# -----------------------------------------------------------------------------
# Search
# -----------------------------------------------------------------------------
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
    """Profile for search results; visibility fields match db.models.VisibilitySettings."""

    id: str
    display_name: Optional[str] = None
    open_to_work: bool
    open_to_contact: bool
    work_preferred_locations: list[str]
    work_preferred_salary_min: Optional[Decimal] = None
    work_preferred_salary_max: Optional[Decimal] = None
    experience_cards: list[ExperienceCardResponse]
    contact: Optional[ContactDetailsResponse] = None  # only if unlocked


class UnlockContactResponse(BaseModel):
    unlocked: bool
    contact: ContactDetailsResponse
