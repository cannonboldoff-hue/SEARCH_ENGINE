"""
Domain types and schemas for Experience Cards.
Single source of truth for prompts, validation, and API.
"""

from datetime import datetime
from typing import Literal, Optional, get_args

from pydantic import BaseModel, Field

# -----------------------------------------------------------------------------
# 1. Enums
# -----------------------------------------------------------------------------

Intent = Literal[
    "work", "education", "project", "business", "research",
    "practice", "exposure", "achievement", "transition", "learning",
    "life_context", "community", "finance", "other", "mixed",
]

ChildIntent = Literal[
    "responsibility", "capability", "method", "outcome",
    "learning", "challenge", "decision", "evidence",
]

ChildRelationType = Literal[
    "describes", "supports", "demonstrates", "results_in",
    "learned_from", "involves", "part_of",
]

SeniorityLevel = Literal[
    "intern", "junior", "mid", "senior", "lead", "principal",
    "staff", "manager", "director", "vp", "executive",
    "founder", "independent", "volunteer", "student",
    "apprentice",      # NEW — learning under a master/ustaad
    "owner",           # NEW — family business / own shop
    "other",
]

EmploymentType = Literal[
    "full_time", "part_time", "contract", "freelance",
    "internship", "volunteer", "self_employed", "founder",
    "apprenticeship",  # formal or informal, under a master
    "family_business", # NEW — working in family-owned business
    "daily_wage",      # NEW — informal daily wage / labour
    "gig",             # NEW — gig economy (delivery, ride-share etc.)
    "other",
]

CompanyType = Literal[
    "startup", "scaleup", "mnc", "sme", "agency", "ngo",
    "government", "university", "research_institution",
    "self_employed", "cooperative",
    "family_business",    # NEW — family-owned business
    "informal",           # NEW — street vendor, local shop, dhaba etc.
    "master_apprentice",  # NEW — ustaad/master-based learning or work
    "other",
]

Confidence = Literal["high", "medium", "low"]

Visibility = Literal["private", "profile_only", "searchable"]

ClaimState = Literal["self_claim", "supported", "verified"]

EvidenceType = Literal["link", "file", "reference"]

ToolType = Literal[
    "software", "equipment", "system",
    "platform", "instrument", "other",
]

EntityType = Literal[
    "person", "organization", "company", "school", "team",
    "community", "place", "event", "program", "domain", "industry",
    "product", "service", "artifact", "document", "portfolio_item",
    "credential", "award", "tool", "equipment", "system", "platform",
    "instrument", "method", "process",
]

# NEW — describes how two parallel experiences relate to each other
ExperienceRelationType = Literal[
    "parallel",       # running simultaneously (job + side business)
    "sequential",     # one after the other
    "nested",         # one within the other (project within a job)
    "transitional",   # one led directly to the other
]

# -----------------------------------------------------------------------------
# 2. Constants
# -----------------------------------------------------------------------------

ALLOWED_CHILD_TYPES: tuple[str, ...] = (
    "skills", "tools", "metrics", "achievements", "responsibilities",
    "collaborations", "domain_knowledge", "exposure", "education", "certifications",
)

ENTITY_TAXONOMY: list[str] = list(get_args(EntityType))

# -----------------------------------------------------------------------------
# 3. Nested field models
# -----------------------------------------------------------------------------

class TimeField(BaseModel):
    start: Optional[str] = None       # YYYY-MM | YYYY-MM-DD
    end: Optional[str] = None
    ongoing: Optional[bool] = None
    text: Optional[str] = None        # user's original phrasing
    confidence: Confidence


class LocationField(BaseModel):
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None
    text: Optional[str] = None        # user's original phrasing
    is_remote: Optional[bool] = None  # NEW — explicit remote flag
    confidence: Confidence


class RoleItem(BaseModel):
    label: str
    seniority: Optional[SeniorityLevel] = None
    confidence: Confidence


class EntityItem(BaseModel):
    type: EntityType
    name: str
    entity_id: Optional[str] = None
    confidence: Confidence


class ToolItem(BaseModel):
    name: str
    type: ToolType
    confidence: Confidence


class ToolingField(BaseModel):
    tools: list[ToolItem] = Field(default_factory=list)
    raw: Optional[str] = None


class OutcomeMetric(BaseModel):
    name: Optional[str] = None
    value: Optional[float] = None
    unit: Optional[str] = None


class OutcomeItem(BaseModel):
    type: str
    label: str
    value_text: Optional[str] = None
    metric: OutcomeMetric
    confidence: Confidence


class EvidenceItem(BaseModel):
    type: EvidenceType
    url: Optional[str] = None
    note: Optional[str] = None
    visibility: Visibility


class PrivacyField(BaseModel):
    visibility: Visibility
    sensitive: bool


class QualityField(BaseModel):
    overall_confidence: Confidence
    claim_state: ClaimState
    needs_clarification: bool
    clarifying_question: Optional[str] = None


class IndexField(BaseModel):
    embedding_ref: Optional[str] = None


# -----------------------------------------------------------------------------
# Person (profile) domain types
# -----------------------------------------------------------------------------

class LocationBasic(BaseModel):
    """Simple location for person profile."""
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None


class PersonVerification(BaseModel):
    status: str = "unverified"
    methods: list = Field(default_factory=list)


class PersonPrivacyDefaults(BaseModel):
    default_visibility: str = "private"


class PersonSchema(BaseModel):
    """Person profile schema (for /profile, serializers)."""
    person_id: str
    username: str
    display_name: str
    photo_url: Optional[str] = None
    bio: Optional[str] = None
    location: LocationBasic
    verification: PersonVerification
    privacy_defaults: PersonPrivacyDefaults
    created_at: datetime
    updated_at: datetime


# Alias for API/serializers (same shape as LocationField).
LocationWithConfidence = LocationField


class LanguageField(BaseModel):
    raw_text: Optional[str] = None
    confidence: Confidence


# NEW — links two experience cards that overlapped in time
class ExperienceRelation(BaseModel):
    related_card_id: str
    relation_type: ExperienceRelationType
    note: Optional[str] = None        # e.g. "ran this side business while employed at X"


# -----------------------------------------------------------------------------
# 4. Experience Card schemas
# -----------------------------------------------------------------------------

class _ExperienceCardBase(BaseModel):
    """Shared fields for parent and child cards."""
    id: str
    person_id: str
    created_by: str
    version: Literal[1] = 1
    edited_at: Optional[datetime] = None
    headline: str
    summary: str
    raw_text: str
    time: TimeField
    location: LocationField
    roles: list[RoleItem] = Field(default_factory=list)
    entities: list[EntityItem] = Field(default_factory=list)
    tooling: ToolingField = Field(default_factory=ToolingField)
    outcomes: list[OutcomeItem] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    privacy: PrivacyField
    quality: QualityField
    index: IndexField = Field(default_factory=IndexField)
    created_at: datetime
    updated_at: datetime


class ExperienceCardParentSchema(_ExperienceCardBase):
    """Parent card — root of a card family."""
    parent_id: Optional[str] = None
    depth: Literal[0] = 0
    relation_type: Optional[str] = None
    intent: Intent
    intent_secondary: list[Intent] = Field(default_factory=list)
    seniority_level: Optional[SeniorityLevel] = None
    employment_type: Optional[EmploymentType] = None
    company_type: Optional[CompanyType] = None
    relations: list[ExperienceRelation] = Field(default_factory=list)  # NEW — parallel/overlapping experiences


class ExperienceCardChildSchema(_ExperienceCardBase):
    """Child card — belongs to a parent."""
    parent_id: str
    depth: Literal[1] = 1
    relation_type: ChildRelationType
    intent: ChildIntent
    child_type: str  # validated against ALLOWED_CHILD_TYPES at service layer


ExperienceCardSchema = ExperienceCardParentSchema