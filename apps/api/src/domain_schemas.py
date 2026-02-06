"""
Domain schemas: enums and core entities (Person, Experience Card v1).
Source of truth for API spec. Use for validation, docs, and future API alignment.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

# -----------------------------------------------------------------------------
# 1.1 Enums (Literal types for JSON schema / OpenAPI)
# -----------------------------------------------------------------------------

Intent = Literal[
    "education",
    "work",
    "project",
    "achievement",
    "certification",
    "responsibility",
    "skill_application",
    "method_used",
    "artifact_created",
    "challenge",
    "decision",
    "learning",
    "life_event",
    "relocation",
    "volunteering",
    "community",
    "finance",
    "other",
    "mixed",
]

ChildRelationType = Literal[
    "component_of",
    "skill_applied",
    "method_used",
    "tool_used",
    "artifact_created",
    "challenge_faced",
    "decision_made",
    "outcome_detail",
    "learning_from",
    "example_of",
]

# Intents allowed only for child cards (subset of Intent)
ChildIntent = Literal[
    "responsibility",
    "outcome",
    "skill_application",
    "method_used",
    "challenge",
    "decision",
    "learning",
    "artifact_created",
]

Visibility = Literal["private", "profile_only", "searchable"]

ClaimState = Literal["self_claim", "supported", "verified"]

Confidence = Literal["high", "medium", "low"]

Reaction = Literal["like", "respect", "insightful", "support", "curious"]

VerificationStatus = Literal["unverified", "verified"]

VerificationMethod = Literal["email_domain", "gov_id", "community", "document"]

EvidenceType = Literal["link", "file", "reference"]

ToolType = Literal["software", "equipment", "system", "platform", "instrument", "other"]

# Entity taxonomy for entities[].type
EntityType = Literal[
    "person",
    "organization",
    "company",
    "school",
    "team",
    "community",
    "place",
    "event",
    "program",
    "domain",
    "industry",
    "product",
    "service",
    "artifact",
    "document",
    "portfolio_item",
    "credential",
    "award",
    "tool",
    "equipment",
    "system",
    "platform",
    "instrument",
    "method",
    "process",
]

# -----------------------------------------------------------------------------
# 1.2 Core entities – nested models
# -----------------------------------------------------------------------------


class LocationBasic(BaseModel):
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None


class PersonVerification(BaseModel):
    status: VerificationStatus
    methods: list[VerificationMethod]


class PersonPrivacyDefaults(BaseModel):
    default_visibility: Visibility


class PersonSchema(BaseModel):
    """Person (user profile)."""

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


# --- Experience Card v1 nested models ---


class LanguageField(BaseModel):
    raw_text: Optional[str] = None
    confidence: Confidence


class TimeField(BaseModel):
    start: Optional[str] = None  # YYYY-MM | YYYY-MM-DD
    end: Optional[str] = None
    ongoing: Optional[bool] = None
    text: Optional[str] = None
    confidence: Confidence


class LocationWithConfidence(LocationBasic):
    text: Optional[str] = None
    confidence: Confidence


class RoleItem(BaseModel):
    label: str
    seniority: Optional[str] = None
    confidence: Confidence


class ActionItem(BaseModel):
    verb: str
    verb_raw: Optional[str] = None
    confidence: Confidence


class TopicItem(BaseModel):
    label: str
    raw: Optional[str] = None
    confidence: Confidence


class EntityItem(BaseModel):
    type: str  # EntityType or extended
    name: str
    entity_id: Optional[str] = None
    confidence: Confidence


class ToolItem(BaseModel):
    name: str
    type: ToolType
    confidence: Confidence


class ProcessItem(BaseModel):
    name: str
    confidence: Confidence


class ToolingField(BaseModel):
    tools: list[ToolItem] = Field(default_factory=list)
    processes: list[ProcessItem] = Field(default_factory=list)
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
    search_phrases: list[str] = Field(default_factory=list)
    embedding_ref: Optional[str] = None


# Shared fields for both parent and child cards (no parent_id/depth/relation_type/intent)
class _ExperienceCardV1FieldsBase(BaseModel):
    id: str
    person_id: str
    created_by: str
    version: Literal[1] = 1
    edited_at: Optional[datetime] = None
    headline: str
    summary: str
    raw_text: str
    language: LanguageField
    time: TimeField
    location: LocationWithConfidence
    roles: list[RoleItem] = Field(default_factory=list)
    actions: list[ActionItem] = Field(default_factory=list)
    topics: list[TopicItem] = Field(default_factory=list)
    entities: list[EntityItem] = Field(default_factory=list)
    tooling: ToolingField = Field(default_factory=ToolingField)
    outcomes: list[OutcomeItem] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    privacy: PrivacyField
    quality: QualityField
    index: IndexField = Field(default_factory=IndexField)
    created_at: datetime
    updated_at: datetime


class ExperienceCardParentV1Schema(_ExperienceCardV1FieldsBase):
    """
    Parent Experience Card: root of a card family.
    depth=0, no parent, relation_type=null. intent is any Intent.
    """

    parent_id: Optional[str] = None
    depth: Literal[0] = 0
    relation_type: Optional[str] = None
    intent: Intent


class ExperienceCardChildV1Schema(_ExperienceCardV1FieldsBase):
    """
    Child Experience Card: belongs to a parent card.
    depth=1, parent_id and relation_type required. intent restricted to ChildIntent.
    """

    parent_id: str
    depth: Literal[1] = 1
    relation_type: ChildRelationType
    intent: ChildIntent


class ExperienceCardV1Schema(BaseModel):
    """
    Experience Card v1 (universal content unit).
    Use ExperienceCardParentV1Schema for parent cards, ExperienceCardChildV1Schema for children.
    This union type remains for backward compatibility and generic validation.
    """

    id: str
    person_id: str
    created_by: str
    version: Literal[1] = 1
    edited_at: Optional[datetime] = None
    parent_id: Optional[str] = None
    depth: int = 0
    relation_type: Optional[str] = None  # ChildRelationType when child
    intent: Intent
    headline: str
    summary: str
    raw_text: str
    language: LanguageField
    time: TimeField
    location: LocationWithConfidence
    roles: list[RoleItem] = Field(default_factory=list)
    actions: list[ActionItem] = Field(default_factory=list)
    topics: list[TopicItem] = Field(default_factory=list)
    entities: list[EntityItem] = Field(default_factory=list)
    tooling: ToolingField = Field(default_factory=ToolingField)
    outcomes: list[OutcomeItem] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    privacy: PrivacyField
    quality: QualityField
    index: IndexField = Field(default_factory=IndexField)
    created_at: datetime
    updated_at: datetime


# Entity taxonomy as list (for validation / docs)
ENTITY_TAXONOMY: list[str] = [
    "person",
    "organization",
    "company",
    "school",
    "team",
    "community",
    "place",
    "event",
    "program",
    "domain",
    "industry",
    "product",
    "service",
    "artifact",
    "document",
    "portfolio_item",
    "credential",
    "award",
    "tool",
    "equipment",
    "system",
    "platform",
    "instrument",
    "method",
    "process",
]
