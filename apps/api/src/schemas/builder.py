from datetime import datetime, date
from typing import Optional

from pydantic import BaseModel, ConfigDict


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
    experience_card_visibility: Optional[bool] = None


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
    experience_card_visibility: Optional[bool] = None


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
    experience_card_visibility: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# -----------------------------------------------------------------------------
# Experience Card Children (dimension cards stored in experience_card_children)
# -----------------------------------------------------------------------------


class ExperienceCardChildPatch(BaseModel):
    """
    Patch payload for ExperienceCardChild.
    Updates are applied into ExperienceCardChild.label and ExperienceCardChild.value (dimension container).
    """

    title: Optional[str] = None
    summary: Optional[str] = None
    tags: Optional[list[str]] = None
    time_range: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None


class ExperienceCardChildResponse(BaseModel):
    """Response DTO for ExperienceCardChild."""

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
